"""Sensor cascade on a document photo: Jev + deterministic checks first, the second sensor only when needed.

Same rules as Scam Shield (app/ai/cascade.py). The second sensor sees the same photo and
answers the same small questions as Jev's question set B (never "is this fake?").
Deterministic hints: a pasted stamp found by copy-move says "text/marks altered: yes";
the paper's key number read by OCR says "right document type: yes"; coloured stamp-ink
blobs say "stamp present: yes". Absence of a hint is no evidence.

The fused answers replace Jev's in the indicators. A disagreement becomes the
SENSORS_DISAGREE indicator (severity high: an officer looks at the paper). The second
sensor's note is stored for officers only, labelled "AI-written, advisory".
"""
from dataclasses import asdict, dataclass, field

from PIL import Image

from app.ai import cascade
from app.ai.second_sensor import SecondSensor, SensorAnswers
from app.decision.jev_client import noul_band
from app.documents.fields import Field
from app.documents.forensics import ForensicReport
from app.documents.imaging import jpeg_bytes
from app.documents.jev_checks import CERTIFICATES, DOC_DESCRIPTIONS, JevDocResult

KEY_FIELD = {"claimant_cnic": "cnic", "deceased_cnic": "cnic", "death_certificate": "certificate_no", "frc": "frc_number"}


def question_text(kind: str) -> dict[str, str]:
    questions = {
        "right_type": f"Is the document in the image {DOC_DESCRIPTIONS[kind]}?",
        "text_altered": "Does any printed or handwritten text in the image look pasted on, painted over, "
                        "or in a different font or background from the text around it?",
        "screen_photo": "Is the image a photo of a screen (monitor or phone display) rather than of paper?",
    }
    if kind in CERTIFICATES:
        questions["stamp_present"] = "Is there an official stamp or seal on the document in the image?"
    return questions


def decisive(kind: str) -> list[str]:
    return ["right_type", "text_altered", *(["stamp_present"] if kind in CERTIFICATES else [])]


def hints(kind: str, fields: dict[str, Field], report: ForensicReport) -> dict[str, bool | None]:
    key = KEY_FIELD.get(kind)
    return {
        "text_altered": True if report.copy_move.found else None,
        "right_type": True if key and key in fields else None,
        "stamp_present": True if kind in CERTIFICATES and report.copy_move.stamp_candidates > 0 else None,
    }


@dataclass(frozen=True)
class DocCascade:
    jev: JevDocResult  # fused answers in Jev's shape, fed to indicators.from_jev
    fused: cascade.Fused | None
    second: SensorAnswers | None
    sensors: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        return {"cascade": self.fused.to_dict() if self.fused else None,
                "second_sensor": self.second.to_dict() if self.second else None, "sensors": self.sensors}


def _jev_probabilities(jev: JevDocResult) -> dict[str, float] | None:
    return {name: a["p"] for name, a in jev.answers.items()} if jev.status == "ok" else None


def run(kind: str, img: Image.Image, fields: dict[str, Field], report: ForensicReport, jev: JevDocResult,
        sensor: SecondSensor | None = None) -> DocCascade:
    sensor = sensor or SecondSensor()
    sensors = [{"name": "deterministic", "status": "ok", "cost_usd": 0.0},
               {"name": "jev", "status": jev.status, "model": jev.model, "latency_ms": jev.latency_ms}]
    jev_p = _jev_probabilities(jev)
    found_hints = hints(kind, fields, report)
    fired = cascade.triggers(jev_p, found_hints, decisive(kind))
    if not sensor.configured or not fired:
        if sensor.configured:
            sensors.append({"name": "second_sensor", "status": "not_needed"})
        fused = cascade.fuse(jev_p, found_hints, None, decisive(kind)) if jev_p is not None else None
        return DocCascade(jev, fused, None, sensors)
    second = sensor.ask(question_text(kind), image_jpeg=jpeg_bytes(img))
    sensors.append({"name": "second_sensor", "status": second.status, "model": second.model, "latency_ms": second.latency_ms,
                    "cost_usd": second.cost_usd})
    if second.status != "ok":  # nothing to fuse: Jev's answers stand unchanged
        fused = cascade.fuse(jev_p, found_hints, None, decisive(kind)) if jev_p is not None else None
        return DocCascade(jev, fused, second, sensors)
    fused = cascade.fuse(jev_p, found_hints, second, decisive(kind))
    answers = {name: {"p": round(p, 4), "band": noul_band(p).value} for name, p in fused.probabilities.items()}
    merged = JevDocResult(**{**asdict(jev), "status": "ok", "answers": answers, "model": jev.model or second.model,
                             "note": "answers fused with the second sensor"})
    return DocCascade(merged, fused, second, sensors)
