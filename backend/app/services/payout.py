"""SafeSwitch: changing where a pension is paid.

Rules (docs/research/survivor-pension.md section 2):
- Confirmation of Payee on the new account: match / close match / no match.
- Hold 48 hours before any change takes effect; 4 business days if a red flag fires
  (account used by another claim, payee not a clear match, change soon after the death).
- Only the claimant herself can confirm, with her own PIN. A helper can start a change
  but never confirm it. Red flags also need an officer's approval.
Every step is audited.
"""
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal
from app.mock import raast, registry
from app.models.payout import PayoutChangeRequest
from app.models.platform import Case, Person, utcnow

STANDARD_HOLD = timedelta(hours=48)
FLAGGED_BUSINESS_DAYS = 4
RECENT_DEATH_DAYS = 30
OPEN_STATUSES = ("held", "confirmed", "flagged", "approved")
CANCELLABLE = OPEN_STATUSES


def add_business_days(start: datetime, days: int) -> datetime:
    current = start
    while days > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            days -= 1
    return current


def payee_check(db: Session, iban: str, claimant: Person) -> raast.TitleFetch:
    """Mock Raast title fetch + our Confirmation-of-Payee verdict for the new account."""
    return raast.title_fetch(db, iban, claimant.display_name, claimant.cnic)


def _flags(db: Session, case: Case, new_iban: str, check: raast.TitleFetch) -> list[str]:
    flags = []
    if check.status == "TIMEOUT":
        flags.append("PAYEE_CHECK_TIMEOUT")  # never auto-accept: an officer decides, hold extended
    elif check.status == "UNAVAILABLE":
        flags.append(f"SERVICE_UNAVAILABLE:{raast.SERVICE}")
    elif check.payee != "match":
        flags.append(f"PAYEE_{check.payee.upper()}")
    if check.account_holding == "JOINT":
        flags.append("JOINT_ACCOUNT")  # federal pensions must not go to a joint account (AGPR DCS): ask for proof
    reused = db.execute(select(Case.reference).where(Case.payout_iban == new_iban, Case.id != case.id,
                                                     Case.claimant_person_id != case.claimant_person_id)).first()
    if reused:
        flags.append("ACCOUNT_USED_BY_ANOTHER_CLAIM")
    if case.deceased_cnic:
        death = registry.get_death(db, case.deceased_cnic)
        if death is not None and (utcnow().date() - death.date_of_death).days <= RECENT_DEATH_DAYS:
            flags.append("CHANGE_SOON_AFTER_DEATH")
    return flags


def request_change(db: Session, principal: Principal, case: Case, new_iban: str) -> PayoutChangeRequest:
    if case.status in ("rejected", "closed", "withdrawn"):
        raise HTTPException(status_code=409, detail=f"This claim is {case.status}: its payout account cannot be changed")
    if db.execute(select(PayoutChangeRequest).where(PayoutChangeRequest.case_id == case.id,
                                                     PayoutChangeRequest.status.in_(OPEN_STATUSES))).first():
        raise HTTPException(status_code=409, detail="A payout change is already in progress for this claim")
    claimant = db.get(Person, case.claimant_person_id)
    check = payee_check(db, new_iban, claimant)
    payee = check.payee
    try:
        flags = _flags(db, case, new_iban, check)
    except registry.MockServiceUnavailable as exc:
        flags = [f"SERVICE_UNAVAILABLE:{exc.service}"]
    now = utcnow()
    hold_until = add_business_days(now, FLAGGED_BUSINESS_DAYS) if flags else now + STANDARD_HOLD
    change = PayoutChangeRequest(case_id=case.id, tenant_id=case.tenant_id, old_iban=case.payout_iban, new_iban=new_iban,
                                 requested_by=principal.id, requested_role=principal.role, payee_result=payee, flags=flags,
                                 payee_check=check.to_dict(),
                                 status="flagged" if flags else "held", hold_until=hold_until)
    db.add(change)
    db.flush()
    audit.record(db, principal.actor, "PAYOUT_CHANGE_REQUESTED", resource=f"payout_change:{change.id}", case_id=case.id,
                 details={"payee": payee, "flags": flags, "hold_until": hold_until.isoformat(), "new_iban_last4": new_iban[-4:]})
    return change


def _get(db: Session, change_id: str) -> PayoutChangeRequest:
    change = db.get(PayoutChangeRequest, change_id, with_for_update=True)
    if change is None:
        raise HTTPException(status_code=404, detail="Payout change not found")
    return change


def confirm(db: Session, principal: Principal, change_id: str) -> PayoutChangeRequest:
    """Called only after the claimant re-entered her own PIN (checked by the API layer)."""
    change = _get(db, change_id)
    case = db.get(Case, change.case_id)
    if principal.person_id is None or principal.person_id != case.claimant_person_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the claimant herself can confirm a payout change")
    if change.status not in ("held", "flagged", "approved") or change.confirmed_at is not None:
        raise HTTPException(status_code=409, detail=f"This change is {change.status}")
    change.confirmed_at = utcnow()
    if change.status in ("held", "approved"):  # a flagged change still waits for the officer
        change.status = "confirmed"
    audit.record(db, principal.actor, "PAYOUT_CHANGE_CONFIRMED", resource=f"payout_change:{change.id}", case_id=case.id)
    return change


def cancel(db: Session, principal: Principal, change_id: str) -> PayoutChangeRequest:
    """The claimant herself (or the helper who started it) can stop a change before it is applied."""
    change = _get(db, change_id)
    case = db.get(Case, change.case_id)
    own = principal.person_id is not None and principal.person_id == case.claimant_person_id
    if not own and principal.id != change.requested_by:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the claimant or the person who started it can cancel")
    if change.status not in CANCELLABLE:
        raise HTTPException(status_code=409, detail=f"This change is {change.status}")
    change.status = "cancelled"
    audit.record(db, principal.actor, "PAYOUT_CHANGE_CANCELLED", resource=f"payout_change:{change.id}", case_id=case.id)
    return change


def officer_review(db: Session, principal: Principal, change_id: str, approve: bool, note: str) -> PayoutChangeRequest:
    change = _get(db, change_id)
    if change.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Payout change not found")  # other departments: not even existence
    if change.status != "flagged":
        raise HTTPException(status_code=409, detail="Only flagged changes in your department need officer review")
    if not approve:
        change.status = "rejected"
    else:
        change.status = "confirmed" if change.confirmed_at else "approved"  # still needs the claimant's PIN
    audit.record(db, principal.actor, "PAYOUT_CHANGE_APPROVED" if approve else "PAYOUT_CHANGE_REJECTED",
                 resource=f"payout_change:{change.id}", case_id=change.case_id, details={"note": note})
    return change


def apply_due(db: Session, now: datetime | None = None) -> list[str]:
    """Apply confirmed changes whose hold has passed (run by a scheduler, or the judge console)."""
    now = now or utcnow()
    due = db.execute(select(PayoutChangeRequest).where(PayoutChangeRequest.status == "confirmed",
                                                       PayoutChangeRequest.hold_until <= now).with_for_update()).scalars().all()
    applied = []
    for change in due:
        case = db.get(Case, change.case_id)
        case.payout_iban = change.new_iban
        case.claim = {**case.claim, "payout_iban": change.new_iban}
        change.status, change.applied_at = "applied", now
        audit.record(db, audit.SYSTEM, "PAYOUT_CHANGE_APPLIED", resource=f"payout_change:{change.id}", case_id=case.id,
                     tenant_id=case.tenant_id, details={"new_iban_last4": change.new_iban[-4:]})
        applied.append(change.id)
    return applied


def view(change: PayoutChangeRequest) -> dict:
    return {"id": change.id, "case_id": change.case_id, "status": change.status, "payee_result": change.payee_result,
            "flags": change.flags, "hold_until": change.hold_until.isoformat(), "new_iban_last4": change.new_iban[-4:],
            "requested_role": change.requested_role, "confirmed": change.confirmed_at is not None,
            "applied_at": change.applied_at.isoformat() if change.applied_at else None,
            "created_at": change.created_at.isoformat() if change.created_at else None,
            "payee_check": change.payee_check}
