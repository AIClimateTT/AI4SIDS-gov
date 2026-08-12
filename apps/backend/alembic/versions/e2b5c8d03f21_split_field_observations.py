"""rename incidents to field_observations and move sitrep rows out

Revision ID: e2b5c8d03f21
Revises: d1a4b7c92e10
"""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2b5c8d03f21"
down_revision: Union[str, Sequence[str], None] = "d1a4b7c92e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("incidents", "field_observations")

    # Move any existing sitrep-sourced rows into their own table under one
    # synthetic backfill submission per corporation. These predate events, so
    # they carry no event and alert_level 'none'.
    connection = op.get_bind()
    # A Python datetime, not sa.func.now(): a SQL function cannot be passed as a
    # bound parameter value.
    now = datetime.now(timezone.utc)
    # COALESCE, not "corporation IS NOT NULL": sitrep_incidents.corporation is
    # NOT NULL, and every row deleted below has to have been copied first. The
    # retired sitreps CSV ingest already fell back to 'unmapped' for a
    # corporation it could not normalise, so reuse that label rather than lose
    # the row.
    corporations = [
        r[0]
        for r in connection.execute(
            sa.text(
                "SELECT DISTINCT COALESCE(corporation, 'unmapped') "
                "FROM field_observations WHERE source = 'sitreps'"
            )
        )
    ]
    for corporation in corporations:
        connection.execute(
            sa.text(
                "INSERT INTO submissions "
                "(corporation, event_id, as_at, alert_level, sequence_no, source_file, ingested_at) "
                "VALUES (:corp, NULL, :now, 'none', 1, 'backfill', :now)"
            ),
            {"corp": corporation, "now": now},
        )
        submission_id = connection.execute(
            sa.text(
                "SELECT id FROM submissions WHERE corporation = :corp "
                "AND source_file = 'backfill' ORDER BY id DESC LIMIT 1"
            ),
            {"corp": corporation},
        ).scalar()
        connection.execute(
            sa.text(
                "INSERT INTO sitrep_incidents "
                "(submission_id, corporation, event_id, row_id, community, street, "
                " incident_type, raw_incident_type, incident_summary, event_date, "
                " injuries_occurred, injuries_count, deaths_occurred, deaths_count, "
                " building_damage, special_needs_occupants, estimated_damage_cost, "
                " action_taken, follow_up_flags, ingested_at) "
                "SELECT :sid, COALESCE(corporation, 'unmapped'), NULL, "
                " CAST(object_id AS VARCHAR), community, street, "
                " incident_type, raw_incident_type, incident_summary, event_date, "
                " injuries_occurred, injuries_count, deaths_occurred, deaths_count, "
                " building_damage, special_needs_occupants, estimated_damage_cost, "
                " action_taken, follow_up_flags, ingested_at "
                "FROM field_observations WHERE source = 'sitreps' "
                "AND COALESCE(corporation, 'unmapped') = :corp"
            ),
            {"sid": submission_id, "corp": corporation},
        )

    connection.execute(sa.text("DELETE FROM field_observations WHERE source = 'sitreps'"))

    # batch_alter_table so this works on SQLite (which needs a table rebuild for
    # DROP COLUMN on older versions) as well as Postgres.
    with op.batch_alter_table("field_observations") as batch:
        batch.drop_column("source")

    # Renaming a table does not rename its indexes, so without this the schema
    # still carries ix_incidents_* names and `alembic check` reports drift.
    op.drop_index("ix_incidents_global_id", table_name="field_observations")
    op.create_index(
        "ix_field_observations_global_id", "field_observations", ["global_id"], unique=True
    )
    op.drop_index("ix_incidents_dedup_hash", table_name="field_observations")
    op.create_index(
        "ix_field_observations_dedup_hash", "field_observations", ["dedup_hash"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_field_observations_dedup_hash", table_name="field_observations")
    op.create_index(
        "ix_incidents_dedup_hash", "field_observations", ["dedup_hash"], unique=False
    )
    op.drop_index("ix_field_observations_global_id", table_name="field_observations")
    op.create_index(
        "ix_incidents_global_id", "field_observations", ["global_id"], unique=True
    )
    with op.batch_alter_table("field_observations") as batch:
        batch.add_column(
            sa.Column("source", sa.String(), nullable=False, server_default="survey123")
        )
    op.rename_table("field_observations", "incidents")
