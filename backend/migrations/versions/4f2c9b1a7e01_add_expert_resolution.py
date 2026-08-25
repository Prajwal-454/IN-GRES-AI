"""add expert request resolution column

Revision ID: 4f2c9b1a7e01
Revises: 16ce5699bb0a
Create Date: 2026-08-13 22:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = '4f2c9b1a7e01'
down_revision = '16ce5699bb0a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('expert_requests', sa.Column('resolution', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('expert_requests', 'resolution')