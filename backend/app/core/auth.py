"""Who is calling? JWT (users) or X-API-Key (outside systems), plus role checks.

Role checks run on the server for every route. A denied attempt is written to
the audit log before the 403 is returned, so judges can see blocked calls.
"""
from collections.abc import Callable
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.security import decode_token, hash_api_key
from app.db import get_db
from app.models.platform import ApiKey, User
from app.schemas.contracts import Role

_bearer = HTTPBearer(auto_error=False)
_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class Principal:
    kind: str  # "user" | "api_key"
    id: str
    role: str  # a Role value, or "integration" for API keys
    tenant_id: str
    person_id: str | None = None
    scopes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def actor(self) -> audit.Actor:
        return audit.Actor("user" if self.kind == "user" else "api_key", self.id, self.role, self.tenant_id)


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")


def _from_jwt(db: Session, token: str) -> Principal:
    try:
        claims = decode_token(token, expected_type="access")
    except jwt.InvalidTokenError as exc:
        raise _unauthorized() from exc
    user = db.get(User, claims["sub"])
    if user is None or not user.active:
        raise _unauthorized()
    return Principal("user", user.id, user.role, user.tenant_id, user.person_id)


def _from_api_key(db: Session, plain: str) -> Principal:
    key = db.execute(select(ApiKey).where(ApiKey.key_hash == hash_api_key(plain))).scalar_one_or_none()
    if key is None or key.revoked_at is not None:
        raise _unauthorized()
    return Principal("api_key", key.id, "integration", key.tenant_id, scopes=tuple(key.scopes or ()))


def get_principal(
    db: Session = Depends(get_db),
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
    api_key: str | None = Depends(_api_key),
) -> Principal:
    if bearer is not None:
        return _from_jwt(db, bearer.credentials)
    if api_key:
        return _from_api_key(db, api_key)
    raise _unauthorized()


def deny(db: Session, principal: Principal, request: Request, reason: str) -> HTTPException:
    """Log the blocked attempt (committed on its own) and return the 403 to raise."""
    audit.record(
        db,
        principal.actor,
        "ACCESS_DENIED",
        resource=f"{request.method} {request.url.path}",
        details={"reason": reason},
    )
    db.commit()
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission for this action")


def require_roles(*roles: Role) -> Callable[..., Principal]:
    allowed = {r.value for r in roles}

    def dependency(
        request: Request,
        principal: Principal = Depends(get_principal),
        db: Session = Depends(get_db),
    ) -> Principal:
        if principal.role not in allowed:
            raise deny(db, principal, request, f"role {principal.role} not in {sorted(allowed)}")
        return principal

    return dependency


def require_scope(scope: str) -> Callable[..., Principal]:
    """For outside systems using API keys (staff users with JWT are not allowed here)."""

    def dependency(
        request: Request,
        principal: Principal = Depends(get_principal),
        db: Session = Depends(get_db),
    ) -> Principal:
        if principal.kind != "api_key" or scope not in principal.scopes:
            raise deny(db, principal, request, f"missing API scope {scope}")
        return principal

    return dependency
