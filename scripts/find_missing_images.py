"""Script to find images that are not loaded in database.

This script compares files in directories with file_ids in database
and finds images that need to be loaded.
"""

import asyncio
import hashlib
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.core.config import settings
from src.core.constants import PicType
from src.core.logger import configure_logging, get_logger
from src.db.models import PicsPool
from src.db.repositories.pics_pool import PicsPoolRepository

logger = get_logger(__name__)

# Create engine
engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


async def find_missing_images() -> None:
    """Find images that are not loaded in database."""
    configure_logging(settings.log_level)
    
    base_dir = Path(__file__).parent.parent
    morning_dir = base_dir / "image" / "morning"
    evening_dir = base_dir / "image" / "evening"
    
    # Get files from directories
    morning_files = sorted(morning_dir.glob("*.jpg")) if morning_dir.exists() else []
    evening_files = sorted(evening_dir.glob("*.jpg")) if evening_dir.exists() else []
    
    print(f"\n📁 Файлы в папках:")
    print(f"   Утренних: {len(morning_files)}")
    print(f"   Вечерних: {len(evening_files)}")
    print(f"   Всего: {len(morning_files) + len(evening_files)}")
    
    async with async_session_maker() as session:
        pics_repo = PicsPoolRepository(session)
        
        # Get file_ids from database
        morning_file_ids_result = await session.execute(
            select(PicsPool.file_id).where(PicsPool.type == PicType.MORNING.value)
        )
        morning_file_ids = set(morning_file_ids_result.scalars().all())
        
        evening_file_ids_result = await session.execute(
            select(PicsPool.file_id).where(PicsPool.type == PicType.EVENING.value)
        )
        evening_file_ids = set(evening_file_ids_result.scalars().all())
        
        print(f"\n💾 Загружено в БД:")
        print(f"   Утренних: {len(morning_file_ids)}")
        print(f"   Вечерних: {len(evening_file_ids)}")
        print(f"   Всего: {len(morning_file_ids) + len(evening_file_ids)}")
        
        # Calculate missing
        missing_morning = len(morning_files) - len(morning_file_ids)
        missing_evening = len(evening_files) - len(evening_file_ids)
        missing_total = missing_morning + missing_evening
        
        print(f"\n❌ Не загружено:")
        print(f"   Утренних: {missing_morning}")
        print(f"   Вечерних: {missing_evening}")
        print(f"   Всего: {missing_total}")
        
        if missing_total == 0:
            print(f"\n✅ Все картинки загружены!")
            await engine.dispose()
            return
        
        # Find which files are missing
        print(f"\n🔍 Поиск пропущенных файлов...")
        
        # For morning files, we can't directly match files to file_ids
        # because file_ids are bot-specific. We need to check if files exist
        # and compare counts
        
        if missing_morning > 0:
            print(f"\n🌅 Утренние картинки:")
            print(f"   В папке: {len(morning_files)}")
            print(f"   В БД: {len(morning_file_ids)}")
            print(f"   Разница: {missing_morning}")
            print(f"\n   💡 Для загрузки пропущенных картинок запустите:")
            print(f"      python scripts/load_images.py <your_chat_id>")
            print(f"      Скрипт автоматически пропустит уже загруженные и загрузит только недостающие.")
        
        if missing_evening > 0:
            print(f"\n🌙 Вечерние картинки:")
            print(f"   В папке: {len(evening_files)}")
            print(f"   В БД: {len(evening_file_ids)}")
            print(f"   Разница: {missing_evening}")
            print(f"\n   💡 Для загрузки пропущенных картинок запустите:")
            print(f"      python scripts/load_images.py <your_chat_id>")
            print(f"      Скрипт автоматически пропустит уже загруженные и загрузит только недостающие.")
        
        # Save list of potentially missing files
        # Note: We can't be 100% sure which files are missing without comparing hashes
        # But we can save the count difference
        
        if missing_morning > 0 or missing_evening > 0:
            print(f"\n📝 Создаю файл со списком для дозагрузки...")
            
            missing_file_path = base_dir / "image" / "missing_images.txt"
            try:
                with open(missing_file_path, "w", encoding="utf-8") as f:
                    f.write("Список пропущенных картинок для дозагрузки\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(f"Утренних не загружено: {missing_morning}\n")
                    f.write(f"Вечерних не загружено: {missing_evening}\n")
                    f.write(f"Всего не загружено: {missing_total}\n\n")
                    f.write("=" * 80 + "\n\n")
                    f.write("Для дозагрузки запустите:\n")
                    f.write("python scripts/load_images.py <your_chat_id>\n")
                    f.write("\nСкрипт автоматически пропустит уже загруженные картинки\n")
                    f.write("и загрузит только недостающие.\n")
                
                print(f"   ✅ Файл создан: {missing_file_path}")
            except Exception as e:
                logger.warning(f"Failed to create missing files list: {e}")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(find_missing_images())
