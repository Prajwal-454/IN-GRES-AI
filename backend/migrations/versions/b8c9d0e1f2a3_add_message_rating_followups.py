"""add message rating and followups

Revision ID: b8c9d0e1f2a3
Revises: a3f4b5c6d7e8
Create Date: 2026-08-22 09:30:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'b8c9d0e1f2a3'
down_revision = 'a3f4b5c6d7e8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('rating', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('rating_note', sa.String(length=500), nullable=True))
    op.add_column('messages', sa.Column('followups', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'followups')
    op.drop_column('messages', 'rating_note')
    op.drop_column('messages', 'rating')
