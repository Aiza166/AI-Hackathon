"""Security: one open claim per claimant per deceased CNIC (red team C1).

Partial unique index backing the advisory lock in services/cases.create_case:
two parallel identical claims can no longer both be inserted.

Revision ID: sec01_cases
Revises: f3a9c1e2b4d6
"""
from alembic import op

revision = "sec01_cases"
down_revision = "f3a9c1e2b4d6"
branch_labels = None
depends_on = None

INDEX = "uq_cases_open_claim_per_claimant"
# Keep in sync with app.decision.facts.ACTIVE_STATUSES.
OPEN = "status IN ('submitted', 'auto_approved', 'proof_requested', 'in_review', 'approved') AND deceased_cnic IS NOT NULL"


def upgrade() -> None:
    op.execute(f"CREATE UNIQUE INDEX {INDEX} ON cases (claimant_person_id, deceased_cnic) WHERE {OPEN}")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX}")
