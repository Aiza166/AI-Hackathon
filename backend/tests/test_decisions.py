"""End-to-end decision behaviour through the API (the demo scenarios)."""


def _decision(body: dict) -> tuple[str, list[str]]:
    data = body["data"]
    return data["status"], data["latest_decision"]["reason_codes"]


def test_clean_widow_claim_with_name_variants_is_auto_approved(file_claim):
    status, reasons = _decision(file_claim("zainab"))
    assert status == "auto_approved"
    assert reasons == ["APPROVED"]


def test_competing_claimant_not_in_family_record_pauses_both_cases(file_claim, client, login):
    zainab = file_claim("zainab")
    rukhsana = file_claim("rukhsana", claimant_cnic="9000000000033", claimant_name="Rukhsana", payout_iban="PK00MOCK0000000000000002")

    assert _decision(rukhsana) == ("in_review", ["NOT_IN_FAMILY_RECORD"])
    assert rukhsana["meta"]["rechecked_cases"] == [zainab["data"]["reference"]]
    again = client.get(f"/api/v1/cases/{zainab['data']['id']}", headers=login("zainab")).json()
    assert _decision(again) == ("in_review", ["DUPLICATE_CLAIM"])


def test_lawful_second_widow_is_a_co_sharer_not_a_fraud_flag(file_claim):
    common = {"deceased_cnic": "9000000000055", "deceased_name": "Abdul Rauf"}
    saima = file_claim("saima", claimant_cnic="9000000000056", claimant_name="Saima", payout_iban="PK00MOCK0000000000000003", **common)
    nasreen = file_claim("nasreen", claimant_cnic="9000000000057", claimant_name="Nasreen", payout_iban="PK00MOCK0000000000000004", **common)
    assert _decision(saima)[0] == "auto_approved"
    assert _decision(nasreen)[0] == "auto_approved"


def test_look_alike_deceased_with_wrong_cnic_is_never_paid(file_claim):
    # Same name "Muhammad Aslam", but the CNIC of a different, living man.
    status, reasons = _decision(file_claim("zainab", deceased_cnic="9000000000044"))
    assert status == "in_review"
    assert "DEATH_NOT_VERIFIED" in reasons
    assert "NOT_IN_FAMILY_RECORD" in reasons


def test_missing_deceased_cnic_with_two_candidates_says_not_sure(file_claim):
    status, reasons = _decision(file_claim("zainab", deceased_cnic=None))
    assert status == "in_review"
    assert reasons == ["MULTIPLE_CANDIDATES"]


def test_missing_nikah_nama_asks_for_that_exact_document(file_claim, client, login):
    body = file_claim("zainab", documents=["death_certificate", "claimant_cnic", "frc"])
    assert _decision(body) == ("proof_requested", ["MISSING_INFO"])
    explanation = client.get(f"/api/v1/cases/{body['data']['id']}/explanation", headers=login("zainab")).json()["data"]
    assert explanation["missing_items"] == ["nikah_nama"]
    assert explanation["explanations"][0]["text_ur"]


def test_payout_account_close_name_match_asks_for_confirmation(file_claim):
    status, reasons = _decision(file_claim("zainab", payout_iban="PK00MOCK0000000000000007"))
    assert status == "proof_requested"
    assert reasons == ["PAYEE_CLOSE_MATCH"]


def test_payout_to_someone_elses_account_goes_to_a_human(file_claim):
    status, reasons = _decision(file_claim("zainab", payout_iban="PK00MOCK0000000000000008"))
    assert status == "in_review"
    assert "ACCOUNT_NOT_OWNED" in reasons


def test_person_already_drawing_a_family_pension_goes_to_a_human(file_claim):
    body = file_claim(
        "kausar", claimant_cnic="9000000000088", claimant_name="Kausar Parveen",
        deceased_cnic="9000000000089", deceased_name="Tariq Mehmood", payout_iban="PK00MOCK0000000000000009",
    )
    assert _decision(body) == ("in_review", ["ALREADY_DRAWING"])


def test_identity_service_outage_routes_to_not_sure_without_guessing(file_claim, client, login):
    client.post("/api/v1/admin/faults", json={"service": "identity", "mode": "error"}, headers=login("admin"))
    status, reasons = _decision(file_claim("zainab"))
    assert status == "in_review"
    assert reasons == ["SERVICE_UNAVAILABLE"]


def test_auditor_trace_shows_rule_version_signals_and_thresholds(file_claim, client, login):
    body = file_claim("zainab")
    decision_id = body["data"]["latest_decision"]["id"]
    trace = client.get(f"/api/v1/decisions/{decision_id}/trace", headers=login("auditor")).json()["data"]
    assert trace["rule_version"]["version"] == 1
    assert trace["thresholds"]["t_auto"] == 0.95
    assert trace["signals"]["deceased_matches"]["death_certificate_vs_identity"]["route"] == "MATCH"
    assert len(trace["input_hash"]) == 64


def test_officer_queue_sorts_by_priority_then_lowest_confidence(file_claim, client, login):
    file_claim("zainab", documents=["death_certificate", "claimant_cnic", "frc"])  # proof requested, priority 1
    file_claim("rukhsana", claimant_cnic="9000000000033", claimant_name="Rukhsana", payout_iban="PK00MOCK0000000000000002")
    queue = client.get("/api/v1/queue", headers=login("officer")).json()["data"]
    priorities = [c["priority"] for c in queue]
    assert priorities == sorted(priorities, reverse=True)
