"""add error_logs table

Revision ID: g7h8i9j0k1l2
Revises: f1g2h3i4j5k6
Create Date: 2026-06-27 07:50:00.000000

Adds the ``error_logs`` table that the global exception handler in
:mod:`arena.error_handler` writes to. Each row is one unhandled
server-side error and carries:

- ``id``: the public UUID shown to the user in the 500 response and
  quoted in the GitHub issue title. Random per error.
- ``method`` / ``path``: the request the user hit, so the maintainer
  can reproduce.
- ``exception_type`` / ``message`` / ``traceback``: enough to debug.
- ``client_ip`` / ``user_agent`` / ``query_string`` / ``extra``: extra
  context, all optional.

We never echo the traceback to the user — the response is intentionally
minimal so we don't leak paths, secrets, or internal state to the wire.
The traceback lives in this table until retention prunes it.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'g7h8i9j0k1l2'
down_revision = 'f1g2h3i4j5k6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "error_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("path", sa.String(2048), nullable=False),
        sa.Column("exception_type", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("traceback", sa.Text(), nullable=False, server_default=""),
        sa.Column("client_ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("query_string", sa.String(2048), nullable=True),
        sa.Column("extra", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # created_at is the natural lookup dimension ("show me today's
    # errors"); an index keeps the admin query cheap as the table grows.
    op.create_index("ix_error_logs_created_at", "error_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_error_logs_created_at", table_name="error_logs")
    op.drop_table("error_logs")
