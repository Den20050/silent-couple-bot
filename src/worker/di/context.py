"""Worker context for dependency injection."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import Settings
from src.core.logger import get_logger
from src.core.protocols.bot_provider import BotProviderProtocol
from src.core.protocols.messenger import MessengerProtocol
from src.worker.services.lock_service import LockService
from src.worker.services.notification_builder import NotificationBuilder
from src.worker.services.pair_scheduler import PairScheduler
from src.worker.services.time_window_service import TimeWindowService

if TYPE_CHECKING:
    from aiogram import Bot

logger = get_logger(__name__)


@dataclass
class WorkerContext:
    """Context for worker tasks with all required dependencies.
    
    Encapsulates dependencies needed by worker tasks:
    - Database session factory
    - Redis client
    - Telegram messenger
    - Bot provider (for bot initialization)
    - Worker services (LockService, PairScheduler, etc.)
    """
    
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis | None
    messenger: MessengerProtocol
    bot_provider: BotProviderProtocol
    
    # Worker services (created on demand)
    _lock_service: LockService | None = None
    _notification_builder: NotificationBuilder | None = None
    _pair_scheduler: PairScheduler | None = None
    _time_window_service: TimeWindowService | None = None
    _bot: "Bot | None" = None
    
    @property
    def lock_service(self) -> LockService:
        """Get LockService instance (lazy initialization)."""
        if self._lock_service is None:
            self._lock_service = LockService(redis_client=self.redis)
        return self._lock_service
    
    @property
    def notification_builder(self) -> NotificationBuilder:
        """Get NotificationBuilder instance (lazy initialization)."""
        if self._notification_builder is None:
            self._notification_builder = NotificationBuilder(messenger=self.messenger)
        return self._notification_builder
    
    def create_pair_scheduler(self, session: AsyncSession) -> PairScheduler:
        """Create PairScheduler instance for a specific session.
        
        Args:
            session: Database session
            
        Returns:
            PairScheduler instance
        """
        return PairScheduler(
            session=session,
            telegram_messenger=self.messenger,
            lock_service=self.lock_service,
        )
    
    @property
    def time_window_service(self) -> TimeWindowService:
        """Get TimeWindowService instance (lazy initialization)."""
        if self._time_window_service is None:
            self._time_window_service = TimeWindowService()
        return self._time_window_service
    
    async def ensure_bot_initialized(self) -> None:
        """Ensure bot is initialized in bot_provider.
        
        This method creates Bot instance and sets it in bot_provider.
        Should be called at the start of worker tasks that need bot.
        """
        if self._bot is not None:
            return
        
        try:
            from aiogram import Bot
            self._bot = Bot(token=self.settings.tg_bot_token)
            self.bot_provider.set_bot(self._bot)
            logger.debug("Bot initialized in WorkerContext")
        except Exception as e:
            logger.error(
                "Failed to initialize bot in WorkerContext",
                error=str(e),
                exc_info=True,
            )
            raise
    
    async def close_bot(self) -> None:
        """Close bot instance if it was created.
        
        Should be called at the end of worker tasks.
        """
        if self._bot is not None:
            try:
                await self._bot.session.close()
            except Exception:
                pass
            self._bot = None


def create_worker_context(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis | None,
    messenger: MessengerProtocol,
    bot_provider: BotProviderProtocol,
) -> WorkerContext:
    """Create worker context with all dependencies.
    
    Args:
        settings: Application settings
        session_factory: Database session factory
        redis: Redis client (optional)
        messenger: Telegram messenger
        bot_provider: Bot provider instance
        
    Returns:
        WorkerContext instance
    """
    return WorkerContext(
        settings=settings,
        session_factory=session_factory,
        redis=redis,
        messenger=messenger,
        bot_provider=bot_provider,
    )

