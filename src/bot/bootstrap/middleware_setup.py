"""Middleware setup for bot application."""

from aiogram import Dispatcher

from src.core.di.container import Container
from src.core.logger import get_logger
from src.bot.middlewares.container import ContainerMiddleware
from src.bot.middlewares.database import DatabaseMiddleware
from src.bot.middlewares.error_handler import ErrorHandlerMiddleware
from src.bot.middlewares.rate_limit import RateLimitMiddleware
from src.bot.middlewares.timezone import TimezoneMiddleware
from src.bot.middlewares.user_activity_logger import UserActivityLoggerMiddleware

logger = get_logger(__name__)


def setup_middlewares(dp: Dispatcher, container: Container) -> None:
    """Set up middlewares for dispatcher.

    Middleware order matters:
    1. ContainerMiddleware - provides container and services
    2. DatabaseMiddleware - provides database session
    3. UserActivityLoggerMiddleware - logs all user actions
    4. TimezoneMiddleware - detects user timezone (needs session)
    5. RateLimitMiddleware - rate limiting (needs Redis)

    Args:
        dp: Dispatcher instance
        container: Dependency injection container
    """
    # 0. Error handler middleware first (catches all exceptions)
    error_handler_middleware = ErrorHandlerMiddleware()
    dp.message.middleware(error_handler_middleware)
    dp.callback_query.middleware(error_handler_middleware)
    
    # 1. Container middleware (provides container and services)
    container_middleware = ContainerMiddleware(container)
    dp.message.middleware(container_middleware)
    dp.callback_query.middleware(container_middleware)

    # 2. Database middleware (provides session)
    database_middleware = DatabaseMiddleware()
    dp.message.middleware(database_middleware)
    dp.callback_query.middleware(database_middleware)

    # 3. User activity logger (logs all actions with session context)
    user_activity_logger = UserActivityLoggerMiddleware()
    dp.message.middleware(user_activity_logger)
    dp.callback_query.middleware(user_activity_logger)

    # 4. Timezone detection (needs session from DatabaseMiddleware)
    timezone_middleware = TimezoneMiddleware()
    dp.message.middleware(timezone_middleware)

    # 5. Rate limiting only if Redis is available
    redis = container.redis
    if redis:
        rate_limit_middleware = RateLimitMiddleware(redis)
        dp.message.middleware(rate_limit_middleware)
        logger.info("Rate limiting enabled")
    else:
        logger.warning("Rate limiting disabled (Redis not available)")
    
    logger.info("Middlewares configured")

