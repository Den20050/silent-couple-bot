"""Fix Alembic version."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
import asyncpg


async def fix():
    url = settings.database_url.replace("postgresql+asyncpg://", "")
    auth_part, db_part = url.split("@", 1)
    user, password = auth_part.split(":", 1)
    host_part, database = db_part.rsplit("/", 1)
    host, port = host_part.split(":", 1)
    
    conn = await asyncpg.connect(
        host=host, port=int(port), user=user, password=password, database=database
    )
    
    # Use truncated version (first 32 chars)
    version = 'add_last_past_due_notification_date'[:32]
    
    await conn.execute(
        "UPDATE alembic_version SET version_num = $1",
        version
    )
    
    new_version = await conn.fetchval("SELECT version_num FROM alembic_version")
    
    print("=" * 60)
    print("Обновление версии Alembic")
    print("=" * 60)
    print(f"Установлена версия: {new_version}")
    print("=" * 60)
    
    await conn.close()


if __name__ == "__main__":
    asyncio.run(fix())
