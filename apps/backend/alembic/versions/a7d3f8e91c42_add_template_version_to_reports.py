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
    op.alter_column('reports', 'template_version', server_default=None)


def downgrade() -> None:
    op.drop_column('reports', 'template_version')
