"""SafeSwitch API: request, confirm (own PIN), officer review, apply after the hold."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin import platform_admin
from app.core.lockout import MAX_FAILURES, recent_failures
from app.api.cases import _load
from app.core import audit
from app.core.auth import Principal, get_principal, require_roles
from app.core.consent import consented_person_ids
from app.core.envelope import ok
from app.core.ratelimit import limiter
from app.core.security import verify_pin
from app.db import get_db
from app.models.payout import PayoutChangeRequest
from app.models.platform import Case, User, utcnow
from app.schemas.contracts import Role
from app.services import payout as svc

router = APIRouter(prefix="/api/v1", tags=["payout (SafeSwitch)"])


class ChangeIn(BaseModel):
    new_iban: str = Field(min_length=10, max_length=34, pattern=r"^[A-Z0-9]+$")


class ConfirmIn(BaseModel):
    pin: str = Field(min_length=4, max_length=8)


class NoteIn(BaseModel):
    note: str = Field(min_length=3, max_length=1000)


@router.post("/cases/{case_id}/payout-change", status_code=201)
@limiter.limit("5/minute")
def request_change(case_id: str, body: ChangeIn, request: Request,
                   principal: Principal = Depends(require_roles(Role.CITIZEN, Role.HELPER)), db: Session = Depends(get_db)) -> dict:
    case = _load(db, principal, request, case_id, lock=True, field="payout_account")
    change = svc.request_change(db, principal, case, body.new_iban)
    db.commit()
    return ok(svc.view(change))


@router.get("/cases/{case_id}/payout-changes")
def list_changes(case_id: str, request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    case = _load(db, principal, request, case_id, field="payout_account")
    rows = db.execute(select(PayoutChangeRequest).where(PayoutChangeRequest.case_id == case.id).order_by(PayoutChangeRequest.created_at.desc())).scalars()
    return ok([svc.view(c) for c in rows])


@router.post("/payout-changes/{change_id}/confirm")
@limiter.limit("5/minute")
def confirm(change_id: str, body: ConfirmIn, request: Request,
            principal: Principal = Depends(require_roles(Role.CITIZEN)), db: Session = Depends(get_db)) -> dict:
    """The claimant re-enters her own PIN. Helpers cannot reach this route at all.

    Same rule as sign-in: 5 wrong PINs here in 15 minutes block the step-up, so a stolen access
    token cannot be used to guess the PIN and redirect the pension. Login failures are not counted:
    anyone who knows her phone number could otherwise lock her payout confirmation."""
    if recent_failures(db, principal.id, "PAYOUT_CONFIRM_FAILED") >= MAX_FAILURES:
        audit.record(db, principal.actor, "PAYOUT_CONFIRM_LOCKED", resource=f"payout_change:{change_id}")
        db.commit()
        raise HTTPException(status_code=429, detail="Too many wrong PINs. Please wait 15 minutes or ask your helper.")
    user = db.get(User, principal.id)
    if user is None or not verify_pin(body.pin, user.pin_hash):
        audit.record(db, principal.actor, "PAYOUT_CONFIRM_FAILED", resource=f"payout_change:{change_id}")
        db.commit()
        raise HTTPException(status_code=403, detail="Wrong PIN")  # 403, not 401: a wrong step-up PIN must not end her session
    change = svc.confirm(db, principal, change_id)
    db.commit()
    return ok(svc.view(change))


@router.post("/payout-changes/{change_id}/cancel")
@limiter.limit("10/minute")
def cancel(change_id: str, request: Request,
           principal: Principal = Depends(require_roles(Role.CITIZEN, Role.HELPER)), db: Session = Depends(get_db)) -> dict:
    """Stop a change before it is applied: the claimant, or the helper who started it."""
    change = svc.cancel(db, principal, change_id)
    db.commit()
    return ok(svc.view(change))


@router.get("/payout-changes")
def officer_list(status: str = "flagged", principal: Principal = Depends(require_roles(Role.OFFICER)),
                 db: Session = Depends(get_db)) -> dict:
    """Officer view: payout changes in this department, flagged ones by default (newest first)."""
    if status not in ("flagged", "held", "confirmed", "approved", "applied", "rejected", "cancelled", "all"):
        raise HTTPException(status_code=422, detail="Unknown status")
    shared = consented_person_ids(db, principal, "payout_account")  # same consent rule as the case view
    query = (select(PayoutChangeRequest, Case.reference).join(Case, Case.id == PayoutChangeRequest.case_id)
             .where(PayoutChangeRequest.tenant_id == principal.tenant_id, Case.claimant_person_id.in_(shared))
             .order_by(PayoutChangeRequest.created_at.desc()).limit(100))
    if status != "all":
        query = query.where(PayoutChangeRequest.status == status)
    return ok([{**svc.view(change), "case_reference": ref} for change, ref in db.execute(query).all()])


@router.post("/payout-changes/{change_id}/{decision}")
def review(change_id: str, decision: str, body: NoteIn,
           principal: Principal = Depends(require_roles(Role.OFFICER)), db: Session = Depends(get_db)) -> dict:
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=404, detail="Unknown action")
    change = svc.officer_review(db, principal, change_id, decision == "approve", body.note)
    db.commit()
    return ok(svc.view(change))


@router.post("/admin/payout/apply-due")
def apply_due(skip_wait: bool = False, principal: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    """Normally a scheduler runs this. skip_wait=true is the judge-console shortcut to show the
    end of a 48-hour hold without waiting; it is audited as such."""
    now = utcnow() + (timedelta(days=30) if skip_wait else timedelta(0))
    if skip_wait:
        audit.record(db, principal.actor, "DEMO_SKIP_PAYOUT_HOLD")
    applied = svc.apply_due(db, now)
    db.commit()
    return ok({"applied": applied})
