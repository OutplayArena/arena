"""add wandb_config_json to sessions

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-07-01 00:00:00.000000

Stores the W&B project/entity/run_name/tags that were requested when a session
was created.  Used by stateless workers to log game results to W&B at game-end
without needing the original request payload.  Never stores an API key.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("wandb_config_json", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "wandb_config_json")
