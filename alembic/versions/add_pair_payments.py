"""add_pair_payments

Revision ID: add_pair_payments
Revises: add_pair_demo_hash
Create Date: 2026-08-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "add_pair_payments"
down_revision: Union[str, None] = "add_pair_demo_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'pair_payments'
            ) THEN
                CREATE TABLE pair_payments (
                    id BIGSERIAL PRIMARY KEY,
                    pair_id BIGINT NOT NULL REFERENCES pairs(id) ON DELETE CASCADE,
                    payer_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    inv_id TEXT NOT NULL UNIQUE,
                    amount NUMERIC(12, 2) NOT NULL,
                    currency TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    is_lifetime BOOLEAN NOT NULL DEFAULT FALSE,
                    paid_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'idx_pair_payments_paid_at'
            ) THEN
                CREATE INDEX idx_pair_payments_paid_at ON pair_payments (paid_at);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'idx_pair_payments_pair_id'
            ) THEN
                CREATE INDEX idx_pair_payments_pair_id ON pair_payments (pair_id);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'idx_pair_payments_currency'
            ) THEN
                CREATE INDEX idx_pair_payments_currency ON pair_payments (currency);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("pair_payments")
