"""Import every model so Alembic sees the full metadata."""
from app.models.audit import AuditEvent
from app.models.consent import Consent, CorrectionRequest
from app.models.payout import PayoutChangeRequest
from app.models.mock import (
    MockAccount,
    MockDeath,
    MockFamilyLink,
    MockFamilyPensionDrawn,
    MockFault,
    MockPension,
    MockPerson,
)
from app.models.platform import (
    ApiKey,
    Case,
    CaseEvent,
    Decision,
    HelperAssignment,
    Person,
    RuleVersion,
    Tenant,
    User,
)

__all__ = [
    "ApiKey",
    "AuditEvent",
    "Case",
    "CaseEvent",
    "Consent",
    "CorrectionRequest",
    "Decision",
    "HelperAssignment",
    "MockAccount",
    "MockDeath",
    "MockFamilyLink",
    "MockFamilyPensionDrawn",
    "MockFault",
    "MockPension",
    "MockPerson",
    "PayoutChangeRequest",
    "Person",
    "RuleVersion",
    "Tenant",
    "User",
]
