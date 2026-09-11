"""add messages and manual_fields to whatsapp_drafts

Revision ID: a8d4e1f27b90
Revises: f3a9c2d18e70
Create Date: 2026-09-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8d4e1f27b90"
down_revision: Union[str, Sequence[str], None] = "f3a9c2d18e70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("whatsapp_drafts") as batch:
        batch.add_column(
            sa.Column("messages", sa.JSON(), nullable=False, server_default="[]")
        )
        batch.add_column(
            sa.Column(
                "manual_fields", sa.JSON(), nullable=False, server_default="[]"
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("whatsapp_drafts") as batch:
        batch.drop_column("manual_fields")
        batch.drop_column("messages")
