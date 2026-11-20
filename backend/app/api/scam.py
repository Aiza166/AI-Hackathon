"""Scam Shield and Scam Map."""
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal, require_roles, require_scope
from app.core.envelope import ok
from app.core.ratelimit import limiter
from app.db import get_db
from app.models.platform import utcnow
from app.models.scam import ScamCheck
from app.schemas.contracts import Role, ScamCheckIn
from app.services import scam as svc

router = APIRouter(prefix="/api/v1", tags=["scam shield"])
# Real-world reporting routes (shown after a scam verdict). Sources: docs/research/win-strategy-jev.md.
REPORT_ROUTES = [
    {"name": "NCCIA cybercrime complaint (official portal)", "url": "https://complaint.nccia.gov.pk/"},
    {"name": "PTA: report fraud calls and SMS", "url": "https://www.pta.gov.pk/category/report-fraud-callssmss-884766986-2023-05-30"},
]


def _run(db: Session, principal: Principal, body: ScamCheckIn) -> dict:
    result = svc.check(db, body.text, body.sender, body.on_call_with_unknown, principal.person_id)
    db.add(ScamCheck(tenant_id=principal.tenant_id, text_hash=svc.text_hash(body.text), scam_type=result.scam_type,
                     area=body.area, signals=result.signals, model_id=result.model_id, verdict=result.verdict, score=result.score))
    audit.record(db, audit.AI, "SCAM_CHECKED", tenant_id=principal.tenant_id,
                 details={"verdict": result.verdict, "score": result.score, "model_id": result.model_id,
                          "fallback": result.signals["fallback"], "requested_by_role": principal.role})
    db.commit()
    return {
        "verdict": result.verdict, "confidence": result.score, "reasons": result.reasons, "reasons_ur": result.reasons_ur,
        "case_cross_check": result.case_cross_check, "model_id": result.model_id,
        "report_routes": REPORT_ROUTES if result.verdict != "LOOKS_GENUINE" else [],
    }


@router.post("/scam/check")
@limiter.limit("20/minute")
def check(request: Request, body: ScamCheckIn,
          principal: Principal = Depends(require_roles(Role.CITIZEN, Role.HELPER, Role.OFFICER)), db: Session = Depends(get_db)) -> dict:
    return ok(_run(db, principal, body))


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
