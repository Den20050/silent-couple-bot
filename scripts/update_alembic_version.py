"""Update Alembic version to match applied migration."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
import asyncpg


async def update_version():
    url = settings.database_url.replace("postgresql+asyncpg://", "")
    auth_part, db_part = url.split("@", 1)
    user, password = auth_part.split(":", 1)
    host_part, database = db_part.rsplit("/", 1)
    host, port = host_part.split(":", 1)
    
    conn = await asyncpg.connect(
        host=host, port=int(port), user=user, password=password, database=database
    )
    
    try:
        # Check current version
        current_version = await conn.fetchval("SELECT version_num FROM alembic_version")
        print(f"Текущая версия: {current_version}")
        
        # Our migration revision
        our_version = 'add_last_past_due_notification_date'
        
        # Check column length limit
        col_info = await conn.fetchrow("""
            SELECT character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = 'alembic_version' 
            AND column_name = 'version_num'
        """)
        
        max_length = col_info['character_maximum_length'] if col_info else None
        print(f"Максимальная длина version_num: {max_length}")
        
        if max_length and len(our_version) > max_length:
            print(f"⚠️  Имя версии слишком длинное ({len(our_version)} символов)")
            print(f"   Максимум: {max_length} символов")
            print(f"   Используем первые {max_length} символов")
            our_version_truncated = our_version[:max_length]
            print(f"   Усеченная версия: {our_version_truncated}")
            
            await conn.execute(
                "UPDATE alembic_version SET version_num = $1",
                our_version_truncated
            )
            print(f"✅ Версия обновлена на: {our_version_truncated}")
        else:
            await conn.execute(
                "UPDATE alembic_version SET version_num = $1",
                our_version
            )
            print(f"✅ Версия обновлена на: {our_version}")
        
        # Verify
        new_version = await conn.fetchval("SELECT version_num FROM alembic_version")
        print(f"Проверка: текущая версия = {new_version}")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(update_version())
