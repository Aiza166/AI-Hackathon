"""Read fields from OCR lines, per document type.

OCR output is noisy (Tesseract merges columns into one line, watermarks break labels),
so each field is found by label proximity first (the label line and the 1-2 lines
under it) and by pattern second. Every field carries a 0-1 confidence; anything below
CONFIRM_BELOW is shown to the citizen to confirm or correct before it is trusted.
"""
import re
from dataclasses import asdict, dataclass
from datetime import date

from app.documents.ocr import OcrLine, OcrResult

CONFIRM_BELOW = 0.85
LABEL_FACTOR = 1.0  # value found on or under its label
PATTERN_FACTOR = 0.6  # value found by pattern only (no label seen)
ROW_FACTOR = 0.8  # value found next to another known value on the same row (label hidden)
LOOKAHEAD_LINES = 2
TALL_LINE_FACTOR = 2.5

CNIC_RE = re.compile(r"(?<!\d)(\d{5})[-\s.]?(\d{7})[-\s.]?(\d)(?!\d)")
_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
DATE_NUM_RE = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})(?!\d)")
DATE_MON_RE = re.compile(r"(?<!\d)(\d{1,2})[\s./-]*([A-Za-z]{3})[a-z]*[\s.,/-]*(\d{4})(?!\d)")
DOC_NUMBER_RE = re.compile(r"\b([A-Z]{2,5}(?:-[A-Z0-9]{1,8}){1,5})\b")
RELATION_MARKERS = re.compile(r"\b(s/o|d/o|w/o|son of|daughter of|wife of)\b.*$", re.IGNORECASE)

DOC_KINDS = ("claimant_cnic", "deceased_cnic", "death_certificate", "frc", "nikah_nama")


@dataclass(frozen=True)
class Field:
    value: str
    confidence: float
    method: str  # label | row | pattern | user

    @property
    def needs_confirmation(self) -> bool:
        return self.confidence < CONFIRM_BELOW

    def to_dict(self) -> dict:
        return {**asdict(self), "needs_confirmation": self.needs_confirmation}


def normalise_cnic(text: str) -> str | None:
    match = CNIC_RE.search(text)
    return "".join(match.groups()) if match else None


def all_cnics(text: str) -> list[str]:
    return list(dict.fromkeys("".join(m.groups()) for m in CNIC_RE.finditer(text)))


def _year(raw: str) -> int:
    year = int(raw)
    if len(raw) == 2:
        year += 1900 if year > 30 else 2000
    return year


def parse_date(text: str) -> date | None:
    """dd.mm.yyyy, dd/mm/yyyy, dd-mm-yyyy (2- or 4-digit year) and dd-Mon-yyyy. Day first, always."""
    for match in DATE_NUM_RE.finditer(text):
        day, month, year = int(match.group(1)), int(match.group(2)), _year(match.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            continue
    for match in DATE_MON_RE.finditer(text):
        month = _MONTHS.get(match.group(2).lower())
        if month:
            try:
                return date(int(match.group(3)), month, int(match.group(1)))
            except ValueError:
                continue
    return None


def clean_name(text: str) -> str:
    text = RELATION_MARKERS.sub("", text)
    text = re.split(r"\(|\bCNIC\b|\d", text)[0]
    text = re.sub(r"[^A-Za-z\s.']", " ", text).replace(".", ". ")
    return re.sub(r"\s+", " ", text).strip(" .'")


def _find_label(lines: list[OcrLine], pattern: str) -> int | None:
    regex = re.compile(pattern, re.IGNORECASE)
    return next((i for i, line in enumerate(lines) if regex.search(line.text)), None)


def _after_label(line: OcrLine, pattern: str) -> str:
    match = re.search(pattern, line.text, re.IGNORECASE)
    return line.text[match.end():] if match else ""


def _height(line: OcrLine) -> int:
    return max(1, line.box[3] - line.box[1])


def _below(lines: list[OcrLine], anchor: OcrLine) -> list[OcrLine]:
    """Lines just under the anchor that overlap it horizontally, nearest first."""
    x0, y0, x1, y1 = anchor.box
    reach = y1 + int(3 * _height(anchor))
    found = [
        line for line in lines
        if line is not anchor and y0 < line.box[1] <= reach and line.box[0] < x1 + 20 and line.box[2] > x0 - 20
    ]
    return sorted(found, key=lambda line: (line.box[1], abs(line.box[0] - x0)))


def _right_of(lines: list[OcrLine], anchor: OcrLine) -> list[OcrLine]:
    """Lines on the same row to the right of the anchor (table layouts), nearest first."""
    x0, y0, x1, y1 = anchor.box
    mid, half = (y0 + y1) / 2, _height(anchor) * 0.75
    found = [
        line for line in lines
        if line is not anchor and line.box[0] >= x1 - 5 and abs((line.box[1] + line.box[3]) / 2 - mid) <= half
    ]
    return sorted(found, key=lambda line: line.box[0])


def _near(lines: list[OcrLine], label: str, extract, same_line: bool = True) -> Field | None:
    """Look after the label on its own line, then to its right, then under it, then at the next lines."""
    idx = _find_label(lines, label)
    if idx is None:
        return None
    anchor = lines[idx]
    candidates = [(_after_label(anchor, label), anchor.confidence)] if same_line else []
    neighbours = _right_of(lines, anchor) + _below(lines, anchor) + lines[idx + 1: idx + 1 + LOOKAHEAD_LINES]
    candidates += [(line.text, line.confidence) for line in neighbours]
    for text, conf in candidates:
        value = extract(text)
        if value:
            return Field(value=value, confidence=round(conf * LABEL_FACTOR, 3), method="label")
    return None


def _beside(lines: list[OcrLine], anchor_extract, extract, factor: float) -> Field | None:
    """A value printed on the same row as another value (e.g. the DOB next to the CNIC number)."""
    for line in lines:
        if anchor_extract(line.text):
            rest = extract(CNIC_RE.sub(" ", line.text))
            if rest:
                return Field(value=rest, confidence=round(line.confidence * factor, 3), method="row")
            for other in _right_of(lines, line):
                value = extract(other.text)
                if value:
                    return Field(value=value, confidence=round(other.confidence * factor, 3), method="row")
    return None


def _by_pattern(lines: list[OcrLine], extract) -> Field | None:
    for line in lines:
        value = extract(line.text)
        if value:
            return Field(value=value, confidence=round(line.confidence * PATTERN_FACTOR, 3), method="pattern")
    return None


def _date_text(text: str) -> str | None:
    found = parse_date(text)
    return found.isoformat() if found else None


def _name_text(text: str) -> str | None:
    name = clean_name(text)
    return name if len(name.replace(" ", "")) >= 3 and not re.search(r"\b(name|husband|father)\b", name, re.I) else None


def _doc_number(text: str) -> str | None:
    match = DOC_NUMBER_RE.search(text.upper())
    return match.group(1) if match else None


def _cnic_field(lines: list[OcrLine], label: str) -> Field | None:
    return _near(lines, label, normalise_cnic) or _by_pattern(lines, normalise_cnic)


def _cnic_card(lines: list[OcrLine]) -> dict[str, Field]:
    found = {
        "cnic": _cnic_field(lines, r"identity\s*n"),
        "name": _near(lines, r"^\s*name\s*$", _name_text, same_line=False),
        "father_or_husband_name": _near(lines, r"(father|husband)", _name_text, same_line=False),
        # Watermarks often hide "Date of"; "Birth" alone is enough. Skip the CNIC on the same line.
        "date_of_birth": _near(lines, r"birth", lambda t: _date_text(CNIC_RE.sub(" ", t)))
        or _beside(lines, normalise_cnic, _date_text, ROW_FACTOR),
    }
    return {k: v for k, v in found.items() if v}


def _not_informant(lines: list[OcrLine]) -> list[OcrLine]:
    """The informant's CNIC is also printed on a death certificate: never take it for the deceased's."""
    return [line for line in lines if not re.search(r"informant|wife|husband|son|daughter", line.text, re.IGNORECASE)]


def _death_certificate(lines: list[OcrLine]) -> dict[str, Field]:
    found = {
        "name_of_deceased": _near(lines, r"name\s*of\s*deceased", _name_text),
        "deceased_cnic": _near(lines, r"deceased\s*c", normalise_cnic) or _by_pattern(_not_informant(lines), normalise_cnic),
        "date_of_death": _near(lines, r"date\s*of\s*death", _date_text),
        "certificate_no": _near(lines, r"(reg(istration)?|certificate)\.?\s*no\.?", _doc_number),
    }
    return {k: v for k, v in found.items() if v}


def _frc(lines: list[OcrLine]) -> dict[str, Field]:
    text = "\n".join(line.text for line in lines)
    found = {"frc_number": _near(lines, r"\bno\.", _doc_number) or _by_pattern(lines, lambda t: _doc_number(t) if "FR" in t.upper() else None)}
    cnics = all_cnics(text)
    if cnics:
        conf = min(line.confidence for line in lines if CNIC_RE.search(line.text))
        found["member_cnics"] = Field(value=",".join(cnics), confidence=round(conf, 3), method="pattern")
    return {k: v for k, v in found.items() if v}


def _nikah_name(lines: list[OcrLine], who: str, marker: str) -> Field | None:
    labelled = re.compile(rf"{who}.*?residence\s*(.+?)\s*{marker}", re.IGNORECASE)
    bare = re.compile(rf"^\W*(?:\d+\s+)?(.+?)\s*{marker}", re.IGNORECASE)  # label hidden: "Name s/o Father"
    for regex, factor, method in ((labelled, LABEL_FACTOR, "label"), (bare, ROW_FACTOR, "row")):
        for line in lines:
            match = regex.search(line.text.replace(",", " "))
            name = _name_text(match.group(1)) if match else None
            if name:
                return Field(value=name, confidence=round(line.confidence * factor, 3), method=method)
    return None


def _nikah_nama(lines: list[OcrLine]) -> dict[str, Field]:
    found = {
        "groom_name": _nikah_name(lines, r"groom", r"s\s*/\s*o"),
        "bride_name": _nikah_name(lines, r"bride", r"d\s*/\s*o"),
        "date_of_marriage": _near(lines, r"date\W*of\W*marriage", _date_text),
    }
    return {k: v for k, v in found.items() if v}


_PARSERS = {
    "claimant_cnic": _cnic_card,
    "deceased_cnic": _cnic_card,
    "death_certificate": _death_certificate,
    "frc": _frc,
    "nikah_nama": _nikah_nama,
}


def drop_overlay_lines(lines: list[OcrLine]) -> list[OcrLine]:
    """Remove lines far taller than normal print: rotated watermark or stamp fragments, not fields."""
    if not lines:
        return []
    heights = sorted(_height(line) for line in lines)
    limit = heights[len(heights) // 2] * TALL_LINE_FACTOR
    return [line for line in lines if _height(line) <= limit]


def extract_fields(kind: str, ocr: OcrResult) -> dict[str, Field]:
    if kind not in _PARSERS:
        raise ValueError(f"unknown document kind {kind}")
    return _PARSERS[kind](drop_overlay_lines(list(ocr.lines)))
