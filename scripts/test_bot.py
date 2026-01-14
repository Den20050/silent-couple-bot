"""Script to test bot connection and basic functionality."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from src.core.redis_client import create_redis_client, test_redis_connection
from aiogram import Bot

logger = get_logger(__name__)


async def test_bot() -> bool:
    """Test bot connection."""
    print("🔍 Проверка подключения бота...")
    
    # Test Telegram Bot API
    try:
        bot = Bot(token=settings.tg_bot_token)
        bot_info = await bot.get_me()
        print(f"✅ Бот подключен: @{bot_info.username} (ID: {bot_info.id})")
        await bot.session.close()
    except Exception as e:
        print(f"❌ Ошибка подключения к Telegram: {e}")
        print("   Проверьте TG_BOT_TOKEN в .env файле")
        return False
    
    # Test Redis
    redis = await create_redis_client()
    if redis:
        if await test_redis_connection(redis):
            print("✅ Redis подключен")
            await redis.aclose()
        else:
            print("❌ Redis подключен, но ping не прошел")
            await redis.aclose()
            return False
    else:
        print("❌ Ошибка подключения к Redis")
        print(f"   URL: {settings.redis_url}, DB: {settings.redis_db}")
        print("   Проверьте, что Redis запущен: docker-compose up -d redis")
        return False
    
    # Test Database
    try:
        from src.db.base import engine
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        print("✅ База данных подключена")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        print("   Проверьте DATABASE_URL в .env файле")
        return False
    
    print("\n✅ Все проверки пройдены! Бот готов к запуску.")
    return True


if __name__ == "__main__":
    configure_logging("INFO")
    success = asyncio.run(test_bot())
    sys.exit(0 if success else 1)

