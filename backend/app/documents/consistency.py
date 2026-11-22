"""Compare fields read from a document with the (mock) government records.

This is the strongest document signal: a CNIC, name, date or certificate number that
disagrees with the registry. Records are read through the same mock service adapters
the decision engine uses (app.mock.registry), so fault injection applies here too.
A field read with low confidence never counts as a mismatch: it becomes "please confirm".
"""
import re
from dataclasses import asdict, dataclass
from datetime import date

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.decision.matching import match_identity, name_similarity
from app.documents.fields import Field, ascii_digits
from app.mock import registry

MISMATCH_MIN_CONFIDENCE = 0.85  # below this an OCR disagreement is "unclear", not a mismatch
NAME_SAME_SCORE = 85  # name_similarity (0-100) for names printed without a CNIC next to them
DOC_NUMBER_SAME_SCORE = 90
DOC_NUMBER_FUZZY_MIN_LEN = 8  # shorter numbers must match exactly
PRINTED_PREFIX = "MOCK"


@dataclass(frozen=True)
class Check:
    field: str
    status: str  # match | mismatch | unclear | not_read | no_record
    read_value: str | None
    record_value: str | None
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _alnum(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _strip_prefix(number: str) -> str:
    """A printed "MOCK" prefix is decoration on our specimen papers, not part of the number."""
    return number[len(PRINTED_PREFIX):] if number.startswith(PRINTED_PREFIX) else number


def same_doc_number(read: str, record: str) -> bool:
    """Exact after normalisation; fuzzy only when both numbers are long enough to carry it.

    The old suffix test accepted "-" or "1" as a match for any number (red team M3).
    """
    a, b = _strip_prefix(_alnum(ascii_digits(read))), _strip_prefix(_alnum(record))
    if not a or not b:
        return False
    if a == b:
        return True
    if min(len(a), len(b)) < DOC_NUMBER_FUZZY_MIN_LEN:
        return False
    return fuzz.ratio(a, b) >= DOC_NUMBER_SAME_SCORE


def _status(agree: bool, read: Field) -> str:
    if agree:
        return "match"
    return "mismatch" if read.confidence >= MISMATCH_MIN_CONFIDENCE else "unclear"


def _compare(name: str, read: Field | None, record: str | None, agree) -> Check:
    if read is None:
        return Check(name, "not_read", None, record)
    if record is None:
        return Check(name, "no_record", read.value, None)
    return Check(name, _status(agree(read.value, record), read), read.value, record)


def _name_check(name: str, read: Field | None, record_name: str | None, read_cnic: str | None, record_cnic: str | None) -> Check:
    """Use the shared matcher: names never match on their own without an exact CNIC."""
    if read is None or record_name is None:
        return _compare(name, read, record_name, lambda a, b: True)
    if read_cnic and record_cnic:
        result = match_identity(read.value, record_name, claimed_cnic=read_cnic, record_cnic=record_cnic)
        agree = result.route == "MATCH"
        return Check(name, _status(agree, read), read.value, record_name, note=f"matcher {result.route} p={result.probability:.3f}")
    score = name_similarity(read.value, record_name)
    return Check(name, _status(score >= NAME_SAME_SCORE, read), read.value, record_name, note=f"name score {score:.0f}")


def _date_equal(read: str, record: str) -> bool:
    return date.fromisoformat(read) == date.fromisoformat(record)


def _value(fields: dict[str, Field], key: str) -> str | None:
    field = fields.get(key)
    return field.value if field else None


def _cnic_card(db: Session, fields: dict[str, Field], expected_cnic: str | None) -> list[Check]:
    checks = [_compare("cnic", fields.get("cnic"), expected_cnic, lambda a, b: a == b)]
    record = registry.get_person(db, expected_cnic) if expected_cnic else None
    if record is not None:
        checks.append(_name_check("name", fields.get("name"), record.full_name, _value(fields, "cnic"), record.cnic))
        dob = record.dob.isoformat() if record.dob else None
        checks.append(_compare("date_of_birth", fields.get("date_of_birth"), dob, _date_equal))
    return checks


def _death_certificate(db: Session, fields: dict[str, Field], deceased_cnic: str | None) -> list[Check]:
    checks = [_compare("deceased_cnic", fields.get("deceased_cnic"), deceased_cnic, lambda a, b: a == b)]
    if not deceased_cnic:
        return checks
    record = registry.get_person(db, deceased_cnic)
    death = registry.get_death(db, deceased_cnic)
    if record is not None:
        read_cnic = _value(fields, "deceased_cnic") or deceased_cnic  # the claim names this person by CNIC
        checks.append(_name_check("name_of_deceased", fields.get("name_of_deceased"), record.full_name, read_cnic, record.cnic))
    if death is None:
        checks.append(Check("death_record", "no_record", None, None, note="no death record for this CNIC"))
        return checks
    checks.append(_compare("date_of_death", fields.get("date_of_death"), death.date_of_death.isoformat(), _date_equal))
    checks.append(_compare("certificate_no", fields.get("certificate_no"), death.certificate_no, same_doc_number))
    return checks


def _frc(db: Session, fields: dict[str, Field], claimant_cnic: str, deceased_cnic: str | None) -> list[Check]:
    family = registry.get_family(db, deceased_cnic) if deceased_cnic else []
    frc_number = family[0].frc_number if family else None
    checks = [_compare("frc_number", fields.get("frc_number"), frc_number, same_doc_number)]
    members = fields.get("member_cnics")
    if members is None:
        return [*checks, Check("member_cnics", "not_read", None, None)]
    read = set(members.value.split(","))
    wanted = {c for c in (claimant_cnic, deceased_cnic) if c}
    found = read & wanted
    # One row hidden by a fold or watermark is not a mismatch; the note tells the officer.
    status = "match" if found else _status(False, members)
    note = f"{len(found)} of {len(wanted)} expected CNICs found"
    return [*checks, Check("member_cnics", status, f"{len(read)} CNICs read", f"{len(wanted)} expected", note=note)]


def _nikah_nama(db: Session, fields: dict[str, Field], claimant_cnic: str, deceased_cnic: str | None) -> list[Check]:
    groom = registry.get_person(db, deceased_cnic) if deceased_cnic else None
    bride = registry.get_person(db, claimant_cnic)
    return [
        _name_check("groom_name", fields.get("groom_name"), groom.full_name if groom else None, None, None),
        _name_check("bride_name", fields.get("bride_name"), bride.full_name if bride else None, None, None),
    ]


def check_against_registry(db: Session, kind: str, fields: dict[str, Field], claimant_cnic: str, deceased_cnic: str | None) -> list[Check]:
    if kind == "claimant_cnic":
        return _cnic_card(db, fields, claimant_cnic)
    if kind == "deceased_cnic":
        return _cnic_card(db, fields, deceased_cnic)
    if kind == "death_certificate":
        return _death_certificate(db, fields, deceased_cnic)
    if kind == "frc":
        return _frc(db, fields, claimant_cnic, deceased_cnic)
    if kind == "nikah_nama":
        return _nikah_nama(db, fields, claimant_cnic, deceased_cnic)
    raise ValueError(f"unknown document kind {kind}")
