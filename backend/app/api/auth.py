"""Login with phone + PIN; refresh tokens. Login is rate limited."""
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.envelope import ok
from app.core.ratelimit import limiter
from app.core.security import create_access_token, create_refresh_token, decode_token, verify_pin
from app.db import get_db
from app.models.platform import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


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
    if user is None or not user.active or not verify_pin(body.pin, user.pin_hash):
        audit.record(db, audit.Actor("user", user.id if user else None), "LOGIN_FAILED", details={"phone_last4": body.phone[-4:]})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong phone number or PIN")
    audit.record(db, audit.Actor("user", user.id, user.role), "LOGIN")
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
