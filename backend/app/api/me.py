"""Who am I, and (for helpers) which families can I act for."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import lockout
from app.core.auth import Principal, deny, get_principal, require_roles
from app.core.consent import active_consent
from app.core.envelope import ok
from app.db import get_db
from app.models.platform import HelperAssignment, Person, User
from app.schemas.contracts import Role

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me")
def me(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, principal.id) if principal.kind == "user" else None
    person = db.get(Person, principal.person_id) if principal.person_id else None
    return ok({
        "id": principal.id, "kind": principal.kind, "role": principal.role, "tenant_id": principal.tenant_id,
        "name": user.name if user else None,
        "person": {"id": person.id, "cnic": person.cnic, "name": person.display_name} if person else None,
    })


@router.get("/helper/families")
def helper_families(principal: Principal = Depends(require_roles(Role.HELPER)), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(
        select(Person).join(HelperAssignment, HelperAssignment.person_id == Person.id)
        .where(HelperAssignment.helper_user_id == principal.id).order_by(Person.display_name)
    ).scalars()
    families = []
    for p in rows:
        # Without the family's consent the helper sees only the name, never the CNIC.
        shared = active_consent(db, principal, p.id, "cnic") is not None
        families.append({"id": p.id, "name": p.display_name, "cnic": p.cnic if shared else None, "consent_active": shared})
    return ok(families)


@router.post("/helper/families/{person_id}/unlock")
def unlock_family(person_id: str, request: Request, principal: Principal = Depends(require_roles(Role.HELPER)),
                  db: Session = Depends(get_db)) -> dict:
    """A helper clears the PIN lockout of a family she is assigned to (audited as PIN_UNLOCKED)."""
    assigned = db.execute(select(HelperAssignment).where(HelperAssignment.helper_user_id == principal.id,
                                                         HelperAssignment.person_id == person_id)).first()
    if assigned is None:
        raise deny(db, principal, request, "not an assigned family")
    user = db.execute(select(User).where(User.person_id == person_id)).scalars().first()
    if user is None:
        raise HTTPException(status_code=404, detail="This family has no sign-in account")
    lockout.unlock(db, principal.actor, user)
    db.commit()
    return ok({"unlocked": True})
