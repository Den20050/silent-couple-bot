"""Bot application factory."""

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat, MenuButtonCommands

from src.core.di.container import Container
from src.core.logger import get_logger
from src.core.redis_client import test_redis_connection
from src.bot.bootstrap import (
    create_bot_and_dispatcher,
    setup_middlewares,
    register_routers,
)

logger = get_logger(__name__)


async def create_bot_app(container: Container) -> tuple[Bot, Dispatcher]:
    """Create bot application: Bot and Dispatcher with all middleware and handlers.

    Args:
        container: Dependency injection container

    Returns:
        Tuple of (Bot, Dispatcher) instances
    """
    # Create bot and dispatcher
    bot, dp = create_bot_and_dispatcher(container)
    
    # Set up middlewares
    setup_middlewares(dp, container)
    
    # Register routers
    register_routers(dp)
    
    logger.info(
        "Bot application created",
        environment=container.settings.environment,
    )

    return bot, dp


async def setup_bot_commands(bot: Bot, container: Container) -> None:
    """Set up bot commands menu.

    Args:
        bot: Bot instance
        container: Dependency injection container
    """
    try:
        # Set commands for all users (without admin commands)
        user_commands = [
            BotCommand(command="start", description="🚀 Начать/Перезапустить бота"),
            BotCommand(command="create_pair", description="➕ Создать пару"),
            BotCommand(command="subscription", description="📊 Подписка"),
            BotCommand(command="pay", description="💳 Оплатить"),
            BotCommand(command="settings", description="⚙️ Настройки"),
            BotCommand(command="share", description="📤 Поделиться ботом"),
            BotCommand(command="feedback", description="💬 Обратная связь"),
            BotCommand(command="bot_info", description="ℹ️ Сведения о боте"),
            BotCommand(command="delete", description="🗑️ Удалить аккаунт"),
        ]
        await bot.set_my_commands(user_commands)
        logger.info(
            "Bot commands menu set for users",
            commands_count=len(user_commands),
        )

        # Set commands for admin (with admin commands) if admin_tg_id is set
        if container.settings.admin_tg_id:
            admin_commands = user_commands + [
                BotCommand(command="admin_stats", description="👑 Статистика"),
                BotCommand(command="admin_reset_demo", description="👑 Сброс демо"),
                BotCommand(command="admin_gift", description="👑 Подарить подписку"),
                BotCommand(command="admin_broadcast", description="👑 Рассылка"),
            ]
            # Set commands only for admin user (in private chat, chat_id = user_id)
            scope = BotCommandScopeChat(chat_id=container.settings.admin_tg_id)
            await bot.set_my_commands(admin_commands, scope=scope)
            logger.info(
                "Bot commands menu set for admin",
                admin_tg_id=container.settings.admin_tg_id,
                commands_count=len(admin_commands),
            )
        
        # Set Menu Button (left of input field)
        # chat_id=None sets global menu button for all chats
        menu_button = MenuButtonCommands()
        await bot.set_chat_menu_button(chat_id=None, menu_button=menu_button)
        logger.info("Menu button configured")
    except Exception as e:
        logger.warning(f"Failed to set bot commands/menu button: {e}")


async def verify_bot_connection(bot: Bot) -> None:
    """Verify bot connection to Telegram.
    
    Args:
        bot: Bot instance
        
    Raises:
        Exception: If connection fails
    """
    bot_info = await bot.get_me()
    logger.info("Bot connected", username=bot_info.username, id=bot_info.id)


async def verify_redis_connection(container: Container) -> None:
    """Verify Redis connection (optional).

    Args:
        container: Dependency injection container
    """
    redis = container.redis
    if redis:
        if await test_redis_connection(redis):
            logger.info("Redis connection verified")
        else:
            logger.warning("Redis connection test failed, but continuing")
    else:
        logger.info("Using MemoryStorage (no Redis)")
