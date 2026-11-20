"""Gather the evidence (signals) for one claim from the mock services.

Everything here is deterministic code. Jev is not used for claim facts in
Phase 1 (it is used for documents and scam messages in later phases).
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.decision.matching import MatchResult, match_identity, name_similarity, parse_name
from app.mock import registry
from app.models.platform import Case, Person
from app.schemas.claims import ClaimIn

ACTIVE_STATUSES = ("submitted", "auto_approved", "proof_requested", "in_review", "approved")
CANDIDATE_MIN_SIMILARITY = 70


@dataclass
class Signals:
    facts: dict = field(default_factory=dict)  # input to the rules engine
    claimant_match: MatchResult | None = None
    deceased_matches: dict = field(default_factory=dict)  # source -> MatchResult
    payee: str = "no_match"  # match | close_match | no_match
    payee_owner_ok: bool = False
    duplicate_claims: list = field(default_factory=list)  # suspicious other claims
    co_sharers: list = field(default_factory=list)  # lawful co-claimants (e.g. second widow in FRC)
    account_reuse: list = field(default_factory=list)
    candidates: list = field(default_factory=list)  # when the deceased CNIC is missing
    service_down: list = field(default_factory=list)

    def to_dict(self) -> dict:
        def m(r: MatchResult | None) -> dict | None:
            return None if r is None else {"p": r.probability, "route": r.route, "levels": r.levels, "weights": r.weights, "reasons": list(r.reasons)}

        return {
            "facts": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in self.facts.items()},
            "claimant_match": m(self.claimant_match),
            "deceased_matches": {k: m(v) for k, v in self.deceased_matches.items()},
            "payee": self.payee,
            "payee_owner_ok": self.payee_owner_ok,
            "duplicate_claims": self.duplicate_claims,
            "co_sharers": self.co_sharers,
            "account_reuse": self.account_reuse,
            "candidates": self.candidates,
            "service_down": self.service_down,
        }


def _age(dob: date | None, today: date) -> int | None:
    if dob is None:
        return None
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _key_token(name: str) -> str:
    tokens = [t for t in parse_name(name).tokens if t != "muhammad"]
    return max(tokens, key=len) if tokens else name.split()[-1]


def _find_candidates(db: Session, claim: ClaimIn, signals: Signals) -> None:
    for person in registry.find_persons_by_name_key(db, _key_token(claim.deceased_name)):
        score = name_similarity(claim.deceased_name, person.full_name)
        if score >= CANDIDATE_MIN_SIMILARITY:
            signals.candidates.append({"cnic": person.cnic, "name": person.full_name, "name_score": round(score, 1)})


def _match_deceased(db: Session, claim: ClaimIn, cnic: str, signals: Signals) -> None:
    record = registry.get_person(db, cnic)
    death = registry.get_death(db, cnic)
    pension = registry.get_pension(db, cnic)
    signals.facts["death_verified"] = death is not None
    signals.facts["pension_found"] = pension is not None and pension.status == "active"
    if record is None:
        return
    signals.deceased_matches["claim_vs_identity"] = match_identity(claim.deceased_name, record.full_name, claimed_cnic=cnic, record_cnic=record.cnic)
    if death is not None:
        signals.deceased_matches["death_certificate_vs_identity"] = match_identity(death.name_on_certificate, record.full_name, claimed_cnic=death.cnic, record_cnic=record.cnic)
        signals.facts["date_of_death"] = death.date_of_death
    if pension is not None:
        signals.deceased_matches["pension_office_vs_identity"] = match_identity(pension.name_in_pension_office, record.full_name, claimed_cnic=pension.pensioner_cnic, record_cnic=record.cnic)


def _family_facts(db: Session, claim: ClaimIn, deceased_cnic: str, signals: Signals) -> None:
    family = registry.get_family(db, deceased_cnic)
    members = {m.member_cnic: m.relation for m in family}
    relation = members.get(claim.claimant_cnic)
    signals.facts["frc_links_claimant"] = relation in ("wife", "son", "daughter")
    signals.facts["relation"] = {"wife": "widow"}.get(relation, relation) if relation else claim.relation_claimed
    wives_alive, wife_death_dates = [], []
    for cnic, rel in members.items():
        if rel != "wife":
            continue
        death = registry.get_death(db, cnic)
        if death is None:
            wives_alive.append(cnic)
        else:
            wife_death_dates.append(death.date_of_death)
    signals.facts["spouse_alive_eligible"] = bool(wives_alive)
    signals.facts["lawful_widows_count"] = max(len(wives_alive), 1)
    signals.facts["eligible_children_count"] = sum(1 for r in members.values() if r in ("son", "daughter"))
    date_of_death = signals.facts.get("date_of_death")
    if signals.facts["relation"] == "widow":
        signals.facts["became_eligible_on"] = date_of_death
    else:
        signals.facts["became_eligible_on"] = max(wife_death_dates) if wife_death_dates else date_of_death
    # Everyone in the FRC who could lawfully share this pension (widows, sons, daughters).
    signals.facts["_frc_family"] = sorted(c for c, r in members.items() if r in ("wife", "son", "daughter"))


def _claimant_facts(db: Session, claim: ClaimIn, signals: Signals, today: date) -> None:
    record = registry.get_person(db, claim.claimant_cnic)
    if record is None:
        return
    signals.claimant_match = match_identity(
        claim.claimant_name, record.full_name,
        claimed_cnic=claim.claimant_cnic, record_cnic=record.cnic,
        claimed_dob=claim.claimant_dob, record_dob=record.dob,
    )
    signals.facts["claimant_dob"] = record.dob  # NADRA CNIC DOB is the single source of truth
    signals.facts["claimant_age"] = _age(record.dob, today)
    signals.facts["claimant_marital_status"] = record.marital_status
    signals.facts["claimant_disabled"] = record.disabled
    signals.facts["already_draws_family_pension"] = registry.already_draws_family_pension(db, claim.claimant_cnic) is not None
    signals.facts["_claimant_registry_name"] = record.full_name


def _payee(db: Session, claim: ClaimIn, signals: Signals) -> None:
    """Mock Confirmation of Payee: match / close match / no match on the account title."""
    account = registry.get_account(db, claim.payout_iban)
    registry_name = signals.facts.get("_claimant_registry_name", claim.claimant_name)
    if account is None:
        signals.payee = "no_match"
        return
    signals.payee_owner_ok = account.owner_cnic == claim.claimant_cnic
    score = name_similarity(account.title, registry_name)
    if not signals.payee_owner_ok or score < 70:
        signals.payee = "no_match"
    elif score >= 95:
        signals.payee = "match"
    else:
        signals.payee = "close_match"


def _other_claims(db: Session, case: Case, claim: ClaimIn, signals: Signals) -> None:
    family = set(signals.facts.get("_frc_family", []))
    others = db.execute(
        select(Case, Person.cnic).join(Person, Person.id == Case.claimant_person_id).where(
            Case.id != case.id, Case.status.in_(ACTIVE_STATUSES), Case.claimant_person_id != case.claimant_person_id,
            or_(Case.deceased_cnic == claim.deceased_cnic, Case.payout_iban == claim.payout_iban),
        ).limit(50)
    ).all()
    for other, other_cnic in others:
        if claim.deceased_cnic and other.deceased_cnic == claim.deceased_cnic:
            entry = {"case": other.reference, "claimant_cnic_last4": other_cnic[-4:]}
            # A claimant in the FRC is a lawful co-sharer; anyone else is a red flag.
            (signals.co_sharers if other_cnic in family else signals.duplicate_claims).append(entry)
        if other.payout_iban == claim.payout_iban:
            signals.account_reuse.append({"case": other.reference})


def gather(db: Session, case: Case, claim: ClaimIn, today: date) -> Signals:
    signals = Signals()
    signals.facts.update({"documents": list(claim.documents), "today": today})
    try:
        _claimant_facts(db, claim, signals, today)
        if claim.deceased_cnic is None:
            _find_candidates(db, claim, signals)
            return signals
        _match_deceased(db, claim, claim.deceased_cnic, signals)
        _family_facts(db, claim, claim.deceased_cnic, signals)
        _payee(db, claim, signals)
        _other_claims(db, case, claim, signals)
    except registry.MockServiceUnavailable as exc:
        signals.service_down.append(exc.service)
    return signals
