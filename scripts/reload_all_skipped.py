"""Script to reload ALL skipped images without duplicate checking.

This script loads all skipped files even if their file_id already exists in DB.
This increases the number of images in the pool, as Telegram may return
different file_ids for the same image when uploaded again.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.core.config import settings
from src.core.constants import PicType
from src.core.logger import configure_logging, get_logger
from src.db.repositories.pics_pool import PicsPoolRepository

logger = get_logger(__name__)

# Create engine
engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def parse_skipped_file(skipped_file_path: Path) -> list[str]:
    """Parse skipped files list from text file.
    
    Returns:
        List of file paths
    """
    skipped_files = []
    current_file = None
    
    with open(skipped_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("File:"):
                if current_file:
                    skipped_files.append(current_file)
                current_file = line.replace("File:", "").strip()
    
    if current_file:
        skipped_files.append(current_file)
    
    return skipped_files


async def reload_all_skipped(
    bot: Bot,
    skipped_files: list[str],
    pic_type: PicType,
    session: AsyncSession,
    admin_chat_id: int,
) -> tuple[int, int, int]:
    """Reload all skipped files without duplicate checking.
    
    Returns:
        (new_loaded_count, duplicate_count, failed_count) - number of new files loaded, duplicates, and failed
    """
    pics_repo = PicsPoolRepository(session)
    new_loaded_count = 0  # Only count files that were actually added to DB
    duplicate_count = 0  # Count files that had duplicate file_ids
    failed_count = 0
    
    print(f"\n🔄 Загружаем {len(skipped_files)} пропущенных файлов (без проверки дубликатов)...")
    estimated_minutes = len(skipped_files) * 5 / 60
    print(f"   Это займет примерно {estimated_minutes:.1f} минут при задержке 5 секунд")
    print(f"   Прогресс будет показываться каждые 10 файлов")
    print(f"   Первые 5 файлов будут показаны подробно\n")
    sys.stdout.flush()  # Force flush to show output immediately
    
    base_delay = 5.0
    current_delay = base_delay
    rate_limit_count = 0
    
    for idx, file_path_str in enumerate(skipped_files, 1):
        file_path = Path(file_path_str)
        
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            print(f"  ⚠️  [{idx}/{len(skipped_files)}] Файл не найден: {file_path.name}")
            failed_count += 1
            continue
        
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
                
                # Save to database (even if file_id already exists, we'll catch IntegrityError)
                try:
                    await pics_repo.add(file_id=file_id, pic_type=pic_type)
                    await session.commit()
                    new_loaded_count += 1
                    loaded = True
                    logger.info(f"Reloaded file", file=str(file_path), file_id=file_id)
                    
                    # Show progress every 10 files or every 50 files processed
                    if new_loaded_count % 10 == 0 or idx % 50 == 0:
                        percentage = (idx / len(skipped_files)) * 100
                        print(f"  ✅ [{idx}/{len(skipped_files)}] Загружено НОВЫХ: {new_loaded_count}, дубликатов: {duplicate_count} ({percentage:.1f}%)")
                        sys.stdout.flush()
                except IntegrityError:
                    # File_id already exists - Telegram returned same file_id for duplicate image
                    # This means the image is already in DB, so we don't count it as "loaded"
                    await session.rollback()
                    duplicate_count += 1
                    loaded = True  # Mark as processed, but don't increment new_loaded_count
                    logger.debug(f"File_id already exists (duplicate image), skipping", file=str(file_path), file_id=file_id)
                
                # Delay between uploads (only if successful)
                if loaded:
                    # Show progress for first few files
                    if idx <= 5:
                        print(f"  ✅ [{idx}/{len(skipped_files)}] Загружено: {file_path.name}")
                        sys.stdout.flush()
                    await asyncio.sleep(current_delay)
                
            except TelegramRetryAfter as e:
                wait_time = e.retry_after
                rate_limit_count += 1
                
                # Increase delay if we're hitting rate limits frequently
                if rate_limit_count > 2:
                    current_delay = min(base_delay * (1 + rate_limit_count * 0.3), 15.0)
                    logger.info(f"Increasing delay to {current_delay:.1f}s due to frequent rate limits")
                    print(f"  ⚠️  Увеличена задержка до {current_delay:.1f} секунд")
                
                logger.warning(f"Rate limit, waiting {wait_time}s", file=str(file_path))
                print(f"  ⏳ Rate limit: ждем {wait_time} секунд...")
                sys.stdout.flush()
                await asyncio.sleep(wait_time)
                
                # Add extra delay after rate limit
                if wait_time > 60:
                    extra_delay = min(wait_time // 10, 30)
                    await asyncio.sleep(extra_delay)
                
                retry_count += 1
                
            except TelegramAPIError as e:
                error_str = str(e)
                logger.error(f"Failed to reload file: {error_str}", file=str(file_path))
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(2.0)
                else:
                    failed_count += 1
                    loaded = True
                    
            except Exception as e:
                logger.error(f"Unexpected error: {e}", file=str(file_path))
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(2.0)
                else:
                    failed_count += 1
                    loaded = True
        
        # Show progress every 50 files
        if idx % 50 == 0 and new_loaded_count % 10 != 0:
            percentage = (idx / len(skipped_files)) * 100
            print(f"  📊 Обработано: {idx}/{len(skipped_files)} ({percentage:.1f}%), новых: {new_loaded_count}, дубликатов: {duplicate_count}, ошибок: {failed_count}")
            sys.stdout.flush()
        
        # Show progress at start and every file for first 5 files
        if idx <= 5:
            print(f"  📤 [{idx}/{len(skipped_files)}] Загружаем: {file_path.name}...")
            sys.stdout.flush()
    
    return new_loaded_count, duplicate_count, failed_count


async def main() -> None:
    """Main function."""
    configure_logging(settings.log_level)
    
    # Get admin chat ID from command line
    admin_chat_id = None
    if len(sys.argv) > 1:
        try:
            admin_chat_id = int(sys.argv[1])
        except ValueError:
            logger.error("Invalid chat_id provided. Usage: python reload_all_skipped.py <your_telegram_chat_id>")
            sys.exit(1)
    else:
        logger.error("No chat_id provided. Usage: python reload_all_skipped.py <your_telegram_chat_id>")
        sys.exit(1)
    
    # Initialize bot
    bot = Bot(token=settings.tg_bot_token)
    logger.info("Using main bot token for reloading all skipped images")
    
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
        await bot.session.close()
        await engine.dispose()
        sys.exit(1)
    
    total_new_loaded = 0
    total_duplicates = 0
    total_failed = 0
    
    print(f"\n⚠️  ВНИМАНИЕ: Этот скрипт загрузит ВСЕ пропущенные файлы без проверки дубликатов.")
    print(f"   Telegram может вернуть одинаковые file_id для одинаковых картинок.")
    print(f"   Если file_id уже есть в БД - файл не будет добавлен (дубликат).")
    print(f"   Только файлы с НОВЫМИ file_id будут добавлены в БД.")
    print(f"\n❓ Продолжить? (yes/no): ", end="")
    confirmation = input().strip().lower()
    
    if confirmation not in ("yes", "y", "да", "д"):
        print("❌ Загрузка отменена.")
        await bot.session.close()
        await engine.dispose()
        sys.exit(0)
    
    async with async_session_maker() as session:
        # Process morning images
        if skipped_files_morning:
            print(f"\n🌅 Обрабатываем утренние картинки...")
            new_loaded, duplicates, failed = await reload_all_skipped(
                bot=bot,
                skipped_files=skipped_files_morning,
                pic_type=PicType.MORNING,
                session=session,
                admin_chat_id=admin_chat_id,
            )
            total_new_loaded += new_loaded
            total_duplicates += duplicates
            total_failed += failed
            print(f"   ✅ Загружено НОВЫХ: {new_loaded}, дубликатов: {duplicates}, ошибок: {failed}")
        
        # Process evening images
        if skipped_files_evening:
            print(f"\n🌙 Обрабатываем вечерние картинки...")
            new_loaded, duplicates, failed = await reload_all_skipped(
                bot=bot,
                skipped_files=skipped_files_evening,
                pic_type=PicType.EVENING,
                session=session,
                admin_chat_id=admin_chat_id,
            )
            total_new_loaded += new_loaded
            total_duplicates += duplicates
            total_failed += failed
            print(f"   ✅ Загружено НОВЫХ: {new_loaded}, дубликатов: {duplicates}, ошибок: {failed}")
        
        # Final statistics
        pics_repo = PicsPoolRepository(session)
        final_morning_count = await pics_repo.count(PicType.MORNING)
        final_evening_count = await pics_repo.count(PicType.EVENING)
        final_total = final_morning_count + final_evening_count
        
        print(f"\n✅ Обработка завершена!")
        print(f"   Загружено НОВЫХ файлов: {total_new_loaded}")
        print(f"   Дубликатов (file_id уже были в БД): {total_duplicates}")
        print(f"   Ошибок: {total_failed}")
        print(f"\n   Всего в БД:")
        print(f"     Утренних: {final_morning_count}")
        print(f"     Вечерних: {final_evening_count}")
        print(f"     Всего: {final_total}")
        
        # Calculate how many new unique file_ids were added
        if skipped_files_morning or skipped_files_evening:
            print(f"\n💡 Примечание:")
            print(f"   Telegram возвращает одинаковые file_id для одинаковых картинок.")
            print(f"   Поэтому многие файлы были пропущены как дубликаты (file_id уже есть в БД).")
            print(f"   Это нормально - количество уникальных картинок ограничено количеством файлов в папке.")
    
    await bot.session.close()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
