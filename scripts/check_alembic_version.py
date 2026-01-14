"""Check Alembic version."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
import asyncpg


async def check():
    url = settings.database_url.replace("postgresql+asyncpg://", "")
    auth_part, db_part = url.split("@", 1)
    user, password = auth_part.split(":", 1)
    host_part, database = db_part.rsplit("/", 1)
    host, port = host_part.split(":", 1)
    
    conn = await asyncpg.connect(
        host=host, port=int(port), user=user, password=password, database=database
    )
    
    # Check column
    col_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'subscriptions' 
            AND column_name = 'last_past_due_notification_date'
        )
    """)
    
    print("=" * 60)
    print("Статус миграции")
    print("=" * 60)
    print(f"Колонка существует: {'✅ Да' if col_exists else '❌ Нет'}")
    
    # Check Alembic version
    version = await conn.fetchval("SELECT version_num FROM alembic_version")
    print(f"Версия Alembic: {version}")
    print(f"Длина версии: {len(version) if version else 0} символов")
    print("=" * 60)
    
    await conn.close()


if __name__ == "__main__":
    asyncio.run(check())
