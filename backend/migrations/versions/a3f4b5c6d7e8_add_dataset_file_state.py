"""add dataset file state (import fingerprints)

Revision ID: a3f4b5c6d7e8
Revises: f1a2b3c4d5e6
Create Date: 2026-08-19 12:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'a3f4b5c6d7e8'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'dataset_file_state',
        sa.Column('dataset_id', sa.Integer(), sa.ForeignKey('datasets.id'), primary_key=True),
        sa.Column('filename', sa.String(255), primary_key=True),
        sa.Column('sha256', sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('dataset_file_state')