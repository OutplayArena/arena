"""add mailbox messages

Revision ID: f1g2h3i4j5k6
Revises: a1b2c3d4e5f6
Create Date: 2026-06-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'f1g2h3i4j5k6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add messages_json column to sessions table
    op.add_column('sessions', sa.Column('messages_json', postgresql.JSONB(), nullable=True))
    
    # Create mailbox_messages table
    op.create_table(
        'mailbox_messages',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=False),
        sa.Column('sender', sa.String(10), nullable=False),
        sa.Column('recipient', sa.String(10), nullable=False, server_default='all'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('round_number', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mailbox_messages_session_id', 'mailbox_messages', ['session_id'])


def downgrade() -> None:
    op.drop_index('ix_mailbox_messages_session_id', table_name='mailbox_messages')
    op.drop_table('mailbox_messages')
    op.drop_column('sessions', 'messages_json')
