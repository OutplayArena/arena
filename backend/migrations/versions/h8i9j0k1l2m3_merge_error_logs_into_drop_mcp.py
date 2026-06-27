"""merge error_logs into the drop_mcp_tables head

Revision ID: h8i9j0k1l2m3
Revises: a3b4c5d6e7f8, g7h8i9j0k1l2
Create Date: 2026-06-27 08:30:00.000000

The alembic history forked at f1g2h3i4j5k6 (add_mailbox):

  f1g2h3i4j5k6 (add_mailbox)
       |
       +--> a3b4c5d6e7f8 (drop_mcp_tables)            [existing]
       |
       +--> g7h8i9j0k1l2 (add_error_logs)              [new]

This migration is the merge point: it has both branches as
``down_revisions`` and an empty upgrade/downgrade body. Running
``alembic upgrade head`` on a fresh database now walks every
revision in the history exactly once and ends with a single head
(h8i9j0k1l2m3) regardless of which branch was last applied.
"""


# revision identifiers, used by Alembic.
revision = 'h8i9j0k1l2m3'
down_revision = ('a3b4c5d6e7f8', 'g7h8i9j0k1l2')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pure merge: nothing to do, the two branches have already
    # created / dropped their own tables in their respective
    # revisions. This migration only exists to give alembic a single
    # head so 'upgrade head' doesn't refuse to run.
    pass


def downgrade() -> None:
    # No-op: undoing the merge would require an explicit choice of
    # which branch to keep; alembic can't synthesise a meaningful
    # ``down_revision`` from a tuple. Operators should downgrade by
    # targeting a specific revision on the branch they want to roll
    # back to.
    pass
