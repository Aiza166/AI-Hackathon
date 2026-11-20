"""Admin: demo reset, API keys, mock-service faults (judge console), users, rules."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal, require_roles
from app.core.envelope import ok
from app.core.security import new_api_key
from app.db import get_db
from app.mock import registry
from app.models.platform import ApiKey, RuleVersion, User, utcnow
from app.schemas.contracts import Role
from app.seed import reset

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
ADMIN = require_roles(Role.ADMIN)
API_SCOPES = Literal["cases:status", "scam:check"]


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    scopes: list[API_SCOPES] = Field(min_length=1)


class FaultIn(BaseModel):
    service: Literal["identity", "death_registry", "pension_office", "payments"]
    mode: Literal["ok", "error", "slow"]
    latency_ms: int = Field(default=0, ge=0, le=10000)


@router.post("/seed/reset")
def seed_reset(principal: Principal = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    """Judge console 'Reset demo'. Audit history is kept; the reset is logged."""
    audit.record(db, principal.actor, "DEMO_RESET_REQUESTED")
    db.commit()
    reset(db)
    return ok({"reset": True, "note": "Sign in again: user IDs changed."})


@router.post("/api-keys", status_code=201)
def create_api_key(body: ApiKeyIn, principal: Principal = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    plain, prefix, key_hash = new_api_key()
    key = ApiKey(tenant_id=principal.tenant_id, name=body.name, key_prefix=prefix, key_hash=key_hash, scopes=list(body.scopes), created_by=principal.id)
    db.add(key)
    db.flush()
    audit.record(db, principal.actor, "API_KEY_CREATED", resource=f"api_key:{key.id}", details={"name": body.name, "scopes": list(body.scopes), "prefix": prefix})
    db.commit()
    return ok({"id": key.id, "api_key": plain, "note": "Shown once. Store it safely."})


@router.get("/api-keys")
def list_api_keys(principal: Principal = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(ApiKey).where(ApiKey.tenant_id == principal.tenant_id)).scalars()
    return ok([{"id": k.id, "name": k.name, "prefix": k.key_prefix, "scopes": k.scopes, "revoked": k.revoked_at is not None} for k in rows])


@router.post("/api-keys/{key_id}/revoke")
def revoke_api_key(key_id: str, principal: Principal = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    key = db.get(ApiKey, key_id)
    if key is None or key.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="API key not found")
    key.revoked_at = utcnow()
    audit.record(db, principal.actor, "API_KEY_REVOKED", resource=f"api_key:{key.id}")
    db.commit()
    return ok({"revoked": True})


@router.post("/faults")
def set_fault(body: FaultIn, principal: Principal = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    """Judge console: break or slow down a mock government service."""
    fault = registry.set_fault(db, body.service, body.mode, body.latency_ms)
    audit.record(db, principal.actor, "MOCK_FAULT_SET", resource=f"mock:{body.service}", details=body.model_dump())
    db.commit()
    return ok({"service": fault.service, "mode": fault.mode, "latency_ms": fault.latency_ms})


@router.get("/users")
def list_users(principal: Principal = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(User).where(User.tenant_id == principal.tenant_id).order_by(User.role, User.name)).scalars()
    return ok([{"id": u.id, "name": u.name, "role": u.role, "phone_last4": u.phone[-4:], "active": u.active} for u in rows])


@router.get("/rules")
def list_rules(principal: Principal = Depends(require_roles(Role.ADMIN, Role.AUDITOR, Role.OFFICER)), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(RuleVersion).order_by(RuleVersion.ruleset, RuleVersion.version)).scalars()
    return ok([{
        "id": r.id, "ruleset": r.ruleset, "version": r.version, "label": r.label, "status": r.status,
        "effective_from": r.effective_from.isoformat() if r.effective_from else None,
        "thresholds": r.thresholds, "rules": r.rules,
    } for r in rows])
