"""One PIN-failure counter for sign-in and payout confirmation, read from the audit log.

- Wrong PINs at login (LOGIN_FAILED) and at SafeSwitch confirm (PAYOUT_CONFIRM_FAILED)
  count together, per user, over the last 15 minutes.
- The lock is per (user, client IP): 5 failures from one IP lock that IP only, so a
  stranger cannot lock Zainab out of her own phone. 20 failures from any IPs lock the
  account everywhere (slow distributed guessing).
- 5 wrong payout-confirm PINs also end every open session (SESSIONS_REVOKED).
- An admin, or the helper assigned to the family, can unlock (PIN_UNLOCKED, audited);
  failures before the unlock no longer count. A successful sign-in from an IP clears
  that IP's count.
No schema change: all state is in the append-only audit log.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core import audit
from app.core.ratelimit import client_ip
from app.models.audit import AuditEvent
from app.models.platform import User, utcnow

WINDOW = timedelta(minutes=15)
MAX_PER_IP = 5
MAX_PER_ACCOUNT = 20
MAX_PAYOUT_FAILURES = 5
FAILURE_ACTIONS = ("LOGIN_FAILED", "PAYOUT_CONFIRM_FAILED")
REVOKE_ACTIONS = ("SESSIONS_REVOKED", "LOGOUT")


def user_resource(user_id: str) -> str:
    return f"user:{user_id}"


def _actor(user: User) -> audit.Actor:
    return audit.Actor("user", user.id, user.role, user.tenant_id)


def _last_unlock(db: Session, user_id: str) -> datetime | None:
    query = select(func.max(AuditEvent.ts)).where(AuditEvent.action == "PIN_UNLOCKED",
                                                   AuditEvent.resource == user_resource(user_id))
    return db.execute(query).scalar()


def _since(db: Session, user_id: str) -> datetime:
    since = utcnow() - WINDOW
    unlocked = _last_unlock(db, user_id)
    return max(since, unlocked) if unlocked else since


def _count(db: Session, user_id: str, actions: tuple[str, ...], since: datetime, ip: str | None = None) -> int:
    query = select(func.count(AuditEvent.seq)).where(AuditEvent.action.in_(actions), AuditEvent.actor_id == user_id,
                                                     AuditEvent.ts > since)
    if ip is not None:
        query = query.where(AuditEvent.details["ip"].as_string() == ip)
    return db.execute(query).scalar() or 0


def _since_for_ip(db: Session, user_id: str, ip: str) -> datetime:
    since = _since(db, user_id)
    last_ok = db.execute(select(func.max(AuditEvent.ts)).where(
        AuditEvent.action == "LOGIN", AuditEvent.actor_id == user_id, AuditEvent.details["ip"].as_string() == ip)).scalar()
    return max(since, last_ok) if last_ok else since


def is_locked(db: Session, user: User, request: Request) -> bool:
    ip = client_ip(request)
    if _count(db, user.id, FAILURE_ACTIONS, _since_for_ip(db, user.id, ip), ip) >= MAX_PER_IP:
        return True
    return _count(db, user.id, FAILURE_ACTIONS, _since(db, user.id)) >= MAX_PER_ACCOUNT


def record_failure(db: Session, user: User, request: Request, action: str, **fields) -> None:
    """Audit a wrong PIN (caller commits). Ends all sessions after too many payout failures."""
    audit.record(db, _actor(user), action, details={"ip": client_ip(request), **fields.pop("details", {})}, **fields)
    if action == "PAYOUT_CONFIRM_FAILED":
        db.flush()
        if _count(db, user.id, ("PAYOUT_CONFIRM_FAILED",), _since(db, user.id)) >= MAX_PAYOUT_FAILURES:
            revoke_sessions(db, user, "SESSIONS_REVOKED", reason="too many wrong payout PINs")


def record_success(db: Session, user: User, request: Request) -> None:
    audit.record(db, _actor(user), "LOGIN", details={"ip": client_ip(request)})


def revoke_sessions(db: Session, user: User, action: str, reason: str) -> None:
    audit.record(db, _actor(user), action, resource=user_resource(user.id), details={"reason": reason})


def unlock(db: Session, actor: audit.Actor, user: User) -> None:
    audit.record(db, actor, "PIN_UNLOCKED", resource=user_resource(user.id), tenant_id=user.tenant_id,
                 details={"target_role": user.role})


def token_revoked(db: Session, user_id: str, issued_ms: int | None) -> bool:
    """True if the user logged out or was locked after this token was issued."""
    revoked_at = db.execute(select(func.max(AuditEvent.ts)).where(
        AuditEvent.action.in_(REVOKE_ACTIONS), AuditEvent.actor_id == user_id, AuditEvent.resource == user_resource(user_id))).scalar()
    if revoked_at is None:
        return False
    if issued_ms is None:
        return True  # tokens without "sid" predate revocation support
    issued = datetime.fromtimestamp(issued_ms / 1000, tz=timezone.utc)
    return issued <= revoked_at
