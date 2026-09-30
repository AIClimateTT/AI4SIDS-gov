"""store timestamps as UTC and event dates as calendar days

Revision ID: d4c8a2f61b35
Revises: b7c3e9a14f20
Create Date: 2026-09-28

Existing rows are converted by what they held before this revision:
creation_date and edit_date were Trinidad wall-clock readings (the old parser
took ISO values as written), ingested_at was already UTC, and event_date /
assessment_date were local midnights standing in for a day.

Trinidad is UTC-4 all year (no daylight saving), which is what makes the fixed
+4 hours on SQLite exact.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d4c8a2f61b35"
down_revision: Union[str, Sequence[str], None] = "b7c3e9a14f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LOCAL_TZ = "America/Port_of_Spain"

# table -> (calendar-date columns, local wall-clock columns, UTC columns)
COLUMNS = {
    "field_observations": (
        ("event_date", "assessment_date"),
        ("creation_date", "edit_date"),
        ("ingested_at",),
    ),
    "sitrep_incidents": (("event_date",), (), ("ingested_at",)),
}


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgres():
        for table, (dates, local, utc) in COLUMNS.items():
            for column in dates:
                op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE date USING {column}::date")
            for column in local:
                op.execute(
                    f"ALTER TABLE {table} ALTER COLUMN {column} TYPE timestamptz "
                    f"USING {column} AT TIME ZONE '{LOCAL_TZ}'"
                )
            for column in utc:
                op.execute(
                    f"ALTER TABLE {table} ALTER COLUMN {column} TYPE timestamptz "
                    f"USING {column} AT TIME ZONE 'UTC'"
                )
        return

    # SQLite has no real date or timezone types, so only the stored text
    # changes. Not batch_alter_table: its copy CASTs to DATE, which SQLite
    # reads as a number and truncates "2024-06-01" to 2024.
    for table, (dates, local, _utc) in COLUMNS.items():
        for column in dates:
            op.execute(f"UPDATE {table} SET {column} = substr({column}, 1, 10) WHERE {column} IS NOT NULL")
        for column in local:
            op.execute(
                f"UPDATE {table} SET {column} = datetime({column}, '+4 hours') WHERE {column} IS NOT NULL"
            )


def downgrade() -> None:
    if _is_postgres():
        for table, (dates, local, utc) in COLUMNS.items():
            for column in dates:
                op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE timestamp USING {column}::timestamp")
            for column in local:
                op.execute(
                    f"ALTER TABLE {table} ALTER COLUMN {column} TYPE timestamp "
                    f"USING {column} AT TIME ZONE '{LOCAL_TZ}'"
                )
            for column in utc:
                op.execute(
                    f"ALTER TABLE {table} ALTER COLUMN {column} TYPE timestamp "
                    f"USING {column} AT TIME ZONE 'UTC'"
                )
        return

    for table, (dates, local, _utc) in COLUMNS.items():
        for column in local:
            op.execute(
                f"UPDATE {table} SET {column} = datetime({column}, '-4 hours') WHERE {column} IS NOT NULL"
            )
        for column in dates:
            op.execute(f"UPDATE {table} SET {column} = {column} || ' 00:00:00' WHERE {column} IS NOT NULL")
