"""Login with phone + PIN; rotating, revocable refresh tokens; sign-out. Rate limited."""
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.envelope import ok
from app.core.lockout import MAX_FAILURES, recent_failures
from app.core.ratelimit import limiter
from app.core.auth import Principal, get_principal
from app.core.security import REFRESH_TOKEN_DAYS, create_access_token, create_refresh_token, decode_token, hash_pin, new_jti, verify_pin
from app.db import get_db
from app.models.platform import User, utcnow
from app.models.session import AuthSession

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
_DUMMY_HASH = hash_pin("not-a-real-pin")  # unknown phones still cost one bcrypt check


class LoginIn(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    pin: str = Field(min_length=4, max_length=8)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=2000)


def _open_session(db: Session, user: User) -> AuthSession:
    # Housekeeping: this user's expired sessions are no longer needed (keeps the table small).
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at < utcnow()))
    session = AuthSession(user_id=user.id, current_jti=new_jti(), expires_at=utcnow() + timedelta(days=REFRESH_TOKEN_DAYS))
    db.add(session)
    db.flush()
    return session


def revoke_session(db: Session, session: AuthSession, reason: str) -> None:
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        session.revoked_reason = reason


def _tokens(user: User, session: AuthSession) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role, user.tenant_id, session.id),
        "refresh_token": create_refresh_token(user.id, session.id, session.current_jti),
        "token_type": "bearer",
        "user": {"id": user.id, "name": user.name, "role": user.role, "tenant_id": user.tenant_id, "person_id": user.person_id},
    }


@router.post("/login")
@limiter.limit("60/minute")  # per IP: judges share one venue IP; guessing is stopped by the per-account lockout
def login(request: Request, body: LoginIn, db: Session = Depends(get_db)) -> dict:
    user = db.execute(select(User).where(User.phone == body.phone)).scalar_one_or_none()
    if user is not None and recent_failures(db, user.id, "LOGIN_FAILED") >= MAX_FAILURES:
        audit.record(db, audit.Actor("user", user.id, user.role, user.tenant_id), "LOGIN_LOCKED")
        db.commit()
        raise HTTPException(status_code=429, detail="Too many wrong PINs. Please wait 15 minutes or ask your helper.")
    pin_ok = verify_pin(body.pin, user.pin_hash if user else _DUMMY_HASH)
    if user is None or not user.active or not pin_ok:
        actor = audit.Actor("user", user.id, user.role, user.tenant_id) if user else audit.Actor("user")
        audit.record(db, actor, "LOGIN_FAILED", details={"phone_last4": body.phone[-4:]})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong phone number or PIN")
    session = _open_session(db, user)
    audit.record(db, audit.Actor("user", user.id, user.role, user.tenant_id), "LOGIN", details={"session": session.id})
    db.commit()
    return ok(_tokens(user, session))


@router.post("/refresh")
@limiter.limit("30/minute")
def refresh(request: Request, body: RefreshIn, db: Session = Depends(get_db)) -> dict:
    try:
        claims = decode_token(body.refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in again") from exc
    session = db.get(AuthSession, claims["sid"], with_for_update=True)
    if session is None or session.user_id != claims["sub"] or session.revoked_at is not None or session.expires_at <= utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in again")
    user = db.get(User, claims["sub"])
    actor = audit.Actor("user", claims["sub"], user.role if user else None, user.tenant_id if user else None)
    if claims["jti"] != session.current_jti:
        # An already-used refresh token came back: someone holds a copy. End the whole session.
        revoke_session(db, session, "reuse")
        audit.record(db, actor, "REFRESH_TOKEN_REUSED", details={"session": session.id})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in again")
    if user is None or not user.active:
        revoke_session(db, session, "user_inactive")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in again")
    session.current_jti = new_jti()  # rotate: the token just used is now spent
    audit.record(db, actor, "TOKEN_REFRESHED", details={"session": session.id})
    db.commit()
    return ok(_tokens(user, session))


@router.post("/logout")
@limiter.limit("30/minute")
def logout(request: Request, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    """Revoke this sign-in session: its refresh token and every access token issued for it stop working."""
    if principal.kind != "user" or principal.session_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only signed-in users can sign out")
    session = db.get(AuthSession, principal.session_id, with_for_update=True)
    if session is not None:
        revoke_session(db, session, "logout")
    audit.record(db, principal.actor, "LOGOUT", details={"session": principal.session_id})
    db.commit()
    return ok({"signed_out": True})
