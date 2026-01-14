"""Dependency Injection container."""

from typing import Optional
from dataclasses import dataclass, field

from redis.asyncio import Redis

from src.core.config import Settings
from src.core.di.providers.storage import (
    SessionFactory,
    provide_session_factory,
    provide_redis,
)
from src.core.di.providers.telegram import (
    provide_bot_provider,
    provide_telegram_messenger,
)
from src.core.di.providers.payment import (
    provide_payment_service,
    provide_webhook_handler,
)

# Import protocols for type hints (DIP compliance)
from src.core.protocols.bot_provider import BotProviderProtocol
from src.core.protocols.messenger import MessengerProtocol
from src.core.protocols.payment import PaymentServiceProtocol

# Import concrete types for runtime (actual implementations)
from src.services.telegram.bot_provider import BotProvider as BotProviderImpl
from src.services.telegram.messenger import TelegramMessenger as TelegramMessengerImpl
from src.services.payment.robokassa_service import RobokassaService as RobokassaServiceImpl
from src.services.payment.webhook_handler import RobokassaWebhookHandler as RobokassaWebhookHandlerImpl


@dataclass
class Container:
    """Dependency Injection container.

    Stores all application dependencies and provides them via properties.
    All dependencies are lazily initialized on first access.
    
    Uses protocols for type hints (DIP compliance) while storing concrete implementations.
    """

    settings: Settings
    _redis: Optional[Redis] = field(default=None, init=False)
    _session_factory: Optional[SessionFactory] = field(default=None, init=False)
    # Store as protocol-compatible types for DIP compliance
    _bot_provider: Optional[BotProviderProtocol] = field(default=None, init=False)
    _telegram_messenger: Optional[MessengerProtocol] = field(default=None, init=False)
    _payment_service: Optional[PaymentServiceProtocol] = field(default=None, init=False)
    _webhook_handler: Optional[RobokassaWebhookHandlerImpl] = field(
        default=None, init=False
    )

    @property
    def redis(self) -> Optional[Redis]:
        """Get Redis client (lazy initialization)."""
        return self._redis

    @property
    def session_factory(self) -> SessionFactory:
        """Get database session factory (lazy initialization)."""
        if self._session_factory is None:
            self._session_factory = provide_session_factory(self.settings)
        return self._session_factory

    @property
    def bot_provider(self) -> BotProviderProtocol:
        """Get bot provider (lazy initialization).
        
        Returns:
            BotProviderProtocol implementation
        """
        if self._bot_provider is None:
            self._bot_provider = provide_bot_provider()
        return self._bot_provider

    @property
    def telegram_messenger(self) -> MessengerProtocol:
        """Get Telegram messenger (lazy initialization).
        
        Returns:
            MessengerProtocol implementation
        """
        if self._telegram_messenger is None:
            self._telegram_messenger = provide_telegram_messenger(
                self.bot_provider,
                self.session_factory,
            )
        return self._telegram_messenger

    @property
    def payment_service(self) -> PaymentServiceProtocol:
        """Get payment service (lazy initialization).
        
        Returns:
            PaymentServiceProtocol implementation
        """
        if self._payment_service is None:
            self._payment_service = provide_payment_service(
                redis=self.redis, settings=self.settings
            )
        return self._payment_service

    @property
    def webhook_handler(self) -> RobokassaWebhookHandlerImpl:
        """Get webhook handler (lazy initialization)."""
        if self._webhook_handler is None:
            self._webhook_handler = provide_webhook_handler(
                redis=self.redis, settings=self.settings
            )
        return self._webhook_handler

    def set_redis(self, redis: Optional[Redis]) -> None:
        """Set Redis client.

        Args:
            redis: Redis client instance
        """
        self._redis = redis

    async def close(self) -> None:
        """Close all resources."""
        if self._session_factory:
            await self._session_factory.close()
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception as e:
                from src.core.logger import get_logger
                logger = get_logger(__name__)
                logger.warning(f"Error closing Redis connection: {e}")


def create_container(log_level: Optional[str] = None) -> Container:
    """Create and initialize dependency injection container.

    Args:
        log_level: Optional log level override (defaults to settings.log_level)

    Returns:
        Initialized container with all dependencies
    """
    from src.core.logger import configure_logging, get_logger

    # Load settings
    settings = Settings()

    # Configure logging
    actual_log_level = log_level or settings.log_level
    configure_logging(
        log_level=actual_log_level,
        log_file=settings.log_file,
        log_file_max_bytes=settings.log_file_max_bytes,
        log_file_backup_count=settings.log_file_backup_count,
    )

    logger = get_logger(__name__)
    logger.info(
        "Creating dependency injection container",
        environment=settings.environment,
        log_level=actual_log_level,
    )

    # Create container
    container = Container(settings=settings)

    logger.info("Container created successfully")

    return container


async def initialize_container(container: Container) -> None:
    """Initialize container resources (Redis, etc.).

    Args:
        container: Container instance
    """
    from src.core.logger import get_logger

    logger = get_logger(__name__)

    # Initialize Redis
    redis = await provide_redis(container.settings)
    container.set_redis(redis)

