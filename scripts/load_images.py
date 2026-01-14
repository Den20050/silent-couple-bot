"""Script to load images to Telegram and save file_ids to database."""

import asyncio
import hashlib
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramRetryAfter
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


async def load_images_from_directory(
    bot: Bot,
    directory: Path,
    pic_type: PicType,
    session: AsyncSession,
    admin_chat_id: int,
) -> int:
    """Load images from directory to Telegram and save file_ids.
    
    Args:
        bot: Bot instance
        directory: Directory with images
        pic_type: Picture type (morning/evening)
        session: Database session
        admin_chat_id: Chat ID to send photos to (for getting file_id)
    
    Returns:
        Number of images loaded
    """
    pics_repo = PicsPoolRepository(session)
    count = 0
    
    # Get all JPG files
    image_files = sorted(directory.glob("*.jpg"))
    
    # Pre-load all existing file_ids for this pic_type to avoid unnecessary uploads
    logger.info(f"Loading existing file_ids from database for {pic_type.value}...")
    result = await session.execute(
        select(PicsPool.file_id).where(PicsPool.type == pic_type.value)
    )
    existing_file_ids = set(result.scalars().all())
    existing_count = len(existing_file_ids)
    logger.info(f"Found {existing_count} existing {pic_type.value} images in database")
    
    logger.info(f"Found {len(image_files)} images in {directory}", pic_type=pic_type.value)
    
    # If we already have all images loaded (or very close - within 5%), skip the entire directory
    # This prevents sending images to Telegram when they're already loaded
    # The 5% threshold accounts for potential duplicates or minor discrepancies
    total_files = len(image_files)
    if existing_count >= total_files:
        logger.info(
            f"All {pic_type.value} images already loaded ({existing_count} >= {total_files}), skipping directory",
            existing=existing_count,
            total=total_files,
            pic_type=pic_type.value,
        )
        print(f"  ✅ [{pic_type.value}] Все картинки уже загружены ({existing_count}/{total_files}), пропускаем")
        return 0
    
    # Calculate how many images we need to load
    remaining = total_files - existing_count
    logger.info(
        f"Need to load {remaining} {pic_type.value} images ({existing_count}/{total_files} already loaded)",
        existing=existing_count,
        total=total_files,
        remaining=remaining,
        pic_type=pic_type.value,
    )
    print(f"  📊 [{pic_type.value}] Загружено: {existing_count}/{total_files}, осталось: {remaining}")
    
    # Calculate file hashes for all files to detect duplicates by content
    # This helps avoid re-uploading the same file even if Telegram returns different file_ids
    logger.info(f"Calculating file hashes to detect duplicates...")
    file_hashes = {}
    uploaded_hashes = set()  # Track hashes of files we've uploaded in this session
    
    def calculate_file_hash(file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    # Pre-calculate all file hashes
    for image_file in image_files:
        try:
            file_hash = calculate_file_hash(image_file)
            file_hashes[image_file] = file_hash
        except Exception as e:
            logger.warning(f"Failed to calculate hash for {image_file}: {e}")
            file_hashes[image_file] = None
    
    logger.info(f"Calculated hashes for {len(file_hashes)} files")
    
    skipped_count = 0
    consecutive_skips = 0  # Track consecutive skips to detect if all images are already loaded
    max_consecutive_skips = 50  # If we skip 50 images in a row without loading any, something's wrong
    skip_file_id_check = False  # Flag to disable file_id checking if Telegram returns duplicates
    
    # Track skipped files with reasons for later analysis
    skipped_files = []  # List of tuples: (file_path, reason, file_id_if_available)
    
    # Adaptive delay - increases if we hit rate limits frequently
    # Increased base delay to 5 seconds to avoid Telegram rate limiting
    # This gives ~0.2 images per second, which is safer for bulk uploads
    base_delay = 5.0  # Base delay between uploads (5 seconds = ~0.2 images per second)
    current_delay = base_delay
    rate_limit_count = 0  # Track how many rate limits we've hit
    
    for idx, image_file in enumerate(image_files, 1):
        # Check file hash first - if we've already uploaded a file with this hash in this session, skip it
        file_hash = file_hashes.get(image_file)
        if file_hash and file_hash in uploaded_hashes:
            reason = f"Duplicate hash in this session (hash: {file_hash[:16]}...)"
            skipped_files.append((str(image_file), reason, None))
            logger.debug(f"File already uploaded in this session (hash match), skipping", file=str(image_file))
            skipped_count += 1
            consecutive_skips += 1
            continue
        # If we've skipped too many consecutive images, disable file_id checking
        # Telegram may return duplicate file_ids for different images, making the check unreliable
        # Also disable if we need to load many images but haven't loaded any yet
        if (consecutive_skips >= max_consecutive_skips or (remaining > 100 and count == 0 and idx > 50)) and not skip_file_id_check:
            skip_file_id_check = True
            logger.warning(
                f"Skipped {consecutive_skips} consecutive {pic_type.value} images without loading any. "
                f"Telegram may be returning duplicate file_ids. Disabling file_id check and loading all remaining images.",
                consecutive_skips=consecutive_skips,
                loaded=count,
                remaining=remaining,
                pic_type=pic_type.value,
            )
            print(f"\n  ⚠️  Пропущено {consecutive_skips} картинок подряд без загрузки новых.")
            print(f"  Telegram возвращает одинаковые file_id для разных картинок.")
            print(f"  Отключаем проверку file_id и загружаем все оставшиеся картинки.\n")
            consecutive_skips = 0  # Reset counter to continue loading
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Upload to Telegram (send to admin's Saved Messages to get file_id)
                photo = FSInputFile(str(image_file))
                # Send without caption for faster processing
                message = await bot.send_photo(
                    chat_id=admin_chat_id,
                    photo=photo,
                )
                
                file_id = message.photo[-1].file_id  # Get highest resolution
                
                # Check if already exists (only if file_id checking is enabled)
                # If we've skipped too many, Telegram may be returning duplicate file_ids, so we skip the check
                if not skip_file_id_check:
                    if file_id in existing_file_ids:
                        reason = f"Duplicate file_id in pre-loaded set (file_id: {file_id})"
                        skipped_files.append((str(image_file), reason, file_id))
                        logger.debug("Image already exists (from pre-loaded set), skipping", file_id=file_id, file=str(image_file))
                        skipped_count += 1
                        consecutive_skips += 1
                        break  # Skip this image, move to next
                    
                    # Double-check in database (in case of race condition)
                    existing = await pics_repo.get_by_file_id(file_id)
                    if existing:
                        reason = f"Duplicate file_id in database (file_id: {file_id})"
                        skipped_files.append((str(image_file), reason, file_id))
                        logger.debug("Image already exists (from database check), skipping", file_id=file_id, file=str(image_file))
                        existing_file_ids.add(file_id)  # Add to set for future checks
                        skipped_count += 1
                        consecutive_skips += 1
                        break  # Skip this image, move to next
                else:
                    # File_id checking disabled - just check if we've uploaded this file hash in this session
                    if file_hash and file_hash in uploaded_hashes:
                        reason = f"Duplicate hash in this session (hash: {file_hash[:16]}...)"
                        skipped_files.append((str(image_file), reason, file_id))
                        logger.debug("File already uploaded in this session (hash match), skipping", file=str(image_file))
                        skipped_count += 1
                        consecutive_skips += 1
                        break  # Skip this image, move to next
                
                # Save to database
                try:
                    await pics_repo.add(file_id=file_id, pic_type=pic_type)
                    await session.commit()
                    
                    # Add to in-memory set to avoid duplicate checks
                    existing_file_ids.add(file_id)
                    # Add file hash to uploaded set to avoid re-uploading same file
                    if file_hash:
                        uploaded_hashes.add(file_hash)
                    count += 1
                    consecutive_skips = 0  # Reset consecutive skips counter when we load a new image
                except IntegrityError:
                    # File_id already exists in database - this is fine, just skip it
                    await session.rollback()
                    reason = f"Duplicate file_id (IntegrityError in database, file_id: {file_id})"
                    skipped_files.append((str(image_file), reason, file_id))
                    logger.debug("File_id already exists in database, skipping", file_id=file_id, file=str(image_file))
                    existing_file_ids.add(file_id)  # Add to set for future checks
                    skipped_count += 1
                    consecutive_skips += 1
                    # Don't break - continue to next image
                    break
                if idx % 10 == 0 or count % 10 == 0:
                    logger.info(
                        f"Progress: {idx}/{len(image_files)} files processed, {count} loaded, {skipped_count} skipped ({pic_type.value})",
                        processed=idx,
                        loaded=count,
                        skipped=skipped_count,
                        total=len(image_files),
                        pic_type=pic_type.value,
                    )
                    # Show percentage
                    percentage = (idx / len(image_files)) * 100
                    print(f"  [{pic_type.value}] Обработано: {idx}/{len(image_files)} ({percentage:.1f}%), загружено: {count}, пропущено: {skipped_count}")
                
                # Add adaptive delay to avoid rate limiting
                # Start with 5 seconds, increase if we hit rate limits
                await asyncio.sleep(current_delay)
                # Reset delay slightly after successful upload (but keep it higher if we've hit limits)
                if rate_limit_count == 0:
                    current_delay = base_delay
                else:
                    # Keep delay higher if we've hit rate limits
                    current_delay = min(base_delay * (1 + rate_limit_count * 0.2), 10.0)
                break  # Success, move to next image
                
            except TelegramRetryAfter as e:
                # Handle rate limiting - wait for specified time
                wait_time = e.retry_after
                rate_limit_count += 1
                
                # Increase delay if we're hitting rate limits frequently
                if rate_limit_count > 2:
                    current_delay = min(base_delay * (1 + rate_limit_count * 0.3), 15.0)  # Max 15 seconds
                    logger.info(f"Increasing delay to {current_delay:.1f}s due to frequent rate limits")
                    print(f"  ⚠️  Увеличена задержка до {current_delay:.1f} секунд из-за частых ограничений")
                
                # If wait time is too long (more than 5 minutes), ask user
                if wait_time > 300:
                    logger.warning(
                        f"Very long rate limit: {wait_time} seconds ({wait_time/60:.1f} minutes)",
                        wait_time=wait_time,
                        file=str(image_file),
                    )
                    print(f"\n  ⚠️  Большой таймаут: {wait_time} секунд ({wait_time/60:.1f} минут)")
                    print(f"  Telegram временно ограничил бота из-за превышения лимитов.")
                    print(f"  Рекомендуется подождать {wait_time/60:.0f} минут и запустить скрипт снова.")
                    print(f"  Или продолжить ожидание сейчас...")
                    print(f"  (Скрипт продолжит через {wait_time} секунд)\n")
                else:
                    logger.warning(
                        f"Rate limit hit, waiting {wait_time} seconds",
                        wait_time=wait_time,
                        file=str(image_file),
                    )
                    print(f"  ⏳ Rate limit: ждем {wait_time} секунд...")
                
                await asyncio.sleep(wait_time)
                # Add extra delay after rate limit to avoid immediate re-hit
                if wait_time > 60:
                    extra_delay = min(wait_time // 10, 30)  # Extra 10% delay, max 30 seconds
                    logger.info(f"Adding extra delay after rate limit: {extra_delay} seconds")
                    await asyncio.sleep(extra_delay)
                retry_count += 1
                
            except Exception as e:
                error_str = str(e)
                # Check if it's a flood control error
                if "Flood control" in error_str or "retry after" in error_str.lower():
                    rate_limit_count += 1
                    
                    # Increase delay if we're hitting rate limits frequently
                    if rate_limit_count > 2:
                        current_delay = min(base_delay * (1 + rate_limit_count * 0.3), 15.0)  # Max 15 seconds
                        logger.info(f"Increasing delay to {current_delay:.1f}s due to frequent rate limits")
                        print(f"  ⚠️  Увеличена задержка до {current_delay:.1f} секунд из-за частых ограничений")
                    
                    # Extract wait time from error message
                    match = re.search(r"retry after (\d+)", error_str.lower())
                    if match:
                        wait_time = int(match.group(1))
                        
                        # If wait time is too long (more than 5 minutes), ask user
                        if wait_time > 300:
                            logger.warning(
                                f"Very long flood control: {wait_time} seconds ({wait_time/60:.1f} minutes)",
                                wait_time=wait_time,
                                file=str(image_file),
                            )
                            print(f"\n  ⚠️  Большой таймаут: {wait_time} секунд ({wait_time/60:.1f} минут)")
                            print(f"  Telegram временно ограничил бота из-за превышения лимитов.")
                            print(f"  Рекомендуется подождать {wait_time/60:.0f} минут и запустить скрипт снова.")
                            print(f"  Или продолжить ожидание сейчас...")
                            print(f"  (Скрипт продолжит через {wait_time} секунд)\n")
                        else:
                            logger.warning(
                                f"Flood control, waiting {wait_time} seconds",
                                wait_time=wait_time,
                                file=str(image_file),
                            )
                            print(f"  ⏳ Flood control: ждем {wait_time} секунд...")
                        
                        await asyncio.sleep(wait_time)
                        # Add extra delay after flood control to avoid immediate re-hit
                        if wait_time > 60:
                            extra_delay = min(wait_time // 10, 30)  # Extra 10% delay, max 30 seconds
                            logger.info(f"Adding extra delay after flood control: {extra_delay} seconds")
                            await asyncio.sleep(extra_delay)
                        retry_count += 1
                    else:
                        logger.error("Failed to load image", file=str(image_file), error=error_str)
                        await session.rollback()
                        break  # Give up on this image
                else:
                    logger.error("Failed to load image", file=str(image_file), error=error_str)
                    await session.rollback()
                    break  # Give up on this image
        
        if retry_count >= max_retries:
            logger.error(
                f"Failed to load image after {max_retries} retries",
                file=str(image_file),
            )
            await session.rollback()
    
    logger.info(
        f"Completed processing {pic_type.value} images",
        total=len(image_files),
        loaded=count,
        skipped=skipped_count,
        pic_type=pic_type.value,
    )
    
    # Save skipped files to a text file for review
    if skipped_files:
        skipped_file_path = directory.parent / f"skipped_{pic_type.value}_{directory.name}.txt"
        try:
            with open(skipped_file_path, "w", encoding="utf-8") as f:
                f.write(f"Skipped {len(skipped_files)} files for {pic_type.value} images\n")
                f.write(f"Directory: {directory}\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write("=" * 80 + "\n\n")
                for file_path, reason, file_id in skipped_files:
                    f.write(f"File: {file_path}\n")
                    f.write(f"Reason: {reason}\n")
                    if file_id:
                        f.write(f"Telegram file_id: {file_id}\n")
                    f.write("-" * 80 + "\n")
            logger.info(f"Saved list of {len(skipped_files)} skipped files to {skipped_file_path}")
            print(f"  📝 Список пропущенных файлов сохранен в: {skipped_file_path}")
        except Exception as e:
            logger.warning(f"Failed to save skipped files list: {e}")
    
    return count


async def main() -> None:
    """Main function."""
    configure_logging(settings.log_level)
    
    # Get admin chat ID from command line or use bot's info
    admin_chat_id = None
    if len(sys.argv) > 1:
        try:
            admin_chat_id = int(sys.argv[1])
        except ValueError:
            logger.error("Invalid chat_id provided. Usage: python load_images.py <your_telegram_chat_id>")
            sys.exit(1)
    
    # Initialize bot - always use main bot for all images
    bot = Bot(token=settings.tg_bot_token)
    logger.info("Using main bot token for all images (TG_BOT_TOKEN)")
    
    # If no chat_id provided, get bot info and ask user to provide their chat_id
    if admin_chat_id is None:
        bot_info = await bot.get_me()
        logger.warning(
            "No chat_id provided. Please provide your Telegram chat_id as argument.\n"
            f"Usage: python scripts/load_images.py <your_telegram_chat_id>\n"
            f"To get your chat_id, send a message to @userinfobot on Telegram."
        )
        await bot.session.close()
        await engine.dispose()
        sys.exit(1)
    
    # Get image directories (from project root)
    base_dir = Path(__file__).parent.parent
    morning_dir = base_dir / "image" / "morning"
    evening_dir = base_dir / "image" / "evening"
    
    logger.info("Starting image loading", admin_chat_id=admin_chat_id)
    logger.info(f"Morning directory: {morning_dir}", exists=morning_dir.exists())
    logger.info(f"Evening directory: {evening_dir}", exists=evening_dir.exists())
    
    async with async_session_maker() as session:
        morning_count = 0
        evening_count = 0
        
        if morning_dir.exists():
            logger.info("Loading morning images...")
            morning_count = await load_images_from_directory(
                bot=bot,
                directory=morning_dir,
                pic_type=PicType.MORNING,
                session=session,
                admin_chat_id=admin_chat_id,
            )
        else:
            logger.warning(f"Morning directory not found: {morning_dir}")
        
        if evening_dir.exists():
            logger.info("Loading evening images...")
            evening_count = await load_images_from_directory(
                bot=bot,
                directory=evening_dir,
                pic_type=PicType.EVENING,
                session=session,
                admin_chat_id=admin_chat_id,
            )
        else:
            logger.warning(f"Evening directory not found: {evening_dir}")
        
        total_count = morning_count + evening_count
        
        # Get final counts from database
        pics_repo = PicsPoolRepository(session)
        final_morning_count = await pics_repo.count(PicType.MORNING)
        final_evening_count = await pics_repo.count(PicType.EVENING)
        final_total = final_morning_count + final_evening_count
        
        logger.info(
            "Images loading completed",
            morning_loaded=morning_count,
            evening_loaded=evening_count,
            total_loaded=total_count,
            final_morning=final_morning_count,
            final_evening=final_evening_count,
            final_total=final_total,
        )
        print(f"\n✅ Загрузка завершена!")
        print(f"   Загружено в этой сессии:")
        print(f"     Утренних: {morning_count}")
        print(f"     Вечерних: {evening_count}")
        print(f"     Всего: {total_count}")
        print(f"\n   Всего в базе данных:")
        print(f"     Утренних: {final_morning_count}")
        print(f"     Вечерних: {final_evening_count}")
        print(f"     Всего: {final_total}")
        print(f"\n💡 Совет: Вы можете удалить сообщения из Saved Messages,")
        print(f"   они больше не нужны - file_id сохранены в БД.")
    
    await bot.session.close()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

