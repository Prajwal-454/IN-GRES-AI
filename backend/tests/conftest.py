import os
import tempfile
from pathlib import Path

_tmpdir = tempfile.mkdtemp(prefix="ingres_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
os.environ["ENABLE_GEOMETRY"] = "false"
os.environ["AUTO_CREATE_SCHEMA"] = "true"
os.environ["LLM_ENABLED"] = "false"
os.environ["LLM_TIMEOUT_SECONDS"] = "3"
# Never auto-refresh real data from states/*.csv during tests (the dev .env
# may have REAL_DATA_AUTO_REFRESH=true, which would otherwise run the full
# real-data import into the shared test database at boot).
os.environ["SEED_REAL_DATA"] = "false"
os.environ["REAL_DATA_AUTO_REFRESH"] = "false"
# Never hit live government APIs during tests (the dev .env enables live sync).
os.environ["LIVE_DATA_ENABLED"] = "false"
os.environ["IMD_API_KEY"] = ""
# Web-search fallback must never touch the network during tests either
# (the web-search tests opt back in explicitly).
os.environ["WEB_SEARCH_ENABLED"] = "false"
# Force the local Ollama preset for tests: even when a test enables
# LLM_ENABLED, no cloud provider key/URL may be used (no network egress).
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_SEARCH_MODEL"] = ""
# Voice tests always use the fast mock STT/TTS (not the local vosk/edge engines).
os.environ["STT_PROVIDER"] = "mock"
os.environ["TTS_PROVIDER"] = "mock"
# Registration CAPTCHA is exercised explicitly in test_captcha.py.
os.environ["REGISTRATION_CAPTCHA_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

TEST_KNOWLEDGE_DOC = Path(__file__).resolve().parents[2] / "knowledge" / "documents"


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as c:
        from app.database import SessionLocal
        from app.database.seed import seed_demo_users
        from app.ingres.demo_data import seed_demo_groundwater

        seed_demo_users()
        db = SessionLocal()
        try:
            seed_demo_groundwater(db)
        finally:
            db.close()
        yield c


@pytest.fixture()
def db_session_factory():
    """A factory returning a fresh ORM session (function-scoped)."""
    from app.database import SessionLocal

    def factory():
        return SessionLocal()

    return factory


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture(scope="session")
def user_token(client: TestClient) -> str:
    return _login(client, "user@ingres.in", "user12345")["access_token"]


@pytest.fixture(scope="session")
def admin_token(client: TestClient) -> str:
    return _login(client, "admin@ingres.in", "admin12345")["access_token"]


@pytest.fixture()
def auth_user(user_token: str):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture()
def auth_admin(admin_token: str):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def knowledge_dir() -> Path:
    return TEST_KNOWLEDGE_DOC
