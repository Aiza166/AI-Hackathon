"""Citizen consent controls: see, share, change, withdraw, correct, and "who saw my data"."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal, deny, require_roles
from app.core.consent import PURPOSE, active_consent, person_resource
from app.core.envelope import ok
from app.db import get_db
from app.models.audit import AuditEvent
from app.models.consent import CONSENT_FIELDS, Consent, CorrectionRequest
from app.models.platform import Person, Tenant, User, utcnow
from app.schemas.contracts import Role

router = APIRouter(prefix="/api/v1", tags=["consent"])
CITIZEN = require_roles(Role.CITIZEN)
FieldName = Literal["cnic", "family_record", "death_certificate", "payout_account", "case_details"]
VISIBLE_ACTIONS = ("DATA_ACCESS", "CONSENT_DENIED", "CONSENT_GRANTED", "CONSENT_CHANGED", "CONSENT_WITHDRAWN",
                   "CORRECTION_REQUESTED", "CORRECTION_APPROVED", "CORRECTION_REJECTED")


class ConsentIn(BaseModel):
    grantee_type: Literal["helper", "department"]
    grantee_id: str = Field(min_length=1, max_length=36)
    fields: list[FieldName] = Field(min_length=1)


class ConsentFieldsIn(BaseModel):
    fields: list[FieldName] = Field(min_length=1)


class CorrectionIn(BaseModel):
    field: Literal["name", "date_of_birth", "payout_account", "family_record"]
    requested_value: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=3, max_length=1000)


class DecisionNote(BaseModel):
    note: str = Field(min_length=3, max_length=1000)


def _grantee_name(db: Session, grantee_type: str, grantee_id: str) -> str:
    if grantee_type == "helper":
        user = db.get(User, grantee_id)
        return user.name if user else "Unknown helper"
    tenant = db.get(Tenant, grantee_id)
    return tenant.name if tenant else "Unknown department"


def _valid_grantee(db: Session, grantee_type: str, grantee_id: str) -> bool:
    if grantee_type == "helper":
        user = db.get(User, grantee_id)
        return user is not None and user.role == Role.HELPER
    return db.get(Tenant, grantee_id) is not None


def _consent_row(db: Session, c: Consent) -> dict:
    return {
        "id": c.id, "grantee_type": c.grantee_type, "grantee_id": c.grantee_id,
        "grantee_name": _grantee_name(db, c.grantee_type, c.grantee_id), "purpose": c.purpose,
        "fields": c.fields, "status": c.status, "created_at": c.created_at.isoformat(),
        "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None,
    }


def _own_consent(db: Session, principal: Principal, request: Request, consent_id: str) -> Consent:
    consent = db.get(Consent, consent_id, with_for_update=True)
    if consent is None or consent.subject_person_id != principal.person_id:
        raise deny(db, principal, request, "not your consent record")
    return consent


@router.get("/me/consents")
def my_consents(principal: Principal = Depends(CITIZEN), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(Consent).where(Consent.subject_person_id == principal.person_id).order_by(Consent.created_at)).scalars()
    return ok({"fields": list(CONSENT_FIELDS), "consents": [_consent_row(db, c) for c in rows]})


@router.post("/me/consents", status_code=201)
def grant(body: ConsentIn, principal: Principal = Depends(CITIZEN), db: Session = Depends(get_db)) -> dict:
    if not _valid_grantee(db, body.grantee_type, body.grantee_id):
        raise HTTPException(status_code=422, detail="Unknown helper or department")
    consent = Consent(subject_person_id=principal.person_id, grantee_type=body.grantee_type, grantee_id=body.grantee_id,
                      purpose=PURPOSE, fields=list(body.fields))
    db.add(consent)
    db.flush()
    audit.record(db, principal.actor, "CONSENT_GRANTED", resource=person_resource(principal.person_id),
                 details={"consent_id": consent.id, "grantee_type": body.grantee_type, "fields": list(body.fields)})
    db.commit()
    return ok(_consent_row(db, consent))


@router.patch("/me/consents/{consent_id}")
def change_fields(consent_id: str, body: ConsentFieldsIn, request: Request, principal: Principal = Depends(CITIZEN), db: Session = Depends(get_db)) -> dict:
    consent = _own_consent(db, principal, request, consent_id)
    if consent.status != "active":
        raise HTTPException(status_code=409, detail="This consent was withdrawn. Grant a new one instead.")
    before = list(consent.fields)
    consent.fields = list(body.fields)
    audit.record(db, principal.actor, "CONSENT_CHANGED", resource=person_resource(principal.person_id),
                 details={"consent_id": consent.id, "before": before, "after": list(body.fields)})
    db.commit()
    return ok(_consent_row(db, consent))


@router.post("/me/consents/{consent_id}/withdraw")
def withdraw(consent_id: str, request: Request, principal: Principal = Depends(CITIZEN), db: Session = Depends(get_db)) -> dict:
    consent = _own_consent(db, principal, request, consent_id)
    if consent.status == "withdrawn":
        return ok(_consent_row(db, consent))
    consent.status = "withdrawn"
    consent.withdrawn_at = utcnow()
    audit.record(db, principal.actor, "CONSENT_WITHDRAWN", resource=person_resource(principal.person_id),
                 details={"consent_id": consent.id, "grantee_type": consent.grantee_type, "grantee_id": consent.grantee_id})
    db.commit()
    return ok(_consent_row(db, consent))


@router.get("/me/access-log")
def access_log(principal: Principal = Depends(CITIZEN), db: Session = Depends(get_db)) -> dict:
    """Who saw or tried to see my data, and every consent change (from the audit log)."""
    rows = db.execute(
        select(AuditEvent).where(AuditEvent.resource == person_resource(principal.person_id), AuditEvent.action.in_(VISIBLE_ACTIONS))
        .order_by(AuditEvent.seq.desc()).limit(200)
    ).scalars()
    names: dict[str, str] = {}

    def who(actor_id: str | None) -> str:
        if actor_id is None:
            return "System"
        if actor_id not in names:
            user = db.get(User, actor_id)
            names[actor_id] = user.name if user else "Outside system"
        return names[actor_id]

    return ok([{
        "seq": e.seq, "ts": e.ts.isoformat(), "action": e.action, "who": who(e.actor_id), "role": e.role,
        "field": e.details.get("field"), "basis": e.details.get("basis"),
    } for e in rows])


@router.post("/me/corrections", status_code=201)
def request_correction(body: CorrectionIn, principal: Principal = Depends(CITIZEN), db: Session = Depends(get_db)) -> dict:
    person = db.get(Person, principal.person_id)
    current = person.display_name if body.field == "name" and person else None
    row = CorrectionRequest(person_id=principal.person_id, tenant_id=principal.tenant_id, field=body.field,
                            current_value=current, requested_value=body.requested_value, reason=body.reason)
    db.add(row)
    db.flush()
    audit.record(db, principal.actor, "CORRECTION_REQUESTED", resource=person_resource(principal.person_id),
                 details={"correction_id": row.id, "field": body.field})
    db.commit()
    return ok({"id": row.id, "status": row.status})


def _correction_row(c: CorrectionRequest) -> dict:
    return {"id": c.id, "person_id": c.person_id, "field": c.field, "current_value": c.current_value,
            "requested_value": c.requested_value, "reason": c.reason, "status": c.status, "created_at": c.created_at.isoformat()}


@router.get("/me/corrections")
def my_corrections(principal: Principal = Depends(CITIZEN), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(CorrectionRequest).where(CorrectionRequest.person_id == principal.person_id)).scalars()
    return ok([_correction_row(c) for c in rows])


@router.get("/corrections")
def pending_corrections(request: Request, principal: Principal = Depends(require_roles(Role.OFFICER, Role.ADMIN)),
                        db: Session = Depends(get_db)) -> dict:
    """Per-row consent (case_details): without it the officer sees a redacted stub, and the refusal is logged."""
    rows = db.execute(select(CorrectionRequest).where(CorrectionRequest.tenant_id == principal.tenant_id, CorrectionRequest.status == "pending")).scalars().all()
    path = f"{request.method} {request.url.path}"
    out = []
    for c in rows:
        if active_consent(db, principal, c.person_id, "case_details") is None:
            audit.record(db, principal.actor, "CONSENT_DENIED", resource=person_resource(c.person_id),
                         details={"field": "case_details", "path": path, "redacted": True})
            out.append({"id": c.id, "person_id": c.person_id, "field": c.field, "status": c.status,
                        "created_at": c.created_at.isoformat(), "consent_active": False})
        else:
            audit.record(db, principal.actor, "DATA_ACCESS", resource=person_resource(c.person_id),
                         details={"field": "case_details", "basis": "consent", "path": path})
            out.append({**_correction_row(c), "consent_active": True})
    db.commit()
    return ok(out)


@router.post("/corrections/{correction_id}/{decision}")
def decide_correction(
    correction_id: str, decision: Literal["approve", "reject"], body: DecisionNote,
    principal: Principal = Depends(require_roles(Role.OFFICER)), db: Session = Depends(get_db),
) -> dict:
    row = db.get(CorrectionRequest, correction_id, with_for_update=True)
    if row is None or row.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Correction request not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"Already {row.status}")
    row.status = "approved" if decision == "approve" else "rejected"
    row.decided_by, row.decided_at = principal.id, utcnow()
    if row.status == "approved" and row.field == "name":
        person = db.get(Person, row.person_id)
        if person is not None:
            person.display_name = row.requested_value  # old value stays in the request row (history)
    audit.record(db, principal.actor, f"CORRECTION_{row.status.upper()}", resource=person_resource(row.person_id),
                 details={"correction_id": row.id, "field": row.field, "note": body.note})
    db.commit()
    return ok(_correction_row(row))
