"""Test script to check if file_ids in database work with current bot token."""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Bot
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


async def test_file_ids() -> None:
    """Test if file_ids in database work with current bot token."""
    configure_logging(settings.log_level)
    
    # Initialize bot with current token
    bot = Bot(token=settings.tg_bot_token)
    bot_info = await bot.get_me()
    logger.info(f"Testing with bot: @{bot_info.username} (ID: {bot_info.id})")
    print(f"\n🤖 Текущий бот: @{bot_info.username} (ID: {bot_info.id})")
    print(f"   Токен: {settings.tg_bot_token[:20]}...")
    
    async with async_session_maker() as session:
        # Get a few file_ids from database
        morning_result = await session.execute(
            select(PicsPool.file_id).where(PicsPool.type == PicType.MORNING.value).limit(3)
        )
        morning_file_ids = morning_result.scalars().all()
        
        evening_result = await session.execute(
            select(PicsPool.file_id).where(PicsPool.type == PicType.EVENING.value).limit(3)
        )
        evening_file_ids = evening_result.scalars().all()
        
        total_morning = await session.execute(
            select(PicsPool).where(PicsPool.type == PicType.MORNING.value)
        )
        total_morning_count = len(list(total_morning.scalars().all()))
        
        total_evening = await session.execute(
            select(PicsPool).where(PicsPool.type == PicType.EVENING.value)
        )
        total_evening_count = len(list(total_evening.scalars().all()))
        
        print(f"\n💾 В БД найдено:")
        print(f"   Утренних: {total_morning_count}")
        print(f"   Вечерних: {total_evening_count}")
        print(f"   Всего: {total_morning_count + total_evening_count}")
        
        if not morning_file_ids and not evening_file_ids:
            print(f"\n✅ В БД нет картинок. Можно загружать новые.")
            await bot.session.close()
            await engine.dispose()
            return
        
        # Test if file_ids work with current bot
        print(f"\n🧪 Тестируем file_id с текущим ботом...")
        
        test_file_id = morning_file_ids[0] if morning_file_ids else (evening_file_ids[0] if evening_file_ids else None)
        
        if test_file_id:
            try:
                # Try to get file info - this will fail if file_id doesn't belong to this bot
                file_info = await bot.get_file(test_file_id)
                print(f"   ✅ file_id работает с текущим ботом!")
                print(f"   ✅ Картинки в БД загружены с ЭТИМ ботом")
                print(f"   ❌ НЕ НУЖНО загружать заново!")
                print(f"\n💡 Если вы хотите загрузить картинки заново, сначала очистите БД:")
                print(f"   python scripts/clear_images.py")
            except Exception as e:
                error_str = str(e)
                if "file not found" in error_str.lower() or "wrong file_id" in error_str.lower():
                    print(f"   ❌ file_id НЕ работает с текущим ботом!")
                    print(f"   ❌ Картинки в БД загружены с ДРУГИМ ботом (другим токеном)")
                    print(f"   ✅ НУЖНО очистить БД и загрузить заново!")
                    print(f"\n💡 Выполните:")
                    print(f"   1. python scripts/clear_images.py")
                    print(f"   2. python scripts/load_images.py <your_chat_id>")
                else:
                    print(f"   ⚠️  Ошибка при проверке: {error_str}")
        else:
            print(f"   ⚠️  Не найдено file_id для тестирования")
    
    await bot.session.close()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_file_ids())
