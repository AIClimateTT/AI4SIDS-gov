"""add sitrep_final_markdown to capture_sessions

Revision ID: b2f7c9d41e08
Revises: 01a294fe9474
Create Date: 2026-08-23

The issued form of a filing — same facts, no citation markers or appendix —
is rendered alongside the draft and stored so the two can never drift.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2f7c9d41e08'
down_revision: Union[str, Sequence[str], None] = '01a294fe9474'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'capture_sessions',
        sa.Column('sitrep_final_markdown', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('capture_sessions', 'sitrep_final_markdown')
