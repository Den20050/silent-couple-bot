"""Check migration via SQLAlchemy."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
from src.db.base import Base
from src.db.models import Subscription
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def check():
    engine = create_async_engine(settings.database_url, echo=False)
    
    async with engine.begin() as conn:
        # Use raw SQL to check column
        result = await conn.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'subscriptions' 
                AND column_name = 'last_past_due_notification_date'
            )
            """
        )
        exists = result.scalar()
        
        print("=" * 60)
        print("Статус миграции")
        print("=" * 60)
        
        if exists:
            print("✅ Колонка 'last_past_due_notification_date' существует")
            print("✅ Миграция применена!")
        else:
            print("❌ Колонка 'last_past_due_notification_date' НЕ найдена")
            print("Применяю миграцию...")
            
            await conn.execute(
                """
                ALTER TABLE subscriptions 
                ADD COLUMN last_past_due_notification_date DATE NULL
                """
            )
            
            print("✅ Миграция применена!")
        
        print("=" * 60)
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check())
