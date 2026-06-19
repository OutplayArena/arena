"""drop mcp_instances and mcp_auth_keys tables

Revision ID: a3b4c5d6e7f8
Revises: f1g2h3i4j5k6
Create Date: 2026-06-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'a3b4c5d6e7f8'
down_revision = 'f1g2h3i4j5k6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table('mcp_instances')
    op.drop_table('mcp_auth_keys')


def downgrade() -> None:
    op.create_table(
        'mcp_auth_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('key_prefix', sa.String(16), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'mcp_instances',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='starting'),
        sa.Column('runtime', sa.String(10), nullable=False, server_default='docker'),
        sa.Column('container_name', sa.String(255), nullable=False),
        sa.Column('dns_name', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False, server_default='8000'),
        sa.Column('public_url', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stopped_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['key_id'], ['mcp_auth_keys.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
