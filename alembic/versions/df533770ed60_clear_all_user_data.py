"""clear_all_user_data

Revision ID: df533770ed60
Revises: a703b4149630
Create Date: 2025-12-30 00:54:40.302418

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df533770ed60'
down_revision: Union[str, None] = 'a703b4149630'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Clear all user data from database.
    
    This migration deletes all user-related data while preserving table structure.
    Tables are cleared in order to respect foreign key constraints:
    1. daily_state (depends on pairs)
    2. subscriptions (depends on pairs and users)
    3. lifetime_pair_history (independent)
    4. pair_demo (independent)
    5. pairs (depends on users)
    6. bot_messages (independent, service table)
    7. users (base table)
    
    Note: pics_pool is NOT cleared as it contains shared picture resources.
    """
    # Clear daily_state (depends on pairs)
    op.execute("TRUNCATE TABLE daily_state CASCADE")
    
    # Clear subscriptions (depends on pairs and users)
    op.execute("TRUNCATE TABLE subscriptions CASCADE")
    
    # Clear lifetime_pair_history (independent)
    op.execute("TRUNCATE TABLE lifetime_pair_history CASCADE")
    
    # Clear pair_demo (independent)
    op.execute("TRUNCATE TABLE pair_demo CASCADE")
    
    # Clear pairs (depends on users)
    op.execute("TRUNCATE TABLE pairs CASCADE")
    
    # Clear bot_messages (service table, but contains user-related messages)
    op.execute("TRUNCATE TABLE bot_messages CASCADE")
    
    # Clear users (base table)
    op.execute("TRUNCATE TABLE users CASCADE")
    
    # Reset sequences to start from 1
    op.execute("ALTER SEQUENCE users_id_seq RESTART WITH 1")
    op.execute("ALTER SEQUENCE pairs_id_seq RESTART WITH 1")
    op.execute("ALTER SEQUENCE subscriptions_id_seq RESTART WITH 1")
    op.execute("ALTER SEQUENCE lifetime_pair_history_id_seq RESTART WITH 1")
    op.execute("ALTER SEQUENCE bot_messages_id_seq RESTART WITH 1")


def downgrade() -> None:
    """
    Downgrade is not possible - data cannot be restored.
    This migration is irreversible by design.
    """
    # Cannot restore deleted data
    pass

