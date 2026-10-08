"""add_consent_audit

Revision ID: add_consent_audit
Revises: c9a3f0e5a1b2
Create Date: 2026-01-29 21:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_consent_audit"
down_revision: Union[str, None] = "c9a3f0e5a1b2"
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
                  AND table_name = 'consent_audit'
            ) THEN
                CREATE TABLE consent_audit (
                    id BIGSERIAL PRIMARY KEY,
                    tg_id BIGINT NOT NULL,
                    consented_at TIMESTAMP NOT NULL DEFAULT now(),
                    consent_ip TEXT
                );
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'idx_consent_audit_tg_id'
            ) THEN
                CREATE INDEX idx_consent_audit_tg_id ON consent_audit (tg_id);
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'idx_consent_audit_consented_at'
            ) THEN
                CREATE INDEX idx_consent_audit_consented_at ON consent_audit (consented_at);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("consent_audit")
