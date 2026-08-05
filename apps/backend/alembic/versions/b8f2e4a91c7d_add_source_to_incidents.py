"""add source to incidents

Revision ID: b8f2e4a91c7d
Revises: f3a1c9d7b204
Create Date: 2026-07-18 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8f2e4a91c7d'
down_revision: Union[str, Sequence[str], None] = 'f3a1c9d7b204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('incidents', sa.Column('source', sa.String(), nullable=False, server_default='survey123'))
    # batch_alter_table because SQLite has no ALTER COLUMN at all — a bare
    # op.alter_column emits "ALTER TABLE ... ALTER COLUMN ... SET DEFAULT",
    # which is a syntax error there. Batch mode rebuilds the table on SQLite
    # and emits a plain ALTER on Postgres.
    with op.batch_alter_table('incidents') as batch:
        batch.alter_column(
            'source',
            existing_type=sa.String(),
            existing_nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    op.drop_column('incidents', 'source')
