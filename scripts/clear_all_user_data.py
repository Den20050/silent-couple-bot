"""Dangerous maintenance script: clears all user-related data.

This is intentionally a script (NOT an Alembic migration) to avoid accidental
execution in production during schema upgrades.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.base import async_session_maker


async def clear_all_user_data() -> None:
    """Delete all user-related data while preserving table structure."""
    async with async_session_maker() as session:
        # Tables are cleared in order to respect foreign key constraints.
        await session.execute(text("TRUNCATE TABLE daily_state CASCADE"))
        await session.execute(text("TRUNCATE TABLE subscriptions CASCADE"))
        await session.execute(text("TRUNCATE TABLE lifetime_pair_history CASCADE"))
        await session.execute(text("TRUNCATE TABLE pair_demo CASCADE"))
        await session.execute(text("TRUNCATE TABLE pairs CASCADE"))
        await session.execute(text("TRUNCATE TABLE bot_messages CASCADE"))
        await session.execute(text("TRUNCATE TABLE users CASCADE"))

        # Reset sequences.
        await session.execute(text("ALTER SEQUENCE users_id_seq RESTART WITH 1"))
        await session.execute(text("ALTER SEQUENCE pairs_id_seq RESTART WITH 1"))
        await session.execute(text("ALTER SEQUENCE subscriptions_id_seq RESTART WITH 1"))
        await session.execute(
            text("ALTER SEQUENCE lifetime_pair_history_id_seq RESTART WITH 1")
        )
        await session.execute(text("ALTER SEQUENCE bot_messages_id_seq RESTART WITH 1"))

        await session.commit()


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="DANGEROUS: clears all user-related data from the database."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required confirmation flag. Without it, the script exits.",
    )
    args = parser.parse_args()

    if not args.yes:
        raise SystemExit(
            "Refusing to run without explicit confirmation. Re-run with: --yes"
        )

    asyncio.run(clear_all_user_data())


if __name__ == "__main__":
    main()

