"""Verify pair_demo migration status."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.db.base import async_session_maker


async def verify() -> None:
    """Verify migration status."""
    async with async_session_maker() as session:
        # Check user_demo
        result = await session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_demo'
            );
        """))
        user_demo_exists = result.scalar()
        
        # Check pair_demo
        result = await session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'pair_demo'
            );
        """))
        pair_demo_exists = result.scalar()
        
        # Check pair_demo structure if exists
        if pair_demo_exists:
            result = await session.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'pair_demo'
                ORDER BY ordinal_position;
            """))
            columns = result.fetchall()
        
        print("=" * 60)
        print("Migration Status:")
        print("=" * 60)
        print(f"user_demo exists: {user_demo_exists}")
        print(f"pair_demo exists: {pair_demo_exists}")
        
        if pair_demo_exists:
            print("\npair_demo columns:")
            for col_name, col_type in columns:
                print(f"  - {col_name}: {col_type}")
        
        print("=" * 60)
        
        if user_demo_exists and not pair_demo_exists:
            print("\n❌ Migration NOT applied!")
            return False
        elif pair_demo_exists:
            if user_demo_exists:
                print("\n⚠️  Both tables exist (unexpected)")
                return False
            else:
                print("\n✅ Migration applied successfully!")
                return True
        else:
            print("\n⚠️  Neither table exists")
            return False


if __name__ == "__main__":
    success = asyncio.run(verify())
    sys.exit(0 if success else 1)
