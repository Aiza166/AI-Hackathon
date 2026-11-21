"""Document evidence for the decision engine: the latest upload of each kind on a case."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import CaseDocument


def document_signals(db: Session, case_id: str) -> dict:
    """{"high": [kinds], "mismatch": [kinds], "analysed": [kinds]} from the newest upload per kind."""
    rows = db.execute(
        select(CaseDocument.kind, CaseDocument.risk_level).where(CaseDocument.case_id == case_id).order_by(CaseDocument.created_at)
    ).all()
    latest = dict(rows)  # later rows overwrite earlier ones: a re-upload replaces the old photo
    return {
        "analysed": sorted(latest),
        "high": sorted(k for k, risk in latest.items() if risk == "high"),
        "mismatch": sorted(k for k, risk in latest.items() if risk == "mismatch"),
    }
