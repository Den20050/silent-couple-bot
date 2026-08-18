"""add pair_first_payment_bonus_hash

Revision ID: add_pair_first_payment_bonus
Revises: add_pair_payments
Create Date: 2026-08-18 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "add_pair_first_payment_bonus"
down_revision: Union[str, None] = "add_pair_payments"
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
                  AND table_name = 'pair_first_payment_bonus_hash'
            ) THEN
                CREATE TABLE pair_first_payment_bonus_hash (
                    pair_hash TEXT PRIMARY KEY,
                    created_at TIMESTAMP NOT NULL DEFAULT now()
                );
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("pair_first_payment_bonus_hash")
