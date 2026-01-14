"""Script to check how many images are loaded in the database."""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, func

from src.core.config import settings
from src.core.constants import PicType
from src.core.logger import configure_logging, get_logger
from src.db.models import PicsPool

logger = get_logger(__name__)

# Create engine
engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def check_images() -> None:
    """Check images count in database and directories."""
    configure_logging(settings.log_level)
    
    # Force output
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    
    # Check files in directories
    base_dir = Path(__file__).parent.parent
    morning_dir = base_dir / "image" / "morning"
    evening_dir = base_dir / "image" / "evening"
    
    morning_files = list(morning_dir.glob("*.jpg")) if morning_dir.exists() else []
    evening_files = list(evening_dir.glob("*.jpg")) if evening_dir.exists() else []
    
    print(f"\n📁 Файлы в папках:")
    print(f"   Утренних: {len(morning_files)}")
    print(f"   Вечерних: {len(evening_files)}")
    print(f"   Всего: {len(morning_files) + len(evening_files)}")
    
    # Check database
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
        
        print(f"\n❌ Не загружено:")
        print(f"   Утренних: {missing_morning}")
        print(f"   Вечерних: {missing_evening}")
        print(f"   Всего: {missing_total}")
        
        if missing_total > 0:
            print(f"\n💡 Запустите скрипт загрузки снова:")
            print(f"   python scripts/load_images.py <your_chat_id>")
            print(f"   Скрипт пропустит уже загруженные картинки и загрузит только недостающие.")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_images())

