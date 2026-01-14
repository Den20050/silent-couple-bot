"""Script to verify if skipped files are real duplicates or need to be reloaded."""

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
    """Parse skipped files list from text file."""
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
                if current_file:
                    skipped_files.append((current_file, current_reason or "Unknown", current_file_id))
                current_file = line.replace("File:", "").strip()
                current_reason = None
                current_file_id = None
            elif line.startswith("Reason:"):
                current_reason = line.replace("Reason:", "").strip()
            elif line.startswith("Telegram file_id:"):
                current_file_id = line.replace("Telegram file_id:", "").strip()
    
    if current_file:
        skipped_files.append((current_file, current_reason or "Unknown", current_file_id))
    
    return skipped_files


async def verify_skipped() -> None:
    """Verify if skipped files are real duplicates."""
    configure_logging(settings.log_level)
    
    base_dir = Path(__file__).parent.parent
    image_dir = base_dir / "image"
    
    evening_skipped = image_dir / "skipped_evening_evening.txt"
    
    if not evening_skipped.exists():
        print("❌ Файл со списком пропущенных картинок не найден.")
        print(f"   Ожидаемый путь: {evening_skipped}")
        await engine.dispose()
        return
    
    print(f"📄 Читаю файл: {evening_skipped}")
    skipped_files = await parse_skipped_file(evening_skipped)
    print(f"   Найдено пропущенных файлов: {len(skipped_files)}")
    
    async with async_session_maker() as session:
        pics_repo = PicsPoolRepository(session)
        
        # Get all file_ids from database
        evening_file_ids_result = await session.execute(
            select(PicsPool.file_id).where(PicsPool.type == PicType.EVENING.value)
        )
        evening_file_ids = set(evening_file_ids_result.scalars().all())
        
        print(f"\n💾 В БД найдено вечерних file_id: {len(evening_file_ids)}")
        
        # Check how many skipped file_ids exist in DB
        skipped_file_ids = [f[2] for f in skipped_files if f[2]]
        unique_skipped_file_ids = set(skipped_file_ids)
        
        print(f"\n🔍 Анализ пропущенных файлов:")
        print(f"   Всего пропущено: {len(skipped_files)}")
        print(f"   С file_id: {len(skipped_file_ids)}")
        print(f"   Уникальных file_id: {len(unique_skipped_file_ids)}")
        
        # Check which file_ids exist in DB
        existing_in_db = 0
        not_in_db = 0
        
        for file_path, reason, file_id in skipped_files:
            if file_id:
                if file_id in evening_file_ids:
                    existing_in_db += 1
                else:
                    not_in_db += 1
        
        print(f"\n📊 Результат проверки:")
        print(f"   file_id есть в БД (реальные дубликаты): {existing_in_db}")
        print(f"   file_id НЕТ в БД (нужно загрузить): {not_in_db}")
        
        # Check reasons
        reasons = Counter([reason for _, reason, _ in skipped_files])
        print(f"\n   Причины пропуска:")
        for reason, count in reasons.items():
            print(f"     - {reason}: {count}")
        
        # Check if files exist
        existing_files = sum(1 for f, _, _ in skipped_files if Path(f).exists())
        missing_files = len(skipped_files) - existing_files
        
        print(f"\n   Файлы на диске:")
        print(f"     - Существуют: {existing_files}")
        print(f"     - Отсутствуют: {missing_files}")
        
        if not_in_db > 0:
            print(f"\n⚠️  ВНИМАНИЕ: {not_in_db} файлов были пропущены, но их file_id НЕТ в БД!")
            print(f"   Это означает, что они НЕ являются дубликатами и их нужно загрузить.")
            print(f"\n💡 Для дозагрузки запустите:")
            print(f"   python scripts/reload_skipped_images.py <your_chat_id>")
        else:
            print(f"\n✅ Все пропущенные файлы являются реальными дубликатами.")
            print(f"   Их file_id уже есть в БД, загружать заново не нужно.")
        
        # Check for duplicate file_ids (same file_id for different files)
        file_id_to_files = {}
        for file_path, reason, file_id in skipped_files:
            if file_id:
                if file_id not in file_id_to_files:
                    file_id_to_files[file_id] = []
                file_id_to_files[file_id].append(file_path)
        
        duplicate_file_ids = {fid: files for fid, files in file_id_to_files.items() if len(files) > 1}
        if duplicate_file_ids:
            print(f"\n⚠️  Обнаружено {len(duplicate_file_ids)} file_id, которые Telegram присвоил разным файлам!")
            print(f"   Это может быть проблемой Telegram API.")
            for file_id, files in list(duplicate_file_ids.items())[:5]:
                print(f"   file_id: {file_id[:50]}...")
                print(f"   Файлов с этим file_id: {len(files)}")
                for f in files[:3]:
                    print(f"     - {Path(f).name}")
                if len(files) > 3:
                    print(f"     ... и еще {len(files) - 3}")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify_skipped())
