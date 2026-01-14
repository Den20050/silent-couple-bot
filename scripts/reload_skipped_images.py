"""Script to reload skipped images that were marked as duplicates.

This script checks skipped files and reloads them if they're not actually duplicates.
"""

import asyncio
import hashlib
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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


async def check_and_reload_skipped(
    bot: Bot,
    skipped_files: list[tuple[str, str, str | None]],  # (file_path, reason, file_id)
    pic_type: PicType,
    session: AsyncSession,
    admin_chat_id: int,
) -> tuple[int, int]:
    """Check skipped files and reload if they're not duplicates.
    
    Returns:
        (reloaded_count, skipped_count) - number of files reloaded and skipped
    """
    pics_repo = PicsPoolRepository(session)
    reloaded_count = 0
    actually_skipped = 0
    
    # Get all existing file_ids for this pic_type
    result = await session.execute(
        select(PicsPool.file_id).where(PicsPool.type == pic_type.value)
    )
    existing_file_ids = set(result.scalars().all())
    
    print(f"\n🔍 Проверяем {len(skipped_files)} пропущенных файлов...")
    
    for idx, (file_path_str, reason, old_file_id) in enumerate(skipped_files, 1):
        file_path = Path(file_path_str)
        
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            print(f"  ⚠️  [{idx}/{len(skipped_files)}] Файл не найден: {file_path.name}")
            actually_skipped += 1
            continue
        
        # Check if file_id exists in database
        if old_file_id:
            existing = await pics_repo.get_by_file_id(old_file_id)
            if existing:
                # File_id exists - this is a real duplicate, skip it
                logger.debug(f"File_id {old_file_id} exists in DB, skipping", file=str(file_path))
                actually_skipped += 1
                if idx % 50 == 0:
                    print(f"  📊 Проверено: {idx}/{len(skipped_files)}, загружено: {reloaded_count}, пропущено: {actually_skipped}")
                continue
        
        # Try to reload the file
        max_retries = 3
        retry_count = 0
        loaded = False
        
        while retry_count < max_retries and not loaded:
            try:
                # Upload to Telegram
                photo = FSInputFile(str(file_path))
                message = await bot.send_photo(
                    chat_id=admin_chat_id,
                    photo=photo,
                )
                
                file_id = message.photo[-1].file_id
                
                # Check if this file_id already exists
                if file_id in existing_file_ids:
                    existing = await pics_repo.get_by_file_id(file_id)
                    if existing:
                        logger.debug(f"File_id {file_id} already exists, skipping", file=str(file_path))
                        actually_skipped += 1
                        loaded = True
                        break
                
                # Save to database
                try:
                    await pics_repo.add(file_id=file_id, pic_type=pic_type)
                    await session.commit()
                    existing_file_ids.add(file_id)
                    reloaded_count += 1
                    loaded = True
                    logger.info(f"Reloaded skipped file", file=str(file_path), file_id=file_id)
                    
                    if reloaded_count % 10 == 0:
                        print(f"  ✅ Загружено: {reloaded_count} файлов")
                except IntegrityError:
                    # File_id already exists - skip it
                    await session.rollback()
                    existing_file_ids.add(file_id)
                    actually_skipped += 1
                    loaded = True
                    logger.debug(f"File_id {file_id} already exists (IntegrityError), skipping", file=str(file_path))
                
                # Delay between uploads
                await asyncio.sleep(5.0)
                
            except TelegramRetryAfter as e:
                wait_time = e.retry_after
                logger.warning(f"Rate limit, waiting {wait_time}s", file=str(file_path))
                print(f"  ⏳ Rate limit: ждем {wait_time} секунд...")
                await asyncio.sleep(wait_time)
                retry_count += 1
                
            except TelegramAPIError as e:
                error_str = str(e)
                if "file not found" in error_str.lower() or "wrong file_id" in error_str.lower():
                    # This might mean the file_id is from a different bot
                    logger.warning(f"File_id error, might be from different bot: {error_str}", file=str(file_path))
                    retry_count += 1
                    if retry_count < max_retries:
                        await asyncio.sleep(2.0)
                    else:
                        actually_skipped += 1
                        loaded = True
                else:
                    logger.error(f"Failed to reload file: {error_str}", file=str(file_path))
                    retry_count += 1
                    if retry_count < max_retries:
                        await asyncio.sleep(2.0)
                    else:
                        actually_skipped += 1
                        loaded = True
                        
            except Exception as e:
                logger.error(f"Unexpected error: {e}", file=str(file_path))
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(2.0)
                else:
                    actually_skipped += 1
                    loaded = True
        
        if idx % 50 == 0:
            print(f"  📊 Проверено: {idx}/{len(skipped_files)}, загружено: {reloaded_count}, пропущено: {actually_skipped}")
    
    return reloaded_count, actually_skipped


async def parse_skipped_file(skipped_file_path: Path) -> list[tuple[str, str, str | None]]:
    """Parse skipped files list from text file.
    
    Returns:
        List of tuples: (file_path, reason, file_id)
    """
    skipped_files = []
    
    if not skipped_file_path.exists():
        logger.warning(f"Skipped file not found: {skipped_file_path}")
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


async def main() -> None:
    """Main function."""
    configure_logging(settings.log_level)
    
    # Get admin chat ID from command line
    admin_chat_id = None
    if len(sys.argv) > 1:
        try:
            admin_chat_id = int(sys.argv[1])
        except ValueError:
            logger.error("Invalid chat_id provided. Usage: python reload_skipped_images.py <your_telegram_chat_id>")
            sys.exit(1)
    else:
        logger.error("No chat_id provided. Usage: python reload_skipped_images.py <your_telegram_chat_id>")
        sys.exit(1)
    
    # Initialize bot
    bot = Bot(token=settings.tg_bot_token)
    logger.info("Using main bot token for reloading skipped images")
    
    # Find skipped files
    base_dir = Path(__file__).parent.parent
    image_dir = base_dir / "image"
    
    skipped_files_morning = []
    skipped_files_evening = []
    
    # Look for skipped files lists
    morning_skipped = image_dir / "skipped_morning_morning.txt"
    evening_skipped = image_dir / "skipped_evening_evening.txt"
    
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
        await bot.session.close()
        await engine.dispose()
        sys.exit(1)
    
    total_reloaded = 0
    total_skipped = 0
    
    async with async_session_maker() as session:
        # Process morning images
        if skipped_files_morning:
            print(f"\n🌅 Обрабатываем утренние картинки...")
            reloaded, skipped = await check_and_reload_skipped(
                bot=bot,
                skipped_files=skipped_files_morning,
                pic_type=PicType.MORNING,
                session=session,
                admin_chat_id=admin_chat_id,
            )
            total_reloaded += reloaded
            total_skipped += skipped
            print(f"   ✅ Загружено: {reloaded}, пропущено (дубликаты): {skipped}")
        
        # Process evening images
        if skipped_files_evening:
            print(f"\n🌙 Обрабатываем вечерние картинки...")
            reloaded, skipped = await check_and_reload_skipped(
                bot=bot,
                skipped_files=skipped_files_evening,
                pic_type=PicType.EVENING,
                session=session,
                admin_chat_id=admin_chat_id,
            )
            total_reloaded += reloaded
            total_skipped += skipped
            print(f"   ✅ Загружено: {reloaded}, пропущено (дубликаты): {skipped}")
        
        # Final statistics
        pics_repo = PicsPoolRepository(session)
        final_morning_count = await pics_repo.count(PicType.MORNING)
        final_evening_count = await pics_repo.count(PicType.EVENING)
        final_total = final_morning_count + final_evening_count
        
        print(f"\n✅ Обработка завершена!")
        print(f"   Загружено новых файлов: {total_reloaded}")
        print(f"   Пропущено (дубликаты): {total_skipped}")
        print(f"\n   Всего в БД:")
        print(f"     Утренних: {final_morning_count}")
        print(f"     Вечерних: {final_evening_count}")
        print(f"     Всего: {final_total}")
    
    await bot.session.close()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
