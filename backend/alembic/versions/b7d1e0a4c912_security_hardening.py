"""security hardening: audit tenant, case reference sequence, stricter audit guard

Revision ID: b7d1e0a4c912
Revises: c96446bc2226
Create Date: 2026-11-21
"""
import sqlalchemy as sa
from alembic import op

revision = "b7d1e0a4c912"
down_revision = "c96446bc2226"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Adding a column is ALTER TABLE, not a row UPDATE, so the append-only trigger allows it.
    op.add_column("audit_events", sa.Column("tenant_id", sa.String(36), nullable=True))
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    # Case references from a sequence: no collisions under concurrent filing, no volume leak.
    op.execute("CREATE SEQUENCE IF NOT EXISTS case_ref_seq START 1001")
    # TRUNCATE escape hatch only inside a *_test database (automated tests), never in dev/demo/prod.
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_events_guard() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'TRUNCATE'
               AND right(current_database(), 5) = '_test'
               AND current_setting('sahara.allow_audit_reset', true) = 'on' THEN
                RETURN NULL;
            END IF;
            RAISE EXCEPTION 'audit_events is append-only (% blocked)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS case_ref_seq")
    op.drop_index("ix_audit_events_tenant_id", table_name="audit_events")
    op.drop_column("audit_events", "tenant_id")
