"""Rule versions: validate drafts, Digital Twin simulation, publish.

Published versions are never edited: a change is a new version. Every decision
keeps the id of the version it used, so old cases still show "decided under v1"
after v2 goes live.
"""
import json
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal
from app.decision.engine import decide
from app.decision.facts import gather
from app.decision.rules import OPERATORS, RULE_KINDS
from app.models.audit import AuditEvent
from app.models.platform import Case, Decision, RuleVersion, utcnow
from app.schemas.claims import ClaimIn
from app.services.cases import RULESET, live_ruleset, ruleset_dict

MAX_SIMULATED_CASES = 200
MAX_CONDITION_DEPTH = 5  # nested any_of/all_of levels (L2): deeper drafts are refused, never recursed
MAX_RULES_JSON_BYTES = 64_000
SIMULATION_MAX_AGE = timedelta(hours=24)  # a publish needs a Digital Twin run this recent (H6)


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def _check_condition(condition: object, where: str, depth: int = 1) -> None:
    if depth > MAX_CONDITION_DEPTH:
        raise _invalid(f"{where}: conditions may nest at most {MAX_CONDITION_DEPTH} levels")
    if not isinstance(condition, dict):
        raise _invalid(f"{where}: each condition must be an object")
    if "any_of" in condition or "all_of" in condition:
        groups = [condition.get("any_of", []), condition.get("all_of", [])]
        if not all(isinstance(g, list) for g in groups):
            raise _invalid(f"{where}: any_of and all_of must be lists")
        for inner in groups[0] + groups[1]:
            _check_condition(inner, where, depth + 1)
        return
    if "fact" not in condition or condition.get("op") not in OPERATORS:
        raise _invalid(f"{where}: each condition needs a fact and a known op ({', '.join(sorted(OPERATORS))})")


def _check_size(rules: list, thresholds: dict) -> None:
    try:
        size = len(json.dumps({"rules": rules, "thresholds": thresholds}, default=str))
    except (TypeError, ValueError, RecursionError):
        raise _invalid("Rules must be plain JSON") from None
    if size > MAX_RULES_JSON_BYTES:
        raise _invalid(f"Rules are too large (max {MAX_RULES_JSON_BYTES} bytes)")


def _check_thresholds(thresholds: dict) -> None:
    values = [thresholds.get("t_human", 0), thresholds.get("t_auto", 0)]
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        raise _invalid("Thresholds must be numbers")
    if not 0 < values[0] < values[1] <= 1:
        raise _invalid("Thresholds must satisfy 0 < t_human < t_auto <= 1")


def _check_rule(rule: object, seen: set[str]) -> None:
    if not isinstance(rule, dict):
        raise _invalid("Each rule must be an object")
    rule_id = rule.get("id")
    kind = rule.get("kind", "gate")
    if not isinstance(rule_id, str) or not rule_id or rule_id in seen or kind not in RULE_KINDS:
        raise _invalid(f"Rule {rule_id!r}: needs a unique id and kind in {sorted(RULE_KINDS)}")
    seen.add(rule_id)
    conditions = [rule.get("applies_if", []), rule.get("require", [])]
    if not all(isinstance(c, list) for c in conditions):
        raise _invalid(f"Rule {rule_id}: applies_if and require must be lists")
    for condition in conditions[0] + conditions[1]:
        _check_condition(condition, rule_id)
    if kind == "gate" and (rule.get("on_fail") not in ("not_eligible", "missing_info") or not rule.get("reason")):
        raise _invalid(f"Rule {rule_id}: gate rules need on_fail and reason")
    limit = rule.get("limit", {})
    if kind == "limit" and (not isinstance(limit, dict) or "default_years" not in limit):
        raise _invalid(f"Rule {rule_id}: limit rules need limit.default_years")


def validate_rules(rules: list, thresholds: dict) -> None:
    """Reject malformed drafts (422, never 500) before they can ever decide a case."""
    if not isinstance(rules, list) or not isinstance(thresholds, dict):
        raise _invalid("rules must be a list and thresholds an object")
    _check_size(rules, thresholds)
    _check_thresholds(thresholds)
    seen: set[str] = set()
    for rule in rules:
        _check_rule(rule, seen)


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
        rows.append({"case": case.reference, "status": case.status, "before": before, "after": after, "changed": changed})
    db.rollback()  # belt and braces: the simulation must never persist anything
    changed_count = sum(1 for r in rows if r["changed"])
    audit.record(db, principal.actor, "RULES_SIMULATED", resource=f"rule_version:{draft.id}",
                 details={"version": draft.version, "checked": len(rows), "changed": changed_count})
    db.commit()
    return {"draft_version": draft.version, "checked": len(rows), "changed": changed_count, "cases": rows}


def _events(db: Session, action: str, draft: RuleVersion) -> list[AuditEvent]:
    return list(db.execute(
        select(AuditEvent).where(AuditEvent.action == action, AuditEvent.resource == f"rule_version:{draft.id}").order_by(AuditEvent.seq)
    ).scalars())


def _latest_simulation(db: Session, draft: RuleVersion) -> AuditEvent:
    runs = _events(db, "RULES_SIMULATED", draft)
    if not runs or runs[-1].ts < utcnow() - SIMULATION_MAX_AGE:
        raise HTTPException(status_code=409, detail="Run the Digital Twin on this draft first (within the last 24 hours)")
    return runs[-1]


def approve(db: Session, principal: Principal, draft: RuleVersion) -> RuleVersion:
    """A second admin signs off on a simulated draft. The publisher must be someone else."""
    if draft.status != "draft":
        raise HTTPException(status_code=409, detail=f"Version {draft.version} is already {draft.status}")
    simulation = _latest_simulation(db, draft)
    audit.record(db, principal.actor, "RULES_APPROVED", resource=f"rule_version:{draft.id}",
                 details={"version": draft.version, "simulation_seq": simulation.seq})
    return draft


def _require_second_admin(db: Session, principal: Principal, draft: RuleVersion, simulation: AuditEvent) -> AuditEvent:
    approvals = [e for e in _events(db, "RULES_APPROVED", draft) if e.seq > simulation.seq and e.actor_id != principal.id]
    if not approvals:
        raise HTTPException(status_code=409, detail="A second admin must approve this draft after the latest Digital Twin run")
    return approvals[-1]


def publish(db: Session, principal: Principal, draft: RuleVersion, today: date | None = None) -> RuleVersion:
    """Publish a simulated, second-admin-approved draft. A future effective_from schedules it:
    the current version keeps deciding until that date (live_ruleset picks by date)."""
    if draft.status != "draft":
        raise HTTPException(status_code=409, detail=f"Version {draft.version} is already {draft.status}")
    today = today or date.today()
    simulation = _latest_simulation(db, draft)
    approval = _require_second_admin(db, principal, draft, simulation)
    current = live_ruleset(db, today)
    scheduled = draft.effective_from is not None and draft.effective_from > today
    if not scheduled:
        current.status = "retired"
    draft.status = "scheduled" if scheduled else "live"
    draft.published_at = utcnow()
    added = sorted({r["id"] for r in draft.rules} - {r["id"] for r in current.rules})
    removed = sorted({r["id"] for r in current.rules} - {r["id"] for r in draft.rules})
    audit.record(db, principal.actor, "RULES_PUBLISHED", resource=f"rule_version:{draft.id}",
                 details={"from_version": current.version, "to_version": draft.version, "rules_added": added,
                          "rules_removed": removed, "status": draft.status,
                          "effective_from": draft.effective_from.isoformat() if draft.effective_from else None,
                          "approved_by": approval.actor_id, "simulation_seq": simulation.seq})
    return draft


def version_or_404(db: Session, version_id: str) -> RuleVersion:
    row = db.get(RuleVersion, version_id, with_for_update=True)
    if row is None:
        raise HTTPException(status_code=404, detail="Rule version not found")
    return row
