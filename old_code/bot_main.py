"""Bot main entry point."""

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat, MenuButtonCommands
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from src.core.redis_client import create_redis_client, test_redis_connection
from src.bot.handlers import (
    admin,
    callbacks,
    delete,
    feedback,
    link,
    menu,
    pay,
    settings as settings_handler,
    start,
    subscription,
)
from src.bot.middlewares.database import DatabaseMiddleware
from src.bot.middlewares.rate_limit import RateLimitMiddleware
from src.bot.middlewares.timezone import TimezoneMiddleware
from src.services.telegram import set_bot

logger = get_logger(__name__)


async def main() -> None:
    """Main bot function."""
    # Configure logging
    configure_logging(settings.log_level)
    
    # Initialize Redis (or use MemoryStorage if Redis unavailable)
    redis = await create_redis_client()
    storage = None
    
    if redis:
        try:
            storage = RedisStorage(redis=redis)
            logger.info("Using Redis storage")
        except Exception as e:
            logger.warning(f"Failed to create RedisStorage: {e}")
            logger.warning("Falling back to MemoryStorage")
            storage = MemoryStorage()
            await redis.aclose()
            redis = None
    else:
        logger.warning("Redis not available, using MemoryStorage")
        logger.warning(
            "Note: FSM state will be lost on restart. For production, use Redis."
        )
        storage = MemoryStorage()
    
    # Initialize bot
    bot = Bot(
        token=settings.tg_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    set_bot(bot)  # Set global bot instance for services
    
    # Initialize dispatcher
    dp = Dispatcher(storage=storage)
    
    # Register middlewares (order matters!)
    # 1. Database middleware first (provides session)
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    
    # 2. Timezone detection (needs session from DatabaseMiddleware)
    dp.message.middleware(TimezoneMiddleware())
    
    # 3. Rate limiting only if Redis is available
    if redis:
        dp.message.middleware(RateLimitMiddleware(redis))
    else:
        logger.warning("Rate limiting disabled (Redis not available)")
    
    # Register routers
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(subscription.router)
    dp.include_router(pay.router)
    dp.include_router(feedback.router)
    dp.include_router(delete.router)
    dp.include_router(link.router)
    dp.include_router(settings_handler.router)
    dp.include_router(callbacks.router)
    
    logger.info("Bot starting", environment=settings.environment)
    
    # Test bot connection
    try:
        bot_info = await bot.get_me()
        logger.info("Bot connected", username=bot_info.username, id=bot_info.id)
    except Exception as e:
        logger.error("Failed to connect to Telegram", error=str(e))
        raise

    # Set bot commands menu
    try:
        # Set commands for all users (without admin commands)
        user_commands = [
            BotCommand(command="start", description="🚀 Начать/Перезапустить бота"),
            BotCommand(command="subscription", description="📊 Подписка"),
            BotCommand(command="pay", description="💳 Оплатить"),
            BotCommand(command="settings", description="⚙️ Настройки"),
            BotCommand(command="feedback", description="💬 Обратная связь"),
            BotCommand(command="delete", description="🗑️ Удалить аккаунт"),
        ]
        await bot.set_my_commands(user_commands)
        logger.info("Bot commands menu set for users", commands_count=len(user_commands))
        
        # Set commands for admin (with admin commands) if admin_tg_id is set
        if settings.admin_tg_id:
            admin_commands = user_commands + [
                BotCommand(command="admin_stats", description="👑 Статистика"),
                BotCommand(command="admin_reset_demo", description="👑 Сброс демо"),
                BotCommand(command="admin_gift", description="👑 Подарить подписку"),
                BotCommand(command="admin_broadcast", description="👑 Рассылка"),
            ]
            # Set commands only for admin user (in private chat, chat_id = user_id)
            scope = BotCommandScopeChat(chat_id=settings.admin_tg_id)
            await bot.set_my_commands(admin_commands, scope=scope)
            logger.info("Bot commands menu set for admin", admin_tg_id=settings.admin_tg_id, commands_count=len(admin_commands))

        # Set Menu Button (left of input field)
        # chat_id=None sets global menu button for all chats
        menu_button = MenuButtonCommands()
        await bot.set_chat_menu_button(chat_id=None, menu_button=menu_button)
        logger.info("Menu button configured")
    except Exception as e:
        logger.warning(f"Failed to set bot commands/menu button: {e}")
    
    # Test Redis connection (optional)
    if redis:
        if await test_redis_connection(redis):
            logger.info("Redis connection verified")
        else:
            logger.warning("Redis connection test failed, but continuing")
    else:
        logger.info("Using MemoryStorage (no Redis)")
    
    # Start bot (polling or webhook)
    if settings.webhook_url:
        logger.info("Webhook mode: use webhook_server.py instead")
        logger.warning(
            "To use webhook, run: uvicorn src.bot.webhook_server:app "
            f"--host 0.0.0.0 --port {settings.webhook_port}"
        )
        logger.info("Switching to polling mode for now...")
        # Fall back to polling if webhook_url is set but webhook server not running
        # This allows development/testing

    # Start polling
    try:
        logger.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error("Polling error", error=str(e))
        raise
    finally:
        await bot.session.close()
        if redis:
            try:
                await redis.aclose()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")


if __name__ == "__main__":
    asyncio.run(main())
