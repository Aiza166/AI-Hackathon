"""Document pipeline units: quality, OCR adapter, field parser, forensics, Jev questions, indicators."""
import io
import json
from datetime import date

import httpx
import pytest
from PIL import Image, ImageEnhance, ImageFilter

from app.core.config import get_settings
from app.decision.jev_client import JevClient
from app.documents import fields, forensics, imaging, indicators, jev_checks, ocr
from tests.doc_fixtures import SAMPLE_DIR, cnic_front_tesseract, death_certificate, frc_azure, nikah_azure_label_hidden, sample

MANIFEST = json.loads((SAMPLE_DIR / "manifest.json").read_text(encoding="utf-8"))["files"]


def _jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


# ---------- quality ----------

@pytest.mark.parametrize("entry", MANIFEST, ids=lambda e: e["file"])
def test_every_sample_document_passes_the_quality_check(entry):
    assert imaging.check_quality(imaging.load(sample(entry["file"]))).ok


def test_blurred_dark_and_tiny_photos_are_sent_back_for_a_retake():
    img = imaging.load(sample("cnic_front_zainab.whatsapp.jpg")).image
    blurred = imaging.check_quality(imaging.load(_jpeg(img.filter(ImageFilter.GaussianBlur(3)))))
    dark = imaging.check_quality(imaging.load(_jpeg(ImageEnhance.Brightness(img).enhance(0.25))))
    tiny = imaging.check_quality(imaging.load(_jpeg(img.resize((200, 126)))))
    assert "blurry" in blurred.problems and not blurred.ok
    assert "too_dark" in dark.problems
    assert "too_small" in tiny.problems


def test_loader_rejects_non_images_and_caps_size():
    with pytest.raises(imaging.BadImage):
        imaging.load(b"%PDF-1.4 not an image")
    big = Image.new("RGB", (4000, 3000), "white")
    loaded = imaging.load(_jpeg(big))
    assert max(loaded.image.size) == imaging.MAX_SIDE
    assert loaded.original_size == (4000, 3000)


# ---------- forensics (tuned on sample_docs) ----------

@pytest.mark.parametrize("entry", MANIFEST, ids=lambda e: e["file"])
def test_copy_move_flags_only_the_pasted_seal(entry):
    result = forensics.detect_copy_move(imaging.load(sample(entry["file"])).image)
    assert result.found == entry["edited"], (entry["file"], result.score)


def test_copy_move_points_at_both_seals_with_keypoint_evidence():
    result = forensics.detect_copy_move(imaging.load(sample("death_certificate_aslam_edited.png")).image)
    assert result.found and result.score >= forensics.COPY_MOVE_NCC
    assert len(result.regions) == 2 and result.orb_matches > 20
    xs = sorted(r[0] for r in result.regions)
    assert xs[1] - xs[0] > 300  # the original seal and the pasted copy, side by side


def test_ela_heatmap_and_screenshot_hint_are_informational():
    loaded = imaging.load(sample("death_certificate_aslam.screenshot.png"))
    report, heatmap = forensics.analyse(loaded.image, loaded.exif)
    assert heatmap[:2] == b"\xff\xd8"  # a JPEG for the officer view
    assert report.looks_like_screenshot
    found = indicators.from_forensics(report)
    assert [i.code for i in found] == ["SCREEN_PHOTO"] and found[0].severity == "info"


def test_missing_exif_never_counts_and_edit_software_is_context_only():
    loaded = imaging.load(sample("cnic_front_zainab.png"))
    report, _ = forensics.analyse(loaded.image, {})
    assert indicators.from_forensics(report) == []
    tagged, _ = forensics.analyse(loaded.image, {"software": "Adobe Photoshop 25"})
    assert [(i.code, i.severity) for i in indicators.from_forensics(tagged)] == [("EDIT_SOFTWARE_TAG", "info")]


# ---------- field parser ----------

@pytest.mark.parametrize("text,expected", [
    ("14.08.2026", date(2026, 8, 14)), ("14/08/2026", date(2026, 8, 14)), ("14-08-2026", date(2026, 8, 14)),
    ("14-Aug-2026", date(2026, 8, 14)), ("14 August 2026", date(2026, 8, 14)), ("01.06.62", date(1962, 6, 1)),
    ("31.02.2026", None), ("no date here", None),
])
def test_dates_are_read_day_first_in_all_printed_formats(text, expected):
    assert fields.parse_date(text) == expected


def test_cnic_regex_accepts_dashes_spaces_or_none():
    assert fields.normalise_cnic("CNIC 90000-0000001-1") == "9000000000011"
    assert fields.normalise_cnic("90000 0000001 1") == "9000000000011"
    assert fields.normalise_cnic("9000000000011") == "9000000000011"
    assert fields.normalise_cnic("90000-000001-1") is None


def test_death_certificate_fields_from_azure_style_lines():
    found = fields.extract_fields("death_certificate", death_certificate())
    assert found["name_of_deceased"].value == "Mohd. Aslam"
    assert found["deceased_cnic"].value == "9000000000011"  # not the informant's CNIC
    assert found["date_of_death"].value == "2026-08-14"
    assert found["certificate_no"].value == "DC-UC12-2026-0412"
    assert not any(f.needs_confirmation for f in found.values())


def test_cnic_card_from_merged_tesseract_lines_needs_confirmation_when_unsure():
    found = fields.extract_fields("claimant_cnic", cnic_front_tesseract())
    assert found["name"].value == "ZAINAB BIBI"
    assert found["cnic"].value == "9000000000022"
    assert found["date_of_birth"].value == "1962-06-01"
    assert found["date_of_birth"].needs_confirmation  # read at 0.76: the citizen confirms it


def test_frc_and_nikah_nama_fields_even_when_labels_are_hidden():
    frc = fields.extract_fields("frc", frc_azure())
    assert frc["frc_number"].value == "MOCK-FRC-1001"
    assert set(frc["member_cnics"].value.split(",")) == {"9000000000022", "9000000000023"}
    nikah = fields.extract_fields("nikah_nama", nikah_azure_label_hidden())
    assert nikah["groom_name"].value == "Muhammad Aslam" and nikah["groom_name"].method == "row"
    assert nikah["bride_name"].value == "Zainab Bibi"


def test_watermark_fragments_are_not_read_as_names():
    result = ocr.OcrResult("azure-prebuilt-read", [
        ocr.OcrLine("Name", 0.99, (39, 110, 84, 126)),
        ocr.OcrLine("MOCI", 0.61, (240, 75, 362, 176)),  # rotated watermark: far taller than print
        ocr.OcrLine("ZAINAB BIBI", 0.99, (36, 134, 221, 161)),
        ocr.OcrLine("Father / Husband Name", 0.99, (38, 199, 212, 217)),
    ])
    assert fields.extract_fields("claimant_cnic", result)["name"].value == "ZAINAB BIBI"


# ---------- OCR adapter ----------

def _azure_settings():
    return get_settings().model_copy(update={"azure_docintel_endpoint": "https://docs.example.test/", "azure_docintel_key": "test-key"})


AZURE_DONE = {"status": "succeeded", "analyzeResult": {"pages": [{
    "words": [{"content": "90000-0000001-1", "span": {"offset": 0, "length": 15}, "confidence": 0.97}],
    "lines": [{"content": "90000-0000001-1", "polygon": [10, 20, 200, 20, 200, 40, 10, 40], "spans": [{"offset": 0, "length": 15}]}],
}]}}


def test_azure_read_submits_polls_and_parses():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        assert request.headers["Ocp-Apim-Subscription-Key"] == "test-key"
        if request.method == "POST":
            assert "prebuilt-read:analyze" in request.url.path
            return httpx.Response(202, headers={"Operation-Location": "https://docs.example.test/ops/1"})
        if len(calls) == 2:
            return httpx.Response(200, json={"status": "running"})
        return httpx.Response(200, json=AZURE_DONE)

    engine = ocr.AzureReadEngine(_azure_settings(), transport=httpx.MockTransport(handler), sleep=lambda _: None)
    result = engine.read(Image.new("RGB", (400, 300), "white"))
    assert result.engine == "azure-prebuilt-read"
    assert result.lines[0].text == "90000-0000001-1" and result.lines[0].confidence == 0.97
    assert result.lines[0].box == (10, 20, 200, 40)
    assert [c[0] for c in calls] == ["POST", "GET", "GET"]


def test_azure_submit_retries_on_503_then_falls_back_to_tesseract(monkeypatch):
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request.method)
        return httpx.Response(503)

    monkeypatch.setattr(ocr.time, "sleep", lambda _: None)
    fallback = ocr.OcrResult("tesseract", [])
    monkeypatch.setattr(ocr.TesseractEngine, "read", lambda self, img: fallback)
    result = ocr.run_ocr(Image.new("RGB", (400, 300)), settings=_azure_settings(), transport=httpx.MockTransport(handler))
    assert result is fallback
    assert attempts == ["POST"] * (ocr.SUBMIT_RETRIES + 1)


def test_no_engine_available_raises_ocr_unavailable(monkeypatch):
    import pytesseract

    def missing(*_, **__):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_data", missing)
    with pytest.raises(ocr.OcrUnavailable):
        ocr.run_ocr(Image.new("RGB", (400, 300)), settings=get_settings().model_copy(update={"azure_docintel_key": None}))


def test_tesseract_words_are_grouped_into_lines_with_confidence():
    data = {"text": ["Name", "", "ZAINAB", "BIBI"], "conf": [96, -1, 90, 80], "block_num": [1, 1, 1, 1],
            "par_num": [1, 1, 1, 1], "line_num": [1, 1, 2, 2], "left": [10, 0, 10, 80], "top": [5, 0, 30, 31],
            "width": [40, 0, 60, 40], "height": [12, 0, 20, 20]}
    lines = ocr.group_tesseract_words(data)
    assert [line.text for line in lines] == ["Name", "ZAINAB BIBI"]
    assert lines[1].confidence == 0.85 and lines[1].box == (10, 30, 120, 51)


# ---------- Jev image questions ----------

def _jev(answers: dict) -> JevClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.headers["TypeSafe-Danger-Zone-Images"] == "true"
        (ref, asset), = body["assets"].items()
        assert asset["format"] == "jpeg" and ref in body["state"]
        assert all(ref in q["instructions"] for q in body["questions"].values())
        return httpx.Response(200, json={"model": "jev-1.14.0", "answers": answers})

    settings = get_settings().model_copy(update={"typesafe_api_key": "test"})
    return JevClient(settings, transport=httpx.MockTransport(handler))


def test_jev_checks_pair_boxes_with_presence_and_band_answers():
    img = imaging.load(sample("death_certificate_aslam.whatsapp.jpg")).image
    client = _jev({
        "right_type": {"noul": 0.9}, "text_altered": {"noul": 0.5}, "screen_photo": {"noul": 0.1},
        "stamp_present": {"noul": 0.85}, "stamp_box": {"box": {"left": 0.3, "top": 0.79, "right": 0.44, "bottom": 0.9}, "confidence": 0.8},
        "text_altered_box": {"box": {"left": 0.1, "top": 0.1, "right": 0.2, "bottom": 0.2}, "confidence": 0.9},
    })
    result = jev_checks.ask_document_questions("death_certificate", img, client=client)
    assert result.status == "ok" and result.model == "jev-1.14.0"
    assert result.answers["text_altered"]["band"] == "undecided"
    assert "stamp_box" in result.boxes and "text_altered_box" not in result.boxes  # presence was not a yes
    codes = {i.code: i.severity for i in indicators.from_jev(result)}
    assert codes == {"JEV_UNDECIDED": "info"}  # undecided never routes by itself


def test_jev_clear_answers_become_indicators():
    img = imaging.load(sample("frc_aslam_family.whatsapp.jpg")).image
    client = _jev({"right_type": {"noul": 0.03}, "text_altered": {"noul": 0.92}, "screen_photo": {"noul": 0.9},
                   "stamp_present": {"noul": 0.1}, "stamp_box": {"box": {}}, "text_altered_box": {"box": {}}})
    result = jev_checks.ask_document_questions("death_certificate", img, client=client)
    codes = {i.code: i.severity for i in indicators.from_jev(result)}
    assert codes == {"TEXT_LOOKS_ALTERED": "high", "WRONG_DOCUMENT": "mismatch", "STAMP_NOT_SEEN": "mismatch", "SCREEN_PHOTO": "info"}


def test_jev_is_skipped_without_a_key_and_unavailable_on_error():
    img = imaging.load(sample("cnic_front_zainab.png")).image
    assert jev_checks.ask_document_questions("claimant_cnic", img).status == "skipped"
    failing = JevClient(get_settings().model_copy(update={"typesafe_api_key": "test"}),
                        transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    result = jev_checks.ask_document_questions("claimant_cnic", img, client=failing)
    # Red team M4/M5: a configured Jev that fails makes the paper "unverified", never silently clean.
    assert result.status == "unavailable" and [i.code for i in indicators.from_jev(result)] == ["CHECK_UNAVAILABLE"]


# ---------- indicators ----------

def test_risk_level_is_the_most_severe_indicator_and_never_a_verdict():
    found = indicators.dedupe([indicators.make("SCREEN_PHOTO"), indicators.make("RECORD_MISMATCH"), indicators.make("STAMP_DUPLICATED")])
    assert [i.code for i in found] == ["STAMP_DUPLICATED", "RECORD_MISMATCH", "SCREEN_PHOTO"]
    assert indicators.risk_level(found) == "high"
    assert indicators.risk_level([indicators.make("SCREEN_PHOTO")]) == "low"
    for code, (_, _, en, ur, cannot) in indicators.TEXTS.items():
        assert "fake" not in en.lower() and "forged" not in en.lower(), code
        assert ur.strip() and cannot.strip()
