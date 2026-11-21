"""Security review H1 + L3, red team L1: list endpoints check consent per row, and payout
changes respect case status and the helper's consent."""
import pytest
from sqlalchemy import func, select

from app.models.audit import AuditEvent
from app.models.consent import Consent
from app.models.platform import Case
from tests.conftest import BASE_CLAIM

IBAN = "PK00MOCK0000000000000009"


def _withdraw(db, case_id: str, grantee_type: str) -> None:
    """Straight in the database: the API refuses to take back the department's access while a
    claim is open (#19), but a consent can still lapse (valid_until) or be withdrawn later."""
    person_id = db.get(Case, case_id).claimant_person_id
    for consent in db.execute(select(Consent).where(Consent.subject_person_id == person_id,
                                                    Consent.grantee_type == grantee_type)).scalars():
        consent.status = "withdrawn"
    db.commit()


def _set_status(db, case_id: str, status: str) -> None:
    db.get(Case, case_id).status = status
    db.commit()


def _count(db, action: str) -> int:
    return db.execute(select(func.count(AuditEvent.seq)).where(AuditEvent.action == action)).scalar()


@pytest.mark.parametrize("path", ["/api/v1/cases", "/api/v1/queue"])
def test_security_h1_lists_redact_cases_after_consent_withdrawal(file_claim, client, login, db, path):
    body = file_claim("zainab", claimant_dob=None)["data"]  # in review, so it is in the queue too
    _withdraw(db, body["id"], "department")
    denied_before = _count(db, "CONSENT_DENIED")

    rows = client.get(path, headers=login("officer")).json()["data"]

    row = next(r for r in rows if r["reference"] == body["reference"])
    assert row == {"reference": body["reference"], "status": body["status"], "consent_active": False}
    assert _count(db, "CONSENT_DENIED") == denied_before + 1  # one row per person per request


def test_security_h1_list_with_consent_shows_full_rows_and_logs_access(file_claim, client, login, db):
    body = file_claim("zainab")["data"]
    rows = client.get("/api/v1/cases", headers=login("officer")).json()["data"]
    row = next(r for r in rows if r["reference"] == body["reference"])
    assert row["deceased_cnic"] == BASE_CLAIM["deceased_cnic"]
    assert db.execute(select(func.count(AuditEvent.seq)).where(
        AuditEvent.action == "DATA_ACCESS", AuditEvent.resource == f"person:{body['claimant_person_id']}")).scalar() >= 1


def test_security_h1_helper_list_shows_stub_after_helper_consent_withdrawn(file_claim, client, login, db):
    body = file_claim("helper")["data"]
    _withdraw(db, body["id"], "helper")
    rows = client.get("/api/v1/cases", headers=login("helper")).json()["data"]
    assert {"reference": body["reference"], "status": body["status"], "consent_active": False} in rows


def test_security_h1_citizen_and_auditor_lists_are_unchanged(file_claim, client, login, db):
    body = file_claim("zainab")["data"]
    _withdraw(db, body["id"], "department")
    own = client.get("/api/v1/cases", headers=login("zainab")).json()["data"]
    assert own[0]["id"] == body["id"]
    oversight = client.get("/api/v1/cases", headers=login("auditor")).json()["data"]
    assert next(r for r in oversight if r["reference"] == body["reference"])["deceased_cnic"] == BASE_CLAIM["deceased_cnic"]


@pytest.mark.parametrize("status", ["rejected", "closed"])
def test_no_payout_change_on_rejected_or_closed_case(client, login, file_claim, db, status):
    case_id = file_claim("zainab")["data"]["id"]
    _set_status(db, case_id, status)
    response = client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": IBAN}, headers=login("zainab"))
    assert response.status_code == 409


def test_apply_due_skips_changes_on_closed_cases(client, login, file_claim, db):
    zainab = login("zainab")
    case_id = file_claim("zainab")["data"]["id"]
    change = client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": "PK00MOCK0000000000000001"},
                         headers=zainab).json()["data"]
    client.post(f"/api/v1/payout-changes/{change['id']}/confirm", json={"pin": "1234"}, headers=zainab)
    _set_status(db, case_id, "closed")
    applied = client.post("/api/v1/admin/payout/apply-due?skip_wait=true", headers=login("admin")).json()["data"]["applied"]
    assert change["id"] not in applied


def test_helper_cannot_cancel_after_consent_withdrawn(client, login, file_claim, db):
    case_id = file_claim("zainab")["data"]["id"]
    helper = login("helper")
    created = client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": IBAN}, headers=helper)
    assert created.status_code in (200, 201), created.text
    _withdraw(db, case_id, "helper")
    assert client.post(f"/api/v1/payout-changes/{created.json()['data']['id']}/cancel", headers=helper).status_code == 403


def test_officer_payout_list_redacts_rows_without_consent(client, login, file_claim, db):
    case_id = file_claim("zainab")["data"]["id"]
    client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": IBAN}, headers=login("zainab"))
    _withdraw(db, case_id, "department")
    rows = client.get("/api/v1/payout-changes?status=all", headers=login("officer")).json()["data"]
    row = next(r for r in rows if r["case_id"] == case_id)
    assert row["consent_active"] is False
    assert "new_iban_last4" not in row and "payee_check" not in row and "flags" not in row
    denied = client.get("/api/v1/audit?action=CONSENT_DENIED", headers=login("auditor")).json()["data"]
    assert any(e["details"].get("field") == "payout_account" for e in denied)


def test_officer_corrections_list_redacts_rows_without_consent(client, login, file_claim, db):
    case_id = file_claim("zainab")["data"]["id"]
    body = {"field": "name", "requested_value": "Zainab B. Bibi", "reason": "Spelling"}
    assert client.post("/api/v1/me/corrections", json=body, headers=login("zainab")).status_code == 201
    _withdraw(db, case_id, "department")
    rows = client.get("/api/v1/corrections", headers=login("officer")).json()["data"]
    assert rows and rows[0]["consent_active"] is False
    assert "requested_value" not in rows[0] and "current_value" not in rows[0]


def test_officer_lists_still_show_rows_with_consent(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": IBAN}, headers=login("zainab"))
    rows = client.get("/api/v1/payout-changes?status=all", headers=login("officer")).json()["data"]
    row = next(r for r in rows if r["case_id"] == case_id)
    assert row["consent_active"] is True and row["new_iban_last4"] == IBAN[-4:]
