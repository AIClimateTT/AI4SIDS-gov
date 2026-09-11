"""add source_kind to whatsapp_drafts

Revision ID: f3a9c2d18e70
Revises: e5b1c7d83a24
Create Date: 2026-09-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a9c2d18e70"
down_revision: Union[str, Sequence[str], None] = "e5b1c7d83a24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("whatsapp_drafts") as batch:
        batch.add_column(
            sa.Column("source_kind", sa.String(), nullable=False, server_default="export")
        )


def downgrade() -> None:
    with op.batch_alter_table("whatsapp_drafts") as batch:
        batch.drop_column("source_kind")
