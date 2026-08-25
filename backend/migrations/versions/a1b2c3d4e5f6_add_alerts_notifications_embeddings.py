"""add alerts, notifications and rag embeddings

Revision ID: a1b2c3d4e5f6
Revises: 4f2c9b1a7e01
Create Date: 2026-08-14 09:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = '4f2c9b1a7e01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'alert_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('metric', sa.String(length=50), nullable=False),
        sa.Column('operator', sa.String(length=10), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('state', sa.String(length=120), nullable=True),
        sa.Column('district', sa.String(length=120), nullable=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('channels', sa.JSON(), nullable=True),
        sa.Column('cooldown_minutes', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        'user_notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('rule_id', sa.Integer(), sa.ForeignKey('alert_rules.id'), nullable=True, index=True),
        sa.Column('kind', sa.String(length=50), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('read', sa.Boolean(), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column('knowledge_chunks', sa.Column('embedding', sa.JSON(), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('embedding_model', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('knowledge_chunks', 'embedding_model')
    op.drop_column('knowledge_chunks', 'embedding')
    op.drop_table('user_notifications')
    op.drop_table('alert_rules')
