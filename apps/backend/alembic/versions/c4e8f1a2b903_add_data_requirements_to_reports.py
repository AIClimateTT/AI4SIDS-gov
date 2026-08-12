"""add data_requirements to reports

Revision ID: c4e8f1a2b903
Revises: b8f2e4a91c7d
Create Date: 2026-07-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e8f1a2b903'
down_revision: Union[str, Sequence[str], None] = 'b8f2e4a91c7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'reports',
        sa.Column('data_requirements', sa.JSON(), nullable=False, server_default='[]'),
    )
    # batch_alter_table because SQLite has no ALTER COLUMN at all — a bare
    # op.alter_column emits "ALTER TABLE ... ALTER COLUMN ... SET DEFAULT",
    # which is a syntax error there. Batch mode rebuilds the table on SQLite
    # and emits a plain ALTER on Postgres.
    with op.batch_alter_table('reports') as batch:
        batch.alter_column(
            'data_requirements',
            existing_type=sa.JSON(),
            existing_nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    op.drop_column('reports', 'data_requirements')
