"""add unique constraint on submissions (corporation, event_id, sequence_no)

Revision ID: f6d2a9c31e57
Revises: e2b5c8d03f21
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f6d2a9c31e57"
down_revision: Union[str, Sequence[str], None] = "e2b5c8d03f21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table: SQLite has no ALTER TABLE ... ADD CONSTRAINT, so
    # adding a unique constraint needs a table rebuild there as well as on
    # Postgres.
    with op.batch_alter_table("submissions") as batch:
        batch.create_unique_constraint(
            "uq_submission_corp_event_sequence",
            ["corporation", "event_id", "sequence_no"],
        )


def downgrade() -> None:
    with op.batch_alter_table("submissions") as batch:
        batch.drop_constraint("uq_submission_corp_event_sequence", type_="unique")
