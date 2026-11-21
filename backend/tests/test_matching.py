from datetime import date

import pytest

from app.decision.matching import match_identity, name_similarity, parse_name


@pytest.mark.parametrize(("a", "b"), [
    ("Muhammad Aslam", "Mohd. Aslam"),
    ("Muhammad Aslam", "Muhammed Aslam"),
    ("Muhammad Aslam", "Mohammad Aslam"),
    ("M. Aslam", "Muhammad Aslam"),
    ("Mst. Zainab Bibi", "Zainab"),
    ("Aslam Muhammad", "Muhammad Aslam"),
])
def test_spelling_variants_of_the_same_name_score_high(a, b):
    assert name_similarity(a, b) >= 95


@pytest.mark.parametrize(("a", "b"), [
    ("Muhammad Aslam", "Muhammad Akram"),
    ("Muhammad Aslam", "Muhammad Asif"),
    ("Zainab Bibi", "Zubaida Bibi"),
])
def test_different_people_sharing_muhammad_do_not_score_high(a, b):
    assert name_similarity(a, b) < 85


def test_relation_marker_is_split_off():
    parsed = parse_name("Zainab Bibi w/o Muhammad Aslam")
    assert parsed.tokens == ("zainab",)
    assert parsed.relation_name == ("muhammad", "aslam")
    assert "bibi" in parsed.honorifics


def test_exact_cnic_and_name_variant_is_a_match():
    result = match_identity("Mohd. Aslam", "Muhammad Aslam", claimed_cnic="9000000000011", record_cnic="9000000000011")
    assert result.route == "MATCH"
    assert result.probability >= 0.95


def test_never_match_without_exact_cnic_even_with_identical_name_and_dob():
    result = match_identity(
        "Muhammad Aslam", "Muhammad Aslam", claimed_cnic=None, record_cnic="9000000000044",
        claimed_dob=date(1955, 9, 2), record_dob=date(1955, 9, 2),
    )
    assert result.route == "ASK"


def test_same_name_different_cnic_goes_to_a_human():
    result = match_identity("Muhammad Aslam", "Muhammad Aslam", claimed_cnic="9000000000011", record_cnic="9000000000044")
    assert result.route == "UNSURE"


def test_cnic_exact_but_name_different_goes_to_a_human():
    result = match_identity("Muhammad Akram", "Muhammad Aslam", claimed_cnic="9000000000011", record_cnic="9000000000011")
    assert result.route == "UNSURE"


def test_one_digit_cnic_typo_is_not_a_match():
    result = match_identity("Muhammad Aslam", "Muhammad Aslam", claimed_cnic="9000000000012", record_cnic="9000000000011")
    assert result.route == "ASK"
    assert result.levels["cnic"] == "one_digit"


def test_weights_are_recorded_for_the_auditor():
    result = match_identity("Mohd. Aslam", "Muhammad Aslam", claimed_cnic="9000000000011", record_cnic="9000000000011")
    assert set(result.weights) == {"prior", "name", "cnic", "dob"}


@pytest.mark.parametrize("honorific", ["Sahib", "Sahab", "Saheb"])
def test_sahib_style_honorifics_are_ignored(honorific):
    assert name_similarity(f"Mohammad Aslam {honorific}", "Muhammad Aslam") >= 95
    assert honorific.lower() in parse_name(f"Mohammad Aslam {honorific}").honorifics


def test_exact_cnic_with_conflicting_dob_is_never_a_match():
    result = match_identity(
        "Muhammad Aslam", "Muhammad Aslam", claimed_cnic="9000000000011", record_cnic="9000000000011",
        claimed_dob=date(1958, 9, 2), record_dob=date(1955, 9, 2),
    )
    assert result.levels["dob"] == "different"
    assert result.route == "ASK"
    assert result.reasons == ("DOB conflicts with the record",)


def test_exact_cnic_with_missing_dob_matches_only_when_dob_is_not_required():
    # Deceased-person checks have no typed DOB, so DOB is not required there.
    result = match_identity(
        "Muhammad Aslam", "Muhammad Aslam", claimed_cnic="9000000000011", record_cnic="9000000000011",
        claimed_dob=None, record_dob=date(1955, 9, 2),
    )
    assert result.route == "MATCH"


def test_claimant_with_blank_dob_is_asked_to_confirm_it():
    result = match_identity(
        "Zainab Bibi", "Zainab Bibi", claimed_cnic="9000000000022", record_cnic="9000000000022",
        claimed_dob=None, record_dob=date(1962, 6, 1), require_dob=True,
    )
    assert result.route == "ASK"
    assert result.reasons == ("date of birth not given",)


@pytest.mark.parametrize("typed", [date(1962, 6, 2), date(1962, 1, 1)])
def test_claimant_dob_must_equal_the_record_exactly(typed):
    result = match_identity(
        "Zainab Bibi", "Zainab Bibi", claimed_cnic="9000000000022", record_cnic="9000000000022",
        claimed_dob=typed, record_dob=date(1962, 6, 1), require_dob=True,
    )
    assert result.route == "ASK"
    assert result.reasons == ("DOB close to the record but not exact",)


def test_claimant_dob_missing_from_the_record_is_not_a_match():
    result = match_identity(
        "Zainab Bibi", "Zainab Bibi", claimed_cnic="9000000000022", record_cnic="9000000000022",
        claimed_dob=date(1962, 6, 1), record_dob=None, require_dob=True,
    )
    assert result.route == "ASK"


def test_claimant_with_exact_dob_matches():
    result = match_identity(
        "Mst. Zainab Bibi", "Zainab Bibi", claimed_cnic="9000000000022", record_cnic="9000000000022",
        claimed_dob=date(1962, 6, 1), record_dob=date(1962, 6, 1), require_dob=True,
    )
    assert result.route == "MATCH"


def test_exact_cnic_with_exact_dob_matches():
    result = match_identity(
        "Muhammad Aslam", "Muhammad Aslam", claimed_cnic="9000000000011", record_cnic="9000000000011",
        claimed_dob=date(1955, 9, 2), record_dob=date(1955, 9, 2),
    )
    assert result.route == "MATCH"


def test_conflicting_dob_does_not_override_cnic_conflict():
    result = match_identity(
        "Muhammad Aslam", "Muhammad Aslam", claimed_cnic="9000000000011", record_cnic="9000000000044",
        claimed_dob=date(1958, 9, 2), record_dob=date(1955, 9, 2),
    )
    assert result.route == "UNSURE"
