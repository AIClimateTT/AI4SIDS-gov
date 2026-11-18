"""sitrep_incidents: area/household scope, house number, impact counts

Revision ID: b7d4e2a96c18
Revises: a3e9c7d15f42
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d4e2a96c18"
down_revision: Union[str, None] = "a3e9c7d15f42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    ("incident_scope", sa.String()),
    ("house_number", sa.String()),
    ("households_affected", sa.Integer()),
    ("persons_affected", sa.Integer()),
    ("persons_displaced", sa.Integer()),
    ("persons_marooned", sa.Integer()),
    ("access_blocked", sa.Boolean()),
)


def upgrade() -> None:
    with op.batch_alter_table("sitrep_incidents") as batch:
        for name, kind in _COLUMNS:
            batch.add_column(sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sitrep_incidents") as batch:
        for name, _kind in reversed(_COLUMNS):
            batch.drop_column(name)
