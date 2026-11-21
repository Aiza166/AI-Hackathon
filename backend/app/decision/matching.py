"""Name and identity matching for Pakistani names.

Pipeline (docs/research/survivor-pension.md section 3):
parse -> canonicalise -> score (Fellegi-Sunter style log2(m/u) weights) -> route.
Rules that never bend: no match without an exact CNIC, "muhammad" carries
little evidence, phonetic codes and token_set_ratio are never used as evidence.
"""
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from rapidfuzz import fuzz

RELATION_MARKERS = {"s/o", "w/o", "d/o", "bin", "bint", "ibn"}
HONORIFICS = {"syed", "sheikh", "shaikh", "haji", "hajji", "chaudhry", "chaudhary", "malik", "begum", "bibi", "mst", "mrs", "mr", "miss"}
MUHAMMAD_VARIANTS = {"muhammad", "mohammad", "mohammed", "muhammed", "mohamad", "mohamed", "mohd", "md", "muhamad"}
COMMON_TOKEN = "muhammad"

# log2(m/u) weights per field level. m = P(level | same person), u = P(level | different people).
# These are design values to tune on the synthetic set, not published figures.
CNIC_WEIGHTS = {"exact": math.log2(0.98 / 1e-6), "one_digit": math.log2(0.01 / 1e-4), "different": math.log2(0.01 / 0.99), "missing": 0.0}
NAME_WEIGHTS = {"ge95": math.log2(0.85 / 0.002), "85_95": math.log2(0.10 / 0.01), "70_85": math.log2(0.03 / 0.05), "lt70": math.log2(0.02 / 0.938)}
DOB_WEIGHTS = {"exact": math.log2(0.95 / 1e-4), "plus_minus_1": math.log2(0.01 / 5e-4), "year": math.log2(0.03 / 0.01), "different": math.log2(0.01 / 0.99), "missing": 0.0}
PRIOR_WEIGHT = math.log2(1 / 1000)  # before evidence, a random pair is very unlikely to match

MATCH_P = 0.95
REVIEW_P = 0.70


@dataclass(frozen=True)
class ParsedName:
    tokens: tuple[str, ...]  # canonical tokens, honorifics removed
    honorifics: tuple[str, ...]
    relation_name: tuple[str, ...]  # text after s/o, w/o, d/o (weak evidence)


@dataclass(frozen=True)
class MatchResult:
    probability: float
    route: str  # MATCH | ASK | UNSURE
    levels: dict = field(default_factory=dict)
    weights: dict = field(default_factory=dict)
    reasons: tuple[str, ...] = ()


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"\b([swd])\s*/\s*o\b", r"\1/o", text)  # "s / o" -> "s/o"
    text = re.sub(r"[.,'\"()\-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def canonical_token(token: str) -> str:
    return COMMON_TOKEN if token in MUHAMMAD_VARIANTS else token


def parse_name(raw: str) -> ParsedName:
    main: list[str] = []
    relation: list[str] = []
    honorifics: list[str] = []
    target = main
    for word in _plain(raw).split(" "):
        if not word:
            continue
        if word in RELATION_MARKERS:
            target = relation
            continue
        if word in HONORIFICS:
            honorifics.append(word)
            continue
        target.append(canonical_token(word))
    return ParsedName(tuple(main), tuple(honorifics), tuple(relation))


def _expand_initial(a: tuple[str, ...], b: tuple[str, ...]) -> tuple[str, ...]:
    """Expand a bare 'm' initial to 'muhammad' only if the other name has it."""
    if "m" in a and COMMON_TOKEN in b:
        return tuple(COMMON_TOKEN if t == "m" else t for t in a)
    return a


def name_similarity(a_raw: str, b_raw: str) -> float:
    a, b = parse_name(a_raw).tokens, parse_name(b_raw).tokens
    a, b = _expand_initial(a, b), _expand_initial(b, a)
    # Down-weight "muhammad": compare the distinctive tokens when both have any.
    a_core = [t for t in a if t != COMMON_TOKEN] or list(a)
    b_core = [t for t in b if t != COMMON_TOKEN] or list(b)
    return fuzz.token_sort_ratio(" ".join(a_core), " ".join(b_core))


def name_level(score: float) -> str:
    if score >= 95:
        return "ge95"
    if score >= 85:
        return "85_95"
    if score >= 70:
        return "70_85"
    return "lt70"


def cnic_level(a: str | None, b: str | None) -> str:
    if not a or not b:
        return "missing"
    if a == b:
        return "exact"
    if len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1:
        return "one_digit"
    return "different"


def dob_level(a: date | None, b: date | None) -> str:
    if a is None or b is None:
        return "missing"
    if a == b:
        return "exact"
    if abs((a - b).days) <= 1:
        return "plus_minus_1"
    if a.year == b.year:
        return "year"
    return "different"


def match_identity(
    claimed_name: str,
    record_name: str,
    *,
    claimed_cnic: str | None,
    record_cnic: str | None,
    claimed_dob: date | None = None,
    record_dob: date | None = None,
    match_p: float = MATCH_P,
) -> MatchResult:
    score = name_similarity(claimed_name, record_name)
    levels = {
        "name": name_level(score),
        "name_score": round(score, 1),
        "cnic": cnic_level(claimed_cnic, record_cnic),
        "dob": dob_level(claimed_dob, record_dob),
    }
    weights = {
        "prior": round(PRIOR_WEIGHT, 2),
        "name": round(NAME_WEIGHTS[levels["name"]], 2),
        "cnic": round(CNIC_WEIGHTS[levels["cnic"]], 2),
        "dob": round(DOB_WEIGHTS[levels["dob"]], 2),
    }
    probability = 1 / (1 + 2 ** (-sum(weights.values())))
    route, reasons = _route(probability, levels, match_p)
    return MatchResult(round(probability, 4), route, levels, weights, reasons)


def _route(probability: float, levels: dict, match_p: float = MATCH_P) -> tuple[str, tuple[str, ...]]:
    if levels["cnic"] == "different":
        return "UNSURE", ("CNIC conflict",)
    if levels["name"] == "lt70":
        return "UNSURE", ("name does not match the record",)
    if levels["cnic"] != "exact":
        return "ASK", ("no exact CNIC: a match is never accepted without it",)
    if probability >= match_p:
        return "MATCH", ()
    if probability >= REVIEW_P:
        return "ASK", ("match not strong enough",)
    return "UNSURE", ("low match probability",)
