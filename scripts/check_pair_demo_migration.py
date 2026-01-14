"""Check if pair_demo migration is applied."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.core.database import async_session_maker


async def check_migration() -> None:
    """Check migration status."""
    try:
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
            
            print("=" * 60)
            print("Migration Status Check")
            print("=" * 60)
            print(f"user_demo table exists: {user_demo_exists}")
            print(f"pair_demo table exists: {pair_demo_exists}")
            print("=" * 60)
            
            if user_demo_exists and not pair_demo_exists:
                print("\n❌ Migration NOT applied - user_demo still exists")
                print("   Run: python scripts/apply_pair_demo_migration.py")
            elif pair_demo_exists:
                print("\n✅ Migration applied - pair_demo table exists")
                if user_demo_exists:
                    print("⚠️  Warning: Both tables exist (should not happen)")
                else:
                    print("✅ user_demo table removed correctly")
            else:
                print("\n⚠️  Neither table exists - creating pair_demo...")
                await session.execute(text("""
                    CREATE TABLE pair_demo (
                        uid_a BIGINT NOT NULL,
                        uid_b BIGINT NOT NULL,
                        PRIMARY KEY (uid_a, uid_b),
                        CONSTRAINT pair_demo_uid_order_check CHECK (uid_a < uid_b)
                    );
                """))
                await session.commit()
                print("✅ Created pair_demo table")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_migration())
