"""The rules engine on the real rulesets (v1 and v2)."""
import json
from datetime import date
from pathlib import Path

from app.decision.rules import evaluate

RULESETS = Path(__file__).parent.parent / "app" / "decision" / "rulesets"
V1 = json.loads((RULESETS / "survivor_pension_v1.json").read_text(encoding="utf-8"))
V2 = json.loads((RULESETS / "survivor_pension_v2.json").read_text(encoding="utf-8"))
ALL_DOCS = ["death_certificate", "claimant_cnic", "frc", "nikah_nama"]


def _facts(**overrides) -> dict:
    base = {
        "relation": "widow", "frc_links_claimant": True, "death_verified": True, "pension_found": True,
        "already_draws_family_pension": False, "documents": ALL_DOCS, "spouse_alive_eligible": True,
        "lawful_widows_count": 1, "eligible_children_count": 0, "claimant_age": 60, "claimant_disabled": False,
        "claimant_marital_status": "widowed", "became_eligible_on": date(2026, 8, 14), "claimant_dob": date(1962, 6, 1),
    }
    return {**base, **overrides}


def test_clean_widow_is_eligible_under_v1():
    assert evaluate(V1, _facts()).outcome == "eligible"


def test_missing_document_names_the_item():
    result = evaluate(V1, _facts(documents=["death_certificate", "claimant_cnic", "frc"]))
    assert result.outcome == "missing_info"
    assert [h.missing_item for h in result.hits] == ["nikah_nama"]


def test_not_eligible_beats_missing_info():
    result = evaluate(V1, _facts(frc_links_claimant=False, documents=[]))
    assert result.outcome == "not_eligible"


def test_son_over_21_is_not_eligible_unless_disabled():
    son = dict(relation="son", spouse_alive_eligible=False, claimant_marital_status="married")
    assert evaluate(V1, _facts(claimant_age=22, **son)).outcome == "not_eligible"
    assert evaluate(V1, _facts(claimant_age=22, claimant_disabled=True, **son)).outcome == "eligible"


def test_divorced_daughter_is_eligible_married_daughter_is_not():
    daughter = dict(relation="daughter", spouse_alive_eligible=False, documents=["death_certificate", "claimant_cnic", "frc"])
    assert evaluate(V1, _facts(claimant_marital_status="divorced", **daughter)).outcome == "eligible"
    assert evaluate(V1, _facts(claimant_marital_status="married", **daughter)).outcome == "not_eligible"


def test_children_wait_while_an_eligible_widow_is_alive():
    result = evaluate(V1, _facts(relation="son", claimant_age=20, spouse_alive_eligible=True, documents=["death_certificate", "claimant_cnic", "frc"]))
    assert result.outcome == "not_eligible"
    assert result.hits[0].reason == "WIDOW_FIRST"


def test_two_widows_share_equally():
    assert evaluate(V1, _facts(lawful_widows_count=2)).share == "1/2"


def test_v2_ten_year_cap_applies_to_heirs_who_became_eligible_after_sep_2024():
    hina = _facts(relation="daughter", spouse_alive_eligible=False, claimant_marital_status="divorced",
                  claimant_dob=date(1991, 12, 12), became_eligible_on=date(2024, 11, 1),
                  documents=["death_certificate", "claimant_cnic", "frc"])
    assert evaluate(V1, hina).entitlement_end is None
    assert evaluate(V2, hina).entitlement_end == date(2034, 11, 1)


def test_v2_child_gets_until_21_if_that_is_later():
    bilal = _facts(relation="son", spouse_alive_eligible=False, claimant_age=18, claimant_dob=date(2020, 1, 1),
                   became_eligible_on=date(2024, 11, 1), documents=["death_certificate", "claimant_cnic", "frc"])
    assert evaluate(V2, bilal).entitlement_end == date(2041, 1, 1)


def test_v2_existing_pensioners_are_exempt():
    before = _facts(relation="daughter", spouse_alive_eligible=False, claimant_marital_status="unmarried",
                    became_eligible_on=date(2020, 1, 1), documents=["death_certificate", "claimant_cnic", "frc"])
    assert evaluate(V2, before).entitlement_end is None


def test_v2_does_not_touch_the_widow():
    assert evaluate(V2, _facts()).entitlement_end is None
