"""Apply pair_demo migration directly."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.core.config import settings
from src.core.database import async_session_maker


async def check_and_apply_migration() -> None:
    """Check current state and apply migration if needed."""
    async with async_session_maker() as session:
        # Check if user_demo table exists
        check_user_demo = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_demo'
            );
        """)
        
        result = await session.execute(check_user_demo)
        user_demo_exists = result.scalar()
        
        # Check if pair_demo table exists
        check_pair_demo = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'pair_demo'
            );
        """)
        
        result = await session.execute(check_pair_demo)
        pair_demo_exists = result.scalar()
        
        print(f"user_demo exists: {user_demo_exists}")
        print(f"pair_demo exists: {pair_demo_exists}")
        
        if user_demo_exists and not pair_demo_exists:
            print("\n✅ Applying migration: replacing user_demo with pair_demo...")
            
            # Drop user_demo table
            await session.execute(text("DROP TABLE IF EXISTS user_demo CASCADE;"))
            print("  ✓ Dropped user_demo table")
            
            # Create pair_demo table
            await session.execute(text("""
                CREATE TABLE pair_demo (
                    uid_a BIGINT NOT NULL,
                    uid_b BIGINT NOT NULL,
                    PRIMARY KEY (uid_a, uid_b),
                    CONSTRAINT pair_demo_uid_order_check CHECK (uid_a < uid_b)
                );
            """))
            print("  ✓ Created pair_demo table")
            
            await session.commit()
            print("\n✅ Migration applied successfully!")
        elif pair_demo_exists:
            print("\n✅ Migration already applied - pair_demo table exists")
        elif not user_demo_exists and not pair_demo_exists:
            print("\n⚠️  Neither user_demo nor pair_demo exists - creating pair_demo...")
            await session.execute(text("""
                CREATE TABLE pair_demo (
                    uid_a BIGINT NOT NULL,
                    uid_b BIGINT NOT NULL,
                    PRIMARY KEY (uid_a, uid_b),
                    CONSTRAINT pair_demo_uid_order_check CHECK (uid_a < uid_b)
                );
            """))
            await session.commit()
            print("  ✓ Created pair_demo table")
        else:
            print("\n⚠️  Unexpected state - both tables exist")


if __name__ == "__main__":
    asyncio.run(check_and_apply_migration())
