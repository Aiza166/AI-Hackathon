"""PIN lockout: count failed PIN checks per user from the audit log (no extra table)."""
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.platform import utcnow

MAX_FAILURES = 5
LOCKOUT = timedelta(minutes=15)


def recent_failures(db: Session, user_id: str, action: str) -> int:
    """Failed PIN checks of one kind (LOGIN_FAILED, PAYOUT_CONFIRM_FAILED) in the lockout window."""
    since = utcnow() - LOCKOUT
    query = select(func.count(AuditEvent.seq)).where(
        AuditEvent.action == action, AuditEvent.actor_id == user_id, AuditEvent.ts >= since,
    )
    return db.execute(query).scalar() or 0
