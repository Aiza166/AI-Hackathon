"""Server-side Idempotency-Key handling (IETF httpapi Idempotency-Key draft).

Flow for one request that carries a key:
1. begin(): insert an "in_flight" row and COMMIT it, so it survives whatever the
   claim transaction does next. If the row already exists:
   - different request body -> 422
   - still in flight         -> 409
   - done                    -> replay the stored response
2. The caller processes the request and commits it.
3. finish(): store the response on the row ("done") and commit.
4. abandon(): on any error the row is deleted so a retry can proceed.

Keys are scoped per principal: two users may send the same key independently.
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.idempotency import IdempotencyKey
from app.models.platform import utcnow

MAX_KEY_LENGTH = 255
# An in-flight row older than this belongs to a request that died without cleanup
# (e.g. the process was killed); a retry may take it over.
STALE_IN_FLIGHT = timedelta(minutes=2)


@dataclass(frozen=True)
class Replay:
    status: int
    body: dict


def request_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def validate_key(key: str) -> str:
    key = key.strip()
    if not key or len(key) > MAX_KEY_LENGTH or not key.isprintable():
        raise HTTPException(status_code=400, detail="Idempotency-Key must be 1-255 printable characters")
    return key


def _existing(db: Session, principal_id: str, key: str) -> IdempotencyKey | None:
    query = select(IdempotencyKey).where(IdempotencyKey.principal_id == principal_id, IdempotencyKey.key == key)
    return db.execute(query).scalar_one_or_none()


def _replay_or_refuse(db: Session, row: IdempotencyKey, digest: str) -> Replay | None:
    """Decide what to do with a key we have seen before. None means "take over the stale row"."""
    if row.request_hash != digest:
        raise HTTPException(status_code=422, detail="This Idempotency-Key was already used with a different request")
    if row.status == "done":
        body = dict(row.response_body or {})
        body["meta"] = {**(body.get("meta") or {}), "idempotent_replay": True}
        return Replay(status=row.response_status or 200, body=body)
    if utcnow() - row.created_at < STALE_IN_FLIGHT:
        raise HTTPException(status_code=409, detail="This request is still being processed. Please wait a moment.")
    row.created_at = utcnow()
    db.commit()
    return None


def begin(db: Session, principal_id: str, key: str, payload: dict) -> Replay | None:
    """Reserve the key. Returns a Replay when a stored response should be sent instead."""
    digest = request_hash(payload)
    row = _existing(db, principal_id, key)
    if row is not None:
        return _replay_or_refuse(db, row, digest)
    db.add(IdempotencyKey(principal_id=principal_id, key=key, request_hash=digest, status="in_flight"))
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent request carrying the same key.
        db.rollback()
        row = _existing(db, principal_id, key)
        if row is None:
            raise HTTPException(status_code=409, detail="This request is still being processed. Please wait a moment.") from None
        return _replay_or_refuse(db, row, digest)
    return None


def finish(db: Session, principal_id: str, key: str, status: int, body: dict) -> None:
    row = _existing(db, principal_id, key)
    if row is None:
        return
    row.status = "done"
    row.response_status = status
    row.response_body = body
    db.commit()


def abandon(db: Session, principal_id: str, key: str) -> None:
    db.rollback()
    db.execute(delete(IdempotencyKey).where(
        IdempotencyKey.principal_id == principal_id, IdempotencyKey.key == key, IdempotencyKey.status == "in_flight",
    ))
    db.commit()
