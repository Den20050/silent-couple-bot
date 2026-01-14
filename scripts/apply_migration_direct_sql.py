"""Apply migration directly via SQL."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.core.database import async_session_maker


async def apply_migration() -> None:
    """Apply migration directly."""
    async with async_session_maker() as session:
        try:
            # Drop user_demo if exists
            await session.execute(text("DROP TABLE IF EXISTS user_demo CASCADE;"))
            print("Dropped user_demo table")
            
            # Create pair_demo
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS pair_demo (
                    uid_a BIGINT NOT NULL,
                    uid_b BIGINT NOT NULL,
                    PRIMARY KEY (uid_a, uid_b),
                    CONSTRAINT pair_demo_uid_order_check CHECK (uid_a < uid_b)
                );
            """))
            print("Created pair_demo table")
            
            await session.commit()
            print("Migration applied successfully!")
        except Exception as e:
            await session.rollback()
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(apply_migration())
