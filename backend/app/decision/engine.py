"""Turn signals + versioned rules into one of three routes.

    AUTO_APPROVE  confidence >= t_auto (0.95) and no red flags
    ASK_PROOF     something specific is missing, or 0.70 <= confidence < 0.95
    UNSURE        "I am not sure": any red flag, a service outage, or < 0.70

The system never rejects anyone by itself. Why 0.95: a wrong approval costs
about 20x a delay, so approve only when p > 20 / (20 + 1) = 0.952.
"""
from dataclasses import dataclass

from app.decision.facts import Signals
from app.decision.rules import RuleResult, evaluate
from app.schemas.contracts import ReasonCode, Route


@dataclass(frozen=True)
class Outcome:
    route: Route
    reasons: tuple[ReasonCode, ...]
    confidence: float
    rule_result: RuleResult
    missing_items: tuple[str, ...]


def _hard_flags(signals: Signals, rules: RuleResult) -> list[ReasonCode]:
    flags: list[ReasonCode] = []
    if signals.duplicate_claims:
        flags.append(ReasonCode.DUPLICATE_CLAIM)
    if signals.account_reuse:
        flags.append(ReasonCode.ACCOUNT_REUSED)
    if signals.payee == "no_match":
        flags.append(ReasonCode.ACCOUNT_NOT_OWNED)
    identity_unsure = [m for m in [signals.claimant_match, *signals.deceased_matches.values()] if m and m.route == "UNSURE"]
    if identity_unsure:
        flags.append(ReasonCode.NAME_MISMATCH)
    if rules.outcome == "not_eligible":
        flags.extend(ReasonCode(h.reason) for h in rules.hits if h.outcome == "not_eligible")
    return flags


def _needs_proof(signals: Signals, rules: RuleResult) -> tuple[list[ReasonCode], list[str]]:
    reasons: list[ReasonCode] = []
    missing = [h.missing_item for h in rules.hits if h.outcome == "missing_info" and h.missing_item]
    reasons.extend(ReasonCode(h.reason) for h in rules.hits if h.outcome == "missing_info")
    if signals.payee == "close_match":
        reasons.append(ReasonCode.PAYEE_CLOSE_MATCH)
        missing.append("payout_account_confirmation")
    if any(m and m.route == "ASK" for m in [signals.claimant_match, *signals.deceased_matches.values()]):
        reasons.append(ReasonCode.NAME_MISMATCH)
    return reasons, missing


def _confidence(signals: Signals) -> float:
    """Conservative: the weakest link decides (min over identity matches and relationship)."""
    probs = [m.probability for m in [signals.claimant_match, *signals.deceased_matches.values()] if m]
    relationship = 1.0 if signals.facts.get("frc_links_claimant") else 0.0
    if signals.claimant_match is None:
        probs.append(0.0)  # claimant not found in the identity registry
    return round(min([*probs, relationship]), 4)


def _unique(codes: list[ReasonCode]) -> tuple[ReasonCode, ...]:
    return tuple(dict.fromkeys(codes))


def decide(signals: Signals, ruleset: dict) -> Outcome:
    thresholds = ruleset["thresholds"]
    empty = RuleResult("missing_info")
    if signals.service_down:
        return Outcome(Route.UNSURE, (ReasonCode.SERVICE_UNAVAILABLE,), 0.0, empty, ())
    if "death_verified" not in signals.facts:
        # Deceased CNIC missing: never pick a person by name alone.
        code = ReasonCode.MULTIPLE_CANDIDATES if len(signals.candidates) > 1 else ReasonCode.MISSING_INFO
        route = Route.UNSURE if len(signals.candidates) > 1 else Route.ASK_PROOF
        return Outcome(route, (code,), 0.0, empty, ("deceased_cnic",))

    rules = evaluate(ruleset, signals.facts)
    confidence = _confidence(signals)
    flags = _hard_flags(signals, rules)
    if flags:
        return Outcome(Route.UNSURE, _unique(flags), confidence, rules, ())
    proof_reasons, missing = _needs_proof(signals, rules)
    if proof_reasons:
        return Outcome(Route.ASK_PROOF, _unique(proof_reasons), confidence, rules, tuple(missing))
    if confidence >= thresholds["t_auto"]:
        approved = [ReasonCode.APPROVED] + ([ReasonCode.TIME_LIMITED] if rules.entitlement_end else [])
        return Outcome(Route.AUTO_APPROVE, tuple(approved), confidence, rules, ())
    if confidence >= thresholds["t_human"]:
        return Outcome(Route.ASK_PROOF, (ReasonCode.LOW_CONFIDENCE,), confidence, rules, ())
    return Outcome(Route.UNSURE, (ReasonCode.LOW_CONFIDENCE,), confidence, rules, ())
