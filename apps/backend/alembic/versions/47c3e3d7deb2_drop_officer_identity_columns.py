"""drop officer identity columns from field_observations

Revision ID: 47c3e3d7deb2
Revises: f6d2a9c31e57
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "47c3e3d7deb2"
down_revision: Union[str, Sequence[str], None] = "f6d2a9c31e57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table: SQLite has no bare DROP COLUMN on older versions, so
    # this needs a table rebuild there as well as on Postgres.
    with op.batch_alter_table("field_observations") as batch:
        batch.drop_column("officer_name")
        batch.drop_column("officer_position")


def downgrade() -> None:
    with op.batch_alter_table("field_observations") as batch:
        batch.add_column(sa.Column("officer_name", sa.String(), nullable=True))
        batch.add_column(sa.Column("officer_position", sa.String(), nullable=True))
