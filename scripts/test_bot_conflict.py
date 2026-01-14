"""Скрипт для проверки конфликта бота - попытка запустить polling и проверить конфликт."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from aiogram import Bot
from aiogram.exceptions import TelegramConflictError

logger = get_logger(__name__)


async def test_polling_conflict() -> None:
    """Попытаться запустить polling и проверить, есть ли конфликт."""
    configure_logging(settings.log_level)
    
    bot = Bot(token=settings.tg_bot_token)
    
    try:
        logger.info("=== Тест конфликта polling ===")
        logger.info("")
        logger.info("Попытка получить обновления через getUpdates...")
        logger.info("(Это безопасно - мы не запускаем полноценный polling)")
        logger.info("")
        
        # Попробовать получить обновления один раз
        try:
            updates = await bot.get_updates(limit=1, timeout=1)
            logger.info("✅ Успешно получены обновления - конфликта нет!")
            logger.info("")
            logger.info("Вывод: Бот НЕ запущен на другом ПК (или запущен, но не использует polling)")
            logger.info("Можно запускать локально: python run.py")
        except TelegramConflictError as e:
            logger.error("❌ КОНФЛИКТ ОБНАРУЖЕН!")
            logger.error(f"Ошибка: {e}")
            logger.error("")
            logger.error("Вывод: Бот уже запущен на другом ПК в polling режиме!")
            logger.error("")
            logger.error("Решение:")
            logger.error("1. Остановите бот на другом ПК")
            logger.error("2. Или установите webhook и запустите бот на сервере:")
            logger.error("   - Укажите WEBHOOK_URL в .env")
            logger.error("   - python scripts/set_webhook.py")
            logger.error("   - Запустите бот на сервере через systemd")
        except Exception as e:
            logger.warning(f"⚠️  Неожиданная ошибка: {e}")
            logger.warning("Это может быть нормально (таймаут или другие причины)")
            logger.info("")
            logger.info("Попробуйте запустить бот: python run.py")
            logger.info("Если появится TelegramConflictError - бот запущен на другом ПК")
        
    except Exception as e:
        logger.error(f"Ошибка при тесте: {e}", exc_info=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(test_polling_conflict())
