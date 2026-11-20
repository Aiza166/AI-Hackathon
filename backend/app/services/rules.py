"""Rule versions: validate drafts, Digital Twin simulation, publish.

Published versions are never edited: a change is a new version. Every decision
keeps the id of the version it used, so old cases still show "decided under v1"
after v2 goes live.
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
from app.services.cases import RULESET, live_ruleset, ruleset_dict

MAX_SIMULATED_CASES = 200


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


def publish(db: Session, principal: Principal, draft: RuleVersion) -> RuleVersion:
    if draft.status != "draft":
        raise HTTPException(status_code=409, detail=f"Version {draft.version} is already {draft.status}")
    current = live_ruleset(db)
    current.status = "retired"
    draft.status = "live"
    draft.published_at = utcnow()
    added = sorted({r["id"] for r in draft.rules} - {r["id"] for r in current.rules})
    removed = sorted({r["id"] for r in current.rules} - {r["id"] for r in draft.rules})
    audit.record(db, principal.actor, "RULES_PUBLISHED", resource=f"rule_version:{draft.id}",
                 details={"from_version": current.version, "to_version": draft.version, "rules_added": added, "rules_removed": removed})
    return draft


def version_or_404(db: Session, version_id: str) -> RuleVersion:
    row = db.get(RuleVersion, version_id, with_for_update=True)
    if row is None:
        raise HTTPException(status_code=404, detail="Rule version not found")
    return row
