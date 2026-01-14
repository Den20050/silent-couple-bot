"""Apply migration and update Alembic version."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
import asyncpg


async def apply():
    url = settings.database_url.replace("postgresql+asyncpg://", "")
    auth_part, db_part = url.split("@", 1)
    user, password = auth_part.split(":", 1)
    host_part, database = db_part.rsplit("/", 1)
    host, port = host_part.split(":", 1)
    
    print("Подключение к БД...")
    conn = await asyncpg.connect(
        host=host, port=int(port), user=user, password=password, database=database
    )
    
    try:
        # Check if column exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'subscriptions' 
                AND column_name = 'last_past_due_notification_date'
            )
        """)
        
        if exists:
            print("✅ Колонка уже существует")
        else:
            print("Применяю миграцию...")
            await conn.execute("""
                ALTER TABLE subscriptions 
                ADD COLUMN last_past_due_notification_date DATE NULL
            """)
            print("✅ Колонка добавлена")
        
        # Update Alembic version
        print("Обновляю версию Alembic...")
        current_version = await conn.fetchval("SELECT version_num FROM alembic_version")
        print(f"Текущая версия: {current_version}")
        
        # Check if our migration revision exists in alembic_version
        our_version = 'add_last_past_due_notification_date'
        if current_version != our_version:
            await conn.execute(
                "UPDATE alembic_version SET version_num = $1",
                our_version
            )
            print(f"✅ Версия Alembic обновлена на: {our_version}")
        else:
            print(f"✅ Версия Alembic уже установлена: {our_version}")
        
    finally:
        await conn.close()
        print("Готово!")


if __name__ == "__main__":
    asyncio.run(apply())
