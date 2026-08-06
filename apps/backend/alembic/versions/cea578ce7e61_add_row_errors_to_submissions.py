"""add row_errors to submissions

Revision ID: cea578ce7e61
Revises: 47c3e3d7deb2
Create Date: 2026-08-06 01:17:17.613013

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cea578ce7e61'
down_revision: Union[str, Sequence[str], None] = '47c3e3d7deb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("submissions") as batch:
        batch.add_column(
            sa.Column("row_errors", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("submissions") as batch:
        batch.drop_column("row_errors")
