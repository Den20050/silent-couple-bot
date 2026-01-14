"""Check migration status and database state."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.db.base import async_session_maker


async def check_status() -> None:
    """Check migration status."""
    async with async_session_maker() as session:
        # Check Alembic version
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        alembic_version = result.scalar()
        print(f"Alembic version: {alembic_version}")
        
        # Check if user_demo exists
        result = await session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_demo'
            );
        """))
        user_demo_exists = result.scalar()
        print(f"user_demo table exists: {user_demo_exists}")
        
        # Check if pair_demo exists
        result = await session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'pair_demo'
            );
        """))
        pair_demo_exists = result.scalar()
        print(f"pair_demo table exists: {pair_demo_exists}")
        
        if pair_demo_exists:
            # Check pair_demo structure
            result = await session.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'pair_demo'
                ORDER BY ordinal_position;
            """))
            columns = result.fetchall()
            print("\npair_demo columns:")
            for col_name, col_type in columns:
                print(f"  - {col_name}: {col_type}")
        
        print("\n" + "=" * 60)
        if pair_demo_exists and not user_demo_exists:
            print("✅ Migration applied successfully!")
            print("   user_demo -> pair_demo conversion completed")
        elif user_demo_exists and not pair_demo_exists:
            print("❌ Migration NOT applied")
            print("   user_demo still exists, pair_demo not created")
        elif pair_demo_exists and user_demo_exists:
            print("⚠️  Both tables exist (unexpected state)")
        else:
            print("⚠️  Neither table exists")


if __name__ == "__main__":
    asyncio.run(check_status())
