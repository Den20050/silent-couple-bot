"""drop_utc_offset_default

Revision ID: drop_utc_offset_default
Revises: add_user_timezone_name
Create Date: 2026-08-28

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "drop_utc_offset_default"
down_revision: Union[str, None] = "add_user_timezone_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "utc_offset",
        existing_type=sa.Integer(),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "utc_offset",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("3"),
    )
