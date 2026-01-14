"""Verify delivery_chat migration."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
import asyncpg

async def verify():
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
        cols = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='pairs' 
            AND column_name IN ('delivery_chat', 'private_chat_id')
        """)
        
        found = [c['column_name'] for c in cols]
        
        if 'delivery_chat' in found and 'private_chat_id' in found:
            print("✅ Миграция применена успешно!")
            print(f"   Найдены колонки: {', '.join(found)}")
            return True
        else:
            print("❌ Миграция не применена!")
            print(f"   Найдены колонки: {', '.join(found) if found else 'нет'}")
            return False
    finally:
        await conn.close()

if __name__ == "__main__":
    result = asyncio.run(verify())
    sys.exit(0 if result else 1)
