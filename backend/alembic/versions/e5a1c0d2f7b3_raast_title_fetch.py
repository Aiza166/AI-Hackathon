"""raast title fetch: account holding/type on mock accounts, payee check on payout changes

Revision ID: e5a1c0d2f7b3
Revises: b4282c33362a
Create Date: 2026-11-21 22:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'e5a1c0d2f7b3'
down_revision = 'b4282c33362a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('mock_accounts', sa.Column('account_type', sa.String(length=10), nullable=False, server_default='ACCOUNT'))
    op.add_column('mock_accounts', sa.Column('holding', sa.String(length=10), nullable=False, server_default='SINGLE'))
    op.add_column('payout_change_requests', sa.Column('payee_check', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('payout_change_requests', 'payee_check')
    op.drop_column('mock_accounts', 'holding')
    op.drop_column('mock_accounts', 'account_type')
