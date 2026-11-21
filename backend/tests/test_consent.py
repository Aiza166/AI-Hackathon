"""Consent and take-back (Challenge 6): withdrawal really stops access, and it is logged."""
from sqlalchemy import func, select

from app.models.audit import AuditEvent


def _consent_id(client, headers, grantee_type: str) -> str:
    consents = client.get("/api/v1/me/consents", headers=headers).json()["data"]["consents"]
    return next(c["id"] for c in consents if c["grantee_type"] == grantee_type and c["status"] == "active")


def test_withdrawing_helper_consent_blocks_the_helpers_next_request(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    zainab, helper = login("zainab"), login("helper")
    assert client.get(f"/api/v1/cases/{case_id}", headers=helper).status_code == 200

    client.post(f"/api/v1/me/consents/{_consent_id(client, zainab, 'helper')}/withdraw", headers=zainab)

    assert client.get(f"/api/v1/cases/{case_id}", headers=helper).status_code == 403
    log = client.get("/api/v1/me/access-log", headers=zainab).json()["data"]
    actions = [row["action"] for row in log]
    assert "CONSENT_WITHDRAWN" in actions
    assert "CONSENT_DENIED" in actions
    assert any(r["action"] == "DATA_ACCESS" and r["who"].startswith("Ayesha") for r in log)


def test_after_withdrawal_helper_cannot_file_and_cannot_see_the_cnic(client, login):
    from tests.conftest import BASE_CLAIM

    zainab, helper = login("zainab"), login("helper")
    client.post(f"/api/v1/me/consents/{_consent_id(client, zainab, 'helper')}/withdraw", headers=zainab)

    assert client.post("/api/v1/cases", json=BASE_CLAIM, headers=helper).status_code == 403
    families = client.get("/api/v1/helper/families", headers=helper).json()["data"]
    zainab_row = next(f for f in families if f["name"] == "Zainab Bibi")
    assert zainab_row["cnic"] is None
    assert zainab_row["consent_active"] is False


def test_removing_one_field_is_enough_to_block_that_data(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    zainab = login("zainab")
    consent_id = _consent_id(client, zainab, "helper")
    response = client.patch(f"/api/v1/me/consents/{consent_id}", json={"fields": ["cnic"]}, headers=zainab)
    assert response.json()["data"]["fields"] == ["cnic"]
    assert client.get(f"/api/v1/cases/{case_id}", headers=login("helper")).status_code == 403


def test_department_access_cannot_be_taken_back_while_her_claim_is_open(client, login, file_claim, db):
    case = file_claim("zainab")["data"]
    zainab = login("zainab")
    dept = _consent_id(client, zainab, "department")
    start = db.execute(select(func.max(AuditEvent.seq))).scalar() or 0

    refused = client.post(f"/api/v1/me/consents/{dept}/withdraw", headers=zainab)
    assert refused.status_code == 409
    assert case["reference"] in refused.json()["error"]["message"]
    narrowed = client.patch(f"/api/v1/me/consents/{dept}", json={"fields": ["cnic"]}, headers=zainab)
    assert narrowed.status_code == 409

    assert client.get(f"/api/v1/cases/{case['id']}", headers=login("officer")).status_code == 200  # officers keep working
    rows = client.get("/api/v1/me/consents", headers=zainab).json()["data"]["consents"]
    dept_row = next(c for c in rows if c["id"] == dept)
    assert dept_row["status"] == "active"
    assert [c["reference"] for c in dept_row["needed_for_claims"]] == [case["reference"]]
    refusals = db.execute(select(AuditEvent).where(AuditEvent.action == "CONSENT_CHANGE_REFUSED", AuditEvent.seq > start)).scalars().all()
    assert sorted(e.details["change"] for e in refusals) == ["hide_fields", "withdraw"]


def test_after_withdrawing_her_claim_department_access_can_be_taken_back(client, login, file_claim, db):
    case = file_claim("zainab", claimant_dob=None)["data"]  # ASK_PROOF: still being decided
    zainab = login("zainab")
    start = db.execute(select(func.max(AuditEvent.seq))).scalar() or 0

    withdrawn = client.post(f"/api/v1/cases/{case['id']}/withdraw", json={"reason": "I want to stop"}, headers=zainab)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["data"]["status"] == "withdrawn"
    taken = client.post(f"/api/v1/me/consents/{_consent_id(client, zainab, 'department')}/withdraw", headers=zainab)
    assert taken.status_code == 200

    assert client.get(f"/api/v1/cases/{case['id']}", headers=login("officer")).status_code == 403
    assert client.get(f"/api/v1/cases/{case['id']}", headers=login("auditor")).status_code == 200  # oversight stays
    assert db.execute(select(AuditEvent).where(AuditEvent.action == "CASE_WITHDRAWN", AuditEvent.seq > start)).scalar_one().case_id == case["id"]


def test_withdrawn_claim_is_final_and_only_the_claimant_can_withdraw(client, login, file_claim, db):
    case_id = file_claim("zainab", claimant_dob=None)["data"]["id"]
    officer = login("officer")
    assert client.post(f"/api/v1/cases/{case_id}/withdraw", headers=login("helper")).status_code == 403
    assert client.post(f"/api/v1/cases/{case_id}/withdraw", headers=officer).status_code == 403
    assert client.post(f"/api/v1/cases/{case_id}/withdraw", headers=login("rukhsana")).status_code == 403
    zainab = login("zainab")
    assert client.post(f"/api/v1/cases/{case_id}/withdraw", headers=zainab).status_code == 200
    assert client.post(f"/api/v1/cases/{case_id}/withdraw", headers=zainab).status_code == 409
    assert client.post(f"/api/v1/cases/{case_id}/approve", json={"reason": "late approval"}, headers=officer).status_code == 409
    assert client.post(f"/api/v1/cases/{case_id}/close", json={"reason": "late close"}, headers=officer).status_code == 409
    # A late document upload (e.g. a photo queued offline) never re-opens it.
    from app.documents.service import redecide
    from app.models.platform import Case

    case = db.get(Case, case_id)
    redecide(db, case)
    db.commit()
    assert client.get(f"/api/v1/cases/{case_id}", headers=zainab).json()["data"]["status"] == "withdrawn"
    explanation = client.get(f"/api/v1/cases/{case_id}/explanation", headers=zainab).json()["data"]
    assert explanation["explanations"] == []
    file_claim("zainab")  # no longer open: she may file again


def test_a_pension_already_being_paid_cannot_be_withdrawn_by_the_claimant(client, login, file_claim):
    case = file_claim("zainab")["data"]
    assert case["status"] == "auto_approved"
    zainab = login("zainab")
    assert client.post(f"/api/v1/cases/{case['id']}/withdraw", headers=zainab).status_code == 409
    rows = client.get("/api/v1/me/consents", headers=zainab).json()["data"]["consents"]
    dept = next(c for c in rows if c["grantee_type"] == "department")
    assert dept["needed_for_claims"][0]["can_withdraw"] is False


def test_withdrawing_a_claim_cancels_its_open_payout_change(client, login, file_claim, db):
    case_id = file_claim("zainab", claimant_dob=None)["data"]["id"]
    zainab = login("zainab")
    change = client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": "PK00MOCK0000000000000013"}, headers=zainab)
    assert change.status_code == 201, change.text
    assert client.post(f"/api/v1/cases/{case_id}/withdraw", headers=zainab).status_code == 200
    from app.models.payout import PayoutChangeRequest

    assert db.get(PayoutChangeRequest, change.json()["data"]["id"]).status == "cancelled"
    again = client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": "PK00MOCK0000000000000013"}, headers=zainab)
    assert again.status_code == 409


def test_no_claim_can_be_filed_while_the_department_access_is_taken_back(client, login):
    from tests.conftest import BASE_CLAIM

    zainab = login("zainab")
    assert client.post(f"/api/v1/me/consents/{_consent_id(client, zainab, 'department')}/withdraw", headers=zainab).status_code == 200
    refused = client.post("/api/v1/cases", json=BASE_CLAIM, headers=zainab)
    assert refused.status_code == 409
    assert "Share access with the department again" in refused.json()["error"]["message"]


def test_helper_access_stays_freely_revocable_with_an_open_claim(client, login, file_claim):
    file_claim("zainab")
    zainab = login("zainab")
    assert client.post(f"/api/v1/me/consents/{_consent_id(client, zainab, 'helper')}/withdraw", headers=zainab).status_code == 200


def test_department_access_can_be_taken_back_when_no_claim_is_open(client, login):
    zainab = login("zainab")
    assert client.post(f"/api/v1/me/consents/{_consent_id(client, zainab, 'department')}/withdraw", headers=zainab).status_code == 200


def test_citizen_cannot_withdraw_someone_elses_consent(client, login):
    zainab_consent = _consent_id(client, login("zainab"), "department")
    assert client.post(f"/api/v1/me/consents/{zainab_consent}/withdraw", headers=login("rukhsana")).status_code == 403


def test_regranting_consent_restores_access(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    zainab, helper = login("zainab"), login("helper")
    consents = client.get("/api/v1/me/consents", headers=zainab).json()["data"]["consents"]
    helper_consent = next(c for c in consents if c["grantee_type"] == "helper")
    client.post(f"/api/v1/me/consents/{helper_consent['id']}/withdraw", headers=zainab)
    regrant = {"grantee_type": "helper", "grantee_id": helper_consent["grantee_id"], "fields": ["case_details", "cnic"]}
    assert client.post("/api/v1/me/consents", json=regrant, headers=zainab).status_code == 201
    assert client.get(f"/api/v1/cases/{case_id}", headers=helper).status_code == 200


def test_correction_request_is_reviewed_by_an_officer(client, login):
    zainab, officer = login("zainab"), login("officer")
    body = {"field": "name", "requested_value": "Zainab Bibi Aslam", "reason": "Name on my CNIC"}
    assert client.post("/api/v1/me/corrections", json=body, headers=zainab).status_code == 201
    pending = client.get("/api/v1/corrections", headers=officer).json()["data"]
    assert pending[0]["current_value"] == "Zainab Bibi"
    decided = client.post(f"/api/v1/corrections/{pending[0]['id']}/approve", json={"note": "Matches CNIC"}, headers=officer)
    assert decided.json()["data"]["status"] == "approved"
    assert client.get("/api/v1/me", headers=zainab).json()["data"]["person"]["name"] == "Zainab Bibi Aslam"
    again = client.post(f"/api/v1/corrections/{pending[0]['id']}/approve", json={"note": "again"}, headers=officer)
    assert again.status_code == 409


def test_seed_has_exactly_one_locked_helper_family(client, login):
    families = client.get("/api/v1/helper/families", headers=login("helper")).json()["data"]
    locked = [f for f in families if f["consent_active"] is False]
    assert len(families) == 40
    assert [f["name"] for f in locked] == ["Mehrunnisa"]
    assert locked[0]["cnic"] is None
