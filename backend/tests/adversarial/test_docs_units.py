"""Red-team regressions on document units: copy-move tolerance, digits/dates, Jev junk, pixel bombs, reuse hashes."""
import io
import math

import pytest
from PIL import Image

from app.decision.jev_client import JevUnavailable
from app.documents import consistency, fields, forensics, imaging, indicators, jev_checks, reuse
from app.documents.ocr import OcrLine, OcrResult
from tests.doc_fixtures import sample

GENUINE = ["death_certificate_aslam.png", "death_certificate_aslam.whatsapp.jpg", "frc_aslam_family.png",
           "nikah_nama_aslam_zainab.whatsapp.jpg", "cnic_front_zainab.png"]


def _edited():
    return imaging.load(sample("death_certificate_aslam_edited.png")).image


def _tweak_paste(angle=0.0, scale=1.0):
    """Re-paste the second seal rotated and/or scaled, as an attacker dodging a template match would."""
    base = _edited()
    x0, y0, x1, y1 = forensics.detect_copy_move(base).regions[1]
    box = (x0 - 12, y0 - 12, x1 + 12, y1 + 12)
    crop = base.crop(box).rotate(angle, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    if scale != 1.0:
        crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.BICUBIC)
    base.paste(crop, box[:2])
    return base


# ---------- M1 copy-move ----------

@pytest.mark.parametrize("angle,scale", [(3, 1.0), (-5, 1.0), (0, 0.9), (0, 1.1), (0, 1.25), (3, 1.1)])
def test_m1_rotated_or_scaled_paste_is_still_flagged(angle, scale):
    result = forensics.detect_copy_move(_tweak_paste(angle, scale))
    assert result.found and result.score >= forensics.COPY_MOVE_NCC


@pytest.mark.parametrize("name", GENUINE)
def test_m1_genuine_samples_stay_unflagged(name):
    assert not forensics.detect_copy_move(imaging.load(sample(name)).image).found


# ---------- L4 digits and dates ----------

def test_l4_urdu_and_arabic_indic_cnic_digits_compare_equal():
    assert fields.normalise_cnic("۹۰۰۰۰-۰۰۰۰۰۰۲-۲") == "9000000000022"
    assert fields.normalise_cnic("٩٠٠٠٠-٠٠٠٠٠٠٢-٢") == "9000000000022"


def test_l4_cnic_regex_is_ascii_only_after_mapping():
    assert fields.CNIC_RE.flags & __import__("re").ASCII


def test_l4_iso_dates_parse_and_urdu_digit_dates_parse():
    assert fields.parse_date("2026-08-14").isoformat() == "2026-08-14"
    assert fields.parse_date("۱۴.۰۸.۲۰۲۶").isoformat() == "2026-08-14"


def test_l4_two_digit_year_needs_confirmation_not_silent():
    ocr = OcrResult("azure", [OcrLine("Date of Death", 0.99, (50, 402, 142, 418)), OcrLine("03/12/24", 0.99, (53, 424, 188, 448))])
    read = fields.extract_fields("death_certificate", ocr)["date_of_death"]
    assert read.value == "2024-12-03" and read.needs_confirmation


def test_l4_four_digit_year_still_trusted():
    ocr = OcrResult("azure", [OcrLine("Date of Death", 0.99, (50, 402, 142, 418)), OcrLine("14.08.2026", 0.99, (53, 424, 188, 448))])
    assert not fields.extract_fields("death_certificate", ocr)["date_of_death"].needs_confirmation


# ---------- M3 document number match ----------

@pytest.mark.parametrize("typed", ["-", "1", "2", "0412", "12-2026-0412"])
def test_m3_short_or_suffix_numbers_never_match(typed):
    assert not consistency.same_doc_number(typed, "DC-UC12-2026-0412")


def test_m3_exact_and_printed_prefix_still_match():
    assert consistency.same_doc_number("DC-UC12-2026-0412", "DC-UC12-2026-0412")
    assert consistency.same_doc_number("MOCK-FRC-1001", "FRC-1001")


# ---------- Jev junk ----------

class _Reply:
    def __init__(self, answers):
        self.answers, self.model, self.latency_ms = answers, "jev-1.14.0", 5


class _Client:
    def __init__(self, reply=None, exc=None):
        self.reply, self.exc = reply, exc

    def ask(self, *args, **kwargs):
        if self.exc:
            raise self.exc
        return self.reply


@pytest.mark.parametrize("answers", [
    {"right_type": {"noul": "abc"}}, {"right_type": {"noul": None}}, {"right_type": {"noul": -5}},
    {"right_type": {"noul": 7}}, {"right_type": {"noul": math.nan}}, {"right_type": {"noul": math.inf}},
    {"right_type": "yes"}, None, [],
])
def test_jev_junk_is_unavailable_never_a_crash(answers):
    img = imaging.load(sample("death_certificate_aslam.png")).image
    result = jev_checks.ask_document_questions("death_certificate", img, client=_Client(_Reply(answers)))
    assert result.status == "unavailable" and result.answers == {}
    found = indicators.from_jev(result)
    assert [i.code for i in found] == ["CHECK_UNAVAILABLE"] and indicators.risk_level(found) == "unverified"


@pytest.mark.parametrize("exc", [ValueError("bad json"), KeyError("answers"), TypeError("x"), JevUnavailable("down")])
def test_jev_parse_errors_are_unavailable(exc):
    img = imaging.load(sample("death_certificate_aslam.png")).image
    assert jev_checks.ask_document_questions("death_certificate", img, client=_Client(exc=exc)).status == "unavailable"


def test_jev_junk_box_confidence_is_ignored():
    img = imaging.load(sample("death_certificate_aslam.png")).image
    reply = _Reply({"text_altered": {"noul": 0.9}, "text_altered_box": {"box": {"left": 0, "top": 0, "right": 1, "bottom": 1}, "confidence": "x"}})
    result = jev_checks.ask_document_questions("death_certificate", img, client=_Client(reply))
    assert result.status == "ok" and "text_altered_box" not in result.boxes


# ---------- M4 unverified tier ----------

def test_m4_missing_required_fields_is_unverified_with_honest_words():
    found = indicators.from_required("death_certificate", {})
    assert indicators.risk_level(found) == "unverified"
    assert found[0].text_en.startswith("We could not read this paper")


# ---------- M6 pixel bomb ----------

def test_m6_pixel_bomb_rejected_from_header_before_decode(monkeypatch):
    buf = io.BytesIO()
    Image.new("L", (6000, 5000)).save(buf, "PNG")  # 30 M pixels, tiny file
    decoded = []
    monkeypatch.setattr(Image.Image, "convert", lambda *a, **k: decoded.append(1))
    with pytest.raises(imaging.ImageTooLarge):
        imaging.load(buf.getvalue())
    assert decoded == []


# ---------- M2 perceptual hash ----------

def test_m2_dhash_survives_recompression_and_separates_people():
    h = {n: reuse.dhash(imaging.load(sample(n)).image) for n in
         ("cnic_front_zainab.png", "cnic_front_zainab.whatsapp.jpg", "cnic_front_aslam.png")}
    assert reuse.hamming(h["cnic_front_zainab.png"], h["cnic_front_zainab.whatsapp.jpg"]) <= reuse.DHASH_MAX_DISTANCE
    assert reuse.hamming(h["cnic_front_zainab.png"], h["cnic_front_aslam.png"]) > reuse.DHASH_MAX_DISTANCE
