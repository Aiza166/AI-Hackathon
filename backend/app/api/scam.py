"""Scam Shield and Scam Map."""
import hashlib
import logging
from collections import Counter
from datetime import timedelta
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal, require_roles, require_scope
from app.api import speech as speech_api
from app.core.envelope import fail, ok
from app.core.ratelimit import client_ip, limiter
from app.db import get_db
from app.models.platform import utcnow
from app.models.scam import ScamCheck
from app.documents.imaging import BadImage, load, sniff_format
from app.documents.ocr import OcrUnavailable, run_ocr
from app.scam import audio, screenshot
from app.schemas.contracts import Role, ScamChannel, ScamCheckIn
from app.services import scam as svc

log = logging.getLogger("sahara.scam")
router = APIRouter(prefix="/api/v1", tags=["scam shield"])
CHECKERS = (Role.CITIZEN, Role.HELPER, Role.OFFICER)
STAFF_ROLES = {Role.OFFICER.value, Role.ADMIN.value, Role.AUDITOR.value}
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")
AUDIO_TYPES = ("audio/", "video/webm", "video/mp4", "video/3gpp")  # recorders label audio-only files as video/* too
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_AUDIO_BYTES = 5 * 1024 * 1024
MAX_TEXT = 2000


def _per_user(request: Request) -> str:
    """Upload limits per signed-in user (token), so a forged forwarding header cannot reset them."""
    auth = request.headers.get("authorization", "")
    return "user:" + hashlib.sha256(auth.encode()).hexdigest()[:32] if auth else client_ip(request)
# Real-world places to report a scam, shown after a scam verdict (real help, not part of the mock).
# Source and confidence for each: docs/research/round2.md section 4. 1799 replaced FIA's 1991.
REPORT_ROUTES = [
    {"id": "nccia_call", "kind": "call", "name": "Call NCCIA cybercrime helpline 1799", "name_ur": "سائبر کرائم ہیلپ لائن 1799 پر کال کریں",
     "url": "tel:1799", "confidence": "confirmed", "source": "https://www.nccia.gov.pk/"},
    {"id": "nccia_portal", "kind": "link", "name": "NCCIA complaint portal (needs your CNIC)", "name_ur": "این سی سی آئی اے کو آن لائن شکایت",
     "url": "https://complaint.nccia.gov.pk/", "confidence": "confirmed", "source": "https://complaint.nccia.gov.pk/"},
    {"id": "pta_portal", "kind": "link", "name": "Report the number to PTA (Reporting Fraudulent Call/SMS)", "name_ur": "نمبر کی شکایت پی ٹی اے کو کریں",
     "url": "https://complaint.pta.gov.pk/", "confidence": "confirmed", "source": "https://pta.gov.pk/category/consumer-complaints"},
    {"id": "pta_call", "kind": "call", "name": "PTA helpline 0800-55055", "name_ur": "پی ٹی اے ہیلپ لائن 0800-55055",
     "url": "tel:080055055", "confidence": "confirmed", "source": "https://complaint.pta.gov.pk/UserLogIn.aspx"},
    {"id": "pta_9000", "kind": "sms", "name": "Forward the spam SMS to 9000 (per PTA, 2023)", "name_ur": "جعلی پیغام 9000 پر بھیجیں",
     "url": "sms:9000", "confidence": "as of 2023", "source": "https://www.pta.gov.pk/category/pta-short-codes-obnoxious-com-420-unsolicit-comdncr-3627-and-spam-reporting-9000-568848153-2023-06-01"},
    {"id": "bank", "kind": "info", "name": "Shared a code? Call your bank now on the number printed on your card", "name_ur": "اگر کوڈ بتا دیا ہے تو ابھی اپنے بینک کو کارڈ پر لکھے نمبر پر کال کریں",
     "url": None, "confidence": "general advice", "source": None},
    {"id": "sunwai", "kind": "link", "name": "Bank did not help? Complain to SBP Sunwai", "name_ur": "بینک نے مدد نہیں کی تو اسٹیٹ بینک سنوائی پر شکایت",
     "url": "https://sunwai.sbp.org.pk/", "confidence": "confirmed", "source": "https://sunwai.sbp.org.pk/about-us.html"},
]
BISP_ROUTE = {"id": "bisp", "kind": "call", "name": "BISP helpline 0800-26477 (official SMS sender is only 8171)", "name_ur": "بی آئی ایس پی ہیلپ لائن 0800-26477",
              "url": "tel:080026477", "confidence": "confirmed", "source": "https://bisp.gov.pk/NewsDetail/M2MzZDg0ZjctYjBkMS00YzQ1LTkwMjQtMmVhZWFiZDgyZmI0"}
BISP_WORDS = ("bisp", "benazir", "8171", "بینظیر", "احساس", "ehsaas")


def report_routes(verdict: str, text: str, sender: str | None) -> list[dict]:
    """No routes for a genuine-looking message. The BISP line only when the message is about BISP."""
    if verdict == "LOOKS_GENUINE":
        return []
    haystack = f"{text} {sender or ''}".lower()
    return [*REPORT_ROUTES, *([BISP_ROUTE] if any(w in haystack for w in BISP_WORDS) else [])]


def _sensor_summary(sensors: list[dict]) -> list[dict]:
    keep = ("name", "status", "model", "latency_ms", "cost_usd")
    return [{k: s.get(k) for k in keep if k in s} for s in sensors]


def _run(db: Session, principal: Principal, body: ScamCheckIn, *, source: str = "text", extracted: dict | None = None) -> dict:
    result = svc.check(db, body.text, body.sender, body.on_call_with_unknown, principal.person_id, channel=body.channel.value)
    signals = {**result.signals, "source": source}
    db.add(ScamCheck(tenant_id=principal.tenant_id, text_hash=svc.text_hash(body.text), scam_type=result.scam_type,
                     area=body.area, signals=signals, model_id=result.model_id, verdict=result.verdict, score=result.score))
    audit.record(db, audit.AI, "SCAM_CHECKED", tenant_id=principal.tenant_id,
                 details={"verdict": result.verdict, "score": result.score, "model_id": result.model_id,
                          "fallback": result.signals["fallback"], "requested_by_role": principal.role,
                          "channel": body.channel.value, "source": source, "question_set": result.signals["question_set"],
                          "sensors": _sensor_summary(result.signals["sensors"]), "cascade": result.signals["cascade"],
                          "cost_usd": result.cost_usd, "latency_ms": result.latency_ms})
    db.commit()
    out = {
        "verdict": result.verdict, "confidence": result.score, "reasons": result.reasons, "reasons_ur": result.reasons_ur,
        "case_cross_check": result.case_cross_check, "case_cross_check_ur": result.case_cross_check_ur,
        "model_id": result.model_id, "channel": body.channel.value,
        "links": result.links, "report_routes": report_routes(result.verdict, body.text, body.sender),
    }
    if extracted is not None:
        out["extracted"] = extracted
    if principal.role in STAFF_ROLES:
        # Officers only: the second sensor's note is AI-written and advisory; citizens get fixed text only.
        out["officer_note"] = result.officer_note
        out["sensors"] = _sensor_summary(result.signals["sensors"])
        out["cascade"] = result.signals["cascade"]
    return out


@router.post("/scam/check")
@limiter.limit("20/minute")
def check(request: Request, body: ScamCheckIn,
          principal: Principal = Depends(require_roles(*CHECKERS)), db: Session = Depends(get_db)) -> dict:
    return ok(_run(db, principal, body))


def _read_upload(upload: UploadFile, allowed: tuple[str, ...], max_bytes: int, what: str) -> tuple[bytes, str]:
    kind = (upload.content_type or "").split(";")[0].strip().lower()
    if not kind.startswith(allowed):
        raise HTTPException(status_code=415, detail=f"Please send {what}")
    data = upload.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"The file is too large ({max_bytes // 1_000_000} MB at most)")
    if not data:
        raise HTTPException(status_code=422, detail="The file is empty")
    return data, kind


def _form_body(text: str, sender: str | None, on_call: bool | None, area: str | None, channel: ScamChannel) -> ScamCheckIn:
    try:
        return ScamCheckIn(text=text[:MAX_TEXT], sender=(sender or None), on_call_with_unknown=on_call, area=area or None,
                           channel=channel)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Some details are not valid") from exc


@router.post("/scam/check-image")
@limiter.limit("10/minute", key_func=_per_user)
def check_image(request: Request, file: UploadFile = File(...), sender: str | None = Form(default=None, max_length=40),
                on_call_with_unknown: bool | None = Form(default=None), area: str | None = Form(default=None, max_length=60),
                principal: Principal = Depends(require_roles(*CHECKERS)), db: Session = Depends(get_db)):
    """A screenshot of a chat or SMS: read it (Azure Document Intelligence, else Tesseract), then the same check.
    The image and the read text are not stored; only the usual fingerprint and signals are."""
    data, _ = _read_upload(file, IMAGE_TYPES, MAX_IMAGE_BYTES, "a JPEG, PNG or WebP screenshot")
    if sniff_format(data) is None:  # the bytes decide, not the declared type (load() also checks size and pixels)
        raise HTTPException(status_code=415, detail="Please send a JPEG, PNG or WebP screenshot")
    try:
        loaded = load(data)
    except BadImage as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        ocr = run_ocr(loaded.image)
    except OcrUnavailable:
        return fail(code="OCR_UNAVAILABLE", message="We could not read the picture. Please type or paste the message.", status=503)
    text, found_sender = screenshot.chat_text(ocr)
    if not text.strip():
        return fail(code="NO_TEXT_FOUND", message="We could not find words in the picture. Please type the message.", status=422)
    channel = ScamChannel.WHATSAPP if "whatsapp" in text.lower() else ScamChannel.SMS
    body = _form_body(text, sender or found_sender, on_call_with_unknown, area, channel)
    extracted = {"text": text, "sender_found": found_sender is not None, "ocr_engine": ocr.engine}
    return ok(_run(db, principal, body, source="screenshot", extracted=extracted))


@router.post("/scam/check-audio")
@limiter.limit("10/minute", key_func=_per_user)
def check_audio(request: Request, audio_file: UploadFile = File(..., alias="audio"),
                kind: Literal["voice_note", "call_recording"] = Form(default="voice_note"),
                lang: Literal["ur", "en"] = Form(default="ur"), sender: str | None = Form(default=None, max_length=40),
                on_call_with_unknown: bool | None = Form(default=None), area: str | None = Form(default=None, max_length=60),
                principal: Principal = Depends(require_roles(*CHECKERS)), db: Session = Depends(get_db)):
    """A voice note or call recording: Azure speech-to-text (server converts WebM/M4A/AMR to WAV), then the same check.
    The audio and the transcript are not stored."""
    settings = speech_api.get_settings()
    if not settings.speech_configured:
        return fail(code="STT_NOT_CONFIGURED", message="Listening is not set up on the server. Please type what was said.", status=503)
    data, content_type = _read_upload(audio_file, AUDIO_TYPES, MAX_AUDIO_BYTES, "a voice note or call recording")
    try:
        wav, simple = audio.prepare_for_stt(data, content_type)
    except audio.AudioUnsupported:
        return fail(code="UNSUPPORTED_AUDIO", message="We could not open this recording. Please type what was said.", status=415)
    try:
        heard = speech_api.recognise(settings, wav, speech_api.STT_TYPES[simple], speech_api.STT_LANGUAGES[lang])
    except httpx.HTTPError as exc:
        log.warning("Azure STT failed: %s", type(exc).__name__)
        return fail(code="STT_UNAVAILABLE", message="Listening is not available right now. Please type what was said.", status=503)
    text = str(heard.get("DisplayText") or "").strip()
    if not text:
        return fail(code="NO_SPEECH", message="We could not hear words. Please type what was said.", status=422)
    channel = ScamChannel.CALL if kind == "call_recording" else ScamChannel.WHATSAPP
    body = _form_body(text, sender, on_call_with_unknown, area, channel)
    confidence = (heard.get("NBest") or [{}])[0].get("Confidence")
    extracted = {"text": text, "confidence": confidence, "language": speech_api.STT_LANGUAGES[lang]}
    return ok(_run(db, principal, body, source=kind, extracted=extracted))


@router.post("/public/scam/check", tags=["public API (API key)"])
@limiter.limit("60/minute")
def public_check(request: Request, body: ScamCheckIn, principal: Principal = Depends(require_scope("scam:check")),
                 db: Session = Depends(get_db)) -> dict:
    """For outside systems (e.g. an SMS gateway) with an API key scoped to scam:check."""
    return ok(_run(db, principal, body))


@router.get("/scam/map")
def scam_map(days: int = Query(default=7, ge=1, le=90),
             principal: Principal = Depends(require_roles(Role.OFFICER, Role.ADMIN, Role.AUDITOR)), db: Session = Depends(get_db)) -> dict:
    """Scam patterns by type, area and hour, from classified messages (no message text, no phone numbers)."""
    since = utcnow() - timedelta(days=days)
    rows = db.execute(select(ScamCheck).where(ScamCheck.tenant_id == principal.tenant_id, ScamCheck.created_at >= since)).scalars().all()
    scams = [r for r in rows if r.verdict == "LIKELY_SCAM"]
    return ok({
        "total_checked": len(rows),
        "by_verdict": dict(Counter(r.verdict for r in rows)),
        "scams_by_type": dict(Counter(r.scam_type for r in scams)),
        "scams_by_area": dict(Counter(r.area or "unknown" for r in scams)),
        "scams_by_hour": dict(sorted(Counter(r.created_at.hour for r in scams).items())),
    })
