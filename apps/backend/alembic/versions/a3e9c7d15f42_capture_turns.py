"""capture_turns: per-change snapshots of a capture session's working set

Revision ID: a3e9c7d15f42
Revises: f1c8a6d29b53
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3e9c7d15f42"
down_revision: Union[str, None] = "f1c8a6d29b53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "capture_turns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("capture_sessions.id"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=True),
        sa.Column("assistant_message", sa.Text(), nullable=True),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("parse_ok", sa.Boolean(), nullable=True),
        sa.Column("template_version", sa.Integer(), nullable=True),
        sa.Column("working", sa.JSON(), nullable=False),
        sa.Column("missing", sa.JSON(), nullable=False),
        sa.Column("sitrep_markdown", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_capture_turns_session_id", "capture_turns", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_capture_turns_session_id", table_name="capture_turns")
    op.drop_table("capture_turns")
