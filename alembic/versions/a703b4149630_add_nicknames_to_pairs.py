"""add_nicknames_to_pairs

Revision ID: a703b4149630
Revises: replace_user_demo_pair
Create Date: 2025-12-29 10:34:42.073284

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a703b4149630'
down_revision: Union[str, None] = 'replace_user_demo_pair'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use conditional SQL to make migration idempotent
    op.execute("""
        DO $$ 
        BEGIN
            -- Add nickname_a column if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'pairs'
                AND column_name = 'nickname_a'
            ) THEN
                ALTER TABLE pairs 
                ADD COLUMN nickname_a TEXT;
            END IF;
            
            -- Add nickname_b column if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'pairs'
                AND column_name = 'nickname_b'
            ) THEN
                ALTER TABLE pairs 
                ADD COLUMN nickname_b TEXT;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Remove columns
    op.drop_column('pairs', 'nickname_b')
    op.drop_column('pairs', 'nickname_a')

