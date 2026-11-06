"""add final_markdown to reports: the clean text a reader gets

Revision ID: f1c8a6d29b53
Revises: e7d2b5c04a91
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1c8a6d29b53"
down_revision: Union[str, None] = "e7d2b5c04a91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("final_markdown", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("reports", "final_markdown")
