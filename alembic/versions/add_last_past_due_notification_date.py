"""add_last_past_due_notification_date

Revision ID: add_last_past_due_notification_date
Revises: 4248837e6f13
Create Date: 2025-12-10 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_last_past_due_notification_date'
down_revision: Union[str, None] = 'add_bot_messages'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_past_due_notification_date column to subscriptions table
    # Use IF NOT EXISTS to make migration idempotent
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'subscriptions'
                AND column_name = 'last_past_due_notification_date'
            ) THEN
                ALTER TABLE subscriptions 
                ADD COLUMN last_past_due_notification_date DATE;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Remove last_past_due_notification_date column from subscriptions table
    op.drop_column('subscriptions', 'last_past_due_notification_date')
