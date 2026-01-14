"""Скрипт для проверки и восстановления webhook при необходимости."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from aiogram import Bot
from src.bot.webhook_server import set_webhook

logger = get_logger(__name__)


async def main() -> None:
    """Проверить webhook и восстановить при необходимости."""
    configure_logging(settings.log_level)
    
    bot = Bot(token=settings.tg_bot_token)
    
    try:
        # Проверить текущий статус
        webhook_info = await bot.get_webhook_info()
        
        logger.info("=== Проверка webhook ===")
        logger.info(f"Текущий статус: {webhook_info.url or 'НЕ УСТАНОВЛЕН'}")
        
        if webhook_info.url:
            logger.info("")
            logger.info("✅ Webhook уже установлен")
            logger.info(f"   URL: {webhook_info.url}")
            logger.info(f"   Pending updates: {webhook_info.pending_update_count}")
            
            if webhook_info.last_error_date:
                logger.warning(f"   ⚠️  Последняя ошибка: {webhook_info.last_error_message}")
            
            logger.info("")
            logger.info("Если бот запущен на другом ПК с webhook - он должен работать.")
            logger.info("Проверьте, отвечает ли бот на сообщения в Telegram.")
            return
        
        # Webhook не установлен - проверить, есть ли URL в настройках
        if not settings.webhook_url:
            logger.warning("")
            logger.warning("⚠️  WEBHOOK_URL не указан в .env")
            logger.warning("Не могу восстановить webhook без URL.")
            logger.warning("")
            logger.warning("Если бот должен работать на сервере:")
            logger.warning("1. Укажите WEBHOOK_URL в .env (например: https://24policybot.ru/webhook/telegram)")
            logger.warning("2. Запустите этот скрипт снова")
            return
        
        # Предложить восстановить webhook
        logger.info("")
        logger.info(f"В .env указан WEBHOOK_URL: {settings.webhook_url}")
        logger.info("")
        
        response = input("Восстановить webhook? (y/n): ")
        if response.lower() != "y":
            logger.info("Отменено")
            return
        
        logger.info("Восстанавливаю webhook...")
        success = await set_webhook()
        
        if success:
            logger.info("✅ Webhook успешно восстановлен!")
            logger.info("")
            logger.info("Теперь проверьте:")
            logger.info("1. Запущен ли бот на сервере: ssh root@91.222.237.94 'sudo systemctl status silent-couple-bot-webhook'")
            logger.info("2. Отвечает ли бот на сообщения в Telegram")
            logger.info("")
            logger.info("Если бот НЕ запущен на сервере - удалите webhook:")
            logger.info("   python scripts/set_webhook.py delete")
        else:
            logger.error("❌ Не удалось восстановить webhook")
            logger.error("Проверьте:")
            logger.error("1. Доступен ли сервер по адресу из WEBHOOK_URL")
            logger.error("2. Настроен ли Nginx для проксирования на webhook сервер")
            logger.error("3. Запущен ли webhook сервер на сервере")
        
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
