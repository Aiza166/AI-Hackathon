"""Audit log: read (auditor/admin), verify the hash chain, replay a case."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal, require_roles
from app.core.envelope import ok
from app.db import get_db
from app.models.audit import AuditEvent
from app.models.platform import Case
from app.schemas.contracts import Role
from app.services.cases import not_found

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
READERS = (Role.AUDITOR, Role.ADMIN)


def _row(e: AuditEvent) -> dict:
    return {
        "seq": e.seq, "ts": e.ts.isoformat(), "actor_type": e.actor_type, "actor_id": e.actor_id, "role": e.role,
        "action": e.action, "resource": e.resource, "case_id": e.case_id, "details": e.details, "hash": e.hash,
    }


@router.get("")
def list_events(
    action: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(require_roles(*READERS)),
    db: Session = Depends(get_db),
) -> dict:
    # Department isolation: only this tenant's events (system-wide events have no tenant).
    query = select(AuditEvent).where(AuditEvent.tenant_id == principal.tenant_id).order_by(AuditEvent.seq.desc()).limit(limit)
    if action:
        query = query.where(AuditEvent.action == action)
    rows = [_row(e) for e in db.execute(query).scalars()]
    audit.record(db, principal.actor, "AUDIT_READ", details={"action_filter": action, "count": len(rows)})
    db.commit()
    return ok(rows)


@router.get("/verify")
def verify(principal: Principal = Depends(require_roles(*READERS)), db: Session = Depends(get_db)) -> dict:
    """Recompute the SHA-256 chain. Any edited or removed row breaks it."""
    return ok(audit.verify_chain(db))


@router.get("/cases/{case_id}/replay")
def replay(case_id: str, principal: Principal = Depends(require_roles(*READERS)), db: Session = Depends(get_db)) -> dict:
    case = db.get(Case, case_id)
    if case is None or case.tenant_id != principal.tenant_id:
        raise not_found()
    rows = db.execute(select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.seq)).scalars()
    return ok({"case_reference": case.reference, "events": [_row(e) for e in rows]})
