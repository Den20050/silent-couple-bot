"""Replace user_demo with pair_demo

Revision ID: replace_user_demo_pair
Revises: add_delivery_chat_to_pairs
Create Date: 2025-12-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'replace_user_demo_pair'
down_revision: Union[str, None] = 'add_delivery_chat_to_pairs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old user_demo table
    op.drop_table('user_demo')
    
    # Create new pair_demo table
    op.create_table(
        'pair_demo',
        sa.Column('uid_a', sa.BigInteger(), nullable=False),
        sa.Column('uid_b', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('uid_a', 'uid_b'),
        sa.CheckConstraint('uid_a < uid_b', name='pair_demo_uid_order_check'),
    )


def downgrade() -> None:
    # Drop pair_demo table
    op.drop_table('pair_demo')
    
    # Recreate old user_demo table
    op.create_table(
        'user_demo',
        sa.Column('tg_id', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('tg_id'),
    )
