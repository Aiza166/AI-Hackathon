"""Mock government and payment services (all data invented).

Each lookup first applies any injected fault (error or delay) for that
service, so the judge console can show what happens when a record service is
down: the decision engine must route to UNSURE, never guess.
"""
import time
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mock import (
    MockAccount,
    MockDeath,
    MockFamilyLink,
    MockFamilyPensionDrawn,
    MockFault,
    MockPension,
    MockPerson,
)

SERVICES = ("identity", "death_registry", "pension_office", "payments", "raast")
SLOW_LIMIT_MS = 2000  # anything slower than this counts as unavailable


class MockServiceUnavailable(Exception):
    def __init__(self, service: str):
        super().__init__(f"{service} unavailable")
        self.service = service


def _check_fault(db: Session, service: str) -> None:
    fault = db.get(MockFault, service)
    if fault is None or fault.mode == "ok":
        return
    if fault.mode in ("error", "timeout"):
        raise MockServiceUnavailable(service)
    if fault.mode == "slow":
        if fault.latency_ms >= SLOW_LIMIT_MS:
            raise MockServiceUnavailable(service)
        time.sleep(fault.latency_ms / 1000)


@dataclass(frozen=True)
class FamilyMember:
    frc_number: str
    head_cnic: str
    member_cnic: str
    relation: str


def get_person(db: Session, cnic: str) -> MockPerson | None:
    _check_fault(db, "identity")
    return db.get(MockPerson, cnic)


def find_persons_by_name_key(db: Session, key_token: str) -> list[MockPerson]:
    """Blocking helper: propose candidates whose name contains the key token."""
    _check_fault(db, "identity")
    pattern = f"%{key_token}%"
    return list(db.execute(select(MockPerson).where(MockPerson.full_name.ilike(pattern))).scalars())


def get_family(db: Session, head_cnic: str) -> list[FamilyMember]:
    _check_fault(db, "identity")
    rows = db.execute(select(MockFamilyLink).where(MockFamilyLink.head_cnic == head_cnic)).scalars()
    return [FamilyMember(r.frc_number, r.head_cnic, r.member_cnic, r.relation) for r in rows]


def get_death(db: Session, cnic: str) -> MockDeath | None:
    _check_fault(db, "death_registry")
    return db.get(MockDeath, cnic)


def get_pension(db: Session, cnic: str) -> MockPension | None:
    _check_fault(db, "pension_office")
    return db.get(MockPension, cnic)


def already_draws_family_pension(db: Session, cnic: str) -> date | None:
    _check_fault(db, "pension_office")
    row = db.get(MockFamilyPensionDrawn, cnic)
    return row.since if row else None


def get_account(db: Session, iban: str) -> MockAccount | None:
    _check_fault(db, "payments")
    return db.get(MockAccount, iban)


def set_fault(db: Session, service: str, mode: str, latency_ms: int = 0) -> MockFault:
    if service not in SERVICES:
        raise ValueError(f"unknown service {service}")
    fault = db.get(MockFault, service) or MockFault(service=service)
    fault.mode = mode
    fault.latency_ms = latency_ms
    db.add(fault)
    db.flush()
    return fault


def fault_mode(db: Session, service: str) -> str:
    fault = db.get(MockFault, service)
    return "ok" if fault is None else fault.mode
