"""Rule versions: validate drafts, Digital Twin simulation, publish.

Published versions are never edited: a change is a new version. Every decision
keeps the id of the version it used, so old cases still show "decided under v1"
after v2 goes live.

Publishing re-decides only cases nobody has decided yet (still pending) whose
entitlement starts on or after the new version's effective date, because the
law in force on that date applies to them. Cases already decided (approved,
auto-approved, rejected, closed, withdrawn) are never touched.

Known limit: later re-decisions of a pending case (a new document, a related claim) use the live
version, whatever the entitlement date. A per-case version choice by entitlement date is not built.
"""
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal
from app.decision.engine import decide
from app.decision.facts import gather
from app.decision.rules import OPERATORS, RULE_KINDS
from app.models.platform import Case, Decision, RuleVersion, utcnow
from app.schemas.claims import ClaimIn
from app.services.cases import RULESET, live_ruleset, ruleset_dict, run_decision

MAX_SIMULATED_CASES = 200
MAX_REDECIDED_CASES = 200  # bound the work one publish can trigger
# Not decided yet: no officer decision and no auto-approval. Only these can move to a new rule version.
PENDING_STATUSES = ("submitted", "proof_requested", "in_review")


def _check_condition(condition: dict, where: str) -> None:
    if "any_of" in condition or "all_of" in condition:
        for inner in condition.get("any_of", []) + condition.get("all_of", []):
            _check_condition(inner, where)
        return
    if "fact" not in condition or condition.get("op") not in OPERATORS:
        raise HTTPException(status_code=422, detail=f"{where}: each condition needs a fact and a known op ({', '.join(sorted(OPERATORS))})")


def validate_rules(rules: list, thresholds: dict) -> None:
    """Reject malformed drafts before they can ever decide a case."""
    if not 0 < thresholds.get("t_human", 0) < thresholds.get("t_auto", 0) <= 1:
        raise HTTPException(status_code=422, detail="Thresholds must satisfy 0 < t_human < t_auto <= 1")
    seen: set[str] = set()
    for rule in rules:
        rule_id = rule.get("id")
        kind = rule.get("kind", "gate")
        if not rule_id or rule_id in seen or kind not in RULE_KINDS:
            raise HTTPException(status_code=422, detail=f"Rule {rule_id!r}: needs a unique id and kind in {sorted(RULE_KINDS)}")
        seen.add(rule_id)
        for condition in rule.get("applies_if", []) + rule.get("require", []):
            _check_condition(condition, rule_id)
        if kind == "gate" and (rule.get("on_fail") not in ("not_eligible", "missing_info") or not rule.get("reason")):
            raise HTTPException(status_code=422, detail=f"Rule {rule_id}: gate rules need on_fail and reason")
        if kind == "limit" and "default_years" not in rule.get("limit", {}):
            raise HTTPException(status_code=422, detail=f"Rule {rule_id}: limit rules need limit.default_years")


def create_draft(db: Session, principal: Principal, label: str, rules: list, thresholds: dict, effective_from: date | None) -> RuleVersion:
    validate_rules(rules, thresholds)
    next_version = (db.execute(select(func.max(RuleVersion.version)).where(RuleVersion.ruleset == RULESET)).scalar() or 0) + 1
    draft = RuleVersion(ruleset=RULESET, version=next_version, label=label, effective_from=effective_from,
                        rules=rules, thresholds=thresholds, status="draft", created_by=principal.id)
    db.add(draft)
    db.flush()
    audit.record(db, principal.actor, "RULES_DRAFTED", resource=f"rule_version:{draft.id}", details={"version": next_version, "label": label})
    return draft


def _latest_decisions(db: Session, tenant_id: str) -> list[tuple[Case, Decision]]:
    latest = select(Decision.case_id, func.max(Decision.created_at).label("at")).group_by(Decision.case_id).subquery()
    rows = db.execute(
        select(Case, Decision)
        .join(latest, latest.c.case_id == Case.id)
        .join(Decision, (Decision.case_id == Case.id) & (Decision.created_at == latest.c.at))
        .where(Case.tenant_id == tenant_id)
        .order_by(Case.created_at)
        .limit(MAX_SIMULATED_CASES)
    ).all()
    return [(c, d) for c, d in rows]


def _summary(route: str, reasons: list, rule_result: dict) -> dict:
    return {"route": route, "reasons": list(reasons), "entitlement_end": rule_result.get("entitlement_end")}


def applies_on_publish(case: Case, became_eligible_on: date | None, draft: RuleVersion) -> bool:
    """Will publishing `draft` re-decide this case? Only pending cases whose entitlement
    starts on or after the draft's effective date (no effective date: never)."""
    if case.status not in PENDING_STATUSES or draft.effective_from is None or became_eligible_on is None:
        return False
    return became_eligible_on >= draft.effective_from


def simulate(db: Session, principal: Principal, draft: RuleVersion, today: date | None = None) -> dict:
    """Digital Twin: re-decide past cases under the draft. Reads only; nothing is saved
    except one audit event saying the simulation ran."""
    today = today or date.today()
    ruleset = ruleset_dict(draft)
    rows = []
    for case, decision in _latest_decisions(db, principal.tenant_id):
        signals = gather(db, case, ClaimIn.model_validate(case.claim), today)
        outcome = decide(signals, ruleset)
        before = _summary(decision.route, decision.reason_codes, decision.rule_result)
        after = _summary(outcome.route.value, [r.value for r in outcome.reasons], outcome.rule_result.to_dict())
        changed = [k for k in before if before[k] != after[k]]
        applies = applies_on_publish(case, signals.facts.get("became_eligible_on"), draft)
        rows.append({"case": case.reference, "status": case.status, "before": before, "after": after, "changed": changed,
                     "applies_on_publish": applies})
    db.rollback()  # belt and braces: the simulation must never persist anything
    changed_count = sum(1 for r in rows if r["changed"])
    will_redecide = sum(1 for r in rows if r["applies_on_publish"])
    audit.record(db, principal.actor, "RULES_SIMULATED", resource=f"rule_version:{draft.id}",
                 details={"version": draft.version, "checked": len(rows), "changed": changed_count, "will_redecide": will_redecide})
    db.commit()
    return {"draft_version": draft.version, "checked": len(rows), "changed": changed_count, "will_redecide": will_redecide, "cases": rows}


def _redecide_pending(db: Session, principal: Principal, draft: RuleVersion, from_version: int, today: date) -> list[str]:
    """Re-decide pending cases the new version now governs (see module docstring). Audited per case."""
    audit.lock_chain(db)
    pending = db.execute(
        select(Case).where(Case.tenant_id == principal.tenant_id, Case.status.in_(PENDING_STATUSES))
        .order_by(Case.created_at).limit(MAX_REDECIDED_CASES).with_for_update()
    ).scalars().all()
    redecided = []
    for case in pending:
        signals = gather(db, case, ClaimIn.model_validate(case.claim), today)
        if not applies_on_publish(case, signals.facts.get("became_eligible_on"), draft):
            continue
        held_by_officer, priority = case.status == "in_review", case.priority
        decision = run_decision(db, case, today=today, ruleset_row=draft)
        if held_by_officer:  # a re-decision never takes a case away from the officer holding it
            case.status, case.priority = "in_review", max(priority, case.priority)
        audit.record(db, principal.actor, "CASE_REDECIDED", resource=f"case:{case.reference}", case_id=case.id, tenant_id=case.tenant_id,
                     details={"from_version": from_version, "to_version": draft.version, "decision_id": decision.id,
                              "entitlement_end": decision.rule_result.get("entitlement_end"), "status": case.status})
        redecided.append(case.reference)
    return redecided


def publish(db: Session, principal: Principal, draft: RuleVersion, today: date | None = None) -> RuleVersion:
    if draft.status != "draft":
        raise HTTPException(status_code=409, detail=f"Version {draft.version} is already {draft.status}")
    current = live_ruleset(db)
    current.status = "retired"
    draft.status = "live"
    draft.published_at = utcnow()
    db.flush()
    added = sorted({r["id"] for r in draft.rules} - {r["id"] for r in current.rules})
    removed = sorted({r["id"] for r in current.rules} - {r["id"] for r in draft.rules})
    redecided = _redecide_pending(db, principal, draft, current.version, today or date.today())
    audit.record(db, principal.actor, "RULES_PUBLISHED", resource=f"rule_version:{draft.id}",
                 details={"from_version": current.version, "to_version": draft.version, "rules_added": added,
                          "rules_removed": removed, "redecided_cases": redecided})
    return draft


def version_or_404(db: Session, version_id: str) -> RuleVersion:
    row = db.get(RuleVersion, version_id, with_for_update=True)
    if row is None:
        raise HTTPException(status_code=404, detail="Rule version not found")
    return row
