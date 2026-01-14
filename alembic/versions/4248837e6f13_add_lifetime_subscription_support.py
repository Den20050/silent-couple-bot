"""add_lifetime_subscription_support

Revision ID: 4248837e6f13
Revises: 84b63ce9899e
Create Date: 2025-11-27 18:39:58.410407

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4248837e6f13'
down_revision: Union[str, None] = '84b63ce9899e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_lifetime column to subscriptions table
    op.add_column('subscriptions', sa.Column('is_lifetime', sa.Boolean(), nullable=False, server_default='false'))
    
    # Create lifetime_pair_history table
    op.create_table('lifetime_pair_history',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('uid_a', sa.BigInteger(), nullable=False),
        sa.Column('uid_b', sa.BigInteger(), nullable=False),
        sa.Column('broken_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('uid_a < uid_b', name='lifetime_uid_order_check'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_lifetime_pair_history_users', 'lifetime_pair_history', ['uid_a', 'uid_b'], unique=False)


def downgrade() -> None:
    # Drop lifetime_pair_history table
    op.drop_index('idx_lifetime_pair_history_users', table_name='lifetime_pair_history')
    op.drop_table('lifetime_pair_history')
    
    # Remove is_lifetime column from subscriptions table
    op.drop_column('subscriptions', 'is_lifetime')

