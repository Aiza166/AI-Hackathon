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
from app.decision.matching import name_similarity
from app.mock import registry
from app.models.payout import PayoutChangeRequest
from app.models.platform import Case, Person, utcnow

STANDARD_HOLD = timedelta(hours=48)
FLAGGED_BUSINESS_DAYS = 4
RECENT_DEATH_DAYS = 30
OPEN_STATUSES = ("held", "confirmed", "flagged", "approved")


def add_business_days(start: datetime, days: int) -> datetime:
    current = start
    while days > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            days -= 1
    return current


def payee_check(db: Session, iban: str, claimant: Person) -> str:
    """Mock Confirmation of Payee: does the account belong to, and carry the name of, the claimant?"""
    account = registry.get_account(db, iban)
    if account is None or account.owner_cnic != claimant.cnic:
        return "no_match"
    score = name_similarity(account.title, claimant.display_name)
    return "match" if score >= 95 else "close_match" if score >= 70 else "no_match"


def _flags(db: Session, case: Case, new_iban: str, payee: str) -> list[str]:
    flags = []
    if payee != "match":
        flags.append(f"PAYEE_{payee.upper()}")
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
    if db.execute(select(PayoutChangeRequest).where(PayoutChangeRequest.case_id == case.id,
                                                     PayoutChangeRequest.status.in_(OPEN_STATUSES))).first():
        raise HTTPException(status_code=409, detail="A payout change is already in progress for this claim")
    claimant = db.get(Person, case.claimant_person_id)
    try:
        payee = payee_check(db, new_iban, claimant)
        flags = _flags(db, case, new_iban, payee)
    except registry.MockServiceUnavailable as exc:
        payee, flags = "no_match", [f"SERVICE_UNAVAILABLE:{exc.service}"]
    now = utcnow()
    hold_until = add_business_days(now, FLAGGED_BUSINESS_DAYS) if flags else now + STANDARD_HOLD
    change = PayoutChangeRequest(case_id=case.id, tenant_id=case.tenant_id, old_iban=case.payout_iban, new_iban=new_iban,
                                 requested_by=principal.id, requested_role=principal.role, payee_result=payee, flags=flags,
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


def officer_review(db: Session, principal: Principal, change_id: str, approve: bool, note: str) -> PayoutChangeRequest:
    change = _get(db, change_id)
    if change.tenant_id != principal.tenant_id or change.status != "flagged":
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
            "applied_at": change.applied_at.isoformat() if change.applied_at else None}
