"""Labelled synthetic claim-decision set and the T_AUTO cost sweep (Challenge 1).

Each case is an in-memory description of what the mock services would return
(identity record, FRC link, death record, payee check, other claims). For every
threshold the case is turned into `Signals` and run through the real
`app.decision.engine.decide` (which calls `app.decision.rules.evaluate`).
Nothing touches the database.

Ground truth `should_approve` says whether paying this claimant is right.
Cost model (from the ruleset thresholds): an auto-approval of a claim that
should not be paid costs C_wrong; any genuine claim that is not auto-approved
costs C_delay (it waits for proof or an officer). An officer catching a bad
claim costs nothing extra.
"""
import random
from dataclasses import dataclass, replace
from datetime import date

from app.decision.engine import decide
from app.decision.facts import Signals
from app.decision.matching import match_identity
from app.evaluation.synth import CnicPool, Identity, entered_dob, make_identity, name_variant, random_dob
from app.schemas.contracts import Route

SEED = 20261122
TODAY = date(2026, 11, 22)
ALL_DOCS = ("death_certificate", "claimant_cnic", "frc", "nikah_nama")
# category -> (count, should_approve)
CATEGORIES = {
    "clean": (40, True),
    "name_variant_same_person": (40, True),
    "lookalike_different_person": (30, False),
    "duplicate_claimant": (20, None),  # half genuine, half not (see _duplicate)
    "missing_document": (25, True),
    "payee_close_match": (15, True),
    "payee_no_match": (15, False),
    "already_drawing": (15, False),
}
SWEEP_START, SWEEP_END, SWEEP_STEP = 0.50, 0.99, 0.01
# Wrong approvals are reported by kind. "Full credentials" means the impostor typed the
# victim's real CNIC, exact name and exact DOB: no data match can tell them apart. In the
# app the claimant CNIC must belong to the logged-in user's own linked person (or a family
# that consented to a helper), so this attack needs an account takeover, not just data.
FULL_CREDENTIALS = "identity theft with full credentials"
IMPOSTOR_KINDS = {"stolen full identity": FULL_CREDENTIALS,
                  "stolen CNIC number, guessed details": "stolen CNIC, guessed details"}


@dataclass(frozen=True)
class ClaimCase:
    case_id: str
    category: str
    should_approve: bool
    claimant_record: Identity  # what the identity registry holds for the CNIC typed in
    claimant_name_entered: str
    claimant_dob_entered: date | None
    deceased_record: Identity
    deceased_name_entered: str
    name_on_death_certificate: str
    name_in_pension_office: str
    date_of_death: date
    documents: tuple[str, ...] = ALL_DOCS
    frc_links_claimant: bool = True
    payee: str = "match"
    duplicate_claims: int = 0
    already_drawing: bool = False
    note: str = ""


def _base(rng: random.Random, cnics: CnicPool, idx: int, category: str, label: bool) -> ClaimCase:
    deceased = make_identity(rng, cnics, "M")
    widow = make_identity(rng, cnics, "F", dob=random_dob(rng, 1950, 1980))
    dod = date(2026, rng.randrange(1, 11), rng.randrange(1, 28))
    return ClaimCase(f"C{idx:03d}", category, label, widow, widow.name, widow.dob, deceased, deceased.name,
                     deceased.name, deceased.name, dod)


def _with_noise(rng: random.Random, case: ClaimCase) -> ClaimCase:
    """Genuine claimants: names on documents vary, typed DOB is sometimes skipped or wrong."""
    dob, _ = entered_dob(rng, case.claimant_record.dob)
    cert = name_variant(rng, case.deceased_record.name)[0] if rng.random() < 0.5 else case.deceased_record.name
    pension = name_variant(rng, case.deceased_record.name)[0] if rng.random() < 0.3 else case.deceased_record.name
    return replace(case, claimant_dob_entered=dob, name_on_death_certificate=cert, name_in_pension_office=pension)


def _name_variant_case(rng: random.Random, case: ClaimCase) -> ClaimCase:
    case = _with_noise(rng, case)
    claimant = name_variant(rng, case.claimant_record.name, relation_name=case.deceased_record.name.split()[-1])[0]
    deceased = name_variant(rng, case.deceased_record.name)[0]
    return replace(case, claimant_name_entered=claimant, deceased_name_entered=deceased)


def _lookalike(rng: random.Random, case: ClaimCase, cnics: CnicPool, i: int) -> ClaimCase:
    """A different person. Most use their own CNIC (not in this FRC); some typed the widow's CNIC
    from a photocopy and guess the name/DOB; two know everything (no data check can stop them)."""
    if i % 3 == 0:  # own CNIC, similar name: registry returns the impostor's own record
        impostor = make_identity(rng, cnics, "F", surname=case.claimant_record.name.split()[-1])
        return replace(case, claimant_record=impostor, claimant_name_entered=impostor.name,
                       claimant_dob_entered=impostor.dob, frc_links_claimant=False, payee="match", note="own CNIC")
    if i in (1, 2):  # knows CNIC, exact name and DOB, and has an account in the widow's name
        return replace(case, payee="match", note="stolen full identity")
    guess_name = name_variant(rng, case.claimant_record.name)[0]
    guess_dob = case.claimant_record.dob.replace(year=case.claimant_record.dob.year + rng.choice((-3, -1, 2, 4)))
    payee = "match" if rng.random() < 0.5 else "no_match"
    return replace(case, claimant_name_entered=guess_name, claimant_dob_entered=rng.choice((guess_dob, None)),
                   payee=payee, note="stolen CNIC number, guessed details")


def _build(rng: random.Random, cnics: CnicPool, idx: int, category: str, label: bool | None, i: int) -> ClaimCase:
    case = _base(rng, cnics, idx, category, bool(label))
    if category == "clean":
        return case
    if category == "name_variant_same_person":
        return _name_variant_case(rng, case)
    if category == "lookalike_different_person":
        return _lookalike(rng, case, cnics, i)
    case = _with_noise(rng, case)
    if category == "duplicate_claimant":
        return replace(case, should_approve=i % 2 == 0, duplicate_claims=1,
                       note="real widow, someone else filed too" if i % 2 == 0 else "outsider filed second claim")
    if category == "missing_document":
        missing = rng.choice(ALL_DOCS)
        return replace(case, documents=tuple(d for d in ALL_DOCS if d != missing), note=f"missing {missing}")
    if category == "payee_close_match":
        return replace(case, payee="close_match")
    if category == "payee_no_match":
        return replace(case, payee="no_match", note="account not in claimant's name")
    if category == "already_drawing":
        return replace(case, already_drawing=True)
    raise ValueError(category)


def generate_cases(seed: int = SEED) -> list[ClaimCase]:
    rng = random.Random(seed)
    cnics = CnicPool(rng)
    cases: list[ClaimCase] = []
    for category, (count, label) in CATEGORIES.items():
        for i in range(count):
            cases.append(_build(rng, cnics, len(cases) + 1, category, label, i))
    return cases


def _age(dob: date) -> int:
    return TODAY.year - dob.year - ((TODAY.month, TODAY.day) < (dob.month, dob.day))


def to_signals(case: ClaimCase, match_p: float) -> Signals:
    rec, dec = case.claimant_record, case.deceased_record
    facts = {
        "documents": list(case.documents), "today": TODAY, "frc_links_claimant": case.frc_links_claimant,
        "relation": "widow", "death_verified": True, "pension_found": True,
        "spouse_alive_eligible": True, "lawful_widows_count": 1, "eligible_children_count": 0,
        "date_of_death": case.date_of_death, "became_eligible_on": case.date_of_death,
        "claimant_dob": rec.dob, "claimant_age": _age(rec.dob), "claimant_marital_status": "widowed",
        "claimant_disabled": False, "already_draws_family_pension": case.already_drawing,
    }

    def m(claimed: str, cnic: str, record: Identity, claimed_dob: date | None = None, record_dob: date | None = None,
          require_dob: bool = False):
        return match_identity(claimed, record.name, claimed_cnic=cnic, record_cnic=record.cnic,
                              claimed_dob=claimed_dob, record_dob=record_dob, match_p=match_p, require_dob=require_dob)

    return Signals(
        facts=facts,
        # Same as the app (facts._claimant_facts): the claimant's typed DOB must equal the record.
        claimant_match=m(case.claimant_name_entered, rec.cnic, rec, case.claimant_dob_entered, rec.dob, require_dob=True),
        deceased_matches={
            "claim_vs_identity": m(case.deceased_name_entered, dec.cnic, dec),
            "death_certificate_vs_identity": m(case.name_on_death_certificate, dec.cnic, dec),
            "pension_office_vs_identity": m(case.name_in_pension_office, dec.cnic, dec),
        },
        payee=case.payee,
        payee_owner_ok=case.payee != "no_match",
        duplicate_claims=[{"case": "SP-MOCK"}] * case.duplicate_claims,
    )


def _with_threshold(ruleset: dict, t: float) -> dict:
    return {**ruleset, "thresholds": {**ruleset["thresholds"], "t_auto": t}}


def run_at(cases: list[ClaimCase], ruleset: dict, t: float) -> list[tuple[ClaimCase, Route, float]]:
    """T_AUTO drives both the engine threshold and the identity matcher's MATCH cut-off (same 0.95 idea)."""
    rs = _with_threshold(ruleset, t)
    return [(c, (o := decide(to_signals(c, t), rs)).route, o.confidence) for c in cases]


def score(results: list[tuple[ClaimCase, Route, float]], c_wrong: float, c_delay: float, t: float) -> dict:
    n = len(results)
    auto = [(c, r) for c, r, _ in results if r == Route.AUTO_APPROVE]
    wrong = sum(1 for c, _ in auto if not c.should_approve)
    delayed = sum(1 for c, r, _ in results if c.should_approve and r != Route.AUTO_APPROVE)
    ask = sum(1 for _, r, _ in results if r == Route.ASK_PROOF)
    unsure = sum(1 for _, r, _ in results if r == Route.UNSURE)
    return {
        "threshold": round(t, 2), "total_cost": wrong * c_wrong + delayed * c_delay,
        "wrong_approvals": wrong, "delayed_genuine": delayed,
        "auto_approve_rate": round(len(auto) / n, 4), "ask_proof_rate": round(ask / n, 4),
        "human_rate": round(unsure / n, 4), "needs_person_rate": round((ask + unsure) / n, 4),
    }


def thresholds() -> list[float]:
    steps = round((SWEEP_END - SWEEP_START) / SWEEP_STEP)
    return [round(SWEEP_START + i * SWEEP_STEP, 2) for i in range(steps + 1)]


def _by_category(results: list[tuple[ClaimCase, Route, float]]) -> dict:
    out: dict[str, dict] = {}
    for c, r, _ in results:
        row = out.setdefault(c.category, {"n": 0, "should_approve": 0, "AUTO_APPROVE": 0, "ASK_PROOF": 0, "UNSURE": 0})
        row["n"] += 1
        row["should_approve"] += int(c.should_approve)
        row[r.value] += 1
    return out


def evaluate_claims(ruleset: dict, seed: int = SEED) -> dict:
    cfg = ruleset["thresholds"]
    c_wrong, c_delay = cfg["cost_wrong_approval"], cfg["cost_delay"]
    configured = cfg["t_auto"]
    cases = generate_cases(seed)
    sweep = [score(run_at(cases, ruleset, t), c_wrong, c_delay, t) for t in thresholds()]
    best_cost = min(row["total_cost"] for row in sweep)
    best = [row["threshold"] for row in sweep if row["total_cost"] == best_cost]
    at_configured = run_at(cases, ruleset, configured)
    wrong_cases = [{"case_id": c.case_id, "category": c.category, "note": c.note,
                    "kind": IMPOSTOR_KINDS.get(c.note, "other")}
                   for c, r, _ in at_configured if r == Route.AUTO_APPROVE and not c.should_approve]
    by_kind: dict[str, int] = {}
    for w in wrong_cases:
        by_kind[w["kind"]] = by_kind.get(w["kind"], 0) + 1
    return {
        "seed": seed, "n_cases": len(cases), "n_should_approve": sum(c.should_approve for c in cases),
        "cost_wrong_approval": c_wrong, "cost_delay": c_delay,
        "analytic_threshold": round(c_wrong / (c_wrong + c_delay), 4),
        "configured_threshold": configured,
        "min_cost": {"threshold": best[0], "range": [best[0], best[-1]], "total_cost": best_cost},
        "at_configured": score(at_configured, c_wrong, c_delay, configured),
        "baseline_never_auto": len([c for c in cases if c.should_approve]) * c_delay,
        "by_category_at_configured": _by_category(at_configured),
        "wrong_approvals_at_configured": wrong_cases,
        "wrong_approvals_by_kind_at_configured": by_kind,
        "sweep": sweep,
    }
