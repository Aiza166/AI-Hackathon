"""Mock document generator: every image is marked MOCK and the edited copy differs only where recorded."""
import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageChops  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "make_mock_docs.py"
spec = importlib.util.spec_from_file_location("make_mock_docs", SCRIPT)
docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs)


def test_generated_images_carry_mock_metadata(tmp_path):
    img = docs.cnic_front(docs.ZAINAB)
    docs.save_png(img, tmp_path / "card.png", "test")
    docs.whatsapp(img, tmp_path / "card.jpg", "test")
    assert Image.open(tmp_path / "card.png").text["MOCK"] == "true"
    jpg = Image.open(tmp_path / "card.jpg")
    assert b"MOCK" in jpg.info["comment"] and max(jpg.size) <= docs.WHATSAPP_MAX_SIDE


def test_edited_death_certificate_changes_only_recorded_regions():
    original = docs.death_certificate()
    edited, edits = docs.tamper(original)
    assert {e["field"] for e in edits} == {"date_of_death", "name_of_deceased", "seal_copy_move"}
    diff = ImageChops.difference(original, edited).getbbox()
    boxes = [e["box"] for e in edits]
    assert diff is not None
    assert diff[0] >= min(b[0] for b in boxes) and diff[1] >= min(b[1] for b in boxes)
    assert diff[2] <= max(b[2] for b in boxes) and diff[3] <= max(b[3] for b in boxes)
