"""add_pair_demo_hash

Revision ID: add_pair_demo_hash
Revises: add_consent_audit
Create Date: 2026-01-31 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_pair_demo_hash"
down_revision: Union[str, None] = "add_consent_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'pair_demo_hash'
            ) THEN
                CREATE TABLE pair_demo_hash (
                    pair_hash TEXT PRIMARY KEY,
                    created_at TIMESTAMP NOT NULL DEFAULT now()
                );
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("pair_demo_hash")
