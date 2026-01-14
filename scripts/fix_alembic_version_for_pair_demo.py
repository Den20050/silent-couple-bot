"""Fix Alembic version to skip already applied migrations."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.db.base import async_session_maker


async def fix_version() -> None:
    """Update Alembic version to match actual DB state."""
    async with async_session_maker() as session:
        # Check current version
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        current_version = result.scalar()
        
        print(f"Current Alembic version in DB: {current_version}")
        
        # Check which migrations are actually applied
        # Check if last_past_due_notification_date column exists
        result = await session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'subscriptions'
                AND column_name = 'last_past_due_notification_date'
            );
        """))
        has_last_past_due = result.scalar()
        
        # Check if delivery_chat column exists
        result = await session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'pairs'
                AND column_name = 'delivery_chat'
            );
        """))
        has_delivery_chat = result.scalar()
        
        # Check if pair_demo table exists
        result = await session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'pair_demo'
            );
        """))
        has_pair_demo = result.scalar()
        
        print(f"last_past_due_notification_date exists: {has_last_past_due}")
        print(f"delivery_chat exists: {has_delivery_chat}")
        print(f"pair_demo exists: {has_pair_demo}")
        
        # Determine target version based on what's actually applied
        if has_pair_demo:
            target_version = 'replace_user_demo_pair'
            print(f"\n✅ pair_demo exists - setting version to: {target_version}")
        elif has_delivery_chat:
            target_version = 'add_delivery_chat_to_pairs'
            print(f"\n✅ delivery_chat exists - setting version to: {target_version}")
        elif has_last_past_due:
            target_version = 'add_last_past_due_notification_date'
            print(f"\n✅ last_past_due_notification_date exists - setting version to: {target_version}")
        else:
            target_version = 'add_bot_messages'
            print(f"\n⚠️  No new columns found - keeping version: {target_version}")
        
        if current_version != target_version:
            await session.execute(text(f"UPDATE alembic_version SET version_num = '{target_version}'"))
            await session.commit()
            print(f"\n✅ Updated Alembic version from {current_version} to {target_version}")
        else:
            print(f"\n✅ Alembic version is already correct: {target_version}")


if __name__ == "__main__":
    asyncio.run(fix_version())
