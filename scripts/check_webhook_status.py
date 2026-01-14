"""Скрипт для проверки статуса webhook и его восстановления."""

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


async def check_webhook_status() -> None:
    """Проверить статус webhook и восстановить при необходимости."""
    configure_logging(settings.log_level)
    
    bot = Bot(token=settings.tg_bot_token)
    
    try:
        # Проверить текущий статус webhook
        webhook_info = await bot.get_webhook_info()
        
        logger.info("=== Статус webhook ===")
        logger.info(f"URL: {webhook_info.url or 'НЕ УСТАНОВЛЕН'}")
        logger.info(f"Pending updates: {webhook_info.pending_update_count}")
        logger.info(f"Last error date: {webhook_info.last_error_date}")
        logger.info(f"Last error message: {webhook_info.last_error_message}")
        logger.info(f"Max connections: {webhook_info.max_connections}")
        
        if webhook_info.url:
            logger.info("")
            logger.info("✅ Webhook установлен")
            logger.info(f"   URL: {webhook_info.url}")
            
            if webhook_info.pending_update_count > 0:
                logger.warning(f"   ⚠️  Есть {webhook_info.pending_update_count} необработанных обновлений")
            
            if webhook_info.last_error_date:
                logger.warning(f"   ⚠️  Последняя ошибка: {webhook_info.last_error_message}")
            
            logger.info("")
            logger.info("Если бот запущен на другом ПК с webhook - это нормально.")
            logger.info("Если хотите использовать polling локально - удалите webhook:")
            logger.info("   python scripts/set_webhook.py delete")
        else:
            logger.info("")
            logger.info("❌ Webhook НЕ установлен")
            logger.info("")
            
            # Предложить восстановить webhook
            if settings.webhook_url:
                logger.info(f"В .env указан WEBHOOK_URL: {settings.webhook_url}")
                logger.info("")
                
                response = input("Восстановить webhook? (y/n): ")
                if response.lower() == "y":
                    logger.info("Восстанавливаю webhook...")
                    from src.bot.webhook_server import set_webhook
                    success = await set_webhook()
                    if success:
                        logger.info("✅ Webhook успешно восстановлен!")
                    else:
                        logger.error("❌ Не удалось восстановить webhook")
                else:
                    logger.info("Отменено")
            else:
                logger.info("WEBHOOK_URL не указан в .env")
                logger.info("Для установки webhook укажите WEBHOOK_URL в .env файле")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке webhook: {e}", exc_info=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(check_webhook_status())
