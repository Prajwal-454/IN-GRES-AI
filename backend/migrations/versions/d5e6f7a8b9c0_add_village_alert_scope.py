"""add village scope to alert rules

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-08-14 10:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'd5e6f7a8b9c0'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('alert_rules', sa.Column('village', sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column('alert_rules', 'village')
