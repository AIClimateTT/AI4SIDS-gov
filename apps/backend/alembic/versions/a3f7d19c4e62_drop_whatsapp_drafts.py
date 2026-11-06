"""drop whatsapp_drafts: capture replaces WhatsApp intake

Revision ID: a3f7d19c4e62
Revises: c6e2f4a81d07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f7d19c4e62"
down_revision: Union[str, None] = "c6e2f4a81d07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("whatsapp_drafts")


def downgrade() -> None:
    op.create_table(
        "whatsapp_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("as_at", sa.DateTime(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("pii_redacted", sa.Boolean(), nullable=False),
        sa.Column("incidents", sa.JSON(), nullable=False),
        sa.Column("logs", sa.JSON(), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("manual_fields", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("briefing_report_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
