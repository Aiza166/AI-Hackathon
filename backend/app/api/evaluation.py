"""Evaluation page API (Challenge 1: show the numbers behind the choices)."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal, deny, require_roles
from app.core.config import get_settings
from app.core.envelope import fail, ok
from app.core.ratelimit import limiter
from app.db import get_db
from app.evaluation import runner
from app.schemas.contracts import Role
from app.services import cases as case_svc

router = APIRouter(prefix="/api/v1/eval", tags=["evaluation"])
READERS = (Role.ADMIN, Role.AUDITOR, Role.OFFICER)


def _live_ruleset(db: Session) -> dict:
    """Evaluate the rules in force today (live, or scheduled and now effective); v1 file if none."""
    try:
        row = case_svc.live_ruleset(db)
    except HTTPException:  # no published version yet
        row = None
    if row is None:
        return runner.default_ruleset()
    return case_svc.ruleset_dict(row)


@router.get("/latest")
def latest(principal: Principal = Depends(require_roles(*READERS)), db: Session = Depends(get_db)) -> dict:
    result = runner.latest()
    if result is None:
        result = runner.run_all(_live_ruleset(db))
    return ok(result)


@router.post("/run")
@limiter.limit("6/minute")
def run(request: Request, live: bool = Query(default=False, description="Run the scam set through the real Jev (admin only)"),
        principal: Principal = Depends(require_roles(*READERS)), db: Session = Depends(get_db)):
    if live and principal.role != Role.ADMIN.value:
        raise deny(db, principal, request, "live evaluation is admin only")
    if live and not get_settings().typesafe_api_key:
        return fail(code="JEV_NOT_CONFIGURED", message="Live evaluation needs the Jev API key on the server.", status=409)
    result = runner.run_all(_live_ruleset(db), live_scam=live)
    audit.record(db, principal.actor, "EVAL_RUN", resource="evaluation", details=result["summary"])
    db.commit()
    return ok(result)
