"""create whatsapp_drafts table

Revision ID: a9c4e2b81d03
Revises: cea578ce7e61
Create Date: 2026-08-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9c4e2b81d03"
down_revision: Union[str, Sequence[str], None] = "cea578ce7e61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("as_at", sa.DateTime(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("pii_redacted", sa.Boolean(), nullable=False),
        sa.Column("incidents", sa.JSON(), nullable=False),
        sa.Column("logs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("whatsapp_drafts")
