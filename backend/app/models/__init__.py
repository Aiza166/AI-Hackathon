"""Import every model so Alembic sees the full metadata."""
from app.models.audit import AuditEvent
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
    "Decision",
    "HelperAssignment",
    "MockAccount",
    "MockDeath",
    "MockFamilyLink",
    "MockFamilyPensionDrawn",
    "MockFault",
    "MockPension",
    "MockPerson",
    "Person",
    "RuleVersion",
    "Tenant",
    "User",
]
