"""OCR adapter: Azure Document Intelligence (prebuilt-read) when configured, else Tesseract.

Both engines return the same OcrResult (lines with a 0-1 confidence and a box), so the
field parser does not care which one ran. If neither works, OcrUnavailable is raised
and the pipeline says "an officer will read this document" instead of guessing.
Keys are never logged or put in error messages.
"""
import io
import logging
import time
from dataclasses import asdict, dataclass, field

import httpx
from PIL import Image

from app.core.config import Settings, get_settings

log = logging.getLogger("sahara.ocr")

AZURE_API_VERSION = "2024-11-30"
AZURE_MODEL = "prebuilt-read"
POLL_INTERVAL_SECONDS = 0.8
SUBMIT_RETRIES = 2  # extra attempts on 429/5xx or network error
TESSERACT_LANG = "eng"  # the fields we read (CNIC, dates, numbers, Latin names) are printed in English


class OcrUnavailable(Exception):
    """No OCR engine could read the image. Callers fall back to "officer reads it"."""


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float  # 0-1
    box: tuple[int, int, int, int]  # x0, y0, x1, y1 in pixels of the analysed image


@dataclass(frozen=True)
class OcrResult:
    engine: str  # azure-prebuilt-read | tesseract
    lines: list[OcrLine] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    def to_dict(self) -> dict:
        return {"engine": self.engine, "lines": [asdict(line) for line in self.lines]}


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _polygon_box(polygon: list[float]) -> tuple[int, int, int, int]:
    xs, ys = polygon[0::2], polygon[1::2]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def _line_confidence(line: dict, words: list[dict]) -> float:
    spans = line.get("spans") or []
    inside = [
        w.get("confidence", 0.0) for w in words
        if any(s["offset"] <= w["span"]["offset"] < s["offset"] + s["length"] for s in spans)
    ]
    return round(sum(inside) / len(inside), 3) if inside else 0.5


def parse_azure_result(payload: dict) -> OcrResult:
    lines: list[OcrLine] = []
    for page in payload.get("analyzeResult", {}).get("pages", []):
        words = page.get("words", [])
        for line in page.get("lines", []):
            polygon = line.get("polygon") or [0, 0, 0, 0]
            lines.append(OcrLine(text=line.get("content", ""), confidence=_line_confidence(line, words), box=_polygon_box(polygon)))
    return OcrResult(engine="azure-prebuilt-read", lines=lines)


class AzureReadEngine:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None, sleep=time.sleep):
        self._settings = settings
        self._client = httpx.Client(timeout=settings.azure_timeout_seconds, transport=transport)
        self._sleep = sleep

    def _headers(self) -> dict:
        return {"Ocp-Apim-Subscription-Key": self._settings.azure_docintel_key or ""}

    def _submit(self, data: bytes) -> str:
        endpoint = (self._settings.azure_docintel_endpoint or "").rstrip("/")
        url = f"{endpoint}/documentintelligence/documentModels/{AZURE_MODEL}:analyze?api-version={AZURE_API_VERSION}"
        last = "no attempt"
        for attempt in range(SUBMIT_RETRIES + 1):
            try:
                response = self._client.post(url, content=data, headers={**self._headers(), "Content-Type": "application/octet-stream"})
            except httpx.HTTPError as exc:
                last = type(exc).__name__
            else:
                if response.status_code == 202 and response.headers.get("Operation-Location"):
                    return response.headers["Operation-Location"]
                last = f"HTTP {response.status_code}"
                if response.status_code not in (429, 500, 502, 503, 504):
                    break
            self._sleep(POLL_INTERVAL_SECONDS * (attempt + 1))
        raise OcrUnavailable(f"Azure read submit failed: {last}")

    def read(self, img: Image.Image) -> OcrResult:
        operation = self._submit(_png_bytes(img))
        deadline = time.monotonic() + self._settings.azure_timeout_seconds
        while time.monotonic() < deadline:
            try:
                response = self._client.get(operation, headers=self._headers())
            except httpx.HTTPError as exc:
                raise OcrUnavailable(f"Azure read poll failed: {type(exc).__name__}") from exc
            if response.status_code != 200:
                raise OcrUnavailable(f"Azure read poll failed: HTTP {response.status_code}")
            payload = response.json()
            status = payload.get("status")
            if status == "succeeded":
                return parse_azure_result(payload)
            if status == "failed":
                raise OcrUnavailable("Azure read failed")
            self._sleep(POLL_INTERVAL_SECONDS)
        raise OcrUnavailable("Azure read timed out")

    def close(self) -> None:
        self._client.close()


class TesseractEngine:
    def read(self, img: Image.Image) -> OcrResult:
        try:
            import pytesseract
        except ImportError as exc:
            raise OcrUnavailable("pytesseract is not installed") from exc
        try:
            data = pytesseract.image_to_data(img.convert("L"), lang=TESSERACT_LANG, output_type=pytesseract.Output.DICT)
        except pytesseract.TesseractNotFoundError as exc:
            raise OcrUnavailable("Tesseract binary not found") from exc
        except (pytesseract.TesseractError, RuntimeError) as exc:
            raise OcrUnavailable(f"Tesseract failed: {type(exc).__name__}") from exc
        return OcrResult(engine="tesseract", lines=group_tesseract_words(data))


def group_tesseract_words(data: dict) -> list[OcrLine]:
    groups: dict[tuple, list[int]] = {}
    for i, word in enumerate(data.get("text", [])):
        if not str(word).strip() or float(data["conf"][i]) < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        groups.setdefault(key, []).append(i)
    lines = []
    for idxs in groups.values():
        x0 = min(data["left"][i] for i in idxs)
        y0 = min(data["top"][i] for i in idxs)
        x1 = max(data["left"][i] + data["width"][i] for i in idxs)
        y1 = max(data["top"][i] + data["height"][i] for i in idxs)
        conf = sum(float(data["conf"][i]) for i in idxs) / len(idxs) / 100
        lines.append(OcrLine(text=" ".join(str(data["text"][i]) for i in idxs), confidence=round(conf, 3), box=(x0, y0, x1, y1)))
    return sorted(lines, key=lambda line: (line.box[1], line.box[0]))


def run_ocr(img: Image.Image, settings: Settings | None = None, transport: httpx.BaseTransport | None = None) -> OcrResult:
    """Azure first (if configured), Tesseract second. Raises OcrUnavailable if both fail."""
    settings = settings or get_settings()
    if settings.docintel_configured:
        engine = AzureReadEngine(settings, transport=transport)
        try:
            return engine.read(img)
        except OcrUnavailable as exc:
            log.warning("Azure OCR unavailable, trying Tesseract: %s", type(exc).__name__)
        finally:
            engine.close()
    return TesseractEngine().read(img)
