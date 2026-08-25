"""add real telephony columns to voice tables

Revision ID: b7e8f9a0b1c2
Revises: a1b2c3d4e5f6
Create Date: 2026-08-14 12:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'b7e8f9a0b1c2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('voice_calls', sa.Column('conversation_id', sa.Integer(), sa.ForeignKey('conversations.id'), nullable=True, index=True))
    op.add_column('voice_calls', sa.Column('phone_number_hash', sa.String(length=64), nullable=True))
    op.add_column('voice_calls', sa.Column('call_state', sa.String(length=20), nullable=True))
    op.add_column('voice_calls', sa.Column('language', sa.String(length=10), nullable=True))
    op.add_column('voice_calls', sa.Column('intent', sa.String(length=50), nullable=True))
    op.add_column('voice_calls', sa.Column('location', sa.String(length=255), nullable=True))
    op.add_column('voice_calls', sa.Column('ai_confidence', sa.Numeric(precision=4, scale=3), nullable=True))
    op.add_column('voice_calls', sa.Column('escalated', sa.Boolean(), nullable=True))
    op.add_column('voice_calls', sa.Column('stream_token', sa.String(length=64), nullable=True))
    op.add_column('voice_calls', sa.Column('transcription', sa.Text(), nullable=True))
    op.add_column('voice_calls', sa.Column('response_time_ms', sa.Float(), nullable=True))

    op.add_column('voice_transcriptions', sa.Column('role', sa.String(length=20), nullable=True))
    op.add_column('voice_transcriptions', sa.Column('intent', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('voice_transcriptions', 'intent')
    op.drop_column('voice_transcriptions', 'role')
    op.drop_column('voice_calls', 'response_time_ms')
    op.drop_column('voice_calls', 'transcription')
    op.drop_column('voice_calls', 'stream_token')
    op.drop_column('voice_calls', 'escalated')
    op.drop_column('voice_calls', 'ai_confidence')
    op.drop_column('voice_calls', 'location')
    op.drop_column('voice_calls', 'intent')
    op.drop_column('voice_calls', 'language')
    op.drop_column('voice_calls', 'call_state')
    op.drop_column('voice_calls', 'phone_number_hash')
    op.drop_column('voice_calls', 'conversation_id')
