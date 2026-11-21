"""Shared test helpers. Since C2, only uploaded and analysed documents count as proof:
a ticked checkbox is a promise, so tests that need an approvable case attach analysed rows."""
from app.documents.service import redecide
from app.models.document import CaseDocument
from app.models.platform import Case

ALL_DOCS = ("death_certificate", "claimant_cnic", "frc", "nikah_nama")


def attach_documents(db, case_id: str, risk: str = "low", kinds=ALL_DOCS) -> None:
    """Simulate analysed uploads (the document pipeline itself is tested elsewhere)."""
    case = db.get(Case, case_id)
    for kind in kinds:
        db.add(CaseDocument(case_id=case.id, tenant_id=case.tenant_id, kind=kind, sha256="0" * 64, width=1, height=1,
                            risk_level=risk, indicator_codes=[], result={}, image_jpeg=b"", ela_jpeg=b"",
                            uploaded_by=case.created_by))
    db.commit()


def redecide_case(db, case_id: str) -> Case:
    case = db.get(Case, case_id)
    redecide(db, case)
    db.commit()
    db.refresh(case)
    return case
