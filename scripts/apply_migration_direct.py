"""Apply migration directly with explicit output."""

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
    
    print("=" * 60)
    print("Применение миграции add_delivery_chat_to_pairs")
    print("=" * 60)
    
    conn = await asyncpg.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=database,
    )
    
    try:
        # Check existing columns
        existing = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='pairs' 
            AND column_name IN ('delivery_chat', 'private_chat_id')
        """)
        existing_names = [r['column_name'] for r in existing]
        print(f"\nСуществующие колонки: {existing_names}")
        
        # Add delivery_chat if not exists
        if 'delivery_chat' not in existing_names:
            print("\n1. Добавление колонки delivery_chat...")
            await conn.execute("""
                ALTER TABLE pairs 
                ADD COLUMN delivery_chat TEXT NOT NULL DEFAULT 'bot_dm'
            """)
            print("   ✅ Колонка delivery_chat добавлена")
            
            print("\n2. Добавление проверки delivery_chat_check...")
            await conn.execute("""
                ALTER TABLE pairs 
                ADD CONSTRAINT delivery_chat_check 
                CHECK (delivery_chat IN ('bot_dm', 'pair_dm'))
            """)
            print("   ✅ Проверка добавлена")
        else:
            print("\n⚠️ Колонка delivery_chat уже существует")
        
        # Add private_chat_id if not exists
        if 'private_chat_id' not in existing_names:
            print("\n3. Добавление колонки private_chat_id...")
            await conn.execute("""
                ALTER TABLE pairs 
                ADD COLUMN private_chat_id BIGINT
            """)
            print("   ✅ Колонка private_chat_id добавлена")
        else:
            print("\n⚠️ Колонка private_chat_id уже существует")
        
        # Verify
        final_check = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='pairs' 
            AND column_name IN ('delivery_chat', 'private_chat_id')
        """)
        final_names = [r['column_name'] for r in final_check]
        
        print("\n" + "=" * 60)
        if 'delivery_chat' in final_names and 'private_chat_id' in final_names:
            print("✅ МИГРАЦИЯ ПРИМЕНЕНА УСПЕШНО!")
            print(f"   Найдены колонки: {', '.join(final_names)}")
        else:
            print("❌ ОШИБКА: не все колонки найдены")
            print(f"   Найдены: {', '.join(final_names) if final_names else 'нет'}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
