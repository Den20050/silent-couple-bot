"""add_user_timezone_name

Revision ID: add_user_timezone_name
Revises: add_pair_first_payment_bonus
Create Date: 2026-08-28

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_user_timezone_name"
down_revision: Union[str, None] = "add_pair_first_payment_bonus"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("timezone_name", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "timezone_name")
