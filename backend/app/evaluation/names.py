"""Name-matching evaluation (Challenge 3): ~500 synthetic identity pairs through match_identity.

Positives: the same person written differently (Muhammad forms, transliteration,
honorifics, word order, typos, s/o w/o d/o, first name only), with the CNIC
typed correctly (5% contain a one-digit CNIC typo) and DOB exact, missing,
off by one day, or wrong.

Hard negatives: different people who look alike on paper.
  same_full_name        identical name, different CNIC and DOB
  same_name_birth_year  identical name, same birth year, different CNIC
  siblings              same surname, different first name, close DOB, different CNIC
  cnic_one_digit_off    identical name, CNIC differs in one digit (another person's record)

Separately reported (not in the headline rates): exact_cnic_impostor, someone
who typed another person's real CNIC with a guessed name variant and a wrong
or missing DOB. Pairs are scored the way the app scores a claimant
(require_dob=True): MATCH needs the typed DOB to equal the record, so a wrong
or blank DOB routes ASK.

A "false match" is a negative routed MATCH. A "false non-match" is a positive
not routed MATCH (it goes to ASK or UNSURE: slower, but safe).
"""
import random
from collections import Counter
from datetime import timedelta

from app.decision.matching import MATCH_P, REVIEW_P, match_identity
from app.evaluation.synth import CnicPool, entered_dob, make_identity, name_variant, random_dob

SEED = 7_2026
N_POSITIVE = 250
NEGATIVE_KINDS = ("same_full_name", "same_name_birth_year", "siblings", "cnic_one_digit_off")
N_PER_NEGATIVE_KIND = 63  # 4 x 63 = 252 negatives
CNIC_TYPO_RATE = 0.05
N_IMPOSTOR = 40


def _positive(rng: random.Random, cnics: CnicPool) -> dict:
    person = make_identity(rng, cnics, rng.choice("MF"))
    variant, kind = name_variant(rng, person.name, relation_name=rng.choice(("Aslam", "Rafiq", "Khan")))
    dob, dob_kind = entered_dob(rng, person.dob)
    typo = rng.random() < CNIC_TYPO_RATE
    claimed_cnic = cnics.one_digit_off(person.cnic) if typo else person.cnic
    return {"label": "same", "kind": "cnic_typo" if typo else kind, "dob": dob_kind,
            "args": (variant, person.name, claimed_cnic, person.cnic, dob, person.dob)}


def _negative(rng: random.Random, cnics: CnicPool, kind: str) -> dict:
    gender = rng.choice("MF")
    a = make_identity(rng, cnics, gender)
    if kind == "same_full_name":
        b_name, b_cnic, b_dob = a.name, cnics.new(), random_dob(rng)
    elif kind == "same_name_birth_year":
        b_name, b_cnic = a.name, cnics.new()
        b_dob = a.dob.replace(month=rng.randrange(1, 13), day=rng.randrange(1, 28))
        if b_dob == a.dob:
            b_dob += timedelta(days=40)
    elif kind == "siblings":
        sib = make_identity(rng, cnics, rng.choice("MF"), surname=a.name.split()[-1], muhammad="Muhammad" in a.name)
        while sib.name == a.name:
            sib = make_identity(rng, cnics, sib.gender, surname=a.name.split()[-1])
        b_name, b_cnic, b_dob = sib.name, sib.cnic, a.dob + timedelta(days=rng.randrange(400, 4000))
    else:  # cnic_one_digit_off
        b_name, b_cnic, b_dob = a.name, cnics.one_digit_off(a.cnic), rng.choice((a.dob, random_dob(rng)))
    # The claimant (person B) types their own details; the record belongs to person A.
    claimed_dob = b_dob if rng.random() < 0.8 else None
    return {"label": "different", "kind": kind, "dob": "exact" if claimed_dob else "missing",
            "args": (b_name, a.name, b_cnic, a.cnic, claimed_dob, a.dob)}


def _impostor(rng: random.Random, cnics: CnicPool) -> dict:
    victim = make_identity(rng, cnics, rng.choice("MF"))
    guess = name_variant(rng, victim.name)[0]
    wrong_dob = victim.dob.replace(year=victim.dob.year + rng.choice((-3, -2, 2, 4)))
    claimed_dob = wrong_dob if rng.random() < 0.5 else None
    return {"label": "impostor", "kind": "exact_cnic_impostor", "dob": "different" if claimed_dob else "missing",
            "args": (guess, victim.name, victim.cnic, victim.cnic, claimed_dob, victim.dob)}


def generate_pairs(seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    cnics = CnicPool(rng)
    pairs = [_positive(rng, cnics) for _ in range(N_POSITIVE)]
    for kind in NEGATIVE_KINDS:
        pairs += [_negative(rng, cnics, kind) for _ in range(N_PER_NEGATIVE_KIND)]
    return pairs + [_impostor(rng, cnics) for _ in range(N_IMPOSTOR)]


def _rates(routes: list[str]) -> dict:
    n = len(routes) or 1
    c = Counter(routes)
    return {"n": len(routes), "MATCH": c["MATCH"], "ASK": c["ASK"], "UNSURE": c["UNSURE"],
            "match_rate": round(c["MATCH"] / n, 4), "ask_rate": round(c["ASK"] / n, 4), "unsure_rate": round(c["UNSURE"] / n, 4)}


def evaluate_names(seed: int = SEED) -> dict:
    pairs = generate_pairs(seed)
    rows = []
    for p in pairs:
        claimed, record, claimed_cnic, record_cnic, claimed_dob, record_dob = p["args"]
        result = match_identity(claimed, record, claimed_cnic=claimed_cnic, record_cnic=record_cnic,
                                claimed_dob=claimed_dob, record_dob=record_dob, require_dob=True)
        rows.append((p, result.route))
    pos = [r for p, r in rows if p["label"] == "same"]
    neg = [r for p, r in rows if p["label"] == "different"]
    impostor = [r for p, r in rows if p["label"] == "impostor"]
    by_kind: dict[str, list[str]] = {}
    for p, r in rows:
        by_kind.setdefault(f"{p['label']}:{p['kind']}", []).append(r)
    all_routes = pos + neg
    return {
        "seed": seed, "n_pairs": len(pos) + len(neg), "n_same_person": len(pos), "n_different_person": len(neg),
        "thresholds": {"match_p": MATCH_P, "review_p": REVIEW_P},
        "false_match_rate": round(neg.count("MATCH") / len(neg), 4),
        "false_non_match_rate": round(sum(r != "MATCH" for r in pos) / len(pos), 4),
        "ask_rate": round(all_routes.count("ASK") / len(all_routes), 4),
        "unsure_rate": round(all_routes.count("UNSURE") / len(all_routes), 4),
        "same_person": _rates(pos), "different_person": _rates(neg),
        "exact_cnic_impostor": {**_rates(impostor), "false_match_rate": round(impostor.count("MATCH") / len(impostor), 4),
                                "note": "Not in the headline rates. MATCH needs the typed DOB to equal the record, so a wrong or blank DOB routes ASK."},
        "by_kind": {k: _rates(v) for k, v in sorted(by_kind.items())},
    }
