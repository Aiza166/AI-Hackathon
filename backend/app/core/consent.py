"""Consent enforcement: every read of a person's data goes through assert_consent().

Rules:
- A citizen can always see their own data.
- A helper needs an active consent from that person, naming the helper and the field.
- Department staff (officer/admin) need an active consent naming their department.
- Auditors have read-only oversight access (logged), because oversight of AI decisions
  must keep working even after a citizen withdraws; they cannot act on a case.
Every allowed read is logged as DATA_ACCESS (shown to the citizen in "who saw my data"),
every refusal as CONSENT_DENIED. Consent is checked on each request, never cached, so a
withdrawal takes effect immediately.
"""
from fastapi import HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal
from app.models.consent import Consent
from app.models.platform import utcnow
from app.schemas.contracts import Role

PURPOSE = "survivor_pension_claim"


def person_resource(person_id: str) -> str:
    return f"person:{person_id}"


def _grantee(principal: Principal) -> tuple | None:
    if principal.role == Role.HELPER:
        return (Consent.grantee_type == "helper", Consent.grantee_id == principal.id)
    if principal.role in (Role.OFFICER, Role.ADMIN):
        return (Consent.grantee_type == "department", Consent.grantee_id == principal.tenant_id)
    return None


def consented_person_ids(db: Session, principal: Principal, field: str) -> set[str]:
    """People who currently share `field` with this helper or department (for list endpoints)."""
    grantee = _grantee(principal)
    if grantee is None:
        return set()
    rows = db.execute(
        select(Consent.subject_person_id, Consent.fields).where(
            Consent.status == "active", *grantee,
            or_(Consent.valid_until.is_(None), Consent.valid_until > utcnow()),
        )
    ).all()
    return {person_id for person_id, fields in rows if field in (fields or [])}


def active_consent(db: Session, principal: Principal, person_id: str, field: str) -> Consent | None:
    if principal.role == Role.HELPER:
        grantee = (Consent.grantee_type == "helper", Consent.grantee_id == principal.id)
    elif principal.role in (Role.OFFICER, Role.ADMIN):
        grantee = (Consent.grantee_type == "department", Consent.grantee_id == principal.tenant_id)
    else:
        return None
    rows = db.execute(
        select(Consent).where(
            Consent.subject_person_id == person_id, Consent.status == "active", *grantee,
            or_(Consent.valid_until.is_(None), Consent.valid_until > utcnow()),
        )
    ).scalars()
    return next((c for c in rows if field in (c.fields or [])), None)


def assert_consent(db: Session, principal: Principal, request: Request, person_id: str, field: str) -> None:
    """Raise 403 (and log CONSENT_DENIED) unless the principal may read this field of this person."""
    if principal.role == Role.CITIZEN and principal.person_id == person_id:
        return
    if principal.role == Role.AUDITOR:
        _log_access(db, principal, request, person_id, field, basis="oversight")
        return
    consent = active_consent(db, principal, person_id, field)
    if consent is None:
        audit.record(
            db, principal.actor, "CONSENT_DENIED", resource=person_resource(person_id),
            details={"field": field, "path": f"{request.method} {request.url.path}"},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This person has not shared this information with you")
    _log_access(db, principal, request, person_id, field, basis=f"consent:{consent.id}")


def _log_access(db: Session, principal: Principal, request: Request, person_id: str, field: str, basis: str) -> None:
    audit.record(
        db, principal.actor, "DATA_ACCESS", resource=person_resource(person_id),
        details={"field": field, "basis": basis, "path": f"{request.method} {request.url.path}"},
    )
    db.commit()


def list_access(db: Session, principal: Principal, request: Request, person_ids, field: str) -> dict[str, bool]:
    """Consent per row for list endpoints (Security review H1).

    Returns {person_id: may_see_details}. Logs one audit row per person per request:
    CONSENT_DENIED for rows that will be redacted, DATA_ACCESS for rows shown to a
    helper, department or auditor (a citizen reading her own rows is not logged)."""
    people = list(dict.fromkeys(person_ids))
    if not people:
        return {}
    path = f"{request.method} {request.url.path}"
    if principal.role == Role.AUDITOR:
        shared, basis = set(people), "oversight"
    elif principal.role == Role.CITIZEN:
        shared, basis = {p for p in people if p == principal.person_id}, None
    else:
        shared, basis = consented_person_ids(db, principal, field), "consent"
    result = {}
    for person_id in people:
        allowed = person_id in shared
        result[person_id] = allowed
        if not allowed:
            audit.record(db, principal.actor, "CONSENT_DENIED", resource=person_resource(person_id),
                         details={"field": field, "path": path, "redacted": True})
        elif basis is not None:
            audit.record(db, principal.actor, "DATA_ACCESS", resource=person_resource(person_id),
                         details={"field": field, "basis": basis, "path": path})
    db.commit()
    return result
