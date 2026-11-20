"""Request/response schemas for survivor pension claims."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.contracts import Explanation, ReasonCode, Route

CNIC_PATTERN = r"^\d{13}$"
DocumentKind = Literal["death_certificate", "claimant_cnic", "frc", "nikah_nama"]


class ClaimIn(BaseModel):
    claimant_cnic: str = Field(pattern=CNIC_PATTERN)
    claimant_name: str = Field(min_length=2, max_length=120)
    claimant_dob: date | None = None
    relation_claimed: Literal["widow", "son", "daughter"]
    deceased_cnic: str | None = Field(default=None, pattern=CNIC_PATTERN)
    deceased_name: str = Field(min_length=2, max_length=120)
    date_of_death: date | None = None
    payout_iban: str = Field(min_length=10, max_length=34, pattern=r"^[A-Z0-9]+$")
    documents: list[DocumentKind] = Field(default_factory=list, max_length=10)


class CaseCreated(BaseModel):
    id: str
    reference: str
    status: str


class DecisionSummary(BaseModel):
    id: str
    route: Route
    reason_codes: list[ReasonCode]
    confidence: float
    rule_version: int
    rule_version_id: str
    model_id: str | None
    created_at: datetime


class CaseView(BaseModel):
    id: str
    reference: str
    status: str
    priority: int
    confidence: float | None
    claimant_person_id: str
    assigned_officer_id: str | None
    deceased_cnic: str | None
    created_at: datetime
    latest_decision: DecisionSummary | None = None


class CitizenExplanation(BaseModel):
    case_reference: str
    status: str
    route: Route | None
    explanations: list[Explanation]
    missing_items: list[str] = []
    entitlement_end: date | None = None


class OfficerAction(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class AssignIn(BaseModel):
    officer_id: str
