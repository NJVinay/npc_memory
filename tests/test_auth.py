from datetime import datetime, timedelta, timezone

import jwt
import pytest

import auth

PROTECTED_PAGES = ["/cover?player_id={id}", "/chat", "/chat_static", "/evaluation"]


def test_login_page_renders(client):
    assert client.get("/login").status_code == 200


def test_register_and_login_sets_auth_cookies(client, player):
    assert client.cookies.get("access_token")
    assert client.cookies.get("refresh_token")


def test_wrong_password_is_rejected(client, player):
    r = client.post("/verify_player", json={"email": player["email"], "password": "wrong-pass1"})
    assert r.status_code == 401


def test_duplicate_email_registration_is_rejected(client, player):
    r = client.post("/create_player_form", data={
        "name": "Copycat", "email": player["email"], "password": "racecar123"
    })
    assert r.status_code == 400


@pytest.mark.parametrize("path", PROTECTED_PAGES)
def test_protected_pages_require_login(client, path):
    assert client.get(path.format(id=1)).status_code == 401


@pytest.mark.parametrize("path", PROTECTED_PAGES)
def test_protected_pages_render_when_logged_in(client, player, path):
    assert client.get(path.format(id=player["id"])).status_code == 200


def test_cannot_open_another_players_pages(client, player):
    other_id = player["id"] + 1000
    assert client.get(f"/cover?player_id={other_id}").status_code == 403
    assert client.get(f"/chat?player_id={other_id}").status_code == 403


def test_malformed_token_is_401_not_500(client):
    client.cookies.set("access_token", "not-a-real-token")
    assert client.get("/chat").status_code == 401


def test_token_signed_with_another_key_is_rejected(client, player):
    forged = jwt.encode(
        {"sub": str(player["id"]), "type": "access",
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "attacker-controlled-key-also-32-bytes-long", algorithm="HS256",
    )
    client.cookies.clear()
    client.cookies.set("access_token", forged)
    assert client.get("/chat").status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client, player):
    refresh = client.cookies.get("refresh_token")
    client.cookies.clear()
    client.cookies.set("access_token", refresh)
    assert client.get("/chat").status_code == 401


def test_start_chat_redirects_to_a_chat_variant(client, player):
    r = client.get(f"/start_chat?player_id={player['id']}", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"].split("?")[0] in {"/chat", "/chat_static"}


def test_token_refresh(client, player):
    r = client.post("/auth/token/refresh")
    assert r.status_code == 200
    assert client.get("/chat").status_code == 200


def test_logout_clears_session(client, player):
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/chat").status_code == 401


# --- Session renewal: expired access token + valid refresh token ---

def expire_access_token(client, player, keep_refresh=True):
    """Swap the client's access token for an expired one, optionally keeping the refresh token."""
    refresh = client.cookies.get("refresh_token")
    expired = auth.create_access_token({"sub": str(player["id"])}, expires_delta=timedelta(seconds=-1))
    client.cookies.clear()
    client.cookies.set("access_token", expired)
    if keep_refresh:
        client.cookies.set("refresh_token", refresh)


def access_cookies_set(response):
    return [c for c in response.headers.get_list("set-cookie") if c.startswith("access_token=")]


def test_expired_session_is_renewed_on_page_load(client, player):
    expire_access_token(client, player)
    r = client.get("/chat")
    assert r.status_code == 200
    [cookie] = access_cookies_set(r)
    assert not cookie.startswith('access_token=""')


def test_chat_continues_after_access_token_expires(client, player):
    expire_access_token(client, player)
    r = client.post("/chat_api", data={"player_id": player["id"], "npc_id": 1, "dialogue": "Still there?"})
    assert r.status_code == 200, r.text


def test_expired_session_without_refresh_token_is_401(client, player):
    expire_access_token(client, player, keep_refresh=False)
    assert client.get("/chat").status_code == 401


def test_logout_is_not_undone_by_session_renewal(client, player):
    expire_access_token(client, player)
    r = client.post("/auth/logout")
    assert r.status_code == 200
    cookies = access_cookies_set(r)
    assert cookies and all(c.startswith('access_token=""') for c in cookies)
