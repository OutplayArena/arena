"""add mcp_instances table

Revision ID: d7e8f9g0h1
Revises: d5e6f7g8h004
Create Date: 2026-06-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd7e8f9g0h1'
down_revision = 'd5e6f7g8h004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mcp_instances',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('runtime', sa.String(length=20), nullable=False),
        sa.Column('container_name', sa.String(length=128), nullable=False),
        sa.Column('dns_name', sa.String(length=256), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stopped_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['key_id'], ['mcp_auth_keys.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('mcp_instances')
