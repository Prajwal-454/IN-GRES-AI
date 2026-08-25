"""add saved scenarios

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-08-24 16:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'd1e2f3a4b5c6'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'saved_scenarios',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('scope_state', sa.String(length=120), nullable=True),
        sa.Column('scope_district', sa.String(length=120), nullable=True),
        sa.Column('scope_village', sa.String(length=120), nullable=True),
        sa.Column('scope_basin', sa.String(length=120), nullable=True),
        sa.Column('metric', sa.String(length=20), nullable=True),
        sa.Column('horizon', sa.Integer(), nullable=True),
        sa.Column('method', sa.String(length=20), nullable=True),
        sa.Column('extraction_change', sa.Float(), nullable=True),
        sa.Column('recharge_change', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('saved_scenarios')
