"""Case lifecycle: create, decide, assign, escalate, approve/reject, close.

Every state change writes a case event and an audit event. Decisions are made
by the decision engine (actor "ai"), and only officers can approve or reject.
"""
import hashlib
import json
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal
from app.decision.engine import Outcome, decide
from app.decision.facts import ACTIVE_STATUSES, gather
from app.decision.matching import name_similarity
from app.models.platform import Case, CaseEvent, Decision, HelperAssignment, Person, RuleVersion, User
from app.schemas.claims import ClaimIn
from app.schemas.contracts import ReasonCode, Role, Route

RULESET = "survivor-pension"
STATUS_FOR_ROUTE = {Route.AUTO_APPROVE: "auto_approved", Route.ASK_PROOF: "proof_requested", Route.UNSURE: "in_review"}
OFFICER_FINAL = ("approved", "rejected", "closed")
CLOSE_BLOCKED = ("approved", "auto_approved", "closed")  # a paid (or payable) pension is never just closed (M8)
# Route strictness: a re-decision of a held case may keep or raise its route, never lower it (H1).
ROUTE_RANK = {Route.AUTO_APPROVE: 0, Route.ASK_PROOF: 1, Route.UNSURE: 2}
ROUTE_FOR_STATUS = {"auto_approved": Route.AUTO_APPROVE, "proof_requested": Route.ASK_PROOF, "in_review": Route.UNSURE}
APPROVAL_EVENT_KINDS = ("approved", "decision_auto_approve")
FIRST_APPROVAL_EVENT = "approval_first"
FOUR_EYES_RESET_EVENTS = ("rejected", "closed")
MAX_RECHECK = 10  # bound the work a single new claim can trigger
SAME_NAME_SCORE = 95  # canonical deceased-name match used for duplicates when no CNIC is given
HIGH_RISK = {ReasonCode.DUPLICATE_CLAIM, ReasonCode.ACCOUNT_REUSED, ReasonCode.ACCOUNT_NOT_OWNED, ReasonCode.NOT_IN_FAMILY_RECORD}
HIGH_RISK_VALUES = frozenset(code.value for code in HIGH_RISK)


def not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")


def live_ruleset(db: Session, today: date | None = None) -> RuleVersion:
    """The ruleset in force today: the newest published version whose effective_from has arrived.

    A version published with a future effective_from is "scheduled" and decides nothing
    before that date; until then the previous live version keeps deciding (H6).
    """
    today = today or date.today()
    row = db.execute(
        select(RuleVersion)
        .where(RuleVersion.ruleset == RULESET, RuleVersion.status.in_(("live", "scheduled")),
               or_(RuleVersion.effective_from.is_(None), RuleVersion.effective_from <= today))
        .order_by(RuleVersion.version.desc()).limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=503, detail="No live ruleset")
    return row


def original_ruleset(db: Session, case: Case) -> RuleVersion | None:
    """The rule version a case was first decided under: re-decisions stay on it (Challenge 04)."""
    first = db.execute(
        select(Decision.rule_version_id).where(Decision.case_id == case.id).order_by(Decision.created_at).limit(1)
    ).scalar_one_or_none()
    return db.get(RuleVersion, first) if first else None


def latest_decision(db: Session, case_id: str) -> Decision | None:
    return db.execute(
        select(Decision).where(Decision.case_id == case_id).order_by(Decision.created_at.desc()).limit(1)
    ).scalar_one_or_none()


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


def person_by_cnic(db: Session, cnic: str) -> Person | None:
    return db.execute(select(Person).where(Person.cnic == cnic)).scalar_one_or_none()


def _claimant_person(db: Session, principal: Principal, claim: ClaimIn) -> Person:
    person = person_by_cnic(db, claim.claimant_cnic)
    allowed = person is not None and (
        (principal.role == Role.CITIZEN and person.id == principal.person_id)
        or (principal.role == Role.HELPER and _helper_assigned(db, principal.id, person.id))
    )
    if not allowed:
        audit.record(db, principal.actor, "ACCESS_DENIED", resource="POST /api/v1/cases", details={"reason": "claim for a person not linked to this user"})
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only file claims for yourself or families assigned to you")
    return person


def _lock_claimant(db: Session, person_id: str) -> None:
    """Serialise claim filing per claimant until commit, so check-then-insert cannot race (C1)."""
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"claim:{person_id}"})


def create_case(db: Session, principal: Principal, claim: ClaimIn) -> Case:
    person = _claimant_person(db, principal, claim)
    _lock_claimant(db, person.id)
    _refuse_duplicate(db, person.id, claim.deceased_cnic, claim.deceased_name)
    number = db.execute(text("SELECT nextval('case_ref_seq')")).scalar()
    case = Case(
        reference=f"SP-{number}",
        tenant_id=principal.tenant_id,
        claimant_person_id=person.id,
        created_by=principal.id,
        status="submitted",
        claim=claim.model_dump(mode="json"),
        deceased_cnic=claim.deceased_cnic,
        payout_iban=claim.payout_iban,
    )
    db.add(case)
    try:
        db.flush()
    except IntegrityError:
        # Backstop for the advisory lock: the partial unique index on open claims (sec01_cases).
        db.rollback()
        raise HTTPException(status_code=409, detail="You already have an open claim for this pension") from None
    _event(db, case, "created", principal.id)
    # CASE_CREATED is audited in run_decision, after the slow registry lookups, so the
    # global audit-chain lock is held only briefly.
    return case


def duplicate_of(
    db: Session, person_id: str, deceased_cnic: str | None, deceased_name: str, exclude_case_id: str | None = None,
) -> str | None:
    """Reference of another claim by this claimant for the same deceased person, if any.

    Counts open claims and claims closed after an approval (M8). With a deceased CNIC we
    compare CNICs, and compare the deceased name against the claimant's claims that have no
    CNIC (H5). Without a CNIC we compare the deceased name canonically (spelling variants,
    honorifics, "Muhammad" down-weighted), so leaving the CNIC blank cannot file twice.
    """
    approved_once = select(CaseEvent.case_id).where(CaseEvent.kind.in_(APPROVAL_EVENT_KINDS))
    query = select(Case.reference, Case.claim, Case.deceased_cnic).where(
        Case.claimant_person_id == person_id,
        or_(Case.status.in_(ACTIVE_STATUSES), (Case.status == "closed") & Case.id.in_(approved_once)),
    )
    if exclude_case_id is not None:
        query = query.where(Case.id != exclude_case_id)
    for reference, claim, other_cnic in db.execute(query).all():
        if deceased_cnic is not None and other_cnic == deceased_cnic:
            return reference
        same_name = name_similarity(deceased_name, (claim or {}).get("deceased_name", "")) >= SAME_NAME_SCORE
        if (deceased_cnic is None or other_cnic is None) and same_name:
            return reference
    return None


def _refuse_duplicate(db: Session, person_id: str, deceased_cnic: str | None, deceased_name: str) -> None:
    """One claim per claimant per deceased person."""
    reference = duplicate_of(db, person_id, deceased_cnic, deceased_name)
    if reference:
        raise HTTPException(status_code=409, detail=f"You already have an open claim for this pension ({reference})")


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


def is_held(case: Case) -> bool:
    """Human hold (H1): a person or a guardrail raised this case to an officer (escalated,
    assigned, or routed "I am not sure"). Until an officer acts, no automated path approves it."""
    return case.status == "in_review" or case.assigned_officer_id is not None


def held_route(case: Case, route: Route) -> Route:
    """Under a hold, keep or tighten the current route; never AUTO_APPROVE."""
    if not is_held(case):
        return route
    floor = ROUTE_FOR_STATUS.get(case.status, Route.ASK_PROOF)
    if ROUTE_RANK[floor] < ROUTE_RANK[Route.ASK_PROOF]:
        floor = Route.ASK_PROOF
    return route if ROUTE_RANK[route] >= ROUTE_RANK[floor] else floor


def run_decision(
    db: Session, case: Case, today: date | None = None, ruleset_row: RuleVersion | None = None, created_by: Principal | None = None,
) -> Decision:
    """Decide (or re-decide) a case. Actor = AI.

    A new case uses the ruleset in force today; a re-decision stays on the version the case
    was first decided under (H6). A re-decision of a held case may only keep or tighten its
    route (H1): this covers uploads, field confirmations and related-claim rechecks alike.
    """
    today = today or date.today()
    ruleset_row = ruleset_row or original_ruleset(db, case) or live_ruleset(db, today)
    claim = ClaimIn.model_validate(case.claim)
    signals = gather(db, case, claim, today)
    outcome = decide(signals, ruleset_dict(ruleset_row))
    held = is_held(case)
    route = held_route(case, outcome.route)
    decision = Decision(
        case_id=case.id,
        rule_version_id=ruleset_row.id,
        model_id=None,  # Jev is not used for claim facts in Phase 1
        input_hash=_input_hash(case.claim),
        signals=signals.to_dict(),
        rule_result={**outcome.rule_result.to_dict(), "missing_items": list(outcome.missing_items),
                     "engine_route": outcome.route.value, "human_hold": held},
        confidence=outcome.confidence,
        thresholds=ruleset_row.thresholds,
        route=route.value,
        reason_codes=[r.value for r in outcome.reasons],
    )
    db.add(decision)
    case.status = STATUS_FOR_ROUTE[route]
    case.priority = max(case.priority or 0, _priority(outcome)) if held else _priority(outcome)
    case.confidence = outcome.confidence
    if route == Route.UNSURE and case.assigned_officer_id is None:
        case.assigned_officer_id = _least_busy_officer(db, case.tenant_id)
    db.flush()
    _event(db, case, f"decision_{route.value.lower()}", "decision-engine", ", ".join(decision.reason_codes))
    if created_by is not None:
        audit.record(db, created_by.actor, "CASE_CREATED", resource=f"case:{case.reference}", case_id=case.id)
    audit.record(
        db, audit.AI, "DECISION_MADE", resource=f"decision:{decision.id}", case_id=case.id, tenant_id=case.tenant_id,
        details={"route": decision.route, "engine_route": outcome.route.value, "human_hold": held,
                 "reasons": decision.reason_codes, "confidence": decision.confidence,
                 "rule_version": ruleset_row.version, "model_id": None},
    )
    return decision


def recheck_related(db: Session, case: Case) -> list[str]:
    """A new claim on the same pension can change other open cases (e.g. a
    competing claimant appears). Re-decide those not yet finalised by an officer.

    Only this department's cases are locked and re-decided (M9); another department's claim
    stays a duplicate signal on this case and is never touched from here."""
    if not case.deceased_cnic:
        return []
    related = db.execute(
        select(Case).where(Case.deceased_cnic == case.deceased_cnic, Case.id != case.id, Case.tenant_id == case.tenant_id,
                           Case.status.in_(ACTIVE_STATUSES), Case.status.not_in(OFFICER_FINAL))
        .order_by(Case.created_at).limit(MAX_RECHECK).with_for_update()
    ).scalars().all()
    for other in related:
        run_decision(db, other)
    return [o.reference for o in related]


def _needs_four_eyes(db: Session, case: Case) -> bool:
    decision = latest_decision(db, case.id)
    return decision is not None and any(code in HIGH_RISK_VALUES for code in decision.reason_codes)


def _first_approver(db: Session, case: Case) -> str | None:
    """The officer who gave the first of two approvals, unless a later officer action reset it."""
    rows = db.execute(select(CaseEvent.kind, CaseEvent.actor_id).where(CaseEvent.case_id == case.id).order_by(CaseEvent.created_at)).all()
    first = None
    for kind, actor in rows:
        if kind == FIRST_APPROVAL_EVENT:
            first = actor
        elif kind in FOUR_EYES_RESET_EVENTS:
            first = None
    return first


def _refuse_own_case(db: Session, principal: Principal, case: Case) -> None:
    if case.created_by != principal.id:
        return
    audit.record(db, principal.actor, "ACCESS_DENIED", resource=f"case:{case.reference}", case_id=case.id,
                 details={"reason": "officer cannot approve a case they filed"})
    db.commit()
    raise HTTPException(status_code=403, detail="You cannot approve a case you filed")


def _approval_complete(db: Session, principal: Principal, case: Case, reason: str) -> bool:
    """Four eyes (Security review M4): a HIGH_RISK case needs two different officers."""
    if not _needs_four_eyes(db, case):
        return True
    first = _first_approver(db, case)
    if first == principal.id:
        raise HTTPException(status_code=409, detail="A second, different officer must approve this high-risk case")
    if first is not None:
        return True
    _event(db, case, FIRST_APPROVAL_EVENT, principal.id, reason)
    audit.record(db, principal.actor, "CASE_APPROVAL_RECORDED", resource=f"case:{case.reference}", case_id=case.id,
                 details={"reason": reason, "approvals": 1, "required": 2})
    return False


def officer_decide(db: Session, principal: Principal, case: Case, approve: bool, reason: str) -> Case:
    if case.status in OFFICER_FINAL:
        raise HTTPException(status_code=409, detail=f"Case is already {case.status}")
    if approve:
        _refuse_own_case(db, principal, case)
        deceased_name = (case.claim or {}).get("deceased_name", "")
        duplicate = duplicate_of(db, case.claimant_person_id, case.deceased_cnic, deceased_name, exclude_case_id=case.id)
        if duplicate:
            raise HTTPException(status_code=409, detail=f"This claimant has another claim for this pension ({duplicate})")
        if not _approval_complete(db, principal, case, reason):
            return case
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
    if case.status in CLOSE_BLOCKED:
        raise HTTPException(status_code=409, detail=f"A case that is {case.status} cannot be closed")
    case.status = "closed"
    _event(db, case, "closed", principal.id, reason)
    audit.record(db, principal.actor, "CASE_CLOSED", resource=f"case:{case.reference}", case_id=case.id, details={"reason": reason})
    return case
