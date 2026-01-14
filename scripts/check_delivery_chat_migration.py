"""Check delivery_chat migration status."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
import asyncpg

logger = get_logger(__name__)


async def check_status():
    """Check migration status."""
    try:
        # Parse connection string
        url = settings.database_url.replace("postgresql+asyncpg://", "")
        auth_part, db_part = url.split("@", 1)
        user, password = auth_part.split(":", 1)
        host_part, database = db_part.rsplit("/", 1)
        host, port = host_part.split(":", 1)
        
        print("=" * 60)
        print("Проверка статуса миграции: add_delivery_chat_to_pairs")
        print("=" * 60)
        print(f"База данных: {host}:{port}/{database}")
        print()
        
        conn = await asyncpg.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
        )
        
        # Check if table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'pairs'
            )
        """)
        
        if not table_exists:
            print("❌ Таблица 'pairs' не найдена!")
            await conn.close()
            return
        
        print("✅ Таблица 'pairs' существует")
        
        # Check if columns exist
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'pairs' 
            AND column_name IN ('delivery_chat', 'private_chat_id')
            ORDER BY column_name
        """)
        
        print()
        found_columns = {col['column_name']: col for col in columns}
        
        if 'delivery_chat' in found_columns:
            col = found_columns['delivery_chat']
            print("✅ Колонка 'delivery_chat' существует")
            print(f"   Тип данных: {col['data_type']}")
            print(f"   Может быть NULL: {col['is_nullable']}")
            print(f"   Значение по умолчанию: {col['column_default'] or 'нет'}")
        else:
            print("❌ Колонка 'delivery_chat' НЕ найдена")
        
        print()
        
        if 'private_chat_id' in found_columns:
            col = found_columns['private_chat_id']
            print("✅ Колонка 'private_chat_id' существует")
            print(f"   Тип данных: {col['data_type']}")
            print(f"   Может быть NULL: {col['is_nullable']}")
            print(f"   Значение по умолчанию: {col['column_default'] or 'нет'}")
        else:
            print("❌ Колонка 'private_chat_id' НЕ найдена")
        
        print()
        
        if 'delivery_chat' in found_columns and 'private_chat_id' in found_columns:
            print("✅ Миграция применена успешно!")
        else:
            print("❌ Миграция НЕ применена полностью!")
            print()
            print("Для применения миграции выполните:")
            print("  alembic upgrade head")
        
        # Check alembic_version table
        print()
        print("Проверка версии Alembic...")
        alembic_table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'alembic_version'
            )
        """)
        
        if alembic_table_exists:
            current_version = await conn.fetchval("SELECT version_num FROM alembic_version")
            print(f"Текущая версия Alembic: {current_version}")
        else:
            print("Таблица 'alembic_version' не найдена")
        
        await conn.close()
        print()
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    configure_logging("INFO")
    asyncio.run(check_status())
