"""Login with phone + PIN, and logout. Login is rate limited and PIN-locked (core/lockout.py).

There is no refresh token: access tokens are short-lived and the app signs in again.
Logout revokes every token the user holds (audit-derived, see core/lockout.token_revoked).
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit, lockout
from app.core.auth import Principal, get_principal
from app.core.envelope import ok
from app.core.ratelimit import limiter
from app.core.security import create_access_token, hash_pin, verify_pin
from app.db import get_db
from app.models.platform import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
_DUMMY_HASH = hash_pin("not-a-real-pin")  # unknown phones still cost one bcrypt check


class LoginIn(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    pin: str = Field(min_length=4, max_length=8)


def _session(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role, user.tenant_id),
        "token_type": "bearer",
        "user": {"id": user.id, "name": user.name, "role": user.role, "tenant_id": user.tenant_id, "person_id": user.person_id},
    }


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, body: LoginIn, db: Session = Depends(get_db)) -> dict:
    user = db.execute(select(User).where(User.phone == body.phone)).scalar_one_or_none()
    if user is not None and lockout.is_locked(db, user, request):
        audit.record(db, audit.Actor("user", user.id, user.role, user.tenant_id), "LOGIN_LOCKED")
        db.commit()
        raise HTTPException(status_code=429, detail="Too many wrong PINs. Please wait 15 minutes or ask your helper.")
    pin_ok = verify_pin(body.pin, user.pin_hash if user else _DUMMY_HASH)
    if user is None or not user.active or not pin_ok:
        if user is not None:
            lockout.record_failure(db, user, request, "LOGIN_FAILED", details={"phone_last4": body.phone[-4:]})
        else:
            audit.record(db, audit.Actor("user"), "LOGIN_FAILED", details={"phone_last4": body.phone[-4:]})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong phone number or PIN")
    lockout.record_success(db, user, request)
    db.commit()
    return ok(_session(user))


@router.post("/logout")
def logout(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    """End every session of this user (all tokens issued before now stop working)."""
    if principal.kind != "user":
        raise HTTPException(status_code=400, detail="Only signed-in users can log out")
    user = db.get(User, principal.id)
    lockout.revoke_sessions(db, user, "LOGOUT", reason="user signed out")
    db.commit()
    return ok({"signed_out": True})
