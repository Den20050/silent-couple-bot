"""add_response_tracking_to_daily_state

Revision ID: add_response_tracking
Revises: 84b63ce9899e
Create Date: 2025-01-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_response_tracking'
down_revision: Union[str, None] = '4248837e6f13'  # After lifetime subscription support
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns for tracking response times
    op.add_column('daily_state', sa.Column('morning_sent_at', sa.DateTime(), nullable=True))
    op.add_column('daily_state', sa.Column('morning_responded_at', sa.DateTime(), nullable=True))
    op.add_column('daily_state', sa.Column('evening_sent_at', sa.DateTime(), nullable=True))
    op.add_column('daily_state', sa.Column('evening_responded_at', sa.DateTime(), nullable=True))
    
    # Add indexes for faster queries
    op.create_index('idx_daily_state_morning_sent', 'daily_state', ['morning_sent_at'])
    op.create_index('idx_daily_state_evening_sent', 'daily_state', ['evening_sent_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_daily_state_evening_sent', table_name='daily_state')
    op.drop_index('idx_daily_state_morning_sent', table_name='daily_state')
    
    # Drop columns
    op.drop_column('daily_state', 'evening_responded_at')
    op.drop_column('daily_state', 'evening_sent_at')
    op.drop_column('daily_state', 'morning_responded_at')
    op.drop_column('daily_state', 'morning_sent_at')

