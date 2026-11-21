"""Document pipeline: quality -> OCR -> fields -> registry checks -> forensics -> Jev -> indicators.

The result is stored per case and fed into the decision engine (the case is re-decided
unless an officer already finished it). Every upload, analysis and field confirmation
writes an audit event. No step can approve or reject: indicators only route.
"""
import logging
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal
from app.documents import cascade_checks, consistency, forensics, indicators, jev_checks
from app.documents.fields import Field, extract_fields
from app.documents.imaging import BadImage, LoadedImage, check_quality, jpeg_bytes, load
from app.documents.ocr import OcrUnavailable, run_ocr
from app.mock.registry import MockServiceUnavailable
from app.models.document import CaseDocument
from app.models.platform import Case, Person
from app.services import cases as case_svc

log = logging.getLogger("sahara.documents")
OFFICER_COPY_QUALITY = 80
MAX_CONFIRMED_VALUE = 120


@dataclass(frozen=True)
class Retake:
    """The photo is too poor to analyse: nothing is stored, the citizen is asked to retake it."""

    quality: dict
    indicator: dict


def _claimant_cnic(db: Session, case: Case) -> str:
    person = db.get(Person, case.claimant_person_id)
    return person.cnic if person else ""


def _ocr_and_fields(kind: str, loaded: LoadedImage) -> tuple[str | None, dict[str, Field], list]:
    try:
        result = run_ocr(loaded.image)
    except OcrUnavailable as exc:
        log.info("OCR unavailable: %s", exc)
        return None, {}, [indicators.make("OCR_UNAVAILABLE")]
    fields = extract_fields(kind, result)
    return result.engine, fields, indicators.from_fields(fields)


def _registry_checks(db: Session, case: Case, kind: str, fields: dict[str, Field]) -> tuple[list, list]:
    if not fields:
        return [], []
    try:
        checks = consistency.check_against_registry(db, kind, fields, _claimant_cnic(db, case), case.deceased_cnic)
    except MockServiceUnavailable as exc:
        # The decision engine routes the case to an officer for the outage itself.
        return [], [indicators.make("OCR_UNAVAILABLE", registry_unavailable=exc.service)]
    return checks, indicators.from_checks(checks)


def _summarise(fields: dict[str, Field], checks: list, report: forensics.ForensicReport, jev: jev_checks.JevDocResult,
               found: list, quality: dict, sensed: cascade_checks.DocCascade) -> dict:
    return {
        **sensed.summary(),
        "quality": quality,
        "fields": {k: f.to_dict() for k, f in fields.items()},
        "checks": [c.to_dict() for c in checks],
        "forensics": report.to_dict(),
        "jev": jev.to_dict(),
        "indicators": [i.to_dict() for i in found],
    }


def analyse_upload(db: Session, principal: Principal, case: Case, kind: str, data: bytes) -> CaseDocument | Retake:
    try:
        loaded = load(data)
    except BadImage as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    quality = check_quality(loaded)
    if not quality.ok:
        audit.record(db, principal.actor, "DOCUMENT_RETAKE_ASKED", resource=f"case:{case.reference}", case_id=case.id,
                     details={"kind": kind, "sha256": loaded.sha256, "problems": list(quality.problems)})
        db.commit()
        return Retake(quality=quality.to_dict(), indicator=indicators.from_quality(quality)[0].to_dict())

    engine, fields, found = _ocr_and_fields(kind, loaded)
    checks, check_indicators = _registry_checks(db, case, kind, fields)
    report, heatmap = forensics.analyse(loaded.image, loaded.exif)
    jev = jev_checks.ask_document_questions(kind, loaded.image)
    sensed = cascade_checks.run(kind, loaded.image, fields, report, jev)
    disagree = [indicators.make("SENSORS_DISAGREE", questions=sensed.fused.disagreements)] \
        if sensed.fused and sensed.fused.disagreements else []
    found = indicators.dedupe([*found, *check_indicators, *indicators.from_forensics(report),
                               *indicators.from_jev(sensed.jev), *disagree])
    risk = indicators.risk_level(found)

    doc = CaseDocument(
        case_id=case.id, tenant_id=case.tenant_id, kind=kind, sha256=loaded.sha256,
        width=loaded.image.width, height=loaded.image.height, ocr_engine=engine, jev_model=jev.model,
        risk_level=risk, indicator_codes=[i.code for i in found],
        result=_summarise(fields, checks, report, jev, found, quality.to_dict(), sensed),
        image_jpeg=jpeg_bytes(loaded.image, OFFICER_COPY_QUALITY), ela_jpeg=heatmap, uploaded_by=principal.id,
    )
    db.add(doc)
    db.flush()
    audit.record(db, principal.actor, "DOCUMENT_UPLOADED", resource=f"document:{doc.id}", case_id=case.id,
                 details={"kind": kind, "sha256": loaded.sha256})
    audit.record(db, audit.AI, "DOCUMENT_ANALYSED", resource=f"document:{doc.id}", case_id=case.id, tenant_id=case.tenant_id,
                 details={"kind": kind, "sha256": loaded.sha256, "risk": risk, "indicators": doc.indicator_codes,
                          "ocr_engine": engine, "jev_model": jev.model, "jev_status": jev.status,
                          "jev_question_set": jev.question_set, "jev_latency_ms": jev.latency_ms,
                          "sensors": sensed.sensors, "cascade": sensed.fused.to_dict() if sensed.fused else None})
    redecide(db, case)
    return doc


def redecide(db: Session, case: Case) -> None:
    """New document evidence: decide again, unless the case is finished (officer decision or withdrawn)."""
    if case.status not in case_svc.FINAL_STATUSES:
        db.refresh(case, with_for_update=True)
        case_svc.run_decision(db, case)


def confirm_fields(db: Session, principal: Principal, case: Case, doc: CaseDocument, values: dict[str, str]) -> CaseDocument:
    """The citizen confirms or corrects fields read with low confidence.

    Corrected values are re-checked against the registry (a typed value is held to the same
    record as a read one) and kept next to what the OCR read, so the officer sees both.
    Forensic and Jev indicators are never cleared by a confirmation.
    """
    result = dict(doc.result)
    read = result.get("fields", {})
    unknown = set(values) - set(read)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown fields: {', '.join(sorted(unknown))}")
    clean = {k: str(v).strip()[:MAX_CONFIRMED_VALUE] for k, v in values.items()}
    merged = {k: Field(value=v["value"], confidence=v["confidence"], method=v["method"]) for k, v in read.items()}
    merged.update({k: Field(value=v, confidence=1.0, method="user") for k, v in clean.items()})
    try:
        checks = consistency.check_against_registry(db, doc.kind, merged, _claimant_cnic(db, case), case.deceased_cnic)
    except MockServiceUnavailable:
        checks = []
    kept = [indicators.Indicator(**i) for i in result.get("indicators", []) if i["code"] not in ("FIELD_CONFIRM", "RECORD_MISMATCH")]
    found = indicators.dedupe([*kept, *indicators.from_checks(checks)])
    corrected = sorted(k for k, v in clean.items() if v != read[k]["value"])
    result.update({"checks": [c.to_dict() for c in checks], "indicators": [i.to_dict() for i in found], "corrected_fields": corrected})
    doc.result = result
    doc.confirmed_fields = clean
    doc.indicator_codes = [i.code for i in found]
    doc.risk_level = indicators.risk_level(found)
    audit.record(db, principal.actor, "DOCUMENT_FIELDS_CONFIRMED", resource=f"document:{doc.id}", case_id=case.id,
                 details={"fields": sorted(clean), "corrected": corrected, "risk": doc.risk_level})
    db.flush()
    redecide(db, case)
    return doc


def list_for_case(db: Session, case_id: str) -> list[CaseDocument]:
    return list(db.execute(select(CaseDocument).where(CaseDocument.case_id == case_id).order_by(CaseDocument.created_at)).scalars())


def citizen_view(doc: CaseDocument) -> dict:
    """What the claimant or helper sees: fields to confirm and citizen-safe reasons only."""
    visible = [i for i in doc.result.get("indicators", []) if i["citizen_visible"]]
    if doc.risk_level == "high":
        # The citizen never sees forensic detail; she is told a person will look at it.
        visible.append({"code": "NEEDS_OFFICER", "text_en": "An officer will look at this paper.", "text_ur": "ایک افسر یہ کاغذ دیکھے گا۔"})
    return {
        "id": doc.id, "kind": doc.kind, "status": "analysed", "risk_level": doc.risk_level if doc.risk_level != "high" else "officer",
        "fields": doc.result.get("fields", {}), "confirmed_fields": doc.confirmed_fields,
        "reasons": [{"code": i["code"], "text_en": i["text_en"], "text_ur": i["text_ur"]} for i in visible],
        "ocr_engine": doc.ocr_engine, "created_at": doc.created_at.isoformat(),
    }


def officer_view(doc: CaseDocument) -> dict:
    return {
        "id": doc.id, "kind": doc.kind, "sha256": doc.sha256, "width": doc.width, "height": doc.height,
        "risk_level": doc.risk_level, "indicators": doc.result.get("indicators", []),
        "fields": doc.result.get("fields", {}), "confirmed_fields": doc.confirmed_fields,
        "corrected_fields": doc.result.get("corrected_fields", []), "checks": doc.result.get("checks", []),
        "forensics": doc.result.get("forensics", {}), "jev": doc.result.get("jev", {}), "quality": doc.result.get("quality", {}),
        "second_sensor": doc.result.get("second_sensor"), "cascade": doc.result.get("cascade"), "sensors": doc.result.get("sensors", []),
        "ocr_engine": doc.ocr_engine, "uploaded_by": doc.uploaded_by, "created_at": doc.created_at.isoformat(),
    }
