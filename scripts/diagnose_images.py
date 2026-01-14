"""Script to diagnose which images are not loaded and why."""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from src.core.config import settings
from src.core.constants import PicType
from src.core.logger import configure_logging, get_logger
from src.db.models import PicsPool

logger = get_logger(__name__)

# Create engine
engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def diagnose() -> None:
    """Diagnose which images are missing."""
    configure_logging(settings.log_level)
    
    # Get files from directories
    base_dir = Path(__file__).parent.parent
    morning_dir = base_dir / "image" / "morning"
    evening_dir = base_dir / "image" / "evening"
    
    morning_files = sorted(morning_dir.glob("*.jpg")) if morning_dir.exists() else []
    evening_files = sorted(evening_dir.glob("*.jpg")) if evening_dir.exists() else []
    
    print(f"\n📁 Файлы в папках:")
    print(f"   Утренних: {len(morning_files)}")
    print(f"   Вечерних: {len(evening_files)}")
    
    async with async_session_maker() as session:
        # Get all loaded file_ids
        result = await session.execute(select(PicsPool))
        loaded_pics = result.scalars().all()
        
        loaded_morning_file_ids = {p.file_id for p in loaded_pics if p.type == PicType.MORNING.value}
        loaded_evening_file_ids = {p.file_id for p in loaded_pics if p.type == PicType.EVENING.value}
        
        print(f"\n💾 Загружено в БД:")
        print(f"   Утренних: {len(loaded_morning_file_ids)}")
        print(f"   Вечерних: {len(loaded_evening_file_ids)}")
        
        # Check evening files
        print(f"\n🔍 Анализ вечерних картинок:")
        missing_evening = []
        
        # Show first 20 missing files
        for idx, file_path in enumerate(evening_files, 1):
            file_name = file_path.name
            
            # Check if this file might be problematic
            # We can't check file_id without uploading, but we can check if it's in a problematic range
            if idx > len(loaded_evening_file_ids):
                missing_evening.append((idx, file_name))
        
        print(f"   Всего вечерних файлов: {len(evening_files)}")
        print(f"   Загружено: {len(loaded_evening_file_ids)}")
        print(f"   Не загружено: {len(evening_files) - len(loaded_evening_file_ids)}")
        
        if missing_evening:
            print(f"\n   Первые 20 не загруженных файлов:")
            for idx, file_name in missing_evening[:20]:
                print(f"     {idx}. {file_name}")
        
        # Check if there are duplicate file_ids
        all_file_ids = [p.file_id for p in loaded_pics]
        duplicates = len(all_file_ids) - len(set(all_file_ids))
        if duplicates > 0:
            print(f"\n⚠️  Найдено дубликатов file_id: {duplicates}")
        
        # Check evening files range
        print(f"\n📊 Диапазон загруженных вечерних картинок:")
        if loaded_evening_file_ids:
            # Try to understand the pattern
            print(f"   Загружено: {len(loaded_evening_file_ids)} из {len(evening_files)}")
            print(f"   Процент: {len(loaded_evening_file_ids) / len(evening_files) * 100:.1f}%")
            
            # Check if it's sequential or random
            if len(loaded_evening_file_ids) == 357:
                print(f"\n   💡 Похоже, загружены первые 357 файлов")
                print(f"   Осталось загрузить файлы с индексами {358} до {len(evening_files)}")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(diagnose())

