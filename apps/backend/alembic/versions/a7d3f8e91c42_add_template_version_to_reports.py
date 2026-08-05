"""add template_version to reports

Revision ID: a7d3f8e91c42
Revises: 6ae0a692151e
Create Date: 2026-07-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d3f8e91c42'
down_revision: Union[str, Sequence[str], None] = '6ae0a692151e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('reports', sa.Column('template_version', sa.Integer(), nullable=False, server_default='1'))
    # batch_alter_table because SQLite has no ALTER COLUMN at all — a bare
    # op.alter_column emits "ALTER TABLE ... ALTER COLUMN ... SET DEFAULT",
    # which is a syntax error there. Batch mode rebuilds the table on SQLite
    # and emits a plain ALTER on Postgres.
    with op.batch_alter_table('reports') as batch:
        batch.alter_column(
            'template_version',
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    op.drop_column('reports', 'template_version')
