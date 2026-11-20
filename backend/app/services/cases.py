"""Case lifecycle: create, decide, assign, escalate, approve/reject, close.

Every state change writes a case event and an audit event. Decisions are made
by the decision engine (actor "ai"), and only officers can approve or reject.
"""
import hashlib
import json
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal
from app.decision.engine import Outcome, decide
from app.decision.facts import ACTIVE_STATUSES, gather
from app.models.platform import Case, CaseEvent, Decision, HelperAssignment, Person, RuleVersion, User
from app.schemas.claims import ClaimIn
from app.schemas.contracts import ReasonCode, Role, Route

RULESET = "survivor-pension"
STATUS_FOR_ROUTE = {Route.AUTO_APPROVE: "auto_approved", Route.ASK_PROOF: "proof_requested", Route.UNSURE: "in_review"}
OFFICER_FINAL = ("approved", "rejected", "closed")
HIGH_RISK = {ReasonCode.DUPLICATE_CLAIM, ReasonCode.ACCOUNT_REUSED, ReasonCode.ACCOUNT_NOT_OWNED, ReasonCode.NOT_IN_FAMILY_RECORD}


def not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")


def live_ruleset(db: Session) -> RuleVersion:
    row = db.execute(select(RuleVersion).where(RuleVersion.ruleset == RULESET, RuleVersion.status == "live")).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=503, detail="No live ruleset")
    return row


def ruleset_dict(row: RuleVersion) -> dict:
    return {"rules": row.rules, "thresholds": row.thresholds, "version": row.version}


def _input_hash(claim: dict) -> str:
    return hashlib.sha256(json.dumps(claim, sort_keys=True, default=str).encode()).hexdigest()


def _priority(outcome: Outcome) -> int:
    if outcome.route == Route.UNSURE:
        return 3 if HIGH_RISK & set(outcome.reasons) else 2
    return 1 if outcome.route == Route.ASK_PROOF else 0


def _event(db: Session, case: Case, kind: str, actor_id: str | None, note: str | None = None) -> None:
    db.add(CaseEvent(case_id=case.id, kind=kind, actor_id=actor_id, note=note))


def _helper_assigned(db: Session, helper_id: str, person_id: str) -> bool:
    row = db.execute(select(HelperAssignment).where(HelperAssignment.helper_user_id == helper_id, HelperAssignment.person_id == person_id))
    return row.first() is not None


def can_view(db: Session, principal: Principal, case: Case) -> bool:
    if principal.role in (Role.OFFICER, Role.ADMIN, Role.AUDITOR):
        return case.tenant_id == principal.tenant_id
    if principal.role == Role.CITIZEN:
        return case.claimant_person_id == principal.person_id
    if principal.role == Role.HELPER:
        return _helper_assigned(db, principal.id, case.claimant_person_id)
    return False


def _claimant_person(db: Session, principal: Principal, claim: ClaimIn) -> Person:
    person = db.execute(select(Person).where(Person.cnic == claim.claimant_cnic)).scalar_one_or_none()
    allowed = person is not None and (
        (principal.role == Role.CITIZEN and person.id == principal.person_id)
        or (principal.role == Role.HELPER and _helper_assigned(db, principal.id, person.id))
    )
    if not allowed:
        audit.record(db, principal.actor, "ACCESS_DENIED", resource="POST /api/v1/cases", details={"reason": "claim for a person not linked to this user"})
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only file claims for yourself or families assigned to you")
    return person


def create_case(db: Session, principal: Principal, claim: ClaimIn) -> Case:
    person = _claimant_person(db, principal, claim)
    count = db.execute(select(func.count(Case.id))).scalar() or 0
    case = Case(
        reference=f"SP-{1001 + count}",
        tenant_id=principal.tenant_id,
        claimant_person_id=person.id,
        created_by=principal.id,
        status="submitted",
        claim=claim.model_dump(mode="json"),
        deceased_cnic=claim.deceased_cnic,
        payout_iban=claim.payout_iban,
    )
    db.add(case)
    db.flush()
    _event(db, case, "created", principal.id)
    audit.record(db, principal.actor, "CASE_CREATED", resource=f"case:{case.reference}", case_id=case.id)
    return case


def _least_busy_officer(db: Session, tenant_id: str) -> str | None:
    load = (
        select(User.id, func.count(Case.id).label("n"))
        .outerjoin(Case, (Case.assigned_officer_id == User.id) & (Case.status == "in_review"))
        .where(User.tenant_id == tenant_id, User.role == Role.OFFICER, User.active.is_(True))
        .group_by(User.id)
        .order_by("n", User.id)
    )
    row = db.execute(load).first()
    return row[0] if row else None


def run_decision(db: Session, case: Case, today: date | None = None, ruleset_row: RuleVersion | None = None) -> Decision:
    """Decide (or re-decide) a case with the live ruleset. Actor = AI."""
    today = today or date.today()
    ruleset_row = ruleset_row or live_ruleset(db)
    claim = ClaimIn.model_validate(case.claim)
    signals = gather(db, case, claim, today)
    outcome = decide(signals, ruleset_dict(ruleset_row))
    decision = Decision(
        case_id=case.id,
        rule_version_id=ruleset_row.id,
        model_id=None,  # Jev is not used for claim facts in Phase 1
        input_hash=_input_hash(case.claim),
        signals=signals.to_dict(),
        rule_result={**outcome.rule_result.to_dict(), "missing_items": list(outcome.missing_items)},
        confidence=outcome.confidence,
        thresholds=ruleset_row.thresholds,
        route=outcome.route.value,
        reason_codes=[r.value for r in outcome.reasons],
    )
    db.add(decision)
    case.status = STATUS_FOR_ROUTE[outcome.route]
    case.priority = _priority(outcome)
    case.confidence = outcome.confidence
    if outcome.route == Route.UNSURE and case.assigned_officer_id is None:
        case.assigned_officer_id = _least_busy_officer(db, case.tenant_id)
    db.flush()
    _event(db, case, f"decision_{outcome.route.value.lower()}", "decision-engine", ", ".join(decision.reason_codes))
    audit.record(
        db, audit.AI, "DECISION_MADE", resource=f"decision:{decision.id}", case_id=case.id,
        details={"route": decision.route, "reasons": decision.reason_codes, "confidence": decision.confidence,
                 "rule_version": ruleset_row.version, "model_id": None},
    )
    return decision


def recheck_related(db: Session, case: Case) -> list[str]:
    """A new claim on the same pension can change other open cases (e.g. a
    competing claimant appears). Re-decide those not yet finalised by an officer."""
    if not case.deceased_cnic:
        return []
    related = db.execute(
        select(Case).where(Case.deceased_cnic == case.deceased_cnic, Case.id != case.id, Case.status.in_(ACTIVE_STATUSES), Case.status.not_in(OFFICER_FINAL))
    ).scalars().all()
    for other in related:
        run_decision(db, other)
    return [o.reference for o in related]


def officer_decide(db: Session, principal: Principal, case: Case, approve: bool, reason: str) -> Case:
    if case.status in OFFICER_FINAL:
        raise HTTPException(status_code=409, detail=f"Case is already {case.status}")
    case.status = "approved" if approve else "rejected"
    _event(db, case, case.status, principal.id, reason)
    audit.record(db, principal.actor, "CASE_APPROVED" if approve else "CASE_REJECTED", resource=f"case:{case.reference}", case_id=case.id, details={"reason": reason})
    return case


def assign(db: Session, principal: Principal, case: Case, officer_id: str) -> Case:
    officer = db.get(User, officer_id)
    if officer is None or officer.role != Role.OFFICER or officer.tenant_id != case.tenant_id:
        raise HTTPException(status_code=422, detail="Not an officer in this department")
    case.assigned_officer_id = officer_id
    _event(db, case, "assigned", principal.id, officer.name)
    audit.record(db, principal.actor, "CASE_ASSIGNED", resource=f"case:{case.reference}", case_id=case.id, details={"officer_id": officer_id})
    return case


def escalate(db: Session, principal: Principal, case: Case, reason: str) -> Case:
    if case.status in OFFICER_FINAL:
        raise HTTPException(status_code=409, detail=f"Case is already {case.status}")
    case.status = "in_review"
    case.priority = max(case.priority, 2)
    if case.assigned_officer_id is None:
        case.assigned_officer_id = _least_busy_officer(db, case.tenant_id)
    _event(db, case, "escalated", principal.id, reason)
    audit.record(db, principal.actor, "CASE_ESCALATED", resource=f"case:{case.reference}", case_id=case.id, details={"reason": reason})
    return case


def close(db: Session, principal: Principal, case: Case, reason: str) -> Case:
    case.status = "closed"
    _event(db, case, "closed", principal.id, reason)
    audit.record(db, principal.actor, "CASE_CLOSED", resource=f"case:{case.reference}", case_id=case.id, details={"reason": reason})
    return case
