"""Synthetic mock identities and name variants for the evaluation sets.

Everything is invented and generated from a fixed seed. Every CNIC starts
with 90000 (mock range). Names are built from generic first-name and
surname pools, never copied from any real record.
"""
import random
from dataclasses import dataclass
from datetime import date, timedelta

MALE_FIRST = ("Aslam", "Akram", "Rafiq", "Tariq", "Javed", "Naeem", "Saleem", "Arshad", "Shahid", "Khalid",
              "Zafar", "Nasir", "Imran", "Irfan", "Rizwan", "Farooq", "Yousuf", "Hanif", "Latif", "Sadiq")
FEMALE_FIRST = ("Zainab", "Fatima", "Ayesha", "Rukhsana", "Nasreen", "Shabana", "Parveen", "Kausar", "Rubina", "Shazia",
                "Samina", "Naseem", "Razia", "Tahira", "Sughra", "Bushra", "Nighat", "Farzana", "Yasmeen", "Ghazala")
SURNAMES = ("Khan", "Ahmed", "Hussain", "Ali", "Iqbal", "Butt", "Qureshi", "Shah", "Mirza", "Abbasi",
            "Baloch", "Memon", "Siddiqui", "Ansari", "Rana", "Akhtar", "Sultana", "Jabeen", "Noreen", "Khatoon")
MUHAMMAD_FORMS = ("Mohd.", "M.", "Muhammed", "Mohammad", "Mohammed")
TRANSLITERATIONS = (("ee", "i"), ("oo", "u"), ("ai", "ay"), ("q", "k"), ("a", "aa"), ("i", "ee"), ("u", "o"))
HONORIFIC_PREFIXES = ("Mst. ", "Syed ", "Haji ", "Mrs ")


@dataclass(frozen=True)
class Identity:
    cnic: str
    name: str
    dob: date
    gender: str  # M | F


class CnicPool:
    """Unique mock CNICs: 90000 + 8 digits."""

    def __init__(self, rng: random.Random, start: int = 10_000_000):
        self._rng = rng
        self._used: set[str] = set()
        self._start = start

    def new(self) -> str:
        while True:
            cnic = f"90000{self._rng.randrange(self._start, 99_999_999):08d}"
            if cnic not in self._used:
                self._used.add(cnic)
                return cnic

    def one_digit_off(self, cnic: str) -> str:
        """A different, unused CNIC that differs from `cnic` in exactly one digit after the mock prefix."""
        while True:
            pos = self._rng.randrange(5, len(cnic))
            digit = str((int(cnic[pos]) + self._rng.randrange(1, 10)) % 10)
            other = cnic[:pos] + digit + cnic[pos + 1:]
            if other not in self._used:
                self._used.add(other)
                return other


def random_dob(rng: random.Random, first_year: int = 1945, last_year: int = 1975) -> date:
    start = date(first_year, 1, 1)
    return start + timedelta(days=rng.randrange((date(last_year, 12, 31) - start).days))


def make_identity(rng: random.Random, cnics: CnicPool, gender: str, *, surname: str | None = None,
                  muhammad: bool | None = None, dob: date | None = None) -> Identity:
    surname = surname or rng.choice(SURNAMES)
    if gender == "M":
        use_muhammad = rng.random() < 0.5 if muhammad is None else muhammad
        name = f"{'Muhammad ' if use_muhammad else ''}{rng.choice(MALE_FIRST)} {surname}"
    else:
        name = f"{rng.choice(FEMALE_FIRST)} {surname}"
    return Identity(cnics.new(), name, dob or random_dob(rng), gender)


def _transliterate(rng: random.Random, name: str) -> str:
    options = [(a, b) for a, b in TRANSLITERATIONS if a in name.lower() and a != b]
    if not options:
        return name
    a, b = rng.choice(options)
    idx = name.lower().index(a)
    replacement = b if not name[idx].isupper() else b.capitalize()
    return name[:idx] + replacement + name[idx + len(a):]


def _typo(rng: random.Random, name: str) -> str:
    letters = [i for i, ch in enumerate(name) if ch.isalpha()]
    i = rng.choice(letters[1:-1] or letters)
    if rng.random() < 0.5:
        return name[:i] + name[i + 1:]  # dropped letter
    j = i + 1 if i + 1 < len(name) and name[i + 1].isalpha() else i - 1
    lo, hi = sorted((i, j))
    return name[:lo] + name[hi] + name[lo] + name[hi + 1:]  # swapped letters


def name_variant(rng: random.Random, name: str, *, relation_name: str | None = None) -> tuple[str, str]:
    """A plausible way the same person's name appears on another document. Returns (variant, kind)."""
    kinds = ["transliteration", "honorific", "order", "typo", "relation", "first_name_only"]
    if "Muhammad" in name:
        kinds += ["muhammad_form", "muhammad_form", "drop_muhammad"]
    kind = rng.choice(kinds)
    parts = name.split()
    if kind == "muhammad_form":
        return name.replace("Muhammad", rng.choice(MUHAMMAD_FORMS)), kind
    if kind == "drop_muhammad":
        return name.replace("Muhammad ", ""), kind
    if kind == "transliteration":
        return _transliterate(rng, name), kind
    if kind == "honorific":
        return (rng.choice(HONORIFIC_PREFIXES) + name) if rng.random() < 0.6 else f"{name} Bibi", kind
    if kind == "order":
        return " ".join(parts[1:] + parts[:1]), kind
    if kind == "typo":
        return _typo(rng, name), kind
    if kind == "relation" and relation_name:
        return f"{name} {rng.choice(('s/o', 'w/o', 'd/o'))} {relation_name}", kind
    if kind == "first_name_only" and len(parts) > 1:
        core = [p for p in parts if p != "Muhammad"]
        return core[0], kind
    return name.upper(), "case_only"


def entered_dob(rng: random.Random, true_dob: date, *, p_exact: float = 0.7, p_missing: float = 0.15,
                p_off_by_one: float = 0.05) -> tuple[date | None, str]:
    """How a claimant types her date of birth: mostly right, sometimes skipped, sometimes wrong."""
    roll = rng.random()
    if roll < p_exact:
        return true_dob, "exact"
    if roll < p_exact + p_missing:
        return None, "missing"
    if roll < p_exact + p_missing + p_off_by_one:
        return true_dob + timedelta(days=1), "off_by_one"
    return true_dob.replace(year=true_dob.year + rng.choice((-2, -1, 1, 3))), "different"
