"""Rule editor, Digital Twin, second-admin approval and publish (no code change, no redeploy)."""
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.admin import platform_admin
from app.core.auth import Principal
from app.core.envelope import ok
from app.db import get_db
from app.services import rules as svc

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])
MAX_DRAFT_BODY_BYTES = 2 * svc.MAX_RULES_JSON_BYTES  # label + rules + thresholds, checked before parsing (L2)


class DraftIn(BaseModel):
    label: str = Field(min_length=3, max_length=200)
    rules: list[dict] = Field(min_length=1, max_length=50)
    thresholds: dict
    effective_from: date | None = None


def _row(r) -> dict:
    return {"id": r.id, "version": r.version, "label": r.label, "status": r.status,
            "effective_from": r.effective_from.isoformat() if r.effective_from else None,
            "published_at": r.published_at.isoformat() if r.published_at else None}


async def _draft_body(request: Request) -> DraftIn:
    """Parse the draft ourselves so oversized or absurdly nested JSON is a 422, never a 500."""
    raw = await request.body()
    if len(raw) > MAX_DRAFT_BODY_BYTES:
        raise HTTPException(status_code=422, detail=f"Draft is too large (max {MAX_DRAFT_BODY_BYTES} bytes)")
    try:
        return DraftIn.model_validate(json.loads(raw))
    except (ValueError, RecursionError):
        raise HTTPException(status_code=422, detail="Draft must be valid JSON") from None
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_input=False)) from None


@router.post("/drafts", status_code=201)
def create_draft(principal: Principal = Depends(platform_admin), body: DraftIn = Depends(_draft_body), db: Session = Depends(get_db)) -> dict:
    draft = svc.create_draft(db, principal, body.label, body.rules, body.thresholds, body.effective_from)
    db.commit()
    return ok(_row(draft))


@router.post("/{version_id}/simulate")
def simulate(version_id: str, principal: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    """Digital Twin: what would change if this version went live? Nothing is saved."""
    draft = svc.version_or_404(db, version_id)
    return ok(svc.simulate(db, principal, draft))


@router.post("/{version_id}/approve")
def approve(version_id: str, principal: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    """Second-admin sign-off on a simulated draft; the publisher must be a different admin."""
    draft = svc.approve(db, principal, svc.version_or_404(db, version_id))
    db.commit()
    return ok(_row(draft))


@router.post("/{version_id}/publish")
def publish(version_id: str, principal: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    published = svc.publish(db, principal, svc.version_or_404(db, version_id))
    db.commit()
    return ok(_row(published))
