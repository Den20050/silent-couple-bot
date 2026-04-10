"""Bot and Dispatcher factory."""

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from src.core.di.container import Container
from src.core.logger import get_logger
from src.services.telegram.bot_factory import create_bot as _create_bot

logger = get_logger(__name__)


def create_bot_and_dispatcher(container: Container) -> tuple[Bot, Dispatcher]:
    """Create Bot and Dispatcher instances.

    Args:
        container: Dependency injection container

    Returns:
        Tuple of (Bot, Dispatcher) instances
    """
    # Get Redis from container
    redis = container.redis

    # Create storage (fallback to MemoryStorage if Redis unavailable)
    if redis:
        try:
            storage = RedisStorage(redis=redis)
            logger.info("Using Redis storage")
        except Exception as e:
            logger.warning(
                "Failed to create RedisStorage, falling back to MemoryStorage",
                error=str(e),
            )
            storage = MemoryStorage()
    else:
        logger.warning("Redis not available, using MemoryStorage")
        storage = MemoryStorage()

    # Initialize bot (with proxy if configured)
    bot = _create_bot(container.settings.tg_bot_token, proxy_url=container.settings.telegram_proxy_url)
    
    # Set bot in provider (for dependency injection)
    container.bot_provider.set_bot(bot)
    
    # Initialize dispatcher
    dp = Dispatcher(storage=storage)
    
    logger.info(
        "Bot and Dispatcher created",
        environment=container.settings.environment,
        storage_type=type(storage).__name__,
    )

    return bot, dp

