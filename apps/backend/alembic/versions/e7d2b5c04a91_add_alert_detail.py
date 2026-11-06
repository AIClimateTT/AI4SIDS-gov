"""add alert_detail: the officer's own wording of the alert

Revision ID: e7d2b5c04a91
Revises: a3f7d19c4e62
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7d2b5c04a91"
down_revision: Union[str, None] = "a3f7d19c4e62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("alert_detail", sa.Text(), nullable=True))
    op.add_column("capture_sessions", sa.Column("alert_detail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("capture_sessions", "alert_detail")
    op.drop_column("submissions", "alert_detail")
