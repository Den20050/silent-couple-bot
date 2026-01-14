"""Безопасное восстановление webhook с проверками."""

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


async def restore_webhook_safely() -> None:
    """Безопасно восстановить webhook с проверками."""
    configure_logging(settings.log_level)
    
    bot = Bot(token=settings.tg_bot_token)
    
    try:
        logger.info("=== Безопасное восстановление webhook ===")
        logger.info("")
        
        # 1. Проверить текущий статус
        webhook_info = await bot.get_webhook_info()
        
        if webhook_info.url:
            logger.info(f"✅ Webhook уже установлен: {webhook_info.url}")
            logger.info("Ничего делать не нужно.")
            return
        
        # 2. Проверить, указан ли WEBHOOK_URL
        if not settings.webhook_url:
            logger.warning("⚠️  WEBHOOK_URL не указан в .env")
            logger.warning("")
            logger.warning("Для установки webhook:")
            logger.warning("1. Откройте .env файл")
            logger.warning("2. Раскомментируйте и заполните:")
            logger.warning("   WEBHOOK_URL=https://24policybot.ru/webhook/telegram")
            logger.warning("   WEBHOOK_PATH=/webhook/telegram")
            logger.warning("   WEBHOOK_PORT=8443")
            logger.warning("   WEBHOOK_SECRET_TOKEN=your-secret-token-here")
            logger.warning("3. Запустите этот скрипт снова")
            return
        
        # 3. Проверить конфликт polling
        logger.info("Проверка конфликта polling...")
        try:
            await bot.get_updates(limit=1, timeout=1)
            logger.info("✅ Конфликта нет - можно устанавливать webhook")
        except Exception as e:
            logger.warning(f"⚠️  Возможный конфликт: {e}")
            logger.warning("Убедитесь, что бот не запущен на других ПК")
        
        logger.info("")
        logger.info(f"Восстанавливаю webhook: {settings.webhook_url}")
        
        response = input("Продолжить? (y/n): ")
        if response.lower() != "y":
            logger.info("Отменено")
            return
        
        # 4. Установить webhook
        success = await set_webhook()
        
        if success:
            logger.info("✅ Webhook успешно восстановлен!")
            logger.info("")
            logger.info("Теперь:")
            logger.info("1. Убедитесь, что бот запущен на сервере:")
            logger.info("   ssh root@91.222.237.94")
            logger.info("   sudo systemctl status silent-couple-bot-webhook")
            logger.info("")
            logger.info("2. Если бот не запущен на сервере - запустите его:")
            logger.info("   sudo systemctl start silent-couple-bot-webhook")
            logger.info("")
            logger.info("3. НЕ запускайте бот локально в polling режиме!")
            logger.info("   Используйте только webhook на сервере")
        else:
            logger.error("❌ Не удалось восстановить webhook")
            logger.error("Проверьте:")
            logger.error("1. Доступен ли сервер по адресу из WEBHOOK_URL")
            logger.error("2. Настроен ли Nginx для проксирования")
            logger.error("3. Запущен ли webhook сервер на сервере")
        
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(restore_webhook_safely())
