"""Sentry scrubbing: no CNIC, IBAN, PIN, phone or token may leave the server; the admin test endpoint."""
import json

import pytest
import sentry_sdk
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from app.core import monitoring
from app.core.monitoring import FILTERED, scrub_breadcrumb, scrub_event, scrub_query_string, scrub_text, sentry_environment, sentry_release
from app.main import create_app

CNIC = "9000000000022"
CNIC_DASHED = "90000-0000001-1"
IBAN = "PK00MOCK0000000000000001"
PHONE = "00000000001"
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJlLXZhbHVl"
API_KEY = "sk_" + "A1b2C3d4E5f6G7h8I9j0K1l2"
SECRETS = (CNIC, CNIC_DASHED, IBAN, PHONE, JWT, API_KEY, "1234")


def _leaks(payload: object) -> list[str]:
    text = json.dumps(payload, default=str)
    return [s for s in SECRETS if s in text]


def _event() -> dict:
    return {
        "event_id": "a" * 32,
        "timestamp": "2026-11-21T10:00:00Z",
        "message": f"claim for {CNIC} paid to {IBAN}, phone {PHONE}, pin 1234",
        "exception": {"values": [{"type": "ValueError", "value": f"bad cnic {CNIC_DASHED} token {JWT}"}]},
        "request": {
            "url": f"https://api.example/api/v1/mock/nadra/{CNIC}?cnic={CNIC}&page=2",
            "method": "POST",
            "query_string": f"cnic={CNIC}&token={JWT}&q=+92{PHONE[1:]}",
            "headers": {"Authorization": f"Bearer {JWT}", "X-API-Key": API_KEY, "Cookie": "s=1", "User-Agent": "test"},
            "data": {"pin": "1234", "claimant_cnic": CNIC, "payout_iban": IBAN},
            "cookies": {"session": "abc"},
            "env": {"REMOTE_ADDR": "10.0.0.1"},
        },
        "user": {"id": "u1", "email": "x@example.org", "ip_address": "10.0.0.1", "role": "officer"},
        "extra": {"body": {"pin": "1234"}, "note": f"api key {API_KEY}", "nested": [{"phone": PHONE}, f"Bearer {JWT}"]},
        "breadcrumbs": {"values": [{"message": f"GET /mock/{CNIC}", "data": {"url": f"/x?iban={IBAN}"}}]},
    }


def test_scrubbed_event_carries_no_cnic_iban_pin_phone_or_token():
    cleaned = scrub_event(_event())
    assert _leaks(cleaned) == []


def test_request_body_cookies_and_env_are_dropped_entirely():
    request = scrub_event(_event())["request"]
    assert "data" not in request and "cookies" not in request and "env" not in request
    assert request["headers"]["Authorization"] == FILTERED
    assert request["headers"]["X-API-Key"] == FILTERED
    assert request["headers"]["User-Agent"] == "test"
    assert request["method"] == "POST"


def test_user_block_keeps_only_the_role():
    assert scrub_event(_event())["user"] == {"role": "officer"}
    assert scrub_event({"user": {"id": "u1"}})["user"] == {}


def test_query_string_keeps_keys_and_masks_values():
    query = scrub_query_string(f"cnic={CNIC}&token={JWT}&page=2")
    assert "cnic=" in query and "page=2" in query
    assert CNIC not in query and JWT not in query


def test_ids_and_timestamps_are_not_rewritten():
    cleaned = scrub_event(_event())
    assert cleaned["event_id"] == "a" * 32
    assert cleaned["timestamp"] == "2026-11-21T10:00:00Z"


def test_scrub_does_not_mutate_the_input():
    event = _event()
    before = json.dumps(event, sort_keys=True)
    scrub_event(event)
    assert json.dumps(event, sort_keys=True) == before


@pytest.mark.parametrize("raw", [
    f"cnic {CNIC}", f"cnic {CNIC_DASHED}", f"iban {IBAN}", f"call {PHONE}", "call 0300-1234567", "call +92 300 1234567",
    "PIN: 1234", "password=987654", f"Authorization: Bearer {JWT}", f"key {API_KEY}", f"jwt {JWT}",
])
def test_scrub_text_masks_each_identifier(raw):
    out = scrub_text(raw)
    digits_left = "".join(ch for ch in out if ch.isdigit())
    assert len(digits_left) <= 4, out
    assert JWT not in out and API_KEY not in out


def test_scrub_text_keeps_ordinary_text():
    assert scrub_text("Rule v1 decided ASK_PROOF in 120 ms") == "Rule v1 decided ASK_PROOF in 120 ms"


def test_breadcrumb_drops_body_and_masks_url_and_message():
    crumb = scrub_breadcrumb({"message": f"lookup {CNIC}", "category": "httpx",
                              "data": {"url": f"https://x/mock/{CNIC}?iban={IBAN}", "body": "pin=1234", "method": "GET"}})
    assert _leaks(crumb) == []
    assert "body" not in crumb["data"] and crumb["data"]["method"] == "GET"


def test_environment_and_release(monkeypatch):
    monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
    monkeypatch.delenv("RAILWAY_PROJECT_ID", raising=False)
    assert sentry_environment("local") == "local"
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    assert sentry_environment("local") == "production"
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")
    assert sentry_environment("local") == "staging"
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    assert sentry_release() is None
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abcdef1234567890")
    assert sentry_release() == "sahara-backend@abcdef123456"


def test_init_is_a_no_op_without_dsn():
    assert monitoring.init_sentry(None, "local") is False
    assert monitoring.is_enabled() is False


def test_sentry_test_endpoint_is_off_without_dsn(client, login):
    response = client.post("/api/v1/admin/sentry-test", headers=login("admin"))
    assert response.status_code == 503


def test_sentry_test_endpoint_is_admin_only(client, login):
    assert client.post("/api/v1/admin/sentry-test", headers=login("officer")).status_code == 403
    assert client.post("/api/v1/admin/sentry-test").status_code == 401


class _CaptureTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.events: list[dict] = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)


@pytest.fixture
def sentry_capture():
    transport = _CaptureTransport()
    sentry_sdk.init(dsn="https://public@o0.ingest.de.sentry.io/0", transport=transport, data_collection=monitoring.DATA_COLLECTION,
                    before_send=scrub_event, before_breadcrumb=scrub_breadcrumb)
    yield transport
    monitoring._enabled = False
    sentry_sdk.get_client().close()
    sentry_sdk.init()  # back to a disabled client


def test_sentry_test_endpoint_reports_a_scrubbed_error_and_audits(login, sentry_capture):
    client = TestClient(create_app(), raise_server_exceptions=False)
    monitoring._enabled = True  # create_app() saw no DSN; the fixture's client is the live one
    response = client.post("/api/v1/admin/sentry-test", headers=login("admin"))
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    sentry_sdk.flush()
    assert sentry_capture.events, "no event reached the transport"
    event = sentry_capture.events[0]
    assert event["exception"]["values"][-1]["type"] == "SentryTestError"
    assert CNIC_DASHED not in json.dumps(event)
    assert "Authorization" not in json.dumps(event.get("request", {}).get("headers", {})) or \
        event["request"]["headers"].get("Authorization") in (None, FILTERED)
    audit_rows = client.get("/api/v1/audit?action=SENTRY_TEST_TRIGGERED", headers=login("auditor")).json()["data"]
    assert len(audit_rows) == 1
