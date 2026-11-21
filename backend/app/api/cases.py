"""Case endpoints for citizens, helpers, officers, admins and auditors."""
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import Principal, deny, get_principal, require_roles
from app.core.consent import assert_consent
from app.core.ratelimit import limiter
from app.core.envelope import ok
from app.db import get_db
from app.decision.explanations import explain
from app.models.platform import Case, Decision, HelperAssignment, RuleVersion
from app.schemas.claims import AssignIn, CaseView, CitizenExplanation, ClaimIn, DecisionSummary, OfficerAction
from app.schemas.contracts import ReasonCode, Role
from app.services import cases as svc
from app.services import idempotency as idem

router = APIRouter(prefix="/api/v1", tags=["cases"])
OFFICER_LIKE = (Role.OFFICER, Role.ADMIN)
STAFF = (Role.OFFICER, Role.ADMIN, Role.AUDITOR)
CAN_ESCALATE = (Role.CITIZEN, Role.HELPER, Role.OFFICER, Role.ADMIN)


def _load(db: Session, principal: Principal, request: Request, case_id: str, lock: bool = False, field: str = "case_details") -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise svc.not_found()
    if not svc.can_view(db, principal, case):
        raise deny(db, principal, request, "not allowed to view this case")
    # Consent is checked on every request (never cached): a withdrawal blocks the very next call.
    assert_consent(db, principal, request, case.claimant_person_id, field)
    if lock:
        # Row lock for state changes, taken after the consent log commit so it is held to the end.
        db.refresh(case, with_for_update=True)
    return case


def _latest_decision(db: Session, case_id: str) -> Decision | None:
    return db.execute(select(Decision).where(Decision.case_id == case_id).order_by(Decision.created_at.desc()).limit(1)).scalar_one_or_none()


def _summary(db: Session, decision: Decision | None) -> DecisionSummary | None:
    if decision is None:
        return None
    version = db.get(RuleVersion, decision.rule_version_id)
    return DecisionSummary(
        id=decision.id, route=decision.route, reason_codes=decision.reason_codes, confidence=decision.confidence,
        rule_version=version.version, rule_version_id=decision.rule_version_id, model_id=decision.model_id, created_at=decision.created_at,
    )


def _view(db: Session, case: Case, principal: Principal | None = None) -> dict:
    is_staff = principal is not None and principal.role in STAFF
    view = CaseView(
        id=case.id, reference=case.reference, status=case.status, priority=case.priority, confidence=case.confidence,
        claimant_person_id=case.claimant_person_id, assigned_officer_id=case.assigned_officer_id if is_staff else None,
        deceased_cnic=case.deceased_cnic, created_at=case.created_at, latest_decision=_summary(db, _latest_decision(db, case.id)),
    )
    return view.model_dump(mode="json")


@router.post("/cases", status_code=201)
@limiter.limit("10/minute")
def create_and_submit(
    request: Request,
    body: ClaimIn,
    principal: Principal = Depends(require_roles(Role.CITIZEN, Role.HELPER)),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """File a claim and run the decision engine on it right away.

    An optional Idempotency-Key header makes retries safe: the same key with the
    same body replays the first response instead of filing a second claim.
    """
    if idempotency_key is None:
        return _file_claim(db, principal, request, body)
    key = idem.validate_key(idempotency_key)
    replay = idem.begin(db, principal.id, key, body.model_dump(mode="json"))
    if replay is not None:
        return JSONResponse(status_code=replay.status, content=replay.body)
    try:
        result = _file_claim(db, principal, request, body)
    except Exception:
        idem.abandon(db, principal.id, key)
        raise
    idem.finish(db, principal.id, key, 201, result)
    return result


def _file_claim(db: Session, principal: Principal, request: Request, body: ClaimIn) -> dict:
    if principal.role == Role.HELPER:
        # A helper may only file for a family that has shared its details with this helper.
        person = svc.person_by_cnic(db, body.claimant_cnic)
        if person is not None:
            assert_consent(db, principal, request, person.id, "case_details")
    case = svc.create_case(db, principal, body)
    svc.run_decision(db, case, created_by=principal)
    affected = svc.recheck_related(db, case)
    db.commit()
    # Never reveal other people's claims to citizens/helpers: they only get a count.
    meta = {"rechecked_cases": affected} if principal.role in STAFF else {"rechecked_count": len(affected)}
    return ok(_view(db, case, principal), meta=meta)


@router.get("/cases")
def list_cases(request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    query = select(Case).order_by(Case.created_at.desc())
    if principal.role == Role.CITIZEN:
        query = query.where(Case.claimant_person_id == principal.person_id)
    elif principal.role == Role.HELPER:
        assigned = select(HelperAssignment.person_id).where(HelperAssignment.helper_user_id == principal.id)
        query = query.where(Case.claimant_person_id.in_(assigned))
    elif principal.role in STAFF:
        query = query.where(Case.tenant_id == principal.tenant_id)
    else:  # e.g. API keys: never list cases
        raise deny(db, principal, request, "role cannot list cases")
    return ok([_view(db, c, principal) for c in db.execute(query.limit(200)).scalars()])


@router.get("/cases/{case_id}")
def get_case(case_id: str, request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    return ok(_view(db, _load(db, principal, request, case_id), principal))


@router.get("/cases/{case_id}/explanation")
def citizen_explanation(case_id: str, request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    """The simple view: fixed Urdu/English sentences with icon and audio key."""
    case = _load(db, principal, request, case_id)
    decision = _latest_decision(db, case.id)
    codes = decision.reason_codes if decision else []
    if case.status == "approved":
        codes = [ReasonCode.APPROVED.value]
    result = CitizenExplanation(
        case_reference=case.reference, status=case.status, route=decision.route if decision else None,
        explanations=[explain(ReasonCode(c)) for c in codes],
        missing_items=(decision.rule_result.get("missing_items", []) if decision else []),
        entitlement_end=(decision.rule_result.get("entitlement_end") if decision else None),
    )
    return ok(result.model_dump(mode="json"))


@router.get("/cases/{case_id}/decisions")
def case_decisions(
    case_id: str, request: Request,
    principal: Principal = Depends(require_roles(Role.OFFICER, Role.ADMIN, Role.AUDITOR)),
    db: Session = Depends(get_db),
) -> dict:
    case = _load(db, principal, request, case_id)
    rows = db.execute(select(Decision).where(Decision.case_id == case.id).order_by(Decision.created_at)).scalars()
    return ok([_summary(db, d).model_dump(mode="json") for d in rows])


@router.get("/decisions/{decision_id}/trace")
def decision_trace(
    decision_id: str, request: Request,
    principal: Principal = Depends(require_roles(Role.OFFICER, Role.ADMIN, Role.AUDITOR)),
    db: Session = Depends(get_db),
) -> dict:
    """The auditor view: input hash, rule version, every signal, confidence, thresholds, route."""
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise svc.not_found()
    case = _load(db, principal, request, decision.case_id)
    version = db.get(RuleVersion, decision.rule_version_id)
    return ok({
        "decision_id": decision.id, "case_reference": case.reference, "created_at": decision.created_at.isoformat(),
        "route": decision.route, "reason_codes": decision.reason_codes, "confidence": decision.confidence,
        "thresholds": decision.thresholds, "rule_version": {"id": version.id, "version": version.version, "label": version.label},
        "model_id": decision.model_id, "input_hash": decision.input_hash, "signals": decision.signals,
        "rule_result": decision.rule_result, "jev_raw": decision.jev_raw,
    })


@router.get("/queue")
def officer_queue(principal: Principal = Depends(require_roles(*OFFICER_LIKE)), db: Session = Depends(get_db)) -> dict:
    """Cases waiting for a human: highest priority first, then lowest confidence."""
    query = (
        select(Case)
        .where(Case.tenant_id == principal.tenant_id, Case.status.in_(("in_review", "proof_requested")))
        .order_by(Case.priority.desc(), Case.confidence.asc().nulls_first(), Case.created_at)
    )
    return ok([_view(db, c, principal) for c in db.execute(query).scalars()])


@router.post("/cases/{case_id}/approve")
def approve(case_id: str, body: OfficerAction, request: Request, principal: Principal = Depends(require_roles(Role.OFFICER)), db: Session = Depends(get_db)) -> dict:
    case = svc.officer_decide(db, principal, _load(db, principal, request, case_id, lock=True), approve=True, reason=body.reason)
    db.commit()
    return ok(_view(db, case, principal))


@router.post("/cases/{case_id}/reject")
def reject(case_id: str, body: OfficerAction, request: Request, principal: Principal = Depends(require_roles(Role.OFFICER)), db: Session = Depends(get_db)) -> dict:
    case = svc.officer_decide(db, principal, _load(db, principal, request, case_id, lock=True), approve=False, reason=body.reason)
    db.commit()
    return ok(_view(db, case, principal))


@router.post("/cases/{case_id}/assign")
def assign(case_id: str, body: AssignIn, request: Request, principal: Principal = Depends(require_roles(*OFFICER_LIKE)), db: Session = Depends(get_db)) -> dict:
    case = svc.assign(db, principal, _load(db, principal, request, case_id, lock=True), body.officer_id)
    db.commit()
    return ok(_view(db, case, principal))


@router.post("/cases/{case_id}/escalate")
def escalate(case_id: str, body: OfficerAction, request: Request, principal: Principal = Depends(require_roles(*CAN_ESCALATE)), db: Session = Depends(get_db)) -> dict:
    """Claimants, helpers and staff (not auditors: they are read-only) can ask for a human."""
    case = svc.escalate(db, principal, _load(db, principal, request, case_id, lock=True), body.reason)
    db.commit()
    return ok(_view(db, case, principal))


@router.post("/cases/{case_id}/close")
def close(case_id: str, body: OfficerAction, request: Request, principal: Principal = Depends(require_roles(*OFFICER_LIKE)), db: Session = Depends(get_db)) -> dict:
    case = svc.close(db, principal, _load(db, principal, request, case_id, lock=True), body.reason)
    db.commit()
    return ok(_view(db, case, principal))
