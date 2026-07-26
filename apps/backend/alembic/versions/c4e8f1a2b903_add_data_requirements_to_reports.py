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
    op.alter_column('reports', 'data_requirements', server_default=None)


def downgrade() -> None:
    op.drop_column('reports', 'data_requirements')
