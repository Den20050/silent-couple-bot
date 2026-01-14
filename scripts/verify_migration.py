"""Verify if migration was applied."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
import asyncpg


async def verify():
    """Verify migration."""
    try:
        url = settings.database_url.replace("postgresql+asyncpg://", "")
        auth_part, db_part = url.split("@", 1)
        user, password = auth_part.split(":", 1)
        host_part, database = db_part.rsplit("/", 1)
        host, port = host_part.split(":", 1)
        
        print(f"Подключение к БД: {host}:{port}/{database}")
        
        conn = await asyncpg.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
        )
        
        # Check column
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'subscriptions' 
                AND column_name = 'last_past_due_notification_date'
            )
        """)
        
        if exists:
            print("✅ Колонка 'last_past_due_notification_date' существует")
            print("✅ Миграция применена!")
        else:
            print("❌ Колонка 'last_past_due_notification_date' НЕ найдена")
            print("Применяю миграцию...")
            
            await conn.execute("""
                ALTER TABLE subscriptions 
                ADD COLUMN last_past_due_notification_date DATE NULL
            """)
            
            print("✅ Миграция применена!")
        
        await conn.close()
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(verify())
