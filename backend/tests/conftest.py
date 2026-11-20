"""Test setup: a separate Postgres database, migrated once, reseeded per test."""
import os

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://sahara:sahara@localhost:5432/sahara_test")
os.environ["DATABASE_URL"] = TEST_DB  # must be set before the app modules read settings
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-0123456789")
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ["TYPESAFE_API_KEY"] = ""  # tests never call the real Jev API

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.core.ratelimit import limiter  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import reset  # noqa: E402

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
BASE_CLAIM = {
    "claimant_cnic": "9000000000022",
    "claimant_name": "Zainab Bibi",
    "relation_claimed": "widow",
    "deceased_cnic": "9000000000011",
    "deceased_name": "Muhammad Aslam",
    "payout_iban": "PK00MOCK0000000000000001",
    "documents": ["death_certificate", "claimant_cnic", "frc", "nikah_nama"],
}
PHONES = {
    "zainab": "00000000001", "rukhsana": "00000000002", "saima": "00000000003", "nasreen": "00000000004",
    "bilal": "00000000005", "hina": "00000000006", "rafiq": "00000000007", "kausar": "00000000008",
    "helper": "00000000010", "officer": "00000000020", "admin": "00000000030", "auditor": "00000000040",
    "welfare_officer": "00000000050",
}


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def seeded():
    limiter.reset()
    with SessionLocal() as db:
        reset(db)
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def login(client):
    def _login(who: str) -> dict:
        response = client.post("/api/v1/auth/login", json={"phone": PHONES[who], "pin": "1234"})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}

    return _login


@pytest.fixture
def file_claim(client, login):
    def _file(who: str, **overrides) -> dict:
        response = client.post("/api/v1/cases", json={**BASE_CLAIM, **overrides}, headers=login(who))
        assert response.status_code == 201, response.text
        return response.json()

    return _file
