"""Clean HTTP APIs in front of the mock government and payment services.

Admin/auditor only: these hold (mock) personal records, and every read is
audited. The decision engine calls app.mock.registry directly in-process.
"""
from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import audit
from app.core.auth import Principal, require_roles
from app.core.envelope import ok
from app.db import get_db
from app.mock import raast, registry
from app.schemas.contracts import Role

router = APIRouter(prefix="/mock", tags=["mock government services (simulated)"])
READERS = require_roles(Role.ADMIN, Role.AUDITOR)


def _lookup(db: Session, principal: Principal, resource: str, fn: Callable[..., Any], *args: Any) -> Any:
    try:
        result = fn(db, *args)
    except registry.MockServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Mock {exc.service} service unavailable") from exc
    audit.record(db, principal.actor, "MOCK_RECORD_READ", resource=resource)
    db.commit()
    if result is None:
        raise HTTPException(status_code=404, detail="No record")
    return result


@router.get("/identity/persons/{cnic}")
def person(cnic: str, principal: Principal = Depends(READERS), db: Session = Depends(get_db)) -> dict:
    p = _lookup(db, principal, f"identity:{cnic[-4:]}", registry.get_person, cnic)
    return ok({"cnic": p.cnic, "full_name": p.full_name, "father_or_husband_name": p.father_or_husband_name,
               "dob": p.dob.isoformat() if p.dob else None, "district": p.district, "marital_status": p.marital_status})


@router.get("/identity/family/{head_cnic}")
def family(head_cnic: str, principal: Principal = Depends(READERS), db: Session = Depends(get_db)) -> dict:
    members = _lookup(db, principal, f"family:{head_cnic[-4:]}", registry.get_family, head_cnic)
    return ok([m.__dict__ for m in members])


@router.get("/death-registry/{cnic}")
def death(cnic: str, principal: Principal = Depends(READERS), db: Session = Depends(get_db)) -> dict:
    d = _lookup(db, principal, f"death:{cnic[-4:]}", registry.get_death, cnic)
    return ok({"cnic": d.cnic, "name_on_certificate": d.name_on_certificate, "date_of_death": d.date_of_death.isoformat(),
               "certificate_no": d.certificate_no, "union_council": d.union_council})


@router.get("/pension-office/{cnic}")
def pension(cnic: str, principal: Principal = Depends(READERS), db: Session = Depends(get_db)) -> dict:
    p = _lookup(db, principal, f"pension:{cnic[-4:]}", registry.get_pension, cnic)
    return ok({"cnic": p.pensioner_cnic, "name": p.name_in_pension_office, "monthly_amount_mock": p.monthly_amount, "status": p.status})


@router.get("/payments/accounts/{iban}/title")
def account_title(iban: str, principal: Principal = Depends(READERS), db: Session = Depends(get_db)) -> dict:
    a = _lookup(db, principal, f"account:{iban[-4:]}", registry.get_account, iban)
    return ok({"iban": a.iban, "title": a.title, "bank": a.bank})


class TitleFetchIn(BaseModel):
    request_id: str | None = Field(default=None, max_length=64)
    proxy_type: Literal["IBAN"] = "IBAN"  # RAAST_ID (mobile alias) is not simulated
    proxy_value: str = Field(min_length=10, max_length=34, pattern=r"^[A-Z0-9]+$")
    expected_name: str = Field(min_length=2, max_length=120)
    expected_cnic: str | None = Field(default=None, pattern=r"^\d{13}$")


@router.post("/raast/title-fetch")
def title_fetch(body: TitleFetchIn, principal: Principal = Depends(READERS), db: Session = Depends(get_db)) -> dict:
    """Simulated Raast title fetch plus OUR Confirmation-of-Payee verdict. Returns a masked title,
    account type, SINGLE/JOINT holding and `cnic_match` (true/false), never the CNIC itself.
    Break it from the judge console: POST /api/v1/admin/faults {"service": "raast", "mode": "timeout"}."""
    result = raast.title_fetch(db, body.proxy_value, body.expected_name, body.expected_cnic)
    audit.record(db, principal.actor, "MOCK_RECORD_READ", resource=f"raast:{body.proxy_value[-4:]}",
                 details={"status": result.status, "match_level": result.match_level})
    db.commit()
    return ok({"request_id": body.request_id, **result.to_dict()})
