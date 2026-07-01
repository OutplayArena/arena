"""add wandb_run_json to sessions

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-07-01 00:00:00.000000

Stores the W&B run identifiers (run_id, run_name, entity, project, url)
for sessions created with wandb_logging=true.  Used to:
  - Surface run coordinates in every turn response so SDK agents can
    attach their own W&B logging to the same run.
  - Reconstruct the WandbGameLogger after a container replacement
    (rolling update) by calling wandb.init(id=..., resume='allow').
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'l2m3n4o5p6q7'
down_revision = 'k1l2m3n4o5p6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("wandb_run_json", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "wandb_run_json")
