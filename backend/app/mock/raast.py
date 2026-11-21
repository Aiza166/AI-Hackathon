"""Mock Raast-style title fetch with our own Confirmation-of-Payee verdict on top.

Real Raast (System Rules Nov 2021, s.3.8) returns the account title and type for a
person to read, not a match verdict, and banks must answer within one minute. The
MATCH / CLOSE_MATCH / NO_MATCH verdict, the CNIC cross-check and the SINGLE/JOINT
holding are OUR design, simulated here (docs/research/round2.md section 2).

Routing (our design): MATCH only when the name is canonically equal, the CNIC matches
and the account is SINGLE. A name variant or a JOINT account is CLOSE_MATCH (ask for
proof: federal pensions must not go to a joint account under AGPR's DCS). NO_MATCH or
a CNIC conflict goes to an officer. UNAVAILABLE or TIMEOUT goes to an officer and never
pays. The CNIC itself is never returned, only `cnic_match`.
"""
import re
import time
from dataclasses import asdict, dataclass, field

from sqlalchemy.orm import Session

from app.decision.matching import name_similarity
from app.mock import registry

SERVICE = "raast"
BANK_CODE = "MOCKBANK"
RAAST_LIMIT_MS = 60_000  # Raast participants must answer a title fetch within 1 minute
SLOW_AS_TIMEOUT_MS = 2_000  # in the demo, an injected delay this long stands for the 1-minute timeout
MATCH_SCORE = 95
CLOSE_SCORE = 70
JOINT_SPLIT = re.compile(r"\s*(?:&|\band\b|/)\s*", re.I)

# Verdict -> payee result used by claims and SafeSwitch, and the route it leads to.
PAYEE_FOR_LEVEL = {"MATCH": "match", "CLOSE_MATCH": "close_match", "NO_MATCH": "no_match", "UNAVAILABLE": "unavailable"}
ROUTE_FOR_LEVEL = {"MATCH": "OK", "CLOSE_MATCH": "ASK_PROOF", "NO_MATCH": "UNSURE", "UNAVAILABLE": "UNSURE"}


@dataclass(frozen=True)
class TitleFetch:
    status: str  # OK | ACCOUNT_NOT_FOUND | UNAVAILABLE | TIMEOUT
    match_level: str  # MATCH | CLOSE_MATCH | NO_MATCH | UNAVAILABLE
    masked_title: str | None = None
    account_type: str | None = None  # ACCOUNT | WALLET
    account_holding: str | None = None  # SINGLE | JOINT
    bank_code: str | None = None
    cnic_match: bool | None = None
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    latency_ms: int = 0
    simulated: bool = True

    @property
    def payee(self) -> str:
        return PAYEE_FOR_LEVEL[self.match_level]

    @property
    def route(self) -> str:
        return ROUTE_FOR_LEVEL[self.match_level]

    @property
    def reachable(self) -> bool:
        return self.status in ("OK", "ACCOUNT_NOT_FOUND")

    def to_dict(self) -> dict:
        return {**asdict(self), "reason_codes": list(self.reason_codes), "route": self.route}


def mask_name(title: str) -> str:
    """'ZAINAB BIBI' -> 'ZA**** BI**'. Each word keeps its first two letters."""
    return " ".join(word[:2] + "*" * max(len(word) - 2, 0) for word in title.split())


def _holders(title: str, holding: str) -> list[str]:
    return [p for p in JOINT_SPLIT.split(title) if p] if holding == "JOINT" else [title]


def _injected_fault(db: Session) -> TitleFetch | None:
    mode = registry.fault_mode(db, SERVICE)
    if mode == "timeout":
        return TitleFetch("TIMEOUT", "UNAVAILABLE", reason_codes=("TIMEOUT",), latency_ms=RAAST_LIMIT_MS)
    if mode == "error":
        return TitleFetch("UNAVAILABLE", "UNAVAILABLE", reason_codes=("SERVICE_UNAVAILABLE",))
    if mode == "slow":
        latency = db.get(registry.MockFault, SERVICE).latency_ms
        if latency >= SLOW_AS_TIMEOUT_MS:
            return TitleFetch("TIMEOUT", "UNAVAILABLE", reason_codes=("TIMEOUT",), latency_ms=RAAST_LIMIT_MS)
        time.sleep(latency / 1000)
    return None


def _verdict(name_score: float, cnic_match: bool, holding: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not cnic_match:
        reasons.append("CNIC_MISMATCH")
    if holding == "JOINT":
        reasons.append("JOINT_ACCOUNT")
    if name_score < CLOSE_SCORE:
        reasons.append("NAME_MISMATCH")
    elif name_score < MATCH_SCORE:
        reasons.append("NAME_VARIANT")
    if not cnic_match or name_score < CLOSE_SCORE:
        return "NO_MATCH", reasons
    if holding == "JOINT" or name_score < MATCH_SCORE:
        return "CLOSE_MATCH", reasons
    return "MATCH", reasons


def title_fetch(db: Session, iban: str, expected_name: str, expected_cnic: str | None) -> TitleFetch:
    """Look up the account behind an IBAN and compare it with who should be paid."""
    started = time.monotonic()
    fault = _injected_fault(db)
    if fault is not None:
        return fault
    try:
        account = registry.get_account(db, iban)
    except registry.MockServiceUnavailable:
        return TitleFetch("UNAVAILABLE", "UNAVAILABLE", reason_codes=("SERVICE_UNAVAILABLE",))
    latency = int((time.monotonic() - started) * 1000)
    if account is None:
        return TitleFetch("ACCOUNT_NOT_FOUND", "NO_MATCH", reason_codes=("ACCOUNT_NOT_FOUND",), latency_ms=latency)
    holders = _holders(account.title, account.holding)
    score = max(name_similarity(holder, expected_name) for holder in holders)
    cnic_match = bool(expected_cnic) and account.owner_cnic == expected_cnic
    level, reasons = _verdict(score, cnic_match, account.holding)
    return TitleFetch(
        "OK", level, masked_title=" & ".join(mask_name(h) for h in holders), account_type=account.account_type,
        account_holding=account.holding, bank_code=BANK_CODE, cnic_match=cnic_match, reason_codes=tuple(reasons),
        latency_ms=latency,
    )
