"""store sitrep preview and issued report id on capture sessions

Revision ID: 4cf37f677064
Revises: d7f2a6c81b3e
Create Date: 2026-08-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4cf37f677064"
down_revision: Union[str, Sequence[str], None] = "d7f2a6c81b3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("capture_sessions") as batch:
        batch.add_column(sa.Column("report_id", sa.String(), nullable=True))
        batch.create_foreign_key(
            "fk_capture_sessions_report_id",
            "reports",
            ["report_id"],
            ["id"],
        )
        batch.add_column(sa.Column("sitrep_markdown", sa.Text(), nullable=True))
        batch.add_column(sa.Column("sitrep_fact_table", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("sitrep_violations", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("sitrep_status", sa.String(), nullable=True))
        batch.add_column(sa.Column("sitrep_generated_at", sa.DateTime(), nullable=True))
        batch.add_column(
            sa.Column("sitrep_source_updated_at", sa.DateTime(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("capture_sessions") as batch:
        batch.drop_column("sitrep_source_updated_at")
        batch.drop_column("sitrep_generated_at")
        batch.drop_column("sitrep_status")
        batch.drop_column("sitrep_violations")
        batch.drop_column("sitrep_fact_table")
        batch.drop_column("sitrep_markdown")
        batch.drop_column("report_id")
