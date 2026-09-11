"""add briefing_report_id to whatsapp_drafts

Revision ID: b7c3e9a14f20
Revises: a8d4e1f27b90
Create Date: 2026-09-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c3e9a14f20"
down_revision: Union[str, Sequence[str], None] = "a8d4e1f27b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("whatsapp_drafts") as batch:
        batch.add_column(sa.Column("briefing_report_id", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("whatsapp_drafts") as batch:
        batch.drop_column("briefing_report_id")
