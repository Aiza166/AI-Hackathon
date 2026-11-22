"""Document upload and review.

Citizens and helpers upload a photo of a paper for their case and confirm what was read.
Officers, admins and auditors see every indicator with its evidence, the stored copy
and the ELA heatmap. Every endpoint passes the same case visibility and consent checks
as the other case reads (a withdrawn consent blocks the very next call).
"""
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy.orm import Session

from app.api.cases import _load
from app.core import audit
from app.core.auth import Principal, deny, require_roles
from app.core.envelope import ok
from app.core.ratelimit import limiter
from app.db import get_db
from app.documents import service
from app.documents.imaging import sniff_format
from app.models.document import CaseDocument
from app.models.platform import Case
from app.schemas.contracts import Role
from app.services import cases as case_svc

router = APIRouter(prefix="/api/v1", tags=["documents"])

DocKind = Literal["claimant_cnic", "deceased_cnic", "death_certificate", "frc", "nikah_nama"]
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
CONSENT_FIELD = {  # which consented field a document of this kind belongs to
    "claimant_cnic": "cnic", "deceased_cnic": "cnic", "death_certificate": "death_certificate",
    "frc": "family_record", "nikah_nama": "family_record",
}
UPLOADERS = (Role.CITIZEN, Role.HELPER, Role.OFFICER)
STAFF = (Role.OFFICER, Role.ADMIN, Role.AUDITOR)
READERS = (*UPLOADERS, Role.ADMIN, Role.AUDITOR)


class ConfirmIn(BaseModel):
    values: dict[str, str] = PydanticField(min_length=1, max_length=10)


def _read_limited(upload: UploadFile) -> bytes:
    if (upload.content_type or "").split(";")[0].strip().lower() not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Please send a JPEG, PNG or WebP photo")
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The photo is too large (8 MB at most)")
    if not data:
        raise HTTPException(status_code=422, detail="The photo is empty")
    if sniff_format(data) is None:  # the bytes decide, not the declared type or file name
        raise HTTPException(status_code=415, detail="Please send a JPEG, PNG or WebP photo")
    return data


def _visible(db: Session, principal: Principal, request: Request, case_id: str) -> None:
    """Role/tenant visibility of the case (no consent log yet): checked before the document id,
    so a caller who cannot see the case cannot learn which document ids exist in it."""
    case = db.get(Case, case_id)
    if case is None:
        raise case_svc.not_found()
    if not case_svc.can_view(db, principal, case):
        raise deny(db, principal, request, "not allowed to view this case")


def _doc(db: Session, case_id: str, doc_id: str) -> CaseDocument:
    doc = db.get(CaseDocument, doc_id)
    if doc is None or doc.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _view(principal: Principal, doc: CaseDocument) -> dict:
    return service.officer_view(doc) if principal.role in STAFF else service.citizen_view(doc)


@router.post("/cases/{case_id}/documents", status_code=201)
@limiter.limit("10/minute")
def upload_document(
    request: Request,
    case_id: str,
    kind: DocKind = Form(...),
    file: UploadFile = File(...),
    principal: Principal = Depends(require_roles(*UPLOADERS)),
    db: Session = Depends(get_db),
) -> dict:
    """Upload one photo. A photo too poor to read comes back as status "retake" (nothing stored)."""
    case = _load(db, principal, request, case_id, field=CONSENT_FIELD[kind])
    data = _read_limited(file)
    result = service.analyse_upload(db, principal, case, kind, data)
    if isinstance(result, service.Retake):
        return ok({"status": "retake", "kind": kind, "quality": result.quality, "reasons": [
            {"code": result.indicator["code"], "text_en": result.indicator["text_en"], "text_ur": result.indicator["text_ur"]}]})
    db.commit()
    return ok({**_view(principal, result), "case_status": case.status})


@router.get("/cases/{case_id}/documents")
def list_documents(case_id: str, request: Request, principal: Principal = Depends(require_roles(*READERS)), db: Session = Depends(get_db)) -> dict:
    case = _load(db, principal, request, case_id)
    return ok([_view(principal, d) for d in service.list_for_case(db, case.id)])


@router.get("/cases/{case_id}/documents/{doc_id}")
def get_document(case_id: str, doc_id: str, request: Request, principal: Principal = Depends(require_roles(*READERS)), db: Session = Depends(get_db)) -> dict:
    _visible(db, principal, request, case_id)  # case access first: no document-existence oracle
    doc = _doc(db, case_id, doc_id)
    _load(db, principal, request, case_id, field=CONSENT_FIELD[doc.kind])
    return ok(_view(principal, doc))


@router.post("/cases/{case_id}/documents/{doc_id}/confirm")
@limiter.limit("20/minute")
def confirm_document_fields(
    request: Request, case_id: str, doc_id: str, body: ConfirmIn,
    principal: Principal = Depends(require_roles(Role.CITIZEN, Role.HELPER)), db: Session = Depends(get_db),
) -> dict:
    _visible(db, principal, request, case_id)
    doc = _doc(db, case_id, doc_id)
    case = _load(db, principal, request, case_id, field=CONSENT_FIELD[doc.kind])
    doc = service.confirm_fields(db, principal, case, doc, body.values)
    db.commit()
    return ok({**_view(principal, doc), "case_status": case.status})


def _image(db: Session, principal: Principal, request: Request, case_id: str, doc_id: str, which: str) -> Response:
    _visible(db, principal, request, case_id)
    doc = _doc(db, case_id, doc_id)
    case = _load(db, principal, request, case_id, field=CONSENT_FIELD[doc.kind])
    audit.record(db, principal.actor, "DOCUMENT_IMAGE_VIEWED", resource=f"document:{doc.id}", case_id=case.id, details={"view": which})
    db.commit()
    body = doc.image_jpeg if which == "image" else doc.ela_jpeg
    return Response(content=body, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


@router.get("/cases/{case_id}/documents/{doc_id}/image")
def document_image(case_id: str, doc_id: str, request: Request, principal: Principal = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)) -> Response:
    """The stored copy (at most 1568 px), for officers and auditors."""
    return _image(db, principal, request, case_id, doc_id, "image")


@router.get("/cases/{case_id}/documents/{doc_id}/ela")
def document_ela(case_id: str, doc_id: str, request: Request, principal: Principal = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)) -> Response:
    """Error level analysis heatmap: context next to the image, never a verdict."""
    return _image(db, principal, request, case_id, doc_id, "ela")


class ClearIn(BaseModel):
    reason: str = PydanticField(min_length=10, max_length=500)


@router.post("/cases/{case_id}/documents/{doc_id}/clear")
@limiter.limit("30/minute")
def clear_document_flag(
    request: Request, case_id: str, doc_id: str, body: ClearIn,
    principal: Principal = Depends(require_roles(Role.OFFICER)), db: Session = Depends(get_db),
) -> dict:
    """An officer looked at a flagged paper and records why it is fine (red team H2). Until then
    the flag stays on the case, whatever is uploaded after it. Audited (DOCUMENT_RISK_CLEARED)."""
    _visible(db, principal, request, case_id)
    doc = _doc(db, case_id, doc_id)
    case = _load(db, principal, request, case_id, field=CONSENT_FIELD[doc.kind])
    doc = service.clear_high_risk(db, principal, case, doc, body.reason.strip())
    db.commit()
    return ok({**_view(principal, doc), "case_status": case.status})
