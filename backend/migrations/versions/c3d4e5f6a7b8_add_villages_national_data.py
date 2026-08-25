"""add villages table and assessment unit coordinates

Revision ID: c3d4e5f6a7b8
Revises: b7e8f9a0b1c2
Create Date: 2026-08-14 13:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'c3d4e5f6a7b8'
down_revision = 'b7e8f9a0b1c2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'villages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('district_id', sa.Integer(), sa.ForeignKey('districts.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=120), nullable=False, index=True),
        sa.Column('code', sa.String(length=30), nullable=True, index=True),
        sa.Column('population', sa.Integer(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('is_demo', sa.Boolean(), nullable=True, server_default=sa.text('0')),
    )

    op.add_column('assessment_units', sa.Column('village_id', sa.Integer(), sa.ForeignKey('villages.id'), nullable=True, index=True))
    op.add_column('assessment_units', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('assessment_units', sa.Column('longitude', sa.Float(), nullable=True))
    op.add_column('assessment_units', sa.Column('is_demo', sa.Boolean(), nullable=True, server_default=sa.text('0')))


def downgrade() -> None:
    op.drop_column('assessment_units', 'is_demo')
    op.drop_column('assessment_units', 'longitude')
    op.drop_column('assessment_units', 'latitude')
    op.drop_column('assessment_units', 'village_id')
    op.drop_table('villages')
