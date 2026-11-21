"""SafeSwitch: payout account changes are held, confirmed by the claimant herself, and flagged when risky."""
from datetime import datetime


def _zainab_case(file_claim) -> str:
    return file_claim("zainab")["data"]["id"]


def _request(client, headers, case_id: str, iban: str):
    return client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": iban}, headers=headers)


def test_own_account_with_a_name_close_match_is_flagged_for_review(client, login, file_claim):
    # "ZAINAB B" is Zainab's own account, but the title is only a close match to her name.
    case_id = _zainab_case(file_claim)
    change = _request(client, login("zainab"), case_id, "PK00MOCK0000000000000007").json()["data"]
    assert change["status"] == "flagged"
    assert change["flags"] == ["PAYEE_CLOSE_MATCH"]


def test_business_days_skip_weekends():
    from app.services.payout import add_business_days

    friday = datetime(2026, 11, 20, 12, 0)
    assert add_business_days(friday, 4) == datetime(2026, 11, 26, 12, 0)


def test_change_to_someone_elses_account_is_flagged_and_held_4_business_days(client, login, file_claim):
    case_id = _zainab_case(file_claim)
    change = _request(client, login("zainab"), case_id, "PK00MOCK0000000000000008").json()["data"]
    assert change["payee_result"] == "no_match"
    assert change["status"] == "flagged"
    held_days = (datetime.fromisoformat(change["hold_until"]) - datetime.now(datetime.fromisoformat(change["hold_until"]).tzinfo)).days
    assert held_days >= 4


def test_helper_can_start_but_never_confirm(client, login, file_claim):
    case_id = _zainab_case(file_claim)
    change = _request(client, login("helper"), case_id, "PK00MOCK0000000000000007").json()["data"]
    assert client.post(f"/api/v1/payout-changes/{change['id']}/confirm", json={"pin": "1234"}, headers=login("helper")).status_code == 403


def test_wrong_pin_does_not_confirm_and_is_logged(client, login, file_claim):
    case_id = _zainab_case(file_claim)
    zainab = login("zainab")
    change = _request(client, zainab, case_id, "PK00MOCK0000000000000007").json()["data"]
    assert client.post(f"/api/v1/payout-changes/{change['id']}/confirm", json={"pin": "9999"}, headers=zainab).status_code == 403
    events = client.get("/api/v1/audit?action=PAYOUT_CONFIRM_FAILED", headers=login("auditor")).json()["data"]
    assert events


def test_flagged_change_needs_claimant_pin_and_officer_then_applies_after_hold(client, login, file_claim):
    case_id = _zainab_case(file_claim)
    zainab, officer = login("zainab"), login("officer")
    change = _request(client, zainab, case_id, "PK00MOCK0000000000000007").json()["data"]
    confirmed = client.post(f"/api/v1/payout-changes/{change['id']}/confirm", json={"pin": "1234"}, headers=zainab).json()["data"]
    assert confirmed["status"] == "flagged"  # still waits for the officer
    approved = client.post(f"/api/v1/payout-changes/{change['id']}/approve", json={"note": "Spoke to her at the desk"}, headers=officer).json()["data"]
    assert approved["status"] == "confirmed"

    assert client.post("/api/v1/admin/payout/apply-due", headers=login("admin")).json()["data"]["applied"] == []  # hold not over
    applied = client.post("/api/v1/admin/payout/apply-due?skip_wait=true", headers=login("admin")).json()["data"]["applied"]
    assert applied == [change["id"]]


def test_only_one_open_change_per_claim(client, login, file_claim):
    case_id = _zainab_case(file_claim)
    zainab = login("zainab")
    _request(client, zainab, case_id, "PK00MOCK0000000000000007")
    assert _request(client, zainab, case_id, "PK00MOCK0000000000000001").status_code == 409


def test_withdrawn_payout_consent_blocks_the_helper(client, login, file_claim):
    case_id = _zainab_case(file_claim)
    zainab = login("zainab")
    consents = client.get("/api/v1/me/consents", headers=zainab).json()["data"]["consents"]
    helper_consent = next(c for c in consents if c["grantee_type"] == "helper")
    client.patch(f"/api/v1/me/consents/{helper_consent['id']}", json={"fields": ["case_details"]}, headers=zainab)
    assert _request(client, login("helper"), case_id, "PK00MOCK0000000000000007").status_code == 403


def test_claimant_can_cancel_a_pending_change_and_start_again(client, login, file_claim):
    case_id = _zainab_case(file_claim)
    change = _request(client, login("zainab"), case_id, "PK00MOCK0000000000000013").json()["data"]
    cancelled = client.post(f"/api/v1/payout-changes/{change['id']}/cancel", headers=login("zainab"))
    assert cancelled.status_code == 200 and cancelled.json()["data"]["status"] == "cancelled"
    assert client.post(f"/api/v1/payout-changes/{change['id']}/cancel", headers=login("zainab")).status_code == 409
    assert _request(client, login("zainab"), case_id, "PK00MOCK0000000000000013").status_code == 201


def test_other_citizen_cannot_cancel(client, login, file_claim):
    case_id = _zainab_case(file_claim)
    change = _request(client, login("zainab"), case_id, "PK00MOCK0000000000000013").json()["data"]
    assert client.post(f"/api/v1/payout-changes/{change['id']}/cancel", headers=login("rukhsana")).status_code == 403


def test_officer_lists_flagged_changes_with_case_reference(client, login, file_claim):
    case = file_claim("zainab")["data"]
    _request(client, login("zainab"), case["id"], "PK00MOCK0000000000000008")
    rows = client.get("/api/v1/payout-changes", headers=login("officer")).json()["data"]
    assert len(rows) == 1 and rows[0]["case_reference"] == case["reference"] and rows[0]["status"] == "flagged"
    assert client.get("/api/v1/payout-changes", headers=login("zainab")).status_code == 403
    assert client.get("/api/v1/payout-changes", headers=login("welfare_officer")).json()["data"] == []
