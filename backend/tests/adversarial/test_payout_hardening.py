"""Security review L3 + H1 remainder, red team L1: payout changes respect case status and consent."""
import pytest

from app.db import SessionLocal
from app.models.platform import Case

IBAN = "PK00MOCK0000000000000009"


def _set_status(case_id: str, status: str) -> None:
    with SessionLocal() as db:
        db.get(Case, case_id).status = status
        db.commit()


def _withdraw(client, login, grantee_type: str) -> None:
    zainab = login("zainab")
    consents = client.get("/api/v1/me/consents", headers=zainab).json()["data"]["consents"]
    for c in consents:
        if c["grantee_type"] == grantee_type and c["status"] == "active":
            assert client.post(f"/api/v1/me/consents/{c['id']}/withdraw", headers=zainab).status_code == 200


@pytest.mark.parametrize("status", ["rejected", "closed"])
def test_no_payout_change_on_rejected_or_closed_case(client, login, file_claim, status):
    case_id = file_claim("zainab")["data"]["id"]
    _set_status(case_id, status)
    response = client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": IBAN}, headers=login("zainab"))
    assert response.status_code == 409


def test_apply_due_skips_changes_on_closed_cases(client, login, file_claim):
    zainab = login("zainab")
    case_id = file_claim("zainab")["data"]["id"]
    change = client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": "PK00MOCK0000000000000001"}, headers=zainab).json()["data"]
    client.post(f"/api/v1/payout-changes/{change['id']}/confirm", json={"pin": "1234"}, headers=zainab)
    _set_status(case_id, "closed")
    applied = client.post("/api/v1/admin/payout/apply-due?skip_wait=true", headers=login("admin")).json()["data"]["applied"]
    assert change["id"] not in applied


def test_helper_cannot_cancel_after_consent_withdrawn(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    helper = login("helper")
    change = client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": IBAN}, headers=helper).json()["data"]
    _withdraw(client, login, "helper")
    assert client.post(f"/api/v1/payout-changes/{change['id']}/cancel", headers=helper).status_code == 403


def test_officer_payout_list_redacts_rows_without_consent(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": IBAN}, headers=login("zainab"))
    _withdraw(client, login, "department")
    rows = client.get("/api/v1/payout-changes?status=all", headers=login("officer")).json()["data"]
    row = next(r for r in rows if r["case_id"] == case_id)
    assert row["consent_active"] is False
    assert "new_iban_last4" not in row and "payee_check" not in row
    denied = client.get("/api/v1/audit?action=CONSENT_DENIED", headers=login("auditor")).json()["data"]
    assert any(e["details"].get("field") == "payout_account" for e in denied)


def test_officer_corrections_list_redacts_rows_without_consent(client, login):
    zainab = login("zainab")
    body = {"field": "name", "requested_value": "Zainab B. Bibi", "reason": "Spelling"}
    assert client.post("/api/v1/me/corrections", json=body, headers=zainab).status_code == 201
    _withdraw(client, login, "department")
    rows = client.get("/api/v1/corrections", headers=login("officer")).json()["data"]
    assert rows and rows[0]["consent_active"] is False
    assert "requested_value" not in rows[0] and "current_value" not in rows[0]


def test_officer_lists_still_show_rows_with_consent(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": IBAN}, headers=login("zainab"))
    rows = client.get("/api/v1/payout-changes?status=all", headers=login("officer")).json()["data"]
    row = next(r for r in rows if r["case_id"] == case_id)
    assert row["consent_active"] is True and row["new_iban_last4"] == IBAN[-4:]
