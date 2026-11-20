"""Public API for outside systems, authenticated with X-API-Key and scopes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal, require_scope
from app.core.envelope import ok
from app.db import get_db
from app.models.platform import Case
from app.services.cases import not_found

router = APIRouter(prefix="/api/v1/public", tags=["public API (API key)"])


@router.get("/cases/{reference}/status")
def case_status(reference: str, principal: Principal = Depends(require_scope("cases:status")), db: Session = Depends(get_db)) -> dict:
    """Status only, no personal data: safe for outside systems such as a bank or SMS gateway."""
    case = db.query(Case).filter(Case.reference == reference, Case.tenant_id == principal.tenant_id).one_or_none()
    if case is None:
        raise not_found()
    audit.record(db, principal.actor, "PUBLIC_STATUS_READ", resource=f"case:{reference}", case_id=case.id)
    db.commit()
    return ok({"reference": case.reference, "status": case.status, "updated_at": case.updated_at.isoformat()})
