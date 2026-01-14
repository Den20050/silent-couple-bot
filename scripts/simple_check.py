"""Simple migration status check."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
import asyncpg


async def main():
    url = settings.database_url.replace("postgresql+asyncpg://", "")
    auth_part, db_part = url.split("@", 1)
    user, password = auth_part.split(":", 1)
    host_part, database = db_part.rsplit("/", 1)
    host, port = host_part.split(":", 1)
    
    conn = await asyncpg.connect(
        host=host, port=int(port), user=user, password=password, database=database
    )
    
    exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'subscriptions' 
            AND column_name = 'last_past_due_notification_date'
        )
    """)
    
    sys.stdout.write(f"Column exists: {exists}\n")
    sys.stdout.flush()
    
    if not exists:
        sys.stdout.write("Applying migration...\n")
        sys.stdout.flush()
        await conn.execute("""
            ALTER TABLE subscriptions 
            ADD COLUMN last_past_due_notification_date DATE NULL
        """)
        sys.stdout.write("Migration applied!\n")
        sys.stdout.flush()
    else:
        sys.stdout.write("Migration already applied!\n")
        sys.stdout.flush()
    
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
