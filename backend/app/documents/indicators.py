"""Turn check results into indicators: fixed bilingual text, a severity, the evidence.

Never a "fake" verdict and never one combined score. Severities, decided in code:
  high      -> the case goes to an officer (UNSURE, DOC_EDIT_RISK)
  mismatch  -> ask for proof (ASK_PROOF, DOC_MISMATCH): a record disagrees or the paper looks wrong
  unverified-> we could not read or check the paper: it never counts as a clean document
               and an officer reads it ("We could not read this paper")
  confirm   -> the citizen is asked to confirm a field we read with low confidence
  info      -> shown to the officer as context only; never changes the route

Jev's "text looks altered" answer only counts when it is a clear yes. On backend/sample_docs
Jev gave the edited death certificate 0.16-0.19 and the original 0.20-0.21 (and the clean
CNICs 0.45, undecided), so an undecided answer is shown to the officer but does not route.
"""
from dataclasses import asdict, dataclass, field

from app.documents.consistency import Check
from app.documents.fields import Field
from app.documents.forensics import ForensicReport
from app.documents.imaging import Quality
from app.documents.jev_checks import JevDocResult

SEVERITY_ORDER = ("high", "mismatch", "unverified", "confirm", "info")

# code: (severity, citizen_visible, english, urdu, what this cannot tell)
TEXTS: dict[str, tuple[str, bool, str, str, str]] = {
    "PHOTO_RETAKE": ("confirm", True,
        "The photo is not clear enough to read. Please take it again in good light, holding the phone still.",
        "تصویر صاف نہیں ہے۔ براہ کرم اچھی روشنی میں فون کو ساکت رکھ کر دوبارہ تصویر لیں۔",
        "A blurry photo says nothing about the paper itself."),
    "OCR_UNAVAILABLE": ("info", True,
        "We could not read this paper automatically. An officer will read it.",
        "ہم یہ کاغذ خود سے نہیں پڑھ سکے۔ ایک افسر اسے پڑھے گا۔",
        "The reading service was not available; nothing is wrong with the paper."),
    "FIELD_CONFIRM": ("confirm", True,
        "Please check the details we read from your paper and correct them if needed.",
        "براہ کرم کاغذ سے پڑھی گئی معلومات دیکھ لیں اور ضرورت ہو تو درست کریں۔",
        "Low reading confidence usually means a blurry or folded photo, not a problem with the paper."),
    "RECORD_MISMATCH": ("mismatch", True,
        "Some details on this paper do not match the government record. You may be asked for another copy.",
        "اس کاغذ کی کچھ معلومات سرکاری ریکارڈ سے نہیں ملتیں۔ آپ سے دوسری کاپی مانگی جا سکتی ہے۔",
        "Records can be wrong too (spelling, old data). An officer compares them."),
    "WRONG_DOCUMENT": ("mismatch", True,
        "This does not look like the paper we asked for. Please check and send the right paper.",
        "یہ وہ کاغذ نہیں لگتا جو مانگا گیا تھا۔ براہ کرم صحیح کاغذ بھیجیں۔",
        "The automatic check can be wrong on unusual layouts."),
    "STAMP_NOT_SEEN": ("mismatch", True,
        "We could not see an official stamp on this paper. Please send a photo where the stamp shows.",
        "ہمیں اس کاغذ پر سرکاری مہر نظر نہیں آئی۔ براہ کرم ایسی تصویر بھیجیں جس میں مہر نظر آئے۔",
        "The stamp may be cut off in the photo or very faint."),
    "STAMP_DUPLICATED": ("high", False,
        "Two stamp impressions on this paper are almost pixel-identical (possible copy-paste). Needs a second look.",
        "اس کاغذ پر دو مہریں تقریباً بالکل ایک جیسی ہیں۔ دوبارہ دیکھنے کی ضرورت ہے۔",
        "Some offices print a digital stamp twice; compare with the issuing office's records."),
    "TEXT_LOOKS_ALTERED": ("high", False,
        "The AI sensor says some text looks pasted on or painted over. Needs a second look.",
        "اے آئی سینسر کے مطابق کچھ تحریر چسپاں یا مٹا کر لکھی لگتی ہے۔ دوبارہ دیکھنے کی ضرورت ہے۔",
        "This is a probability from a sensor, not proof. Corrections by the issuing office look similar."),
    "JEV_UNDECIDED": ("info", False,
        "The AI sensor was not sure about this photo (type or edits). Shown for context only.",
        "اے آئی سینسر اس تصویر کے بارے میں پُریقین نہیں تھا۔ صرف معلومات کے لیے۔",
        "An undecided answer carries no evidence either way."),
    "SCREEN_PHOTO": ("info", False,
        "This looks like a photo or screenshot of a screen. The officer may ask for the paper.",
        "یہ اسکرین کی تصویر لگتی ہے۔ افسر اصل کاغذ مانگ سکتا ہے۔",
        "Forwarded copies are normal; this is context, not a problem."),
    "DOC_UNREADABLE": ("unverified", True,
        "We could not read this paper. An officer will read it.",
        "ہم یہ کاغذ نہیں پڑھ سکے۔ ایک افسر اسے پڑھے گا۔",
        "A blank, cut-off or unusual photo can hide the details; nothing is wrong with the person."),
    "CHECK_UNAVAILABLE": ("unverified", True,
        "We could not check this paper automatically. An officer will look at it.",
        "ہم یہ کاغذ خود سے جانچ نہیں سکے۔ ایک افسر اسے دیکھے گا۔",
        "The checking service did not answer properly; this says nothing about the paper."),
    "DOC_REUSED": ("high", False,
        "This paper, or a near-identical photo of it, was already sent on another claim for a different person. Needs a second look.",
        "یہ کاغذ یا اس کی تقریباً ایک جیسی تصویر کسی دوسرے شخص کے دعوے میں پہلے بھیجی جا چکی ہے۔ دوبارہ دیکھنے کی ضرورت ہے۔",
        "Families share papers and a helper may send the same photo twice; compare the two cases."),
    "DOC_SEEN_BEFORE": ("info", False,
        "The same paper was already sent on another case about the same person. Context only.",
        "یہی کاغذ اسی شخص کے کسی دوسرے کیس میں پہلے بھیجا جا چکا ہے۔ صرف معلومات کے لیے۔",
        "Co-sharers (two widows, children) send the same certificate lawfully."),
    "REPEATED_UPLOAD": ("info", False,
        "This kind of paper was uploaded several times on this case. Look at the earlier copies too.",
        "اس کیس میں یہ کاغذ کئی بار بھیجا گیا۔ پہلی کاپیاں بھی دیکھیں۔",
        "A blurry first photo is the usual reason; an earlier flag stays until an officer clears it."),
    "RESOLVED_BY_TYPING": ("info", False,
        "A detail that disagreed or was unclear now matches because the claimant typed it, not because it was read from the paper.",
        "ایک معلومات اب اس لیے ملتی ہے کہ درخواست گزار نے اسے خود لکھا، کاغذ سے نہیں پڑھی گئی۔",
        "Typing a correction is normal for a blurry photo; compare the typed value with the image."),
    "EDIT_SOFTWARE_TAG": ("info", False,
        "The photo file names editing software. Context only.",
        "تصویر کی فائل میں ایڈیٹنگ سافٹ ویئر کا نام ہے۔ صرف معلومات کے لیے۔",
        "Many phones and apps write this tag; missing or present metadata proves nothing."),
}
EDIT_SOFTWARE = ("photoshop", "gimp", "picsart", "snapseed", "canva", "lightroom", "pixlr")


@dataclass(frozen=True)
class Indicator:
    code: str
    severity: str
    citizen_visible: bool
    text_en: str
    text_ur: str
    cannot_tell_en: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def make(code: str, **evidence) -> Indicator:
    severity, visible, en, ur, cannot = TEXTS[code]
    return Indicator(code, severity, visible, en, ur, cannot, evidence)


def from_quality(quality: Quality) -> list[Indicator]:
    return [] if quality.ok else [make("PHOTO_RETAKE", problems=list(quality.problems))]


def from_fields(fields: dict[str, Field]) -> list[Indicator]:
    unsure = sorted(k for k, f in fields.items() if f.needs_confirmation)
    return [make("FIELD_CONFIRM", fields=unsure)] if unsure else []


def from_checks(checks: list[Check]) -> list[Indicator]:
    out = []
    mismatched = [c.to_dict() for c in checks if c.status == "mismatch"]
    if mismatched:
        out.append(make("RECORD_MISMATCH", checks=mismatched))
    unclear = sorted(c.field for c in checks if c.status == "unclear")
    if unclear:
        out.append(make("FIELD_CONFIRM", fields=unclear, reason="disagrees with record at low reading confidence"))
    return out


def from_forensics(report: ForensicReport) -> list[Indicator]:
    out = []
    if report.copy_move.found:
        out.append(make("STAMP_DUPLICATED", score=report.copy_move.score, regions=report.copy_move.regions,
                        orb_matches=report.copy_move.orb_matches))
    if report.looks_like_screenshot:
        out.append(make("SCREEN_PHOTO", source="layout"))
    software = report.exif.get("software", "")
    if any(name in software.lower() for name in EDIT_SOFTWARE):
        out.append(make("EDIT_SOFTWARE_TAG", software=software))
    return out


def from_jev(result: JevDocResult) -> list[Indicator]:
    if result.status == "unavailable":  # configured but down or junk: fail closed, never "clean"
        return [make("CHECK_UNAVAILABLE", sensor="jev", note=result.note[:120])]
    if result.status != "ok":
        return []
    a = result.answers
    band = {name: v["band"] for name, v in a.items()}
    out = []
    if band.get("text_altered") == "yes":
        out.append(make("TEXT_LOOKS_ALTERED", p=a["text_altered"]["p"], box=result.boxes.get("text_altered_box")))
    if band.get("right_type") == "no":
        out.append(make("WRONG_DOCUMENT", p=a["right_type"]["p"]))
    if band.get("stamp_present") == "no":
        out.append(make("STAMP_NOT_SEEN", p=a["stamp_present"]["p"]))
    if band.get("screen_photo") == "yes":
        out.append(make("SCREEN_PHOTO", source="jev", p=a["screen_photo"]["p"]))
    undecided = sorted(n for n in ("right_type", "text_altered", "stamp_present") if band.get(n) == "undecided")
    if undecided:
        out.append(make("JEV_UNDECIDED", questions=undecided))
    return out


def dedupe(indicators: list[Indicator]) -> list[Indicator]:
    """One indicator per code (merge evidence), most severe first."""
    merged: dict[str, Indicator] = {}
    for ind in indicators:
        if ind.code in merged:
            old = merged[ind.code]
            merged[ind.code] = Indicator(old.code, old.severity, old.citizen_visible, old.text_en, old.text_ur,
                                         old.cannot_tell_en, {**old.evidence, **{f"also_{k}": v for k, v in ind.evidence.items()}})
        else:
            merged[ind.code] = ind
    return sorted(merged.values(), key=lambda i: SEVERITY_ORDER.index(i.severity))


def risk_level(indicators: list[Indicator]) -> str:
    severities = {i.severity for i in indicators}
    if "high" in severities:
        return "high"
    if "mismatch" in severities:
        return "mismatch"
    if "unverified" in severities:
        return "unverified"
    return "confirm" if "confirm" in severities else "low"


# The fields without which a paper of this kind says nothing we can check.
REQUIRED_FIELDS = {
    "claimant_cnic": ("cnic",),
    "deceased_cnic": ("cnic",),
    "death_certificate": ("name_of_deceased", "date_of_death"),
    "frc": ("member_cnics",),
    "nikah_nama": ("groom_name", "bride_name"),
}


def from_required(kind: str, fields: dict[str, Field]) -> list[Indicator]:
    missing = [k for k in REQUIRED_FIELDS.get(kind, ()) if k not in fields]
    return [make("DOC_UNREADABLE", missing_fields=missing)] if missing else []
