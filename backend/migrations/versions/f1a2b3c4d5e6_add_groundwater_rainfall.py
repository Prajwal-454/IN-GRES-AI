"""add groundwater rainfall measurements

Revision ID: f1a2b3c4d5e6
Revises: e6f7a8b9c0d1
Create Date: 2026-08-18 12:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'f1a2b3c4d5e6'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'groundwater_rainfall',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('assessment_unit_id', sa.Integer(), sa.ForeignKey('assessment_units.id'), nullable=False, index=True),
        sa.Column('dataset_id', sa.Integer(), sa.ForeignKey('datasets.id'), nullable=True, index=True),
        sa.Column('year', sa.Integer(), nullable=False, index=True),
        sa.Column('month', sa.Integer(), nullable=True),
        sa.Column('value_mm', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('is_demo', sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('groundwater_rainfall')