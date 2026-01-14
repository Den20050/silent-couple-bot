"""Скрипт для проверки, запущен ли бот на другом ПК или сервере."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from aiogram import Bot

logger = get_logger(__name__)


async def check_bot_status() -> None:
    """Проверить статус бота и определить, запущен ли он где-то еще."""
    configure_logging(settings.log_level)
    
    bot = Bot(token=settings.tg_bot_token)
    
    try:
        logger.info("=== Проверка статуса бота ===")
        logger.info("")
        
        # 1. Проверить webhook статус
        logger.info("1. Проверка webhook...")
        webhook_info = await bot.get_webhook_info()
        
        if webhook_info.url:
            logger.info(f"   ✅ Webhook установлен: {webhook_info.url}")
            logger.info(f"   Pending updates: {webhook_info.pending_update_count}")
            
            if webhook_info.last_error_date:
                logger.warning(f"   ⚠️  Последняя ошибка: {webhook_info.last_error_message}")
            
            logger.info("")
            logger.info("   📍 Вывод: Бот настроен на работу через webhook")
            logger.info("   Это означает, что бот должен работать на сервере.")
            logger.info("")
            logger.info("   Проверьте на сервере:")
            logger.info("   ssh root@91.222.237.94")
            logger.info("   sudo systemctl status silent-couple-bot-webhook")
            logger.info("")
            logger.info("   ⚠️  НЕ запускайте бот локально в polling режиме!")
            logger.info("   Это вызовет конфликт с webhook.")
        else:
            logger.info("   ❌ Webhook НЕ установлен")
            logger.info("")
            logger.info("   📍 Вывод: Бот может работать в polling режиме")
            logger.info("")
            logger.info("   ⚠️  ВНИМАНИЕ: Если бот запущен на другом ПК в polling режиме,")
            logger.info("   это вызовет конфликт при попытке запустить локально!")
            logger.info("")
            logger.info("   Рекомендации:")
            logger.info("   1. Проверьте все ПК - не запущен ли бот где-то еще")
            logger.info("   2. Если бот должен работать на сервере - установите webhook:")
            logger.info("      python scripts/set_webhook.py")
            logger.info("   3. Если бот должен работать локально - убедитесь, что он")
            logger.info("      не запущен на других ПК")
        
        logger.info("")
        logger.info("2. Проверка бота через getMe...")
        bot_info = await bot.get_me()
        logger.info(f"   ✅ Бот доступен: @{bot_info.username} (ID: {bot_info.id})")
        logger.info(f"   Имя: {bot_info.first_name}")
        
        logger.info("")
        logger.info("=== Рекомендации ===")
        logger.info("")
        
        if webhook_info.url:
            logger.info("✅ Webhook установлен - используйте webhook режим на сервере")
            logger.info("❌ НЕ запускайте локально в polling режиме")
        else:
            logger.info("✅ Webhook не установлен - можно использовать polling локально")
            logger.info("⚠️  Убедитесь, что бот НЕ запущен на других ПК")
            logger.info("")
            logger.info("Для установки webhook (если бот должен работать на сервере):")
            logger.info("1. Укажите WEBHOOK_URL в .env")
            logger.info("2. Запустите: python scripts/set_webhook.py")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке: {e}", exc_info=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(check_bot_status())
