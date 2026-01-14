"""Storage providers (Redis, Database)."""

from typing import Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)

from src.core.config import Settings
from src.core.logger import get_logger
from src.core.redis_client import create_redis_client, test_redis_connection

logger = get_logger(__name__)


class SessionFactory:
    """Factory for creating database sessions."""

    def __init__(self, database_url: str, is_development: bool = False) -> None:
        """Initialize session factory.

        Args:
            database_url: Database connection URL
            is_development: Whether in development mode (enables SQL echo)
        """
        self.database_url = database_url
        self.is_development = is_development
        self._engine: Optional[AsyncEngine] = None
        self._session_maker: Optional[async_sessionmaker[AsyncSession]] = None

    def initialize(self) -> None:
        """Initialize engine and session maker."""
        if self._engine is None:
            self._engine = create_async_engine(
                self.database_url,
                echo=self.is_development,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
            self._session_maker = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
            logger.info("Database session factory initialized")

    async def create_session(self) -> AsyncSession:
        """Create a new database session.

        Returns:
            AsyncSession instance (context manager)
        """
        if self._session_maker is None:
            self.initialize()
        assert self._session_maker is not None
        return self._session_maker()

    def __call__(self) -> AsyncSession:
        """Make factory callable for convenience.

        Returns:
            AsyncSession instance (context manager)
        """
        if self._session_maker is None:
            self.initialize()
        assert self._session_maker is not None
        return self._session_maker()

    async def close(self) -> None:
        """Close engine and all connections."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database engine closed")


def provide_session_factory(settings: Settings) -> SessionFactory:
    """Provide database session factory.

    Args:
        settings: Application settings

    Returns:
        SessionFactory instance
    """
    factory = SessionFactory(
        database_url=settings.database_url,
        is_development=settings.is_development,
    )
    factory.initialize()
    return factory


async def provide_redis(settings: Settings) -> Optional[Redis]:
    """Provide Redis client.

    Args:
        settings: Application settings

    Returns:
        Redis client instance or None if unavailable
    """
    redis = await create_redis_client()
    
    if redis:
        if await test_redis_connection(redis):
            logger.info("Redis connection verified")
        else:
            logger.warning("Redis connection test failed, but continuing")
    else:
        logger.info("Redis not available, continuing without it")
    
    return redis

