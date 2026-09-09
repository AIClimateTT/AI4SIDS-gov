"""add quality_eval, workflow_events, and report_ratings

Revision ID: e5b1c7d83a24
Revises: c8e3a1b47d90
Create Date: 2026-09-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5b1c7d83a24"
down_revision: Union[str, Sequence[str], None] = "c8e3a1b47d90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("quality_eval", sa.JSON(), nullable=True))
    op.create_table(
        "workflow_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workflow", sa.String(), nullable=False),
        sa.Column("step", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("assisted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "report_ratings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("report_id", sa.String(), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("report_id", "user_id", name="uq_report_ratings_report_user"),
    )


def downgrade() -> None:
    op.drop_table("report_ratings")
    op.drop_table("workflow_events")
    op.drop_column("reports", "quality_eval")
