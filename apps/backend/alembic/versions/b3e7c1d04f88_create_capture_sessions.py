"""create capture_sessions table

Revision ID: b3e7c1d04f88
Revises: a9c4e2b81d03
Create Date: 2026-08-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3e7c1d04f88"
down_revision: Union[str, Sequence[str], None] = "a9c4e2b81d03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "capture_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("corporation", sa.String(), nullable=False, index=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("as_at", sa.DateTime(), nullable=False),
        sa.Column("alert_level", sa.String(), nullable=False),
        sa.Column("present_activity", sa.Text(), nullable=True),
        sa.Column("situation_overview", sa.Text(), nullable=True),
        sa.Column("incidents", sa.JSON(), nullable=False),
        sa.Column("logs", sa.JSON(), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("capture_sessions")
