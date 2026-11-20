"""Append-only, SHA-256 hash-chained audit log.

Every user, AI and system action is recorded with record(). Each row's hash
covers the previous row's hash, so editing or removing any row breaks the
chain, and verify_chain() reports the first broken row.
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.platform import utcnow

GENESIS_HASH = "0" * 64
_CHAIN_LOCK_KEY = 74_220_011  # arbitrary constant for pg_advisory_xact_lock


@dataclass(frozen=True)
class Actor:
    actor_type: str  # user | ai | system | agent | api_key
    actor_id: str | None = None
    role: str | None = None


SYSTEM = Actor("system")
AI = Actor("ai", "decision-engine")


def _canonical(ts: datetime, actor: Actor, action: str, resource: str | None, case_id: str | None, details: dict) -> str:
    body = {
        "ts": ts.astimezone(timezone.utc).isoformat(),  # normalised: DB session time zone must not matter
        "actor_type": actor.actor_type,
        "actor_id": actor.actor_id,
        "role": actor.role,
        "action": action,
        "resource": resource,
        "case_id": case_id,
        "details": details,
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)


def _hash(prev_hash: str, canonical: str) -> str:
    return hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


def record(
    db: Session,
    actor: Actor,
    action: str,
    *,
    resource: str | None = None,
    case_id: str | None = None,
    details: dict | None = None,
) -> AuditEvent:
    """Append one event. Runs inside the caller's transaction; the advisory lock
    serialises writers so the chain never forks."""
    details = details or {}
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CHAIN_LOCK_KEY})
    last = db.execute(select(AuditEvent.hash).order_by(AuditEvent.seq.desc()).limit(1)).scalar()
    prev_hash = last or GENESIS_HASH
    ts = utcnow()
    canonical = _canonical(ts, actor, action, resource, case_id, details)
    event = AuditEvent(
        ts=ts,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        role=actor.role,
        action=action,
        resource=resource,
        case_id=case_id,
        details=details,
        prev_hash=prev_hash,
        hash=_hash(prev_hash, canonical),
    )
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> dict:
    prev_hash = GENESIS_HASH
    count = 0
    for event in db.execute(select(AuditEvent).order_by(AuditEvent.seq)).scalars():
        actor = Actor(event.actor_type, event.actor_id, event.role)
        canonical = _canonical(event.ts, actor, event.action, event.resource, event.case_id, event.details)
        if event.prev_hash != prev_hash or event.hash != _hash(prev_hash, canonical):
            return {"intact": False, "checked": count, "first_broken_seq": event.seq}
        prev_hash = event.hash
        count += 1
    return {"intact": True, "checked": count, "first_broken_seq": None}
