"""
Shared test fixtures.

The app reads its configuration and creates the database engine at import
time, so the test environment is set up here before any project module is
imported. load_dotenv() never overrides variables that are already set, so
nothing from .env (which points at the production database) leaks in.
"""

import os
import tempfile
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)  # templates/ and static/ are resolved relative to the cwd

_test_db_url = f"sqlite:///{Path(tempfile.mkdtemp(prefix='npc_memory_tests_'), 'test.db').as_posix()}"
os.environ.update({
    "ENVIRONMENT": "test",
    "TEST_DATABASE_URL": _test_db_url,
    "DATABASE_URL": _test_db_url,
    "SECRET_KEY": "test-secret-key-at-least-32-bytes-long",
    "JWT_SECRET_KEY": "test-jwt-secret-key-at-least-32-bytes",
    "USE_EXTERNAL_LLM": "true",
    "LLM_PROVIDER": "groq",
    "LLM_API_KEY": "test-dummy-key",
    "REQUIRE_SERVICE_API_KEY": "true",
    "SERVICE_API_KEY": "test-service-key",
    "ALLOWED_EMAILS": "",
    "ALLOWED_EMAIL_DOMAINS": "",
})

import dependencies  # noqa: E402
import llm_adapter  # noqa: E402
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# Per-IP limits (e.g. 3 registrations/minute) would trip across tests
dependencies.limiter.enabled = False

STUB_REPLY = "Solid choice. The 2004 V10 gives you serious top speed."


@pytest.fixture
def stub_reply():
    return STUB_REPLY


@pytest.fixture
def service_headers():
    """Header required by the programmatic API routes (REQUIRE_SERVICE_API_KEY=true)."""
    return {"x-service-key": "test-service-key"}


@pytest.fixture(autouse=True)
def llm_prompts(monkeypatch):
    """Stub the Groq call so no test hits the network; collects the prompts sent."""
    prompts = []

    def fake_groq(prompt, max_tokens=150, temperature=0.4):
        prompts.append(prompt)
        return STUB_REPLY

    monkeypatch.setattr(llm_adapter, "generate_with_groq", fake_groq)
    return prompts


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def player(client):
    """Register a fresh email/password player and log the client in as them."""
    email = f"{uuid.uuid4().hex[:12]}@example.com"
    password = "racecar123"

    r = client.post("/create_player_form", data={"name": "Test Driver", "email": email, "password": password})
    assert r.status_code == 200, r.text
    r = client.post("/verify_player", json={"email": email, "password": password})
    assert r.status_code == 200, r.text

    return {"id": r.json()["player_id"], "email": email, "password": password}
