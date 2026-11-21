"""Scam Shield and Scam Map."""
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal, require_roles, require_scope
from app.core.config import get_settings
from app.core.envelope import fail, ok
from app.core.ratelimit import limiter
from app.db import get_db
from app.models.platform import utcnow
from app.models.scam import ScamCheck
from app.schemas.contracts import Role, ScamCheckIn
from app.services import scam as svc

router = APIRouter(prefix="/api/v1", tags=["scam shield"])
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


# Scam Map areas are a fixed list, so free text (names, numbers, abuse) never reaches the map.
AREAS = ("Karachi South", "Karachi East", "Karachi West", "Karachi Central", "Korangi", "Malir", "Keamari",
         "Hyderabad", "Sukkur", "Larkana", "Mirpurkhas", "Lahore", "Islamabad", "Rawalpindi", "Peshawar", "Quetta",
         "Multan", "Faisalabad", "Gujranwala", "Sialkot", "other")
_AREA_LOOKUP = {a.casefold(): a for a in AREAS}
JEV_DAILY_CHECKS_PER_USER = 200  # each check can call Jev (paid); caps runaway cost from one account or key
jev_quota = svc.PerUserQuota(JEV_DAILY_CHECKS_PER_USER, 24 * 3600)


def area_of(value: str | None) -> str | None:
    """Known area, or 'other' for anything not on the list; None stays None."""
    if value is None or not value.strip():
        return None
    return _AREA_LOOKUP.get(" ".join(value.split()).casefold(), "other")


def _run(db: Session, principal: Principal, body: ScamCheckIn) -> dict:
    result = svc.check(db, body.text, body.sender, body.on_call_with_unknown, principal.person_id,
                       user_key=f"{principal.kind}:{principal.id}", secret=get_settings().jwt_secret)
    db.add(ScamCheck(tenant_id=principal.tenant_id, text_hash=svc.text_hash(body.text), scam_type=result.scam_type,
                     area=area_of(body.area), signals=result.signals, model_id=result.model_id, verdict=result.verdict, score=result.score))
    audit.record(db, audit.AI, "SCAM_CHECKED", tenant_id=principal.tenant_id,
                 details={"verdict": result.verdict, "score": result.score, "model_id": result.model_id,
                          "fallback": result.signals["fallback"], "disagreement": result.signals["disagreement"],
                          "steering": result.signals["steering"], "breaker_active": result.signals["breaker_active"],
                          "requested_by_role": principal.role})
    db.commit()
    return {
        "verdict": result.verdict, "confidence": result.score, "reasons": result.reasons, "reasons_ur": result.reasons_ur,
        "case_cross_check": result.case_cross_check, "model_id": result.model_id,
        "report_routes": report_routes(result.verdict, body.text, body.sender),
    }


def _over_quota(principal: Principal):
    if jev_quota.allow(f"{principal.kind}:{principal.id}"):
        return None
    return fail(code="SCAM_CHECK_QUOTA", message="Daily scam check limit reached. Please try again tomorrow or ask a helper.", status=429)


@router.get("/scam/areas")
def areas(principal: Principal = Depends(require_roles(*tuple(Role)))) -> dict:
    return ok({"areas": list(AREAS)})


@router.post("/scam/check", response_model=None)
@limiter.limit("20/minute")
def check(request: Request, body: ScamCheckIn,
          principal: Principal = Depends(require_roles(Role.CITIZEN, Role.HELPER, Role.OFFICER)), db: Session = Depends(get_db)):
    return _over_quota(principal) or ok(_run(db, principal, body))


@router.post("/scam/canary")
@limiter.limit("6/minute")
def canary(request: Request, principal: Principal = Depends(require_roles(Role.ADMIN)), db: Session = Depends(get_db)) -> dict:
    """Admin only: run a known scam through Jev. If Jev clears it, no check can say LOOKS_GENUINE for 30 minutes."""
    outcome = svc.run_canary()
    audit.record(db, principal.actor, "SCAM_CANARY_RUN", tenant_id=principal.tenant_id,
                 details={"status": outcome["status"], "tripped": outcome["tripped"], "model_id": outcome.get("model_id")})
    db.commit()
    return ok(outcome)


@router.post("/public/scam/check", tags=["public API (API key)"], response_model=None)
@limiter.limit("60/minute")
def public_check(request: Request, body: ScamCheckIn, principal: Principal = Depends(require_scope("scam:check")),
                 db: Session = Depends(get_db)):
    """For outside systems (e.g. an SMS gateway) with an API key scoped to scam:check."""
    return _over_quota(principal) or ok(_run(db, principal, body))


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
