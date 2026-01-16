"""add_user_notification_windows

Revision ID: 5b1b5f9c2b2a
Revises: a703b4149630
Create Date: 2026-01-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5b1b5f9c2b2a"
down_revision: Union[str, None] = "a703b4149630"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "morning_window_start_hour",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("7"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "evening_window_start_hour",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("21"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "notification_windows_prompted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Optional sanity checks (hours in [0..23])
    op.create_check_constraint(
        "users_morning_window_start_hour_check",
        "users",
        "morning_window_start_hour >= 0 AND morning_window_start_hour <= 23",
    )
    op.create_check_constraint(
        "users_evening_window_start_hour_check",
        "users",
        "evening_window_start_hour >= 0 AND evening_window_start_hour <= 23",
    )


def downgrade() -> None:
    op.drop_constraint("users_evening_window_start_hour_check", "users", type_="check")
    op.drop_constraint("users_morning_window_start_hour_check", "users", type_="check")
    op.drop_column("users", "notification_windows_prompted")
    op.drop_column("users", "evening_window_start_hour")
    op.drop_column("users", "morning_window_start_hour")

