"""Server-side access control and the tamper-evident audit log."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core import audit


@pytest.mark.parametrize(("who", "method", "path", "expected"), [
    ("zainab", "get", "/api/v1/queue", 403),
    ("zainab", "get", "/api/v1/audit", 403),
    ("zainab", "post", "/api/v1/admin/seed/reset", 403),
    ("helper", "get", "/api/v1/queue", 403),
    ("auditor", "get", "/api/v1/audit", 200),
    ("auditor", "get", "/api/v1/queue", 403),
    ("officer", "get", "/api/v1/queue", 200),
    ("officer", "get", "/api/v1/audit", 403),
    ("admin", "get", "/api/v1/admin/users", 200),
])
def test_role_matrix(client, login, who, method, path, expected):
    response = getattr(client, method)(path, headers=login(who))
    assert response.status_code == expected


def test_no_token_is_401(client):
    assert client.get("/api/v1/cases").status_code == 401


def test_citizen_cannot_approve_and_attempt_is_logged(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    response = client.post(f"/api/v1/cases/{case_id}/approve", json={"reason": "self approve"}, headers=login("zainab"))
    assert response.status_code == 403
    denied = client.get("/api/v1/audit?action=ACCESS_DENIED", headers=login("auditor")).json()["data"]
    assert any("approve" in (e["resource"] or "") for e in denied)


def test_auditor_cannot_approve(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    assert client.post(f"/api/v1/cases/{case_id}/approve", json={"reason": "x" * 5}, headers=login("auditor")).status_code == 403


def test_citizen_cannot_see_someone_elses_case(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    assert client.get(f"/api/v1/cases/{case_id}", headers=login("rafiq")).status_code == 403


def test_citizen_cannot_file_a_claim_for_someone_else(client, login):
    from tests.conftest import BASE_CLAIM

    response = client.post("/api/v1/cases", json=BASE_CLAIM, headers=login("rafiq"))
    assert response.status_code == 403


def test_helper_can_file_for_an_assigned_family_only(client, login):
    from tests.conftest import BASE_CLAIM

    assert client.post("/api/v1/cases", json=BASE_CLAIM, headers=login("helper")).status_code == 201
    other = {**BASE_CLAIM, "claimant_cnic": "9000000000033", "claimant_name": "Rukhsana"}
    assert client.post("/api/v1/cases", json=other, headers=login("helper")).status_code == 403


def test_officer_from_another_department_cannot_see_the_case(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    assert client.get(f"/api/v1/cases/{case_id}", headers=login("welfare_officer")).status_code == 403


def test_officer_approves_and_cannot_decide_twice(client, login, file_claim):
    case_id = file_claim("rukhsana", claimant_cnic="9000000000033", claimant_name="Rukhsana", payout_iban="PK00MOCK0000000000000002")["data"]["id"]
    officer = login("officer")
    assert client.post(f"/api/v1/cases/{case_id}/reject", json={"reason": "Not in family record"}, headers=officer).json()["data"]["status"] == "rejected"
    assert client.post(f"/api/v1/cases/{case_id}/approve", json={"reason": "changed mind"}, headers=officer).status_code == 409


def test_api_key_scope_is_enforced(client, login, file_claim):
    reference = file_claim("zainab")["data"]["reference"]
    created = client.post("/api/v1/admin/api-keys", json={"name": "Mock SMS gateway", "scopes": ["cases:status"]}, headers=login("admin")).json()["data"]
    key = {"X-API-Key": created["api_key"]}
    response = client.get(f"/api/v1/public/cases/{reference}/status", headers=key)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "auto_approved"
    assert client.get("/api/v1/public/cases/SP-0000/status", headers={"X-API-Key": "sk_wrong"}).status_code == 401
    assert client.get(f"/api/v1/public/cases/{reference}/status", headers=login("zainab")).status_code == 403


def test_audit_chain_verifies(client, login, file_claim):
    file_claim("zainab")
    result = client.get("/api/v1/audit/verify", headers=login("auditor")).json()["data"]
    assert result["intact"] is True
    assert result["checked"] > 0


def test_audit_rows_cannot_be_updated_or_deleted(db):
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("UPDATE audit_events SET action = 'X'"))
    db.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("DELETE FROM audit_events"))
    db.rollback()


def test_tampering_is_detected_by_the_chain(db):
    audit.record(db, audit.SYSTEM, "TEST_EVENT", details={"amount": 100})
    db.commit()
    # Simulate an attacker with database superuser rights bypassing the trigger.
    db.execute(text("ALTER TABLE audit_events DISABLE TRIGGER audit_events_no_update_delete"))
    db.execute(text("UPDATE audit_events SET details = '{\"amount\": 999}' WHERE action = 'TEST_EVENT'"))
    db.execute(text("ALTER TABLE audit_events ENABLE TRIGGER audit_events_no_update_delete"))
    db.commit()
    result = audit.verify_chain(db)
    assert result["intact"] is False
    # Repair so later tests start from an intact chain.
    db.execute(text("SET sahara.allow_audit_reset = 'on'"))
    db.execute(text("TRUNCATE audit_events RESTART IDENTITY"))
    db.commit()


def test_me_returns_own_person_and_helper_sees_40_families(client, login):
    me = client.get("/api/v1/me", headers=login("zainab")).json()["data"]
    assert me["person"]["cnic"] == "9000000000022"
    families = client.get("/api/v1/helper/families", headers=login("helper")).json()["data"]
    assert len(families) == 40
    assert client.get("/api/v1/helper/families", headers=login("zainab")).status_code == 403


# ---- Fixes from the security review -------------------------------------------------

def test_api_key_cannot_list_cases(client, login, file_claim):
    file_claim("zainab")
    created = client.post("/api/v1/admin/api-keys", json={"name": "Partner", "scopes": ["scam:check"]}, headers=login("admin")).json()["data"]
    assert client.get("/api/v1/cases", headers={"X-API-Key": created["api_key"]}).status_code == 403


def test_auditor_cannot_escalate(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    assert client.post(f"/api/v1/cases/{case_id}/escalate", json={"reason": "stop it"}, headers=login("auditor")).status_code == 403


def test_second_open_claim_for_the_same_pension_is_refused(client, login, file_claim):
    from tests.conftest import BASE_CLAIM

    file_claim("zainab")
    assert client.post("/api/v1/cases", json=BASE_CLAIM, headers=login("zainab")).status_code == 409


def test_citizen_does_not_see_assigned_officer(client, login, file_claim):
    case = file_claim("rukhsana", claimant_cnic="9000000000033", claimant_name="Rukhsana", payout_iban="PK00MOCK0000000000000002")
    assert case["data"]["assigned_officer_id"] is None
    staff_view = client.get(f"/api/v1/cases/{case['data']['id']}", headers=login("officer")).json()["data"]
    assert staff_view["assigned_officer_id"] is not None


def test_account_locks_after_five_wrong_pins(client):
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"phone": "00000000001", "pin": "0000"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"phone": "00000000001", "pin": "1234"}).status_code == 429


def test_audit_log_is_scoped_to_the_readers_department(client, login, file_claim):
    file_claim("zainab")
    rows = client.get("/api/v1/audit?limit=500", headers=login("auditor")).json()["data"]
    assert rows
    tenant = client.get("/api/v1/me", headers=login("auditor")).json()["data"]["tenant_id"]
    from app.db import SessionLocal
    from app.models.audit import AuditEvent

    with SessionLocal() as db:
        tenants = {db.get(AuditEvent, r["seq"]).tenant_id for r in rows}
    assert tenants == {tenant}


def test_case_references_come_from_a_sequence(file_claim):
    first = file_claim("zainab")["data"]["reference"]
    second = file_claim("rukhsana", claimant_cnic="9000000000033", claimant_name="Rukhsana", payout_iban="PK00MOCK0000000000000002")["data"]["reference"]
    assert first != second
    assert int(second.split("-")[1]) > int(first.split("-")[1])


def test_pin_lockout_is_per_account_not_per_venue(client):
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"phone": "00000000001", "pin": "0000"})
    assert client.post("/api/v1/auth/login", json={"phone": "00000000001", "pin": "1234"}).status_code == 429
    # Another judge on the same IP is not affected by Zainab's lockout.
    assert client.post("/api/v1/auth/login", json={"phone": "00000000002", "pin": "1234"}).status_code == 200


def test_login_per_ip_limit_allows_a_room_of_judges_but_is_still_limited(client):
    phones = ["00000000001", "00000000002", "00000000003", "00000000004", "00000000005", "00000000006"]
    codes = [client.post("/api/v1/auth/login", json={"phone": phones[i % len(phones)], "pin": "1234"}).status_code for i in range(60)]
    assert codes == [200] * 60
    assert client.post("/api/v1/auth/login", json={"phone": "00000000001", "pin": "1234"}).status_code == 429
