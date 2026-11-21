"""Jev image questions on a document photo (question set B). Jev is a sensor; code decides.

Small observable yes/no questions only, never "is this fake?". Each Box is paired with
its presence Noul (a Box always returns a box). Bands: > 0.7 yes, < 0.3 no, between =
undecided. If Jev is not configured, times out or errors, the checks are skipped and
the other indicators still stand; nothing here can approve anything.
Logged: model, latency, every probability, question-set version, image SHA-256 (never the image).
"""
import base64
import uuid
from dataclasses import asdict, dataclass, field

from PIL import Image

from app.core.config import Settings, get_settings
from app.decision.jev_client import Band, JevClient, JevUnavailable, box, noul, noul_band
from app.documents.imaging import MIN_SIDE, jpeg_bytes

QUESTION_SET = "B-documents-v1"
DOC_DESCRIPTIONS = {
    "claimant_cnic": "a Pakistani national identity card (CNIC), front or back",
    "deceased_cnic": "a Pakistani national identity card (CNIC), front or back",
    "death_certificate": "a death certificate",
    "frc": "a family registration certificate listing family members",
    "nikah_nama": "a nikah nama (marriage registration form)",
}
CERTIFICATES = {"death_certificate", "frc", "nikah_nama"}  # these carry an official stamp
BOX_MIN_CONFIDENCE = 0.6  # TypeSafe Box docs example value; boxes are evidence for the officer only


@dataclass(frozen=True)
class JevDocResult:
    status: str  # ok | skipped | unavailable
    model: str | None = None
    latency_ms: int | None = None
    question_set: str = QUESTION_SET
    answers: dict = field(default_factory=dict)  # name -> {"p": float, "band": str}
    boxes: dict = field(default_factory=dict)  # name -> [x0, y0, x1, y1] fractions, only when its Noul said yes
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _questions(kind: str, ref: str) -> dict:
    doc = DOC_DESCRIPTIONS[kind]
    questions = {
        "right_type": noul(f"Is the document in image {ref} {doc}?"),
        "text_altered": noul(
            f"In image {ref}, does any printed or handwritten text look pasted on, painted over, "
            "or in a different font or background from the text around it?"
        ),
        "text_altered_box": box(f"In image {ref}, where is the text that looks pasted on or painted over?"),
        "screen_photo": noul(f"Is image {ref} a photo of a screen (monitor or phone display) rather than of paper?"),
    }
    if kind in CERTIFICATES:
        questions["stamp_present"] = noul(f"Is there an official stamp or seal on the document in image {ref}?")
        questions["stamp_box"] = box(f"In image {ref}, where is the official stamp or seal?")
    return questions


def _sendable(img: Image.Image) -> Image.Image | None:
    """Jev needs 280-1568 px per side; the loader already capped the long side."""
    return img if min(img.size) >= MIN_SIDE else None


def _box(answer: dict) -> list[float] | None:
    b = answer.get("box") or {}
    conf = answer.get("confidence")
    if conf is not None and conf < BOX_MIN_CONFIDENCE:
        return None
    try:
        return [round(float(b[k]), 3) for k in ("left", "top", "right", "bottom")]
    except (KeyError, TypeError, ValueError):
        return None


def ask_document_questions(kind: str, img: Image.Image, settings: Settings | None = None, client: JevClient | None = None) -> JevDocResult:
    settings = settings or get_settings()
    if client is None and not settings.typesafe_api_key:
        return JevDocResult(status="skipped", note="Jev not configured")
    sendable = _sendable(img)
    if sendable is None:
        return JevDocResult(status="skipped", note="image smaller than Jev's 280 px minimum")
    ref = f"img-{uuid.uuid4()}"  # fresh reference per image per request (TypeSafe guidance)
    assets = {ref: {"type": "image", "format": "jpeg", "data_base64": base64.b64encode(jpeg_bytes(sendable)).decode()}}
    jev = client or JevClient(settings)
    try:
        result = jev.ask(f"Document photo: {ref}", _questions(kind, ref), assets=assets, timeout=settings.jev_image_timeout_seconds)
    except JevUnavailable as exc:
        return JevDocResult(status="unavailable", note=str(exc))
    finally:
        if client is None:
            jev.close()
    answers, boxes = {}, {}
    for name, answer in result.answers.items():
        if "noul" in answer:
            p = float(answer["noul"])
            answers[name] = {"p": round(p, 4), "band": noul_band(p).value}
    for name, presence in (("text_altered_box", "text_altered"), ("stamp_box", "stamp_present")):
        if name in result.answers and answers.get(presence, {}).get("band") == Band.YES.value:
            found = _box(result.answers[name])
            if found:
                boxes[name] = found
    return JevDocResult(status="ok", model=result.model, latency_ms=result.latency_ms, answers=answers, boxes=boxes)
