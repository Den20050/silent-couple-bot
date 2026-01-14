"""Script to analyze skipped images without reloading them.

This script shows statistics about skipped files and helps determine
if they're real duplicates or need to be reloaded.
"""

import asyncio
import sys
from pathlib import Path
from collections import Counter

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


async def parse_skipped_file(skipped_file_path: Path) -> list[tuple[str, str, str | None]]:
    """Parse skipped files list from text file.
    
    Returns:
        List of tuples: (file_path, reason, file_id)
    """
    skipped_files = []
    
    if not skipped_file_path.exists():
        return skipped_files
    
    current_file = None
    current_reason = None
    current_file_id = None
    
    with open(skipped_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            
            if line.startswith("File:"):
                # Save previous file if exists
                if current_file:
                    skipped_files.append((current_file, current_reason or "Unknown", current_file_id))
                
                # Start new file
                current_file = line.replace("File:", "").strip()
                current_reason = None
                current_file_id = None
                
            elif line.startswith("Reason:"):
                current_reason = line.replace("Reason:", "").strip()
                
            elif line.startswith("Telegram file_id:"):
                current_file_id = line.replace("Telegram file_id:", "").strip()
    
    # Save last file
    if current_file:
        skipped_files.append((current_file, current_reason or "Unknown", current_file_id))
    
    return skipped_files


async def analyze_skipped() -> None:
    """Analyze skipped files."""
    configure_logging(settings.log_level)
    
    # Find skipped files
    base_dir = Path(__file__).parent.parent
    image_dir = base_dir / "image"
    
    morning_skipped = image_dir / "skipped_morning_morning.txt"
    evening_skipped = image_dir / "skipped_evening_evening.txt"
    
    skipped_files_morning = []
    skipped_files_evening = []
    
    if morning_skipped.exists():
        print(f"📄 Найден файл с пропущенными утренними картинками: {morning_skipped}")
        skipped_files_morning = await parse_skipped_file(morning_skipped)
        print(f"   Найдено пропущенных файлов: {len(skipped_files_morning)}")
    
    if evening_skipped.exists():
        print(f"📄 Найден файл с пропущенными вечерними картинками: {evening_skipped}")
        skipped_files_evening = await parse_skipped_file(evening_skipped)
        print(f"   Найдено пропущенных файлов: {len(skipped_files_evening)}")
    
    if not skipped_files_morning and not skipped_files_evening:
        print("\n❌ Не найдено файлов со списком пропущенных картинок.")
        print("   Файлы должны называться:")
        print("   - image/skipped_morning_morning.txt")
        print("   - image/skipped_evening_evening.txt")
        print("\n   Эти файлы создаются автоматически при запуске load_images.py")
        await engine.dispose()
        return
    
    async with async_session_maker() as session:
        pics_repo = PicsPoolRepository(session)
        
        # Get all file_ids from database
        morning_file_ids_result = await session.execute(
            select(PicsPool.file_id).where(PicsPool.type == PicType.MORNING.value)
        )
        morning_file_ids = set(morning_file_ids_result.scalars().all())
        
        evening_file_ids_result = await session.execute(
            select(PicsPool.file_id).where(PicsPool.type == PicType.EVENING.value)
        )
        evening_file_ids = set(evening_file_ids_result.scalars().all())
        
        # Analyze morning files
        if skipped_files_morning:
            print(f"\n🌅 Анализ утренних картинок:")
            print(f"   Всего пропущено: {len(skipped_files_morning)}")
            
            reasons = Counter([reason for _, reason, _ in skipped_files_morning])
            print(f"\n   Причины пропуска:")
            for reason, count in reasons.items():
                print(f"     - {reason}: {count}")
            
            # Check how many have file_ids that exist in DB
            with_file_id = [f for f in skipped_files_morning if f[2]]
            existing_file_ids = 0
            missing_file_ids = 0
            
            for file_path, reason, file_id in skipped_files_morning:
                if file_id:
                    if file_id in morning_file_ids:
                        existing_file_ids += 1
                    else:
                        missing_file_ids += 1
                else:
                    missing_file_ids += 1
            
            print(f"\n   Статистика:")
            print(f"     - С file_id в БД (реальные дубликаты): {existing_file_ids}")
            print(f"     - Без file_id или file_id не в БД (нужно загрузить): {missing_file_ids}")
            
            # Check if files exist
            existing_files = sum(1 for f, _, _ in skipped_files_morning if Path(f).exists())
            missing_files = len(skipped_files_morning) - existing_files
            
            print(f"     - Файлы существуют на диске: {existing_files}")
            print(f"     - Файлы отсутствуют на диске: {missing_files}")
        
        # Analyze evening files
        if skipped_files_evening:
            print(f"\n🌙 Анализ вечерних картинок:")
            print(f"   Всего пропущено: {len(skipped_files_evening)}")
            
            reasons = Counter([reason for _, reason, _ in skipped_files_evening])
            print(f"\n   Причины пропуска:")
            for reason, count in reasons.items():
                print(f"     - {reason}: {count}")
            
            # Check how many have file_ids that exist in DB
            existing_file_ids = 0
            missing_file_ids = 0
            
            for file_path, reason, file_id in skipped_files_evening:
                if file_id:
                    if file_id in evening_file_ids:
                        existing_file_ids += 1
                    else:
                        missing_file_ids += 1
                else:
                    missing_file_ids += 1
            
            print(f"\n   Статистика:")
            print(f"     - С file_id в БД (реальные дубликаты): {existing_file_ids}")
            print(f"     - Без file_id или file_id не в БД (нужно загрузить): {missing_file_ids}")
            
            # Check if files exist
            existing_files = sum(1 for f, _, _ in skipped_files_evening if Path(f).exists())
            missing_files = len(skipped_files_evening) - existing_files
            
            print(f"     - Файлы существуют на диске: {existing_files}")
            print(f"     - Файлы отсутствуют на диске: {missing_files}")
        
        # Summary
        total_skipped = len(skipped_files_morning) + len(skipped_files_evening)
        total_in_db_morning = len(morning_file_ids)
        total_in_db_evening = len(evening_file_ids)
        
        print(f"\n📊 Итоговая статистика:")
        print(f"   Всего пропущено картинок: {total_skipped}")
        print(f"   Утренних в БД: {total_in_db_morning}")
        print(f"   Вечерних в БД: {total_in_db_evening}")
        print(f"   Всего в БД: {total_in_db_morning + total_in_db_evening}")
        
        if total_skipped > 0:
            print(f"\n💡 Для проверки и дозагрузки пропущенных картинок запустите:")
            print(f"   python scripts/reload_skipped_images.py <your_chat_id>")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(analyze_skipped())
