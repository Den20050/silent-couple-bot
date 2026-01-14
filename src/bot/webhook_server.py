"""Telegram webhook server using FastAPI."""

from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat, MenuButtonCommands, Update
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.logger import get_logger
from src.core.redis_client import create_redis_client, test_redis_connection
from src.core.bootstrap import bootstrap
from src.core.di.container import Container
from src.bot.middlewares.container import ContainerMiddleware
from src.bot.middlewares.database import DatabaseMiddleware
from src.bot.middlewares.rate_limit import RateLimitMiddleware
from src.bot.middlewares.timezone import TimezoneMiddleware
from src.bot.middlewares.ip_injector import IPInjectorMiddleware, ip_context
from src.services.telegram import set_bot

logger = get_logger(__name__)

# Global instances
dp: Dispatcher | None = None
bot: Bot | None = None
redis_storage_client = None  # Store Redis client for RedisStorage globally


async def setup_bot() -> tuple[Bot, Dispatcher]:
    """Initialize bot and dispatcher."""
    global bot, dp, redis_client, redis_storage_client
    
    # If bot and dispatcher already initialized, return them
    if bot is not None and dp is not None:
        return bot, dp

    # Bootstrap application to get container with all dependencies
    container: Container = await bootstrap()
    
    # Initialize Redis (or use MemoryStorage if Redis unavailable)
    # RedisStorage needs its own Redis client with its own connection pool
    # Create separate client for RedisStorage to avoid connection closure issues
    if redis_storage_client is None:
        redis_storage_client = await create_redis_client()
    # Use container's Redis for rate limiting middleware (it's already initialized)
    redis_client = container.redis
    storage = None

    if redis_storage_client:
        try:
            # RedisStorage will manage its own connection pool
            storage = RedisStorage(redis=redis_storage_client)
            logger.info("Using Redis storage")
        except Exception as e:
            logger.warning(f"Failed to create RedisStorage: {e}")
            logger.warning("Falling back to MemoryStorage")
            storage = MemoryStorage()
            # Don't close redis_storage_client here - keep it for RedisStorage
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
    # 0. Container middleware first (provides container and services like bot_provider, telegram_messenger)
    container_middleware = ContainerMiddleware(container)
    dp.message.middleware(container_middleware)
    dp.callback_query.middleware(container_middleware)

    # 1. Database middleware (provides session)
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    # 2. IP injector (injects IP from context into data dict)
    dp.message.middleware(IPInjectorMiddleware())
    dp.callback_query.middleware(IPInjectorMiddleware())

    # 3. Timezone detection (needs session from DatabaseMiddleware and IP from data)
    dp.message.middleware(TimezoneMiddleware())
    dp.callback_query.middleware(TimezoneMiddleware())

    # 4. Rate limiting only if Redis is available
    if redis_client:
        dp.message.middleware(RateLimitMiddleware(redis_client))
    else:
        logger.warning("Rate limiting disabled (Redis not available)")

    # Register routers using the same order as router_registry
    from src.bot.bootstrap.router_registry import register_routers
    register_routers(dp)

    logger.info("Bot initialized", environment=settings.environment)

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
            BotCommand(command="create_pair", description="➕ Создать пару"),
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
        menu_button = MenuButtonCommands()
        await bot.set_chat_menu_button(chat_id=None, menu_button=menu_button)
        logger.info("Menu button configured")
    except Exception as e:
        logger.warning(f"Failed to set bot commands/menu button: {e}")

    # Test Redis connection (optional)
    if redis_client:
        if await test_redis_connection(redis_client):
            logger.info("Redis connection verified")
        else:
            logger.warning("Redis connection test failed, but continuing")
    else:
        logger.info("Using MemoryStorage (no Redis)")

    return bot, dp


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    # Startup
    await setup_bot()
    logger.info("Webhook server started")
    yield
    # Shutdown
    global bot, redis_storage_client
    if bot:
        await bot.session.close()
    if redis_storage_client:
        try:
            await redis_storage_client.aclose()
        except Exception as e:
            logger.warning(f"Error closing Redis storage connection: {e}")
    # Container's Redis is managed by container lifecycle
    logger.info("Webhook server stopped")


# Create FastAPI app
app = FastAPI(
    title="Silent Couple Bot Webhook Server",
    lifespan=lifespan,
)

# Include Robokassa webhook router
# This adds /webhook/robokassa endpoint for payment notifications
from src.bot.handlers.webhook import webhook_router
app.include_router(webhook_router)


@app.post(settings.webhook_path)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
) -> JSONResponse:
    """Handle Telegram webhook."""
    global bot, dp

    logger.info("Webhook request received", path=settings.webhook_path)

    if not bot or not dp:
        logger.error("Bot or dispatcher not initialized")
        raise HTTPException(status_code=503, detail="Bot not initialized")

    # Verify secret token if configured
    if settings.webhook_secret_token:
        if x_telegram_bot_api_secret_token != settings.webhook_secret_token:
            client_ip = request.client.host if request.client else None
            logger.warning("Invalid webhook secret token", ip=client_ip)
            raise HTTPException(
                status_code=403, detail="Invalid secret token"
            )

    # Parse update
    try:
        update_data = await request.json()
        update = Update(**update_data)
        logger.info(
            "Webhook update parsed",
            update_id=update.update_id,
            has_message=update.message is not None,
            has_callback_query=update.callback_query is not None,
        )
    except Exception as e:
        logger.error("Failed to parse webhook update", error=str(e), exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid update data")

    # Extract IP from request headers
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    ip = (
        request.headers.get("X-Real-IP")
        or (forwarded_for.split(",")[0].strip() if forwarded_for else None)
        or request.headers.get("CF-Connecting-IP")
        or (request.client.host if request.client else None)
    )

    # Set IP in context for middleware to inject into data dict
    # This allows handlers and middleware to access IP without modifying frozen Pydantic models
    if ip:
        ip_context.set(ip)
        logger.debug("IP set in context", ip=ip)

    # Process update
    try:
        logger.debug("Processing update", update_id=update.update_id)
        await dp.feed_update(bot, update)
        logger.info("Update processed successfully", update_id=update.update_id)
    except Exception as e:
        logger.error(
            "Error processing webhook update",
            update_id=update.update_id,
            error=str(e),
            exc_info=True,
        )
        # Still return 200 to prevent Telegram from retrying
        return JSONResponse(content={"ok": True})
    finally:
        # Clear IP from context after processing
        ip_context.set(None)

    return JSONResponse(content={"ok": True})


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "bot_initialized": bot is not None and dp is not None}


async def set_webhook() -> bool:
    """Set webhook URL in Telegram."""
    global bot
    if not bot:
        bot, _ = await setup_bot()

    if not settings.webhook_url:
        logger.error("WEBHOOK_URL not configured")
        return False

    try:
        await bot.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.webhook_secret_token,
        )
        logger.info("Webhook set", url=settings.webhook_url)
        return True
    except Exception as e:
        logger.error("Failed to set webhook", error=str(e))
        return False


async def delete_webhook() -> bool:
    """Delete webhook (switch back to polling)."""
    global bot
    if not bot:
        bot, _ = await setup_bot()

    try:
        await bot.delete_webhook()
        logger.info("Webhook deleted")
        return True
    except Exception as e:
        logger.error("Failed to delete webhook", error=str(e))
        return False
