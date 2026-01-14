"""Check migration status and save to file."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

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
    
    result_file = project_root / "migration_status.txt"
    
    with open(result_file, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("Проверка статуса миграции\n")
        f.write(f"Время проверки: {datetime.now()}\n")
        f.write("=" * 60 + "\n\n")
        
        try:
            conn = await asyncpg.connect(
                host=host, port=int(port), user=user, password=password, database=database
            )
            
            f.write(f"✅ Подключение к БД успешно: {host}:{port}/{database}\n\n")
            
            # Check column
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'subscriptions' 
                    AND column_name = 'last_past_due_notification_date'
                )
            """)
            
            if exists:
                f.write("✅ Колонка 'last_past_due_notification_date' существует\n")
                f.write("✅ Миграция применена!\n\n")
                
                # Get column details
                col_info = await conn.fetchrow("""
                    SELECT data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = 'subscriptions' 
                    AND column_name = 'last_past_due_notification_date'
                """)
                
                if col_info:
                    f.write("Детали колонки:\n")
                    f.write(f"  Тип: {col_info['data_type']}\n")
                    f.write(f"  NULL разрешен: {col_info['is_nullable']}\n")
                    f.write(f"  По умолчанию: {col_info['column_default'] or 'нет'}\n")
            else:
                f.write("❌ Колонка 'last_past_due_notification_date' НЕ найдена\n")
                f.write("❌ Миграция НЕ применена!\n\n")
                f.write("Применяю миграцию...\n")
                
                await conn.execute("""
                    ALTER TABLE subscriptions 
                    ADD COLUMN last_past_due_notification_date DATE NULL
                """)
                
                f.write("✅ Миграция применена!\n")
            
            # Check Alembic version
            f.write("\n")
            alembic_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'alembic_version'
                )
            """)
            
            if alembic_exists:
                version = await conn.fetchval("SELECT version_num FROM alembic_version")
                f.write(f"Текущая версия Alembic: {version}\n")
            
            await conn.close()
            f.write("\n" + "=" * 60 + "\n")
            f.write("Проверка завершена успешно!\n")
            
        except Exception as e:
            f.write(f"❌ Ошибка: {e}\n")
            import traceback
            f.write(traceback.format_exc())
    
    print(f"Результат сохранен в файл: {result_file}")
    print("Откройте файл migration_status.txt для просмотра результатов")


if __name__ == "__main__":
    asyncio.run(main())
