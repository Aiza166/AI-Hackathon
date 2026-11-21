"""Shared contracts between backend and frontend.

The frontend generates its TypeScript types from the OpenAPI spec, so changing
these enums or models changes the frontend contract. Tell the other person.
"""
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Role(StrEnum):
    CITIZEN = "citizen"
    HELPER = "helper"
    OFFICER = "officer"
    ADMIN = "admin"
    AUDITOR = "auditor"


class Route(StrEnum):
    AUTO_APPROVE = "AUTO_APPROVE"
    ASK_PROOF = "ASK_PROOF"
    UNSURE = "UNSURE"  # "I am not sure": a human (officer) takes over


class ReasonCode(StrEnum):
    APPROVED = "APPROVED"
    DUPLICATE_CLAIM = "DUPLICATE_CLAIM"
    NAME_MISMATCH = "NAME_MISMATCH"
    MISSING_DEATH_CERT = "MISSING_DEATH_CERT"
    MISSING_INFO = "MISSING_INFO"
    ACCOUNT_NOT_OWNED = "ACCOUNT_NOT_OWNED"
    ACCOUNT_REUSED = "ACCOUNT_REUSED"
    DOC_EDIT_RISK = "DOC_EDIT_RISK"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    JEV_UNDECIDED = "JEV_UNDECIDED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    NOT_IN_FAMILY_RECORD = "NOT_IN_FAMILY_RECORD"
    DEATH_NOT_VERIFIED = "DEATH_NOT_VERIFIED"
    NO_PENSION_RECORD = "NO_PENSION_RECORD"
    ALREADY_DRAWING = "ALREADY_DRAWING"
    CHILD_OVER_AGE = "CHILD_OVER_AGE"
    DAUGHTER_MARRIED = "DAUGHTER_MARRIED"
    WIDOW_FIRST = "WIDOW_FIRST"
    PAYEE_CLOSE_MATCH = "PAYEE_CLOSE_MATCH"
    TIME_LIMITED = "TIME_LIMITED"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    CONFIRM_DOB = "CONFIRM_DOB"  # claimant left her date of birth blank: ask, never reject
    DOB_MISMATCH = "DOB_MISMATCH"  # typed DOB differs from the identity record
    DOC_MISMATCH = "DOC_MISMATCH"


class CaseStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    AUTO_APPROVED = "auto_approved"
    PROOF_REQUESTED = "proof_requested"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


class ScamVerdict(StrEnum):
    LIKELY_SCAM = "LIKELY_SCAM"
    LOOKS_GENUINE = "LOOKS_GENUINE"
    NOT_SURE = "NOT_SURE"


class CaseOut(BaseModel):
    id: str
    status: CaseStatus
    claimant_person_id: str
    deceased_cnic: str
    priority: int = Field(ge=0, le=3)
    assigned_officer_id: str | None = None
    created_at: datetime


class Explanation(BaseModel):
    """What the citizen sees and hears: fixed text, never generated."""

    reason_code: ReasonCode
    text_ur: str
    text_en: str
    audio_key: str
    icon: str


class DecisionOut(BaseModel):
    id: str
    case_id: str
    route: Route
    reason_codes: list[ReasonCode]
    confidence: float = Field(ge=0, le=1)
    rule_version_id: str
    model_id: str | None  # Jev model that actually answered, or None if Jev was not used
    created_at: datetime


class DecisionTrace(DecisionOut):
    """Auditor view: everything needed to reproduce the decision."""

    input_hash: str
    signals: dict
    jev_raw: dict | None
    thresholds: dict


class ConsentOut(BaseModel):
    id: str
    subject_person_id: str
    grantee_type: str
    grantee_id: str
    purpose: str
    fields: list[str]
    valid_until: datetime | None
    status: str


class ScamCheckIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    sender: str | None = Field(default=None, max_length=40)
    on_call_with_unknown: bool | None = None
    area: str | None = Field(default=None, max_length=60)


class ScamCheckOut(BaseModel):
    verdict: ScamVerdict
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]
    case_cross_check: str | None = None


class RuleVersionOut(BaseModel):
    id: str
    ruleset: str
    version: int
    status: str
    thresholds: dict
    published_at: datetime | None
