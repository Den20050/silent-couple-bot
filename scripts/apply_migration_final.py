"""Apply migration - final version."""

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
    exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'subscriptions' 
            AND column_name = 'last_past_due_notification_date'
        )
    """)
    
    if not exists:
        print("Добавляю колонку...")
        await conn.execute("""
            ALTER TABLE subscriptions 
            ADD COLUMN last_past_due_notification_date DATE NULL
        """)
        print("✅ Колонка добавлена!")
    else:
        print("✅ Колонка уже существует")
    
    # Note: Alembic version will be updated automatically when running:
    # python -m alembic upgrade head
    # We don't update it manually to avoid breaking the migration chain
    
    await conn.close()
    print("Миграция применена успешно!")
    print("\nДля обновления версии Alembic выполните:")
    print("  python -m alembic stamp add_last_past_due_notification_date")


if __name__ == "__main__":
    asyncio.run(main())
