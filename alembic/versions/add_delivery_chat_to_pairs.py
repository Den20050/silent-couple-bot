"""add_delivery_chat_to_pairs

Revision ID: add_delivery_chat_to_pairs
Revises: add_last_past_due_notification_date
Create Date: 2025-12-10 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_delivery_chat_to_pairs'
down_revision: Union[str, None] = 'add_last_past_due_notification_date'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use conditional SQL to make migration idempotent
    op.execute("""
        DO $$ 
        BEGIN
            -- Add delivery_chat column if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'pairs'
                AND column_name = 'delivery_chat'
            ) THEN
                ALTER TABLE pairs 
                ADD COLUMN delivery_chat TEXT DEFAULT 'bot_dm' NOT NULL;
            END IF;
            
            -- Add check constraint if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE table_schema = 'public' 
                AND table_name = 'pairs'
                AND constraint_name = 'delivery_chat_check'
            ) THEN
                ALTER TABLE pairs 
                ADD CONSTRAINT delivery_chat_check 
                CHECK (delivery_chat IN ('bot_dm', 'pair_dm'));
            END IF;
            
            -- Add private_chat_id column if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'pairs'
                AND column_name = 'private_chat_id'
            ) THEN
                ALTER TABLE pairs 
                ADD COLUMN private_chat_id BIGINT;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Remove columns
    op.drop_constraint('delivery_chat_check', 'pairs', type_='check')
    op.drop_column('pairs', 'private_chat_id')
    op.drop_column('pairs', 'delivery_chat')
