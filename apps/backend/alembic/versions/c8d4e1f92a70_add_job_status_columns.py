"""add report job error and whatsapp draft job columns

Revision ID: c8d4e1f92a70
Revises: b3e7c1d04f88
Create Date: 2026-08-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d4e1f92a70"
down_revision: Union[str, Sequence[str], None] = "b3e7c1d04f88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("error", sa.Text(), nullable=True))
    op.add_column(
        "whatsapp_drafts",
        sa.Column("status", sa.String(), nullable=False, server_default="ready"),
    )
    op.add_column("whatsapp_drafts", sa.Column("error", sa.Text(), nullable=True))
    op.add_column("whatsapp_drafts", sa.Column("source_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("whatsapp_drafts", "source_text")
    op.drop_column("whatsapp_drafts", "error")
    op.drop_column("whatsapp_drafts", "status")
    op.drop_column("reports", "error")
