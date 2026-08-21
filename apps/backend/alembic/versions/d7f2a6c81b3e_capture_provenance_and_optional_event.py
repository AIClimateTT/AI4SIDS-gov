"""add capture provenance and make capture session event optional

Revision ID: d7f2a6c81b3e
Revises: c8d4e1f92a70
Create Date: 2026-08-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7f2a6c81b3e"
down_revision: Union[str, Sequence[str], None] = "c8d4e1f92a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("capture_sessions") as batch:
        batch.add_column(
            sa.Column("manual_fields", sa.JSON(), nullable=False, server_default="[]")
        )
        batch.alter_column("event_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("capture_sessions") as batch:
        batch.alter_column("event_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("manual_fields")
