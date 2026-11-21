"""Security review H2 / red team H7: judge-console shortcuts and docs are locked in production."""
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app

TOKEN = "console-token-for-tests-0123456789"


@pytest.fixture
def prod(monkeypatch):
    def _set(token: str | None = TOKEN, allow_docs: bool = False) -> None:
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DEMO_PIN", "2468")
        monkeypatch.setenv("DEMO_ADMIN_PIN", "8642")
        monkeypatch.setenv("DEMO_OFFICER_PIN", "7531")
        monkeypatch.setenv("ALLOW_DOCS", "true" if allow_docs else "false")
        if token is None:
            monkeypatch.delenv("DEMO_CONSOLE_TOKEN", raising=False)
        else:
            monkeypatch.setenv("DEMO_CONSOLE_TOKEN", token)
        get_settings.cache_clear()

    yield _set
    monkeypatch.undo()
    get_settings.cache_clear()


def test_production_reset_needs_console_token(client, login, prod):
    admin = login("admin")  # seeded with the local PIN before switching to production
    prod()
    assert client.post("/api/v1/admin/seed/reset", headers=admin).status_code == 404
    bad = {**admin, "X-Demo-Console-Token": "wrong"}
    assert client.post("/api/v1/admin/seed/reset", headers=bad).status_code == 404
    good = {**admin, "X-Demo-Console-Token": TOKEN}
    assert client.post("/api/v1/admin/seed/reset", headers=good).status_code == 200


def test_production_faults_and_skip_wait_disabled_without_token(client, login, prod):
    admin = login("admin")
    prod(token=None)
    body = {"service": "identity", "mode": "error"}
    assert client.post("/api/v1/admin/faults", json=body, headers=admin).status_code == 404
    assert client.post("/api/v1/admin/faults", json=body, headers={**admin, "X-Demo-Console-Token": ""}).status_code == 404
    assert client.post("/api/v1/admin/payout/apply-due?skip_wait=true", headers=admin).status_code == 404
    # The normal scheduler path (no skip) still works.
    assert client.post("/api/v1/admin/payout/apply-due", headers=admin).status_code == 200


def test_local_environment_keeps_console_open(client, login):
    admin = login("admin")
    assert client.post("/api/v1/admin/faults", json={"service": "identity", "mode": "ok"}, headers=admin).status_code == 200


def test_production_hides_docs_unless_allowed(prod):
    prod()
    client = TestClient(create_app())
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    prod(allow_docs=True)
    client = TestClient(create_app())
    assert client.get("/openapi.json").status_code == 200


def test_openapi_description_has_no_demo_pin():
    description = TestClient(create_app()).get("/openapi.json").json()["info"]["description"]
    assert "1234" not in description


def test_production_seed_refuses_default_privileged_pins(monkeypatch):
    from app import seed

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEMO_PIN", "5555")
    monkeypatch.delenv("DEMO_ADMIN_PIN", raising=False)
    monkeypatch.delenv("DEMO_OFFICER_PIN", raising=False)
    monkeypatch.delenv("DEMO_ADMIN2_PIN", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            seed.demo_pins()
        monkeypatch.setenv("DEMO_ADMIN_PIN", "1234")
        monkeypatch.setenv("DEMO_OFFICER_PIN", "7531")
        with pytest.raises(RuntimeError):
            seed.demo_pins()
        monkeypatch.setenv("DEMO_ADMIN_PIN", "8642")
        pins = seed.demo_pins()
        assert pins == {"default": "5555", "admin": "8642", "officer": "7531", "admin2": "8642"}
        monkeypatch.setenv("DEMO_ADMIN2_PIN", "1234")
        with pytest.raises(RuntimeError):
            seed.demo_pins()  # the second admin may not use the public PIN either
        monkeypatch.setenv("DEMO_ADMIN2_PIN", "9753")
        assert seed.demo_pins()["admin2"] == "9753"
        monkeypatch.delenv("DEMO_PIN")
        with pytest.raises(RuntimeError):
            seed.demo_pins()  # no 1234 default in production
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_local_seed_defaults_to_1234(monkeypatch):
    from app import seed

    for name in ("DEMO_PIN", "DEMO_ADMIN_PIN", "DEMO_OFFICER_PIN", "DEMO_ADMIN2_PIN"):
        monkeypatch.delenv(name, raising=False)
    assert seed.demo_pins() == {"default": "1234", "admin": "1234", "officer": "1234", "admin2": "1234"}
