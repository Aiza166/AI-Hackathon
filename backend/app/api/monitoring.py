"""Admin: trigger a test error so the Sentry dashboard can be shown (judge demo)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core import audit, monitoring
from app.core.auth import Principal, require_roles
from app.db import get_db
from app.schemas.contracts import Role

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class SentryTestError(RuntimeError):
    """Deliberate error raised by the sentry-test endpoint."""


@router.post("/sentry-test")
def sentry_test(principal: Principal = Depends(require_roles(Role.ADMIN)), db: Session = Depends(get_db)) -> dict:
    """Raise a deliberate error (answered as a generic 500) that shows up in Sentry. Off without SENTRY_DSN."""
    if not monitoring.is_enabled():
        raise HTTPException(status_code=503, detail="Error monitoring is not configured")
    audit.record(db, principal.actor, "SENTRY_TEST_TRIGGERED", resource="monitoring:sentry")
    db.commit()  # the audit event must survive the error below
    # Contains a mock CNIC on purpose: the dashboard should show it masked.
    raise SentryTestError("Sentry test error from the admin console (mock CNIC 90000-0000001-1)")
