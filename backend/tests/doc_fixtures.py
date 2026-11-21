"""OCR line fixtures shaped like real engine output on backend/sample_docs (all mock data)."""
from pathlib import Path

from app.documents.ocr import OcrLine, OcrResult

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_docs"


def sample(name: str) -> bytes:
    return (SAMPLE_DIR / name).read_bytes()


def L(text: str, box: tuple[int, int, int, int], conf: float = 0.99) -> OcrLine:  # noqa: N802
    return OcrLine(text=text, confidence=conf, box=box)


def death_certificate(name: str = "Mohd. Aslam", date_text: str = "14.08.2026", conf: float = 0.99) -> OcrResult:
    """Azure-style: one line per label/value, out of reading order, watermark fragments mixed in."""
    return OcrResult("azure-prebuilt-read", [
        L("DEATH CERTIFICATE (MOCK)", (274, 92, 833, 134)),
        L("Union Council", (53, 143, 132, 156)),
        L("UC-12 Gulshan (mock)", (53, 159, 303, 186)),
        L("Name of Deceased", (52, 214, 177, 230)),
        L(name, (53, 235, 221, 261), conf),
        L("SPECIMES0412", (682, 132, 1066, 398), 0.4),
        L("90000-0000001-1", (52, 356, 237, 379)),
        L("Date of Death", (50, 402, 142, 418)),
        L(date_text, (53, 424, 188, 448), conf),
        L("Informant", (52, 677, 113, 693)),
        L("Zainab Bibi (Wife) CNIC 90000-0000002-2", (50, 695, 518, 722)),
        L("Reg. No. DC-UC12-2026-0412", (760, 161, 1057, 185)),
        L("Deceased CNIC", (52, 339, 145, 353)),
    ])


def cnic_front_tesseract() -> OcrResult:
    """Tesseract-style: columns merged into one line, labels garbled by the watermark."""
    return OcrResult("tesseract", [
        L("MOCK / SPECIMEN - NOT A REAL DOCUMENT - SAHARA PROTOTYPE", (37, 26, 975, 46), 0.93),
        L("Name", (41, 113, 82, 125), 0.96),
        L("ZAINAB BIBI", (40, 137, 219, 159), 0.93),
        L("Father / Husband Name", (42, 203, 210, 215), 0.93),
        L("GHULAM RASOOL", (41, 227, 308, 249), 0.9),
        L("Identity Number Date ot Birth", (42, 383, 502, 397), 0.59),
        L("90000-0000002-2 01.06.1962 Pe ai", (41, 397, 942, 435), 0.76),
    ])


def frc_azure() -> OcrResult:
    return OcrResult("azure-prebuilt-read", [
        L("FAMILY REGISTRATION CERTIFICATE (MOCK)", (117, 92, 989, 134)),
        L("No. MOCK-FRC-1001", (900, 175, 1180, 195)),
        L("Zainab Bibi CNIC 90000-0000002-2", (51, 258, 446, 281)),
        L("Muhammad Aslam", (106, 422, 263, 440)),
        L("90000-0000002-3", (579, 547, 730, 564)),
    ])


def nikah_azure_label_hidden() -> OcrResult:
    return OcrResult("azure-prebuilt-read", [
        L("2", (52, 265, 65, 283)),
        L("Muhammad Aslam s/o Ghulam Nabi, Karachi", (499, 263, 940, 286)),
        L("Bride, father, residence", (133, 398, 337, 419)),
        L("Zainab Bibi d/o Ghulam Rasool, Karachi", (499, 398, 900, 420)),
    ])
