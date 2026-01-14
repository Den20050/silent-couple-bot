"""Final migration check."""

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
    
    # Check column
    col_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'subscriptions' 
            AND column_name = 'last_past_due_notification_date'
        )
    """)
    
    # Check version
    version = await conn.fetchval("SELECT version_num FROM alembic_version")
    
    print("=" * 60)
    print("ИТОГОВЫЙ СТАТУС МИГРАЦИИ")
    print("=" * 60)
    print()
    
    if col_exists:
        print("✅ Колонка 'last_past_due_notification_date' добавлена")
        print("✅ Миграция применена успешно!")
    else:
        print("❌ Колонка не найдена")
        print("❌ Миграция НЕ применена")
    
    print()
    print(f"Текущая версия Alembic: {version}")
    print()
    print("=" * 60)
    
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
