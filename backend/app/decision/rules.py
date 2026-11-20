"""A small rules engine: eligibility rules are data (JSON), not code.

Rules are stored as versioned rows in `rule_versions`, so an admin can publish
a new version without a code change or redeploy, and every decision records
which version it used. Rules never reject anyone: `not_eligible` only sends
the case to an officer.

Rule kinds:
  gate   - applies_if + require; if a requirement fails -> on_fail outcome + reason
  limit  - applies_if; sets an entitlement end date (e.g. the 10-year cap)
  share  - computes each claimant's share of the pension
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Any

OUTCOME_ORDER = {"eligible": 0, "missing_info": 1, "not_eligible": 2}
RULE_KINDS = frozenset({"gate", "limit", "share"})
OPERATORS = frozenset({"is_true", "is_false", "eq", "ne", "in", "not_in", "contains", "date_gte", "date_lt", "gte", "lte"})


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    outcome: str
    reason: str
    missing_item: str | None = None


@dataclass(frozen=True)
class RuleResult:
    outcome: str  # eligible | missing_info | not_eligible
    hits: tuple[RuleHit, ...] = ()
    entitlement_end: date | None = None
    share: str | None = None
    evaluated: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "hits": [h.__dict__ for h in self.hits],
            "entitlement_end": self.entitlement_end.isoformat() if self.entitlement_end else None,
            "share": self.share,
            "evaluated": list(self.evaluated),
        }


def _as_date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def check(condition: dict, facts: dict) -> bool:
    if "any_of" in condition:
        return any(check(c, facts) for c in condition["any_of"])
    if "all_of" in condition:
        return all(check(c, facts) for c in condition["all_of"])
    value = facts.get(condition["fact"])
    op, target = condition["op"], condition.get("value")
    if op == "is_true":
        return value is True
    if op == "is_false":
        return value is False
    if op == "eq":
        return value == target
    if op == "ne":
        return value != target
    if op == "in":
        return value in target
    if op == "not_in":
        return value not in target
    if op == "contains":
        return target in (value or [])
    if value is None:
        return False  # missing data never satisfies a numeric or date comparison
    if op in ("date_gte", "date_lt"):
        left, right = _as_date(value), _as_date(target)
        return left >= right if op == "date_gte" else left < right
    if op == "gte":
        return value >= target
    if op == "lte":
        return value <= target
    raise ValueError(f"unknown operator {op}")


def _gate(rule: dict, facts: dict) -> RuleHit | None:
    if all(check(c, facts) for c in rule.get("require", [])):
        return None
    return RuleHit(rule["id"], rule["on_fail"], rule["reason"], rule.get("missing_item"))


def _add_years(start: date, years: int) -> date:
    try:
        return start.replace(year=start.year + years)
    except ValueError:  # 29 Feb
        return start.replace(year=start.year + years, day=28)


def _limit(rule: dict, facts: dict) -> date | None:
    """Entitlement end date, or None for no limit (e.g. disabled child: for life)."""
    limit = rule["limit"]
    if facts.get("claimant_disabled") and limit.get("disabled") == "life":
        return None
    start = _as_date(facts["became_eligible_on"])
    end = _add_years(start, limit["default_years"])
    child_age = limit.get("child_until_age")
    dob = _as_date(facts.get("claimant_dob"))
    if child_age and dob and facts.get("relation") in ("son", "daughter"):
        end = max(end, _add_years(dob, child_age))
    return end


def _share(rule: dict, facts: dict) -> str:
    widows = facts.get("lawful_widows_count", 1)
    children = facts.get("eligible_children_count", 0)
    n = max(widows + children, 1)
    if n <= rule["max_equal_split"]:
        return f"1/{n}"
    return "1/4 (widow)" if facts.get("relation") == "widow" else f"remainder split among {children} children"


def evaluate(ruleset: dict, facts: dict) -> RuleResult:
    hits: list[RuleHit] = []
    evaluated: list[str] = []
    entitlement_end = None
    share = None
    for rule in ruleset["rules"]:
        if not all(check(c, facts) for c in rule.get("applies_if", [])):
            continue
        evaluated.append(rule["id"])
        kind = rule.get("kind", "gate")
        if kind == "gate":
            hit = _gate(rule, facts)
            if hit:
                hits.append(hit)
        elif kind == "limit":
            entitlement_end = _limit(rule, facts)
            hits.append(RuleHit(rule["id"], "eligible", rule["reason"]))
        elif kind == "share":
            share = _share(rule, facts)
    outcome = max((h.outcome for h in hits), key=OUTCOME_ORDER.__getitem__, default="eligible")
    return RuleResult(outcome, tuple(hits), entitlement_end, share, tuple(evaluated))
