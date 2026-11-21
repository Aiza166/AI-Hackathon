"""Document evidence for the decision engine, per document kind on a case.

- "analysed": kinds whose newest upload was actually read and checked (risk not "unverified").
  A blank or unreadable paper never counts as provided.
- "high": kinds with ANY upload at high risk that an officer has not cleared. A later clean
  photo does not erase an earlier flag (red team H2); only an officer's audited clear does.
- "mismatch": kinds whose newest upload disagrees with a record.
- "unverified": kinds whose newest upload could not be read or checked.
- "uploads": number of stored uploads per kind (repeated re-uploads are a signal).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import CaseDocument

UNVERIFIED = "unverified"


def is_cleared(result: dict | None) -> bool:
    return bool((result or {}).get("cleared"))


def document_signals(db: Session, case_id: str) -> dict:
    rows = db.execute(
        select(CaseDocument.kind, CaseDocument.risk_level, CaseDocument.result)
        .where(CaseDocument.case_id == case_id).order_by(CaseDocument.created_at)
    ).all()
    latest: dict[str, str] = {}
    sticky_high: set[str] = set()
    uploads: dict[str, int] = {}
    for kind, risk, result in rows:
        latest[kind] = risk  # later rows overwrite earlier ones
        uploads[kind] = uploads.get(kind, 0) + 1
        if risk == "high" and not is_cleared(result):
            sticky_high.add(kind)
    return {
        "analysed": sorted(k for k, risk in latest.items() if risk != UNVERIFIED),
        "high": sorted(sticky_high),
        "mismatch": sorted(k for k, risk in latest.items() if risk == "mismatch"),
        "unverified": sorted(k for k, risk in latest.items() if risk == UNVERIFIED),
        "uploads": dict(sorted(uploads.items())),
    }
