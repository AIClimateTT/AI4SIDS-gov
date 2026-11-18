"""prompt registry: prompt_versions, and which prompt and model each turn used

Revision ID: c5f1a8e3d720
Revises: b7d4e2a96c18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5f1a8e3d720"
down_revision: Union[str, None] = "b7d4e2a96c18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prompt_versions",
        sa.Column("hash", sa.String(64), primary_key=True),
        sa.Column("prompt_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_prompt_versions_prompt_id", "prompt_versions", ["prompt_id"])

    with op.batch_alter_table("capture_sessions") as batch:
        batch.add_column(sa.Column("prompt_hash", sa.String(64), nullable=True))

    with op.batch_alter_table("capture_turns") as batch:
        batch.add_column(sa.Column("prompt_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("prompt_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("prompt_hash", sa.String(64), nullable=True))
        batch.add_column(sa.Column("model", sa.String(), nullable=True))
        batch.add_column(sa.Column("retried", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("interventions", sa.JSON(), nullable=True))
        batch.create_index("ix_capture_turns_prompt_id", ["prompt_id"])


def downgrade() -> None:
    with op.batch_alter_table("capture_turns") as batch:
        batch.drop_index("ix_capture_turns_prompt_id")
        for name in (
            "interventions",
            "retried",
            "model",
            "prompt_hash",
            "prompt_version",
            "prompt_id",
        ):
            batch.drop_column(name)
    with op.batch_alter_table("capture_sessions") as batch:
        batch.drop_column("prompt_hash")
    op.drop_index("ix_prompt_versions_prompt_id", table_name="prompt_versions")
    op.drop_table("prompt_versions")
