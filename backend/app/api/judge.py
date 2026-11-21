"""Judge console API (platform admin only): live status, AI outage simulation, activity feed, sample documents.

Everything here is a demo control for the PROTOTYPE. Role checks are on the server (platform admin of the
pension department), every change is audited, and nothing returns a key, endpoint or other secret: provider
settings come back as booleans, plus the public model ids.
"""
import json
import shutil
import threading
import time
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.admin import platform_admin
from app.core import audit, outages
from app.core.auth import Principal
from app.core.envelope import ok
from app.core.ratelimit import limiter
from app.db import get_db
from app.decision.jev_client import JevClient
from app.core.config import get_settings
from app.evaluation import runner
from app.mock import registry
from app.models.audit import AuditEvent

router = APIRouter(prefix="/api/v1/admin/judge", tags=["judge console"])

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_docs"
ACTIVITY_LIMIT = 20
ACTIVITY_AUDIT_EVERY_S = 300  # the feed polls every 10 s: log a read once per 5 minutes per admin, not every poll
REASON_MAX = 80
MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg"}

_activity_lock = threading.Lock()
_activity_logged: dict[str, float] = {}


class OutageIn(BaseModel):
    target: Literal["jev", "second_sensor", "azure_ocr", "azure_speech"]
    down: bool


def _providers() -> dict:
    """Which providers are configured: booleans and public model ids only, never keys or endpoints."""
    s = get_settings()
    return {
        "jev": bool(s.typesafe_api_key),
        "second_sensor": s.second_sensor_configured,
        "azure_ocr": s.docintel_configured,
        "azure_speech": s.speech_configured,
        "tesseract": shutil.which("tesseract") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "jev_model": s.jev_model,
        "second_sensor_model": s.second_sensor_deployment if s.second_sensor_configured else None,
    }


def _readiness(db: Session) -> dict:
    db.execute(text("SELECT 1"))
    jev = JevClient()
    try:
        reachable = jev.reachable()
    finally:
        jev.close()
    return {"database": "ok", "jev_reachable": reachable, "jev_model": get_settings().jev_model,
            "jev_simulated_down": outages.is_down("jev")}


def _last_eval() -> dict | None:
    result = runner.latest()
    if result is None:
        return None
    return {"generated_at": result.get("generated_at"), "source": result.get("source", "this_process"),
            "scam_mode": result.get("scam", {}).get("mode")}


@router.get("/status")
def status(principal: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    """One call for the console: readiness, providers, faults, simulated outages, last eval, audit chain."""
    chain = audit.verify_chain(db)
    data = {
        "readiness": _readiness(db),
        "providers": _providers(),
        "faults": {svc: registry.fault_mode(db, svc) for svc in registry.SERVICES},
        "outages": outages.status(),
        "outage_minutes": outages.OUTAGE_MINUTES,
        "last_eval": _last_eval(),
        "audit_chain": {"intact": chain["intact"], "checked": chain["checked"], "first_broken_seq": chain["first_broken_seq"]},
    }
    audit.record(db, principal.actor, "JUDGE_CONSOLE_STATUS_READ", resource="judge_console",
                 details={"chain_intact": chain["intact"]})
    db.commit()
    return ok(data)


@router.post("/outages")
@limiter.limit("30/minute")
def set_outage(request: Request, body: OutageIn, principal: Principal = Depends(platform_admin),
               db: Session = Depends(get_db)) -> dict:
    """Make an AI provider behave as if it were down (auto-expires), to show the fallback live."""
    expires = outages.set_outage(body.target, body.down)
    expires_at = expires.isoformat(timespec="seconds") if expires else None
    audit.record(db, principal.actor, "AI_OUTAGE_SIMULATED", resource=f"provider:{body.target}",
                 details={"target": body.target, "down": body.down, "expires_at": expires_at})
    db.commit()
    return ok({"target": body.target, "simulated_down": body.down, "expires_at": expires_at})


def _reason(details: dict | None) -> str | None:
    """A short reason code for the feed. Details are already redacted (no CNIC/IBAN) when written."""
    if not details:
        return None
    reasons = details.get("reasons") or details.get("reason_codes")
    if isinstance(reasons, list) and reasons:
        joined = ", ".join(str(r) for r in reasons)
        return f"{details['route']}: {joined}"[:REASON_MAX] if details.get("route") else joined[:REASON_MAX]
    for key in ("route", "verdict", "reason"):
        if details.get(key):
            return str(details[key])[:REASON_MAX]
    if details.get("service") and details.get("mode"):
        return f"{details['service']}: {details['mode']}"
    if details.get("target") is not None and "down" in details:
        return f"{details['target']}: {'down' if details['down'] else 'restored'}"
    return None


def _log_activity_read(db: Session, principal: Principal) -> None:
    now = time.monotonic()
    with _activity_lock:
        last = _activity_logged.get(principal.id)
        if last is not None and now - last < ACTIVITY_AUDIT_EVERY_S:
            return
        _activity_logged[principal.id] = now
    audit.record(db, principal.actor, "AUDIT_READ", resource="judge_console", details={"feed": "recent_activity"})
    db.commit()


@router.get("/activity")
def activity(principal: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    """Last 20 audit events of this department: time, actor type and role, action, reason code. No ids, no details."""
    _log_activity_read(db, principal)
    query = (select(AuditEvent).where(AuditEvent.tenant_id == principal.tenant_id)
             .order_by(AuditEvent.seq.desc()).limit(ACTIVITY_LIMIT))
    rows = [{"seq": e.seq, "ts": e.ts.isoformat(), "actor_type": e.actor_type, "role": e.role, "action": e.action,
             "reason": _reason(e.details)} for e in db.execute(query).scalars()]
    return ok(rows)


def _sample_files() -> dict[str, dict]:
    """Allowlist built from manifest.json: only these exact names can ever be served."""
    manifest = json.loads((SAMPLE_DIR / "manifest.json").read_text(encoding="utf-8"))["files"]
    return {e["file"]: {"file": e["file"], "doc": e["doc"], "variant": e["variant"], "edited": bool(e["edited"])}
            for e in manifest if Path(e["file"]).suffix in MEDIA_TYPES and (SAMPLE_DIR / e["file"]).is_file()}


@router.get("/sample-docs")
def sample_docs(principal: Principal = Depends(platform_admin)) -> dict:
    return ok(sorted(_sample_files().values(), key=lambda e: (e["edited"], e["doc"], e["variant"])))


@router.get("/sample-docs/{name}", response_model=None)
def sample_doc(name: str, principal: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> FileResponse:
    """Mock sample images (MOCK / SPECIMEN watermark) for the upload demo. Unknown names are 404, never a path."""
    entry = _sample_files().get(name)
    if entry is None:
        raise HTTPException(status_code=404, detail="Sample document not found")
    audit.record(db, principal.actor, "SAMPLE_DOC_DOWNLOADED", resource=f"sample_doc:{entry['file']}",
                 details={"edited": entry["edited"]})
    db.commit()
    path = SAMPLE_DIR / entry["file"]
    return FileResponse(path, media_type=MEDIA_TYPES[path.suffix], filename=entry["file"],
                        headers={"Cache-Control": "no-store"})
