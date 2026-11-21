"""Document reuse registry: the same paper sent on more than one claim.

Fingerprints per upload (kept in CaseDocument.result["fingerprints"], so no new column):
  sha256      exact bytes
  dhash       256-bit difference hash of the analysed image (survives WhatsApp recompression
              and resizing). On backend/sample_docs a recompressed copy is 1-4 bits away and a
              different person's card on the same template is 9+ bits away, so the bar is 5.
  doc_number  the certificate / FRC number read from the paper, normalised

A match on another case is compared by its subject (the person the paper is about):
  different subject -> DOC_REUSED (high, officer only)
  same subject      -> DOC_SEEN_BEFORE (info: co-sharers lawfully send the same certificate)
Searched across all cases and tenants; the officer sees "another case", never its details.
"""
import re
from dataclasses import dataclass

import numpy as np
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.fields import Field, ascii_digits
from app.models.document import CaseDocument
from app.models.platform import Case

DHASH_SIZE = 16
DHASH_MAX_DISTANCE = 5
DOC_NUMBER_MIN_LEN = 6
SCAN_LIMIT = 5000  # newest uploads of the same kind compared by perceptual hash
NUMBER_FIELDS = ("certificate_no", "frc_number")


def dhash(img: Image.Image) -> str:
    small = img.convert("L").resize((DHASH_SIZE + 1, DHASH_SIZE), Image.LANCZOS)
    pixels = np.asarray(small, dtype=np.int16)
    bits = (pixels[:, 1:] > pixels[:, :-1]).flatten()
    return "".join("1" if b else "0" for b in bits)


def hamming(a: str, b: str) -> int:
    if len(a) != len(b):
        return len(a) + len(b)
    return sum(x != y for x, y in zip(a, b))


def doc_number(fields: dict[str, Field]) -> str | None:
    for key in NUMBER_FIELDS:
        if key in fields:
            number = re.sub(r"[^A-Z0-9]", "", ascii_digits(fields[key].value).upper())
            if len(number) >= DOC_NUMBER_MIN_LEN:
                return number
    return None


def fingerprints(sha256: str, img: Image.Image, fields: dict[str, Field]) -> dict:
    return {"sha256": sha256, "dhash": dhash(img), "doc_number": doc_number(fields)}


def subject(kind: str, case: Case) -> str | None:
    """Who the paper is about: a match about someone else is reuse."""
    if kind == "claimant_cnic":
        return f"person:{case.claimant_person_id}"
    if kind == "nikah_nama":
        return f"couple:{case.claimant_person_id}:{case.deceased_cnic}"
    return f"deceased:{case.deceased_cnic}" if case.deceased_cnic else None


@dataclass(frozen=True)
class Match:
    how: tuple[str, ...]  # sha256 | dhash | doc_number
    same_subject: bool
    same_tenant: bool


def _how(mine: dict, theirs: dict, sha256: str) -> tuple[str, ...]:
    how = []
    if sha256 == mine["sha256"]:
        how.append("sha256")
    if theirs.get("dhash") and hamming(theirs["dhash"], mine["dhash"]) <= DHASH_MAX_DISTANCE:
        how.append("dhash")
    if mine.get("doc_number") and theirs.get("doc_number") == mine["doc_number"]:
        how.append("doc_number")
    return tuple(how)


def find_matches(db: Session, case: Case, kind: str, mine: dict) -> list[Match]:
    rows = db.execute(
        select(CaseDocument.sha256, CaseDocument.result["fingerprints"], CaseDocument.tenant_id, Case)
        .join(Case, Case.id == CaseDocument.case_id)
        .where(CaseDocument.kind == kind, CaseDocument.case_id != case.id)
        .order_by(CaseDocument.created_at.desc()).limit(SCAN_LIMIT)
    ).all()
    own_subject = subject(kind, case)
    found = []
    for sha256, theirs, tenant_id, other in rows:
        how = _how(mine, theirs if isinstance(theirs, dict) else {}, sha256)
        if how:
            same = own_subject is not None and subject(kind, other) == own_subject
            found.append(Match(how=how, same_subject=same, same_tenant=tenant_id == case.tenant_id))
    return found
