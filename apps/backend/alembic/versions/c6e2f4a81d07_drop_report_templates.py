"""drop report_templates: templates are YAML files in code

Revision ID: c6e2f4a81d07
Revises: d4c8a2f61b35
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c6e2f4a81d07"
down_revision: Union[str, None] = "d4c8a2f61b35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("report_templates")


def downgrade() -> None:
    op.create_table(
        "report_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("data_requirements", sa.JSON(), nullable=False),
        sa.Column("narration", sa.JSON(), nullable=False),
        sa.Column("render", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_report_templates_name_version"),
    )
