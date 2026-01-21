"""add_pair_notification_windows_owner

Revision ID: c9a3f0e5a1b2
Revises: 5b1b5f9c2b2a
Create Date: 2026-01-21

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9a3f0e5a1b2"
down_revision: Union[str, None] = "5b1b5f9c2b2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pairs",
        sa.Column(
            "morning_window_start_hour",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("7"),
        ),
    )
    op.add_column(
        "pairs",
        sa.Column(
            "evening_window_start_hour",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("21"),
        ),
    )
    op.add_column(
        "pairs",
        sa.Column(
            "notification_window_owner_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "pairs_morning_window_start_hour_check",
        "pairs",
        "morning_window_start_hour >= 0 AND morning_window_start_hour <= 23",
    )
    op.create_check_constraint(
        "pairs_evening_window_start_hour_check",
        "pairs",
        "evening_window_start_hour >= 0 AND evening_window_start_hour <= 23",
    )


def downgrade() -> None:
    op.drop_constraint(
        "pairs_evening_window_start_hour_check",
        "pairs",
        type_="check",
    )
    op.drop_constraint(
        "pairs_morning_window_start_hour_check",
        "pairs",
        type_="check",
    )
    op.drop_column("pairs", "notification_window_owner_id")
    op.drop_column("pairs", "evening_window_start_hour")
    op.drop_column("pairs", "morning_window_start_hour")

