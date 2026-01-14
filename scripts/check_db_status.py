"""Quick script to check current database status."""

import asyncio
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


async def check_status() -> None:
    """Check current database status."""
    configure_logging(settings.log_level)
    
    # Count files in directories
    base_dir = Path(__file__).parent.parent
    morning_dir = base_dir / "image" / "morning"
    evening_dir = base_dir / "image" / "evening"
    
    morning_files = list(morning_dir.glob("*.jpg")) if morning_dir.exists() else []
    evening_files = list(evening_dir.glob("*.jpg")) if evening_dir.exists() else []
    
    print(f"\n📁 Файлы в папках:")
    print(f"   Утренних: {len(morning_files)}")
    print(f"   Вечерних: {len(evening_files)}")
    print(f"   Всего: {len(morning_files) + len(evening_files)}")
    
    async with async_session_maker() as session:
        # Count by type
        morning_count_result = await session.execute(
            select(func.count(PicsPool.file_id)).where(PicsPool.type == PicType.MORNING.value)
        )
        morning_count = morning_count_result.scalar() or 0
        
        evening_count_result = await session.execute(
            select(func.count(PicsPool.file_id)).where(PicsPool.type == PicType.EVENING.value)
        )
        evening_count = evening_count_result.scalar() or 0
        
        total_count = morning_count + evening_count
        
        print(f"\n💾 Загружено в БД:")
        print(f"   Утренних: {morning_count}")
        print(f"   Вечерних: {evening_count}")
        print(f"   Всего: {total_count}")
        
        # Calculate missing
        missing_morning = len(morning_files) - morning_count
        missing_evening = len(evening_files) - evening_count
        missing_total = missing_morning + missing_evening
        
        print(f"\n📊 Статистика:")
        print(f"   Утренних не загружено: {missing_morning}")
        print(f"   Вечерних не загружено: {missing_evening}")
        print(f"   Всего не загружено: {missing_total}")
        
        # Coverage percentage
        if len(morning_files) > 0:
            morning_coverage = (morning_count / len(morning_files)) * 100
            print(f"\n   Покрытие утренних: {morning_coverage:.1f}%")
        
        if len(evening_files) > 0:
            evening_coverage = (evening_count / len(evening_files)) * 100
            print(f"   Покрытие вечерних: {evening_coverage:.1f}%")
        
        if total_count > 0:
            total_coverage = (total_count / (len(morning_files) + len(evening_files))) * 100
            print(f"   Общее покрытие: {total_coverage:.1f}%")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_status())
