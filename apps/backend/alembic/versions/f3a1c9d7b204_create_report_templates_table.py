"""create report_templates table

Revision ID: f3a1c9d7b204
Revises: a7d3f8e91c42
Create Date: 2026-07-16 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a1c9d7b204'
down_revision: Union[str, Sequence[str], None] = 'a7d3f8e91c42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('report_templates',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=False),
    sa.Column('params', sa.JSON(), nullable=False),
    sa.Column('data_requirements', sa.JSON(), nullable=False),
    sa.Column('narration', sa.JSON(), nullable=False),
    sa.Column('render', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'version', name='uq_report_templates_name_version'),
    )


def downgrade() -> None:
    op.drop_table('report_templates')
