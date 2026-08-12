"""create events, submissions, sitrep_incidents, situation_logs

Revision ID: d1a4b7c92e10
Revises: c4e8f1a2b903
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1a4b7c92e10"
down_revision: Union[str, Sequence[str], None] = "c4e8f1a2b903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("corporation", sa.String(), nullable=False, index=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("hazard_type", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("corporation", sa.String(), nullable=False, index=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True, index=True),
        sa.Column("as_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("alert_level", sa.String(), nullable=False, server_default="none"),
        sa.Column("present_activity", sa.Text(), nullable=True),
        sa.Column("situation_overview", sa.Text(), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_file", sa.String(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "sitrep_incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False, index=True),
        sa.Column("corporation", sa.String(), nullable=False, index=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True, index=True),
        sa.Column("row_id", sa.String(), nullable=False),
        sa.Column("community", sa.String(), nullable=True),
        sa.Column("street", sa.String(), nullable=True),
        sa.Column("incident_type", sa.String(), nullable=True),
        sa.Column("raw_incident_type", sa.String(), nullable=True),
        sa.Column("incident_summary", sa.Text(), nullable=True),
        sa.Column("event_date", sa.DateTime(), nullable=True),
        sa.Column("injuries_occurred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("injuries_count", sa.Integer(), nullable=True),
        sa.Column("deaths_occurred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deaths_count", sa.Integer(), nullable=True),
        sa.Column("building_damage", sa.Text(), nullable=True),
        sa.Column("special_needs_occupants", sa.Integer(), nullable=True),
        sa.Column("estimated_damage_cost", sa.Numeric(), nullable=True),
        sa.Column("action_taken", sa.Text(), nullable=True),
        sa.Column("follow_up_flags", sa.JSON(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "corporation", "event_id", "row_id", name="uq_sitrep_incident_corp_event_row"
        ),
    )
    op.create_table(
        "situation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False, index=True),
        sa.Column("category", sa.String(), nullable=False, index=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("item", sa.String(), nullable=True, index=True),
        sa.Column("quantity", sa.Numeric(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("situation_logs")
    op.drop_table("sitrep_incidents")
    op.drop_table("submissions")
    op.drop_table("events")
