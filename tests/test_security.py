"""Admin endpoints, Google/GitHub sign-in, rate-limit keys, error messages and schema upgrades."""

import json
import uuid
from types import SimpleNamespace
from urllib.parse import parse_qs, quote, urlparse

import httpx
import pytest
from sqlalchemy import create_engine, inspect, text
from starlette.requests import Request

import auth
import main
import oauth_routes
from config import config
from database import Base, add_missing_columns, get_db
from dependencies import client_ip, player_or_ip

CONSENT = {"name": "Test Driver", "consent_participate": True, "consent_data": True, "consent_age": True}


# --- Admin endpoints ---

def test_participant_list_needs_the_admin_key_even_when_service_keys_are_off(client, monkeypatch, service_headers):
    monkeypatch.setattr(config, "REQUIRE_SERVICE_API_KEY", False)

    assert client.get("/players").status_code == 401
    assert client.post("/create_player", json={"name": f"api-{uuid.uuid4()}"}).status_code == 401
    assert client.get("/players", headers=service_headers).status_code == 200


def test_admin_endpoints_refuse_everything_without_a_configured_key(client, monkeypatch):
    monkeypatch.setattr(config, "SERVICE_API_KEY", "")

    assert client.get("/players", headers={"x-service-key": ""}).status_code == 401


# --- Rate-limit keys ---

def make_request(headers=None):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": "/", "query_string": b"",
                    "headers": raw, "client": ("10.0.0.1", 1234)})


def test_rate_limit_key_is_the_address_the_proxy_saw():
    # The left-most entry is whatever the visitor sent; the proxy appends the real address
    assert client_ip(make_request({"X-Forwarded-For": "6.6.6.6, 203.0.113.9"})) == "203.0.113.9"
    assert client_ip(make_request()) == "10.0.0.1"


def test_chat_rate_limit_is_per_player():
    token = auth.create_access_token({"sub": "42"})

    assert player_or_ip(make_request({"Cookie": f"access_token={token}"})) == "player:42"
    assert player_or_ip(make_request()) == "10.0.0.1"


# --- Google / GitHub sign-in ---

@pytest.fixture
def provider(monkeypatch):
    """Fake Google and GitHub endpoints. Set google_user, github_user and github_emails per test."""
    fake = SimpleNamespace(google_user={}, github_user={}, github_emails=[])

    def handler(request):
        url = str(request.url)
        if url.startswith(("https://oauth2.googleapis.com/token", "https://github.com/login/oauth/access_token")):
            return httpx.Response(200, json={"access_token": "provider-token"})
        if url.startswith("https://www.googleapis.com/oauth2/v2/userinfo"):
            return httpx.Response(200, json=fake.google_user)
        if url == "https://api.github.com/user":
            return httpx.Response(200, json=fake.github_user)
        if url == "https://api.github.com/user/emails":
            return httpx.Response(200, json=fake.github_emails)
        return httpx.Response(404)

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(oauth_routes.httpx, "AsyncClient",
                        lambda *args, **kwargs: real_async_client(transport=httpx.MockTransport(handler)))
    return fake


def start_sign_in(client, provider_name, consent=CONSENT):
    """What login.html does: put the consent in a cookie, then go to /auth/login. Returns the state."""
    if consent is not None:
        # Same host as the server's own cookies, as in a browser, so the server can clear it
        client.cookies.set("pending_consent", quote(json.dumps(consent)), domain="testserver.local")
    r = client.get(f"/auth/login/{provider_name}", follow_redirects=False)
    return parse_qs(urlparse(r.headers["location"]).query)["state"][0]


def finish_sign_in(client, provider_name, state):
    return client.get(f"/auth/callback/{provider_name}?code=abc&state={state}", follow_redirects=False)


def sign_in(client, provider_name, consent=True):
    state = start_sign_in(client, provider_name, CONSENT if consent else None)
    return finish_sign_in(client, provider_name, state)


def google_user(email=None, verified=True, user_id=None):
    return {"id": user_id or uuid.uuid4().hex, "email": email or f"{uuid.uuid4().hex[:10]}@example.com",
            "verified_email": verified, "name": "Gina Google"}


def sets_session(response):
    return any(c.startswith("access_token=") and not c.startswith('access_token=""')
               for c in response.headers.get_list("set-cookie"))


def test_login_redirect_carries_a_state_value(client):
    r = client.get("/auth/login/github", follow_redirects=False)

    assert parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    assert any(c.startswith("oauth_state=") for c in r.headers.get_list("set-cookie"))


def test_callback_without_the_matching_state_is_refused(client, provider):
    provider.google_user = google_user()
    client.get("/auth/login/google", follow_redirects=False)

    r = client.get("/auth/callback/google?code=abc&state=forged", follow_redirects=False)

    assert r.status_code == 400
    assert not sets_session(r)


def test_google_sign_in_creates_an_account_and_stores_consent(client, provider):
    provider.google_user = google_user()

    r = sign_in(client, "google")

    assert r.status_code == 307
    assert r.headers["location"].startswith("/cover?player_id=")
    player_id = r.headers["location"].split("=")[1]
    assert client.get(f"/start_chat?player_id={player_id}", follow_redirects=False).status_code == 307


def test_sign_in_without_consent_goes_to_the_consent_step(client, provider):
    provider.google_user = google_user()

    r = sign_in(client, "google", consent=False)

    assert r.headers["location"] == "/login?consent=required"


def test_unverified_email_is_refused(client, provider):
    provider.google_user = google_user(verified=False)

    r = sign_in(client, "google")

    assert r.status_code == 400
    assert not sets_session(r)


def test_sign_in_cannot_take_over_a_password_account(client, provider, logged_in_player):
    client.cookies.clear()
    provider.google_user = google_user(email=logged_in_player["email"])

    r = sign_in(client, "google")

    assert r.status_code == 409
    assert not sets_session(r)


def test_returning_user_is_matched_by_provider_account_not_email(client, provider):
    user_id = uuid.uuid4().hex
    provider.google_user = google_user(user_id=user_id)
    first = sign_in(client, "google").headers["location"]

    provider.google_user = google_user(user_id=user_id)  # same Google account, new email address
    second = sign_in(client, "google").headers["location"]

    assert first == second


def test_github_uses_the_verified_primary_email(client, provider):
    provider.github_user = {"id": 123456, "login": "octo", "email": "public@example.com"}
    provider.github_emails = [{"email": "unverified@example.com", "primary": True, "verified": False}]
    assert sign_in(client, "github").status_code == 400

    provider.github_emails = [{"email": f"{uuid.uuid4().hex[:10]}@example.com", "primary": True, "verified": True}]
    assert sign_in(client, "github").status_code == 307


# --- Error messages ---

def test_health_check_hides_database_errors(client):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("connection to server at db.internal.example failed")

    main.app.dependency_overrides[get_db] = lambda: BrokenSession()
    try:
        r = client.get("/health")
    finally:
        main.app.dependency_overrides.clear()

    assert r.status_code == 503
    assert "db.internal" not in r.text


# --- Schema upgrades ---

def test_new_columns_are_added_to_existing_tables(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE npc_memory (id INTEGER PRIMARY KEY, player_id INTEGER NOT NULL, "
            "npc_id INTEGER NOT NULL, dialogue TEXT NOT NULL, timestamp DATETIME NOT NULL)"
        ))

    add_missing_columns(engine, Base.metadata)

    columns = {c["name"] for c in inspect(engine).get_columns("npc_memory")}
    assert {"source", "reply_status", "raw_reply", "llm_model", "response_time_ms", "mentions_part"} <= columns


# --- Consent hand-off during sign-in ---

def test_consent_is_moved_out_of_the_readable_cookie_at_sign_in_start(client):
    client.cookies.set("pending_consent", quote(json.dumps(CONSENT)))

    r = client.get("/auth/login/google", follow_redirects=False)

    set_cookies = r.headers.get_list("set-cookie")
    assert any(c.startswith('pending_consent=""') for c in set_cookies)
    sealed = [c for c in set_cookies if c.startswith("oauth_consent=")]
    assert sealed and "httponly" in sealed[0].lower()


def test_consent_from_an_abandoned_sign_in_is_not_reused(client, provider):
    start_sign_in(client, "google")  # participant A consents, then leaves at the provider's page
    provider.google_user = google_user()

    state = start_sign_in(client, "google", consent=None)  # participant B starts without consent
    r = finish_sign_in(client, "google", state)

    assert r.headers["location"] == "/login?consent=required"


def test_failed_callback_clears_the_sign_in_cookies(client, provider):
    provider.google_user = google_user(verified=False)

    r = sign_in(client, "google")

    assert r.status_code == 400
    cleared = {c.split("=")[0] for c in r.headers.get_list("set-cookie") if '=""' in c}
    assert {"oauth_state", "oauth_consent", "pending_consent"} <= cleared


def test_consent_that_cannot_be_saved_is_explained(client, provider):
    provider.google_user = google_user()
    too_long = {**CONSENT, "course": "x" * 500}

    state = start_sign_in(client, "google", consent=too_long)
    r = finish_sign_in(client, "google", state)

    assert r.headers["location"] == "/login?consent=invalid"


def test_non_ascii_key_or_state_is_refused_cleanly(client, provider):
    assert client.get("/players", headers={"x-service-key": "nyckel-åäö".encode("utf-8")}).status_code == 401
    client.get("/auth/login/google", follow_redirects=False)
    assert client.get("/auth/callback/google?code=abc&state=tillstånd", follow_redirects=False).status_code == 400
