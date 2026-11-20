"""Login with phone + PIN; refresh tokens. Login is rate limited."""
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.envelope import ok
from app.core.ratelimit import limiter
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_pin, verify_pin
from app.db import get_db
from app.models.audit import AuditEvent
from app.models.platform import User, utcnow

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
MAX_FAILURES = 5
LOCKOUT = timedelta(minutes=15)
_DUMMY_HASH = hash_pin("not-a-real-pin")  # unknown phones still cost one bcrypt check


def _recent_failures(db: Session, user_id: str) -> int:
    since = utcnow() - LOCKOUT
    query = select(func.count(AuditEvent.seq)).where(
        AuditEvent.action == "LOGIN_FAILED", AuditEvent.actor_id == user_id, AuditEvent.ts >= since,
    )
    return db.execute(query).scalar() or 0


class LoginIn(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    pin: str = Field(min_length=4, max_length=8)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=2000)


def _tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role, user.tenant_id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "user": {"id": user.id, "name": user.name, "role": user.role, "tenant_id": user.tenant_id, "person_id": user.person_id},
    }


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, body: LoginIn, db: Session = Depends(get_db)) -> dict:
    user = db.execute(select(User).where(User.phone == body.phone)).scalar_one_or_none()
    if user is not None and _recent_failures(db, user.id) >= MAX_FAILURES:
        audit.record(db, audit.Actor("user", user.id, user.role, user.tenant_id), "LOGIN_LOCKED")
        db.commit()
        raise HTTPException(status_code=429, detail="Too many wrong PINs. Please wait 15 minutes or ask your helper.")
    pin_ok = verify_pin(body.pin, user.pin_hash if user else _DUMMY_HASH)
    if user is None or not user.active or not pin_ok:
        actor = audit.Actor("user", user.id, user.role, user.tenant_id) if user else audit.Actor("user")
        audit.record(db, actor, "LOGIN_FAILED", details={"phone_last4": body.phone[-4:]})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong phone number or PIN")
    audit.record(db, audit.Actor("user", user.id, user.role, user.tenant_id), "LOGIN")
    db.commit()
    return ok(_tokens(user))


@router.post("/refresh")
@limiter.limit("30/minute")
def refresh(request: Request, body: RefreshIn, db: Session = Depends(get_db)) -> dict:
    try:
        claims = decode_token(body.refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in again") from exc
    user = db.get(User, claims["sub"])
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in again")
    return ok(_tokens(user))
