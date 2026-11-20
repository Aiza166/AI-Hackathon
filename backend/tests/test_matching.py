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
