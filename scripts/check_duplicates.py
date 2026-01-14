"""Script to check for duplicate file_ids in database."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.core.config import settings
from src.core.constants import PicType
from src.core.logger import configure_logging, get_logger
from src.db.models import PicsPool

logger = get_logger(__name__)

# Create engine
engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def check_duplicates() -> None:
    """Check for duplicates in database."""
    configure_logging(settings.log_level)
    
    async with async_session_maker() as session:
        # Count total records
        total_morning = await session.execute(
            select(func.count(PicsPool.file_id)).where(PicsPool.type == PicType.MORNING.value)
        )
        total_evening = await session.execute(
            select(func.count(PicsPool.file_id)).where(PicsPool.type == PicType.EVENING.value)
        )
        
        morning_count = total_morning.scalar() or 0
        evening_count = total_evening.scalar() or 0
        
        print(f"\n📊 Текущее состояние БД:")
        print(f"   Утренних записей: {morning_count}")
        print(f"   Вечерних записей: {evening_count}")
        print(f"   Всего: {morning_count + evening_count}")
        
        # Expected counts
        expected_morning = 1104
        expected_evening = 645
        
        print(f"\n📁 Ожидаемое количество:")
        print(f"   Утренних файлов: {expected_morning}")
        print(f"   Вечерних файлов: {expected_evening}")
        print(f"   Всего: {expected_morning + expected_evening}")
        
        print(f"\n📈 Разница:")
        print(f"   Утренних: {morning_count - expected_morning} (лишних)")
        print(f"   Вечерних: {evening_count - expected_evening} (лишних)")
        
        if evening_count > expected_evening:
            excess_evening = evening_count - expected_evening
            print(f"\n⚠️  В БД {excess_evening} лишних вечерних записей")
            print(f"   Это может привести к повторению картинок")
            print(f"   Вероятность повтора: ~{excess_evening / evening_count * 100:.1f}%")
        
        if morning_count > expected_morning:
            excess_morning = morning_count - expected_morning
            print(f"\n⚠️  В БД {excess_morning} лишних утренних записей")
            print(f"   Это может привести к повторению картинок")
            print(f"   Вероятность повтора: ~{excess_morning / morning_count * 100:.1f}%")
    
    await engine.dispose()


if __name__ == "__main__":
    import asyncio
    asyncio.run(check_duplicates())

