"""Rule editor, Digital Twin and publish (no code change, no redeploy)."""
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.admin import platform_admin
from app.core.auth import Principal
from app.core.envelope import ok
from app.db import get_db
from app.services import rules as svc

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


class DraftIn(BaseModel):
    label: str = Field(min_length=3, max_length=200)
    rules: list[dict] = Field(min_length=1, max_length=50)
    thresholds: dict
    effective_from: date | None = None


def _row(r) -> dict:
    return {"id": r.id, "version": r.version, "label": r.label, "status": r.status,
            "effective_from": r.effective_from.isoformat() if r.effective_from else None,
            "published_at": r.published_at.isoformat() if r.published_at else None}


@router.post("/drafts", status_code=201)
def create_draft(body: DraftIn, principal: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    draft = svc.create_draft(db, principal, body.label, body.rules, body.thresholds, body.effective_from)
    db.commit()
    return ok(_row(draft))


@router.post("/{version_id}/simulate")
def simulate(version_id: str, principal: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    """Digital Twin: what would change if this version went live? Nothing is saved."""
    draft = svc.version_or_404(db, version_id)
    return ok(svc.simulate(db, principal, draft))


@router.post("/{version_id}/publish")
def publish(version_id: str, principal: Principal = Depends(platform_admin), db: Session = Depends(get_db)) -> dict:
    published = svc.publish(db, principal, svc.version_or_404(db, version_id))
    db.commit()
    return ok(_row(published))
