"""Check if migration is needed and apply it."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
import asyncpg

logger = get_logger(__name__)


async def check_and_apply() -> None:
    """Check if column exists and apply migration if needed."""
    try:
        # Parse connection string
        url = settings.database_url.replace("postgresql+asyncpg://", "")
        auth_part, db_part = url.split("@", 1)
        user, password = auth_part.split(":", 1)
        host_part, database = db_part.rsplit("/", 1)
        host, port = host_part.split(":", 1)
        
        conn = await asyncpg.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
        )
        
        # Check if column exists
        column_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'subscriptions' 
                AND column_name = 'last_past_due_notification_date'
            )
        """)
        
        if column_exists:
            print("✅ Колонка 'last_past_due_notification_date' уже существует в таблице 'subscriptions'")
            print("Миграция уже применена.")
        else:
            print("❌ Колонка 'last_past_due_notification_date' не найдена в таблице 'subscriptions'")
            print("Применяю миграцию...")
            
            # Apply migration
            await conn.execute("""
                ALTER TABLE subscriptions 
                ADD COLUMN last_past_due_notification_date DATE NULL
            """)
            
            print("✅ Миграция применена успешно!")
            
            # Verify
            column_exists_after = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'subscriptions' 
                    AND column_name = 'last_past_due_notification_date'
                )
            """)
            
            if column_exists_after:
                print("✅ Проверка: колонка успешно добавлена")
            else:
                print("❌ Ошибка: колонка не была добавлена")
                sys.exit(1)
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    configure_logging("INFO")
    asyncio.run(check_and_apply())
