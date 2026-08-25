"""add anomaly flags and report schedules

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-24 10:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'anomaly_flags',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('kind', sa.String(length=50), nullable=False, index=True),
        sa.Column('severity', sa.String(length=20), nullable=True, index=True),
        sa.Column('metric', sa.String(length=50), nullable=False),
        sa.Column('assessment_id', sa.Integer(), sa.ForeignKey('groundwater_assessments.id'), nullable=True, index=True),
        sa.Column('assessment_unit_id', sa.Integer(), sa.ForeignKey('assessment_units.id'), nullable=True, index=True),
        sa.Column('dataset_id', sa.Integer(), sa.ForeignKey('datasets.id'), nullable=True, index=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('state_name', sa.String(length=120), nullable=True),
        sa.Column('district_name', sa.String(length=120), nullable=True),
        sa.Column('unit_name', sa.String(length=255), nullable=True),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('expected_min', sa.Float(), nullable=True),
        sa.Column('expected_max', sa.Float(), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, index=True),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('review_note', sa.String(length=500), nullable=True),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index('ix_anomaly_flags_fingerprint', 'anomaly_flags', ['fingerprint'], unique=True)
    op.create_index(
        'ix_anomaly_flags_status_severity', 'anomaly_flags', ['status', 'severity']
    )

    op.create_table(
        'report_schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('state', sa.String(length=120), nullable=True),
        sa.Column('district', sa.String(length=120), nullable=True),
        sa.Column('village', sa.String(length=120), nullable=True),
        sa.Column('frequency', sa.String(length=20), nullable=True),
        sa.Column('recipients', sa.JSON(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status', sa.String(length=50), nullable=True),
        sa.Column('last_error', sa.String(length=500), nullable=True),
        sa.Column('last_file', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('report_schedules')
    op.drop_index('ix_anomaly_flags_status_severity', table_name='anomaly_flags')
    op.drop_index('ix_anomaly_flags_fingerprint', table_name='anomaly_flags')
    op.drop_table('anomaly_flags')
