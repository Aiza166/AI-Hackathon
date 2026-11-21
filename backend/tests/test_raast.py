"""Mock Raast title fetch + our Confirmation-of-Payee layer, and how SafeSwitch and claims use it."""
from datetime import datetime

from app.mock import raast

ZAINAB_CNIC = "9000000000022"


def _fetch(client, headers, iban: str, name: str = "Zainab Bibi", cnic: str | None = ZAINAB_CNIC):
    response = client.post("/mock/raast/title-fetch",
                           json={"proxy_type": "IBAN", "proxy_value": iban, "expected_name": name, "expected_cnic": cnic},
                           headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _fault(client, login, mode: str) -> None:
    response = client.post("/api/v1/admin/faults", json={"service": "raast", "mode": mode}, headers=login("admin"))
    assert response.status_code == 200, response.text


def _change(client, login, case_id: str, iban: str) -> dict:
    response = client.post(f"/api/v1/cases/{case_id}/payout-change", json={"new_iban": iban}, headers=login("zainab"))
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_mask_keeps_first_two_letters_of_each_word():
    assert raast.mask_name("ZAINAB BIBI") == "ZA**** BI**"


def test_own_single_account_is_a_match_with_masked_title_and_no_cnic(client, login):
    data = _fetch(client, login("admin"), "PK00MOCK0000000000000001")
    assert data["status"] == "OK" and data["match_level"] == "MATCH"
    assert data["masked_title"] == "ZA**** BI**"
    assert data["account_type"] == "ACCOUNT" and data["account_holding"] == "SINGLE"
    assert data["cnic_match"] is True and data["simulated"] is True
    assert ZAINAB_CNIC not in str(data)


def test_joint_account_is_only_a_close_match(client, login):
    data = _fetch(client, login("admin"), "PK00MOCK0000000000000012")
    assert data["account_holding"] == "JOINT"
    assert data["match_level"] == "CLOSE_MATCH" and data["route"] == "ASK_PROOF"
    assert "JOINT_ACCOUNT" in data["reason_codes"]


def test_someone_elses_account_is_no_match(client, login):
    data = _fetch(client, login("admin"), "PK00MOCK0000000000000008")
    assert data["match_level"] == "NO_MATCH" and data["cnic_match"] is False


def test_unknown_account_is_no_match(client, login):
    data = _fetch(client, login("admin"), "PK00MOCK0000000000009999")
    assert data["status"] == "ACCOUNT_NOT_FOUND" and data["match_level"] == "NO_MATCH"


def test_timeout_fault_never_gives_a_verdict(client, login):
    _fault(client, login, "timeout")
    data = _fetch(client, login("admin"), "PK00MOCK0000000000000001")
    assert data["status"] == "TIMEOUT" and data["match_level"] == "UNAVAILABLE" and data["route"] == "UNSURE"


def test_citizen_cannot_call_the_mock_title_fetch(client, login):
    response = client.post("/mock/raast/title-fetch", json={"proxy_value": "PK00MOCK0000000000000001", "expected_name": "Zainab"},
                           headers=login("zainab"))
    assert response.status_code == 403


def test_safeswitch_to_joint_account_is_flagged_for_proof(client, login, file_claim):
    change = _change(client, login, file_claim("zainab")["data"]["id"], "PK00MOCK0000000000000012")
    assert change["status"] == "flagged"
    assert "JOINT_ACCOUNT" in change["flags"]
    assert change["payee_check"]["masked_title"] == "ZA**** BI** & IM*** AS***"
    assert change["payee_check"]["route"] == "ASK_PROOF"


def test_safeswitch_timeout_holds_for_an_officer_and_never_auto_accepts(client, login, file_claim):
    case_id = file_claim("zainab")["data"]["id"]
    _fault(client, login, "timeout")
    change = _change(client, login, case_id, "PK00MOCK0000000000000013")
    assert change["status"] == "flagged"
    assert change["payee_result"] == "unavailable"
    assert change["flags"] == ["PAYEE_CHECK_TIMEOUT"]
    hold = datetime.fromisoformat(change["hold_until"])
    assert (hold - datetime.now(hold.tzinfo)).days >= 4
    confirmed = client.post(f"/api/v1/payout-changes/{change['id']}/confirm", json={"pin": "1234"}, headers=login("zainab")).json()["data"]
    assert confirmed["status"] == "flagged"  # her PIN alone is not enough: an officer must approve


def test_safeswitch_to_own_wallet_is_a_clean_48h_hold(client, login, file_claim):
    change = _change(client, login, file_claim("zainab")["data"]["id"], "PK00MOCK0000000000000013")
    assert change["status"] == "held" and change["flags"] == []
    assert change["payee_check"]["account_type"] == "WALLET"


def test_claim_to_joint_account_asks_for_proof(file_claim):
    data = file_claim("zainab", payout_iban="PK00MOCK0000000000000012")["data"]
    assert data["status"] == "proof_requested"
    assert data["latest_decision"]["reason_codes"] == ["PAYEE_CLOSE_MATCH"]


def test_claim_while_title_fetch_times_out_goes_to_an_officer(client, login, file_claim):
    _fault(client, login, "timeout")
    data = file_claim("zainab")["data"]
    assert data["status"] == "in_review"
    assert data["latest_decision"]["reason_codes"] == ["SERVICE_UNAVAILABLE"]
