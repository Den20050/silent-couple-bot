"""Script to understand why so many files were skipped."""

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

logger = get_logger(__name__)

# Create engine
engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def check_logic() -> None:
    """Check why so many files were skipped."""
    configure_logging(settings.log_level)
    
    base_dir = Path(__file__).parent.parent
    evening_dir = base_dir / "image" / "evening"
    
    # Count files in directory
    evening_files = sorted(evening_dir.glob("*.jpg")) if evening_dir.exists() else []
    
    print(f"\n📁 Файлы в папке evening:")
    print(f"   Всего файлов: {len(evening_files)}")
    
    async with async_session_maker() as session:
        # Get file_ids from database
        evening_file_ids_result = await session.execute(
            select(PicsPool.file_id).where(PicsPool.type == PicType.EVENING.value)
        )
        evening_file_ids = set(evening_file_ids_result.scalars().all())
        
        print(f"\n💾 В БД:")
        print(f"   Уникальных file_id: {len(evening_file_ids)}")
        
        # Read skipped file
        skipped_file = base_dir / "image" / "skipped_evening_evening.txt"
        if skipped_file.exists():
            print(f"\n📄 Файл со списком пропущенных:")
            print(f"   Путь: {skipped_file}")
            
            # Parse skipped files
            skipped_files = []
            current_file = None
            current_file_id = None
            
            with open(skipped_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("File:"):
                        if current_file:
                            skipped_files.append((current_file, current_file_id))
                        current_file = line.replace("File:", "").strip()
                        current_file_id = None
                    elif line.startswith("Telegram file_id:"):
                        current_file_id = line.replace("Telegram file_id:", "").strip()
            
            if current_file:
                skipped_files.append((current_file, current_file_id))
            
            print(f"   Пропущено файлов: {len(skipped_files)}")
            
            # Check unique file_ids in skipped files
            skipped_file_ids = [fid for _, fid in skipped_files if fid]
            unique_skipped_file_ids = set(skipped_file_ids)
            
            print(f"\n🔍 Анализ пропущенных файлов:")
            print(f"   Всего пропущено: {len(skipped_files)}")
            print(f"   С file_id: {len(skipped_file_ids)}")
            print(f"   Уникальных file_id: {len(unique_skipped_file_ids)}")
            
            # Check if file_ids exist in DB
            existing_in_db = sum(1 for _, fid in skipped_files if fid and fid in evening_file_ids)
            not_in_db = len(skipped_file_ids) - existing_in_db
            
            print(f"\n📊 Проверка file_id:")
            print(f"   file_id есть в БД: {existing_in_db}")
            print(f"   file_id НЕТ в БД: {not_in_db}")
            
            # Check for duplicate file_ids (same file_id for multiple files)
            file_id_to_files = {}
            for file_path, file_id in skipped_files:
                if file_id:
                    if file_id not in file_id_to_files:
                        file_id_to_files[file_id] = []
                    file_id_to_files[file_id].append(file_path)
            
            duplicate_file_ids = {fid: files for fid, files in file_id_to_files.items() if len(files) > 1}
            if duplicate_file_ids:
                print(f"\n⚠️  ВАЖНО: Обнаружено {len(duplicate_file_ids)} file_id, которые Telegram присвоил РАЗНЫМ файлам!")
                print(f"   Это объясняет, почему так много файлов пропущено.")
                
                total_duplicate_files = sum(len(files) - 1 for files in duplicate_file_ids.values())
                print(f"\n   Статистика дубликатов:")
                print(f"   - Уникальных file_id с дубликатами: {len(duplicate_file_ids)}")
                print(f"   - Всего файлов с дублирующимися file_id: {sum(len(files) for files in duplicate_file_ids.values())}")
                print(f"   - Избыточных файлов (которые можно удалить): {total_duplicate_files}")
                
                # Show examples
                print(f"\n   Примеры (первые 5):")
                for idx, (file_id, files) in enumerate(list(duplicate_file_ids.items())[:5], 1):
                    print(f"   {idx}. file_id: {file_id[:60]}...")
                    print(f"      Файлов с этим file_id: {len(files)}")
                    for f in files[:3]:
                        print(f"        - {Path(f).name}")
                    if len(files) > 3:
                        print(f"        ... и еще {len(files) - 3} файлов")
            else:
                print(f"\n✅ Все file_id уникальны - нет дубликатов от Telegram.")
            
            # Summary
            print(f"\n📈 Итоговая статистика:")
            print(f"   Файлов в папке: {len(evening_files)}")
            print(f"   file_id в БД: {len(evening_file_ids)}")
            print(f"   Пропущено файлов: {len(skipped_files)}")
            print(f"   Загружено в этой сессии: 0")
            
            if len(evening_files) == len(evening_file_ids) + len(skipped_files):
                print(f"\n✅ Математика сходится:")
                print(f"   {len(evening_files)} (в папке) = {len(evening_file_ids)} (в БД) + {len(skipped_files)} (пропущено)")
            else:
                print(f"\n⚠️  Математика НЕ сходится:")
                print(f"   {len(evening_files)} (в папке) ≠ {len(evening_file_ids)} (в БД) + {len(skipped_files)} (пропущено)")
                print(f"   Разница: {len(evening_files) - len(evening_file_ids) - len(skipped_files)}")
        else:
            print(f"\n❌ Файл со списком пропущенных не найден: {skipped_file}")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_logic())
