"""Remove common_chat_id from pairs

Revision ID: remove_common_chat_id
Revises: add_response_tracking_to_daily_state
Create Date: 2025-01-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'remove_common_chat_id'
down_revision: Union[str, None] = 'add_response_tracking'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop index first
    op.drop_index('idx_pairs_common_chat', table_name='pairs')
    # Drop column
    op.drop_column('pairs', 'common_chat_id')


def downgrade() -> None:
    # Add column back
    op.add_column('pairs', sa.Column('common_chat_id', sa.BigInteger(), nullable=True))
    # Recreate index
    op.create_index('idx_pairs_common_chat', 'pairs', ['common_chat_id'], unique=False)

