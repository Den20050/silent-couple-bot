"""Add last_surprise_at to daily_state

Revision ID: add_last_surprise_at
Revises: remove_common_chat_id
Create Date: 2025-01-15 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_last_surprise_at'
down_revision: Union[str, None] = 'remove_common_chat_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_surprise_at column
    op.add_column('daily_state', sa.Column('last_surprise_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Drop column
    op.drop_column('daily_state', 'last_surprise_at')

