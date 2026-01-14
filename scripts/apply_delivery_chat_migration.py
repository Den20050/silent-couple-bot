"""Apply delivery_chat migration directly."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
import asyncpg

async def apply_migration():
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
    
    try:
        print("Применение миграции add_delivery_chat_to_pairs...")
        
        # Check if columns already exist
        existing_cols = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='pairs' 
            AND column_name IN ('delivery_chat', 'private_chat_id')
        """)
        
        existing = [c['column_name'] for c in existing_cols]
        
        if 'delivery_chat' in existing and 'private_chat_id' in existing:
            print("✅ Колонки уже существуют, миграция уже применена!")
            return True
        
        # Add delivery_chat column
        if 'delivery_chat' not in existing:
            print("Добавление колонки delivery_chat...")
            await conn.execute("""
                ALTER TABLE pairs 
                ADD COLUMN delivery_chat TEXT NOT NULL DEFAULT 'bot_dm'
            """)
            print("✅ Колонка delivery_chat добавлена")
            
            # Add check constraint
            print("Добавление проверки для delivery_chat...")
            await conn.execute("""
                ALTER TABLE pairs 
                ADD CONSTRAINT delivery_chat_check 
                CHECK (delivery_chat IN ('bot_dm', 'pair_dm'))
            """)
            print("✅ Проверка delivery_chat_check добавлена")
        else:
            print("⚠️ Колонка delivery_chat уже существует")
        
        # Add private_chat_id column
        if 'private_chat_id' not in existing:
            print("Добавление колонки private_chat_id...")
            await conn.execute("""
                ALTER TABLE pairs 
                ADD COLUMN private_chat_id BIGINT
            """)
            print("✅ Колонка private_chat_id добавлена")
        else:
            print("⚠️ Колонка private_chat_id уже существует")
        
        # Update alembic_version (only if columns were added)
        if 'delivery_chat' not in existing or 'private_chat_id' not in existing:
            print("Обновление версии Alembic...")
            # Check current version
            current_version = await conn.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
            print(f"Текущая версия: {current_version}")
            
            if current_version:
                await conn.execute("""
                    UPDATE alembic_version 
                    SET version_num = 'add_delivery_chat_to_pairs'
                    WHERE version_num = %s
                """, current_version)
            else:
                await conn.execute("""
                    INSERT INTO alembic_version (version_num) 
                    VALUES ('add_delivery_chat_to_pairs')
                """)
            
                print("✅ Версия Alembic обновлена")
        
        print()
        print("✅ Миграция применена успешно!")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при применении миграции: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    import sys
    result = asyncio.run(apply_migration())
    if result:
        print("\n✅ Миграция успешно применена!", file=sys.stdout)
    else:
        print("\n❌ Ошибка при применении миграции!", file=sys.stderr)
    sys.exit(0 if result else 1)
