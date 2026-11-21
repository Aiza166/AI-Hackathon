"""Red-team regressions on document units: document numbers (M3), unverified (M4)."""
import pytest

from app.documents import consistency, indicators

# ---------- M3 document number match ----------

@pytest.mark.parametrize("typed", ["-", "1", "2", "0412", "12-2026-0412"])
def test_m3_short_or_suffix_numbers_never_match(typed):
    assert not consistency.same_doc_number(typed, "DC-UC12-2026-0412")


def test_m3_exact_and_printed_prefix_still_match():
    assert consistency.same_doc_number("DC-UC12-2026-0412", "DC-UC12-2026-0412")
    assert consistency.same_doc_number("MOCK-FRC-1001", "FRC-1001")


# ---------- M4 unverified tier ----------

def test_m4_missing_required_fields_is_unverified_with_honest_words():
    found = indicators.from_required("death_certificate", {})
    assert indicators.risk_level(found) == "unverified"
    assert found[0].text_en.startswith("We could not read this paper")
