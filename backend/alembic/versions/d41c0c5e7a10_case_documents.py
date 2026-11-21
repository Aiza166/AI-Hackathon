"""case documents (upload analysis, officer copy, ELA heatmap)

Revision ID: d41c0c5e7a10
Revises: e5a1c0d2f7b3
Create Date: 2026-11-21 16:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'd41c0c5e7a10'
down_revision = 'e5a1c0d2f7b3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'case_documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('case_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('width', sa.Integer(), nullable=False),
        sa.Column('height', sa.Integer(), nullable=False),
        sa.Column('ocr_engine', sa.String(length=40), nullable=True),
        sa.Column('jev_model', sa.String(length=40), nullable=True),
        sa.Column('risk_level', sa.String(length=10), nullable=False),
        sa.Column('indicator_codes', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('confirmed_fields', sa.JSON(), nullable=True),
        sa.Column('image_jpeg', sa.LargeBinary(), nullable=False),
        sa.Column('ela_jpeg', sa.LargeBinary(), nullable=False),
        sa.Column('uploaded_by', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_case_documents_case_id'), 'case_documents', ['case_id'], unique=False)
    op.create_index(op.f('ix_case_documents_tenant_id'), 'case_documents', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_case_documents_tenant_id'), table_name='case_documents')
    op.drop_index(op.f('ix_case_documents_case_id'), table_name='case_documents')
    op.drop_table('case_documents')
