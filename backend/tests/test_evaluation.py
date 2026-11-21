"""Evaluation API (Challenge 1): labelled synthetic sets, threshold sweep, name and scam metrics."""
import pytest

from app.evaluation import claims, names, runner, scam_eval
from app.models.audit import AuditEvent
from app.schemas.contracts import Route


@pytest.fixture(scope="module")
def ruleset():
    return runner.default_ruleset()


@pytest.fixture(scope="module")
def claim_result(ruleset):
    return claims.evaluate_claims(ruleset)


def test_claim_set_is_deterministic_labelled_and_mock_only():
    first, second = claims.generate_cases(), claims.generate_cases()
    assert first == second
    assert len(first) == 200
    assert {c.category for c in first} == set(claims.CATEGORIES)
    cnics = [c.claimant_record.cnic for c in first] + [c.deceased_record.cnic for c in first]
    assert all(cnic.startswith("90000") and len(cnic) == 13 for cnic in cnics)


def test_sweep_covers_050_to_099_and_cost_formula_holds(claim_result):
    sweep = claim_result["sweep"]
    assert [row["threshold"] for row in sweep][:2] == [0.5, 0.51]
    assert len(sweep) == 50 and sweep[-1]["threshold"] == 0.99
    for row in sweep:
        assert row["total_cost"] == 20 * row["wrong_approvals"] + 1 * row["delayed_genuine"]
        assert row["auto_approve_rate"] + row["ask_proof_rate"] + row["human_rate"] == pytest.approx(1.0)
    assert claim_result["min_cost"]["total_cost"] <= claim_result["at_configured"]["total_cost"]
    assert claim_result["analytic_threshold"] == pytest.approx(20 / 21, abs=1e-4)


def test_red_flag_categories_never_auto_approve_at_any_threshold(ruleset):
    cases = [c for c in claims.generate_cases()
             if c.category in ("payee_no_match", "already_drawing", "duplicate_claimant", "missing_document")]
    for t in (0.5, 0.95, 0.99):
        assert all(route != Route.AUTO_APPROVE for _, route, _ in claims.run_at(cases, ruleset, t))


def test_clean_claims_auto_approve_at_the_configured_threshold(claim_result):
    clean = claim_result["by_category_at_configured"]["clean"]
    assert clean["AUTO_APPROVE"] == clean["n"]


def test_name_eval_has_no_false_matches_on_hard_negatives():
    result = names.evaluate_names()
    assert 480 <= result["n_pairs"] <= 520
    assert result["false_match_rate"] == 0.0
    assert result["by_kind"]["different:cnic_one_digit_off"]["MATCH"] == 0
    assert result["by_kind"]["different:same_full_name"]["MATCH"] == 0
    assert 0 < result["false_non_match_rate"] < 0.5  # variants that need a person are counted, not hidden
    for pair in names.generate_pairs():
        assert pair["args"][2].startswith("90000") and pair["args"][3].startswith("90000")


def test_match_p_override_keeps_default_behaviour():
    from app.decision.matching import match_identity

    default = match_identity("Mohd. Aslam", "Muhammad Aslam", claimed_cnic="9000000000011", record_cnic="9000000000011")
    strict = match_identity("Mohd. Aslam", "Muhammad Aslam", claimed_cnic="9000000000011", record_cnic="9000000000011", match_p=1.01)
    assert default.route == "MATCH" and strict.route == "ASK"


def test_scam_fallback_never_says_genuine_and_misses_nothing():
    result = scam_eval.evaluate_scam(live=False)
    assert result["mode"] == "keyword_fallback" and result["n"] == 40
    assert result["model_id"] is None and result["fallback_count"] == 40
    assert result["fnr"] == 0.0 and result["genuine_passed_rate"] == 0.0
    assert set(result["by_language"]) == {"en", "roman_ur", "ur"}


def test_officer_reads_latest_in_envelope(client, login):
    response = client.get("/api/v1/eval/latest", headers=login("officer"))
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True and body["data"]["prototype"] is True
    assert {"claims", "names", "scam", "summary"} <= set(body["data"])


def test_citizen_cannot_read_or_run_eval(client, login):
    headers = login("zainab")
    assert client.get("/api/v1/eval/latest", headers=headers).status_code == 403
    assert client.post("/api/v1/eval/run", headers=headers).status_code == 403


def test_auditor_run_is_audited_and_cached(client, login, db):
    response = client.post("/api/v1/eval/run", headers=login("auditor"))
    assert response.status_code == 200, response.text
    summary = response.json()["data"]["summary"]
    assert summary["scam_mode"] == "keyword_fallback"
    # The audit log is append-only and survives between tests, so take the newest event.
    event = db.query(AuditEvent).filter(AuditEvent.action == "EVAL_RUN").order_by(AuditEvent.seq.desc()).first()
    assert event.role == "auditor" and event.details["min_cost_threshold"] == summary["min_cost_threshold"]
    latest = client.get("/api/v1/eval/latest", headers=login("officer")).json()["data"]
    assert latest["generated_at"] == response.json()["data"]["generated_at"]


def test_live_scam_eval_is_admin_only_and_needs_a_key(client, login):
    assert client.post("/api/v1/eval/run?live=true", headers=login("officer")).status_code == 403
    response = client.post("/api/v1/eval/run?live=true", headers=login("admin"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "JEV_NOT_CONFIGURED"
