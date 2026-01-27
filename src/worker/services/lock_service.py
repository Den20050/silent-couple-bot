"""Redis lock service for task execution."""

from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
)

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


class LockService:
    """Service for managing Redis locks for task execution."""
    
    def __init__(self, redis_client: Optional[Redis] = None) -> None:
        """Initialize lock service.
        
        Args:
            redis_client: Redis client instance (optional, will be created if None)
        """
        self._redis_client = redis_client
        self._own_client = False
    
    async def acquire_task_lock(
        self,
        task_name: str,
        lock_ttl: int | None = None,
    ) -> bool:
        """Acquire Redis lock for task execution.
        
        Args:
            task_name: Name of the task
            lock_ttl: Lock TTL in seconds (default: from settings)
            
        Returns:
            True if lock was acquired, False otherwise
        """
        redis_client = await self.get_redis_client()
        if redis_client is None:
            logger.warning("Redis client is None, skipping task lock", task=task_name)
            return False
        
        lock_key = f"{settings.redis_key_prefix_task_lock}:{task_name}"
        
        # Use TTL from settings if not provided
        if lock_ttl is None:
            lock_ttl = settings.task_lock_ttl_seconds
        
        try:
            lock_acquired = await redis_client.set(
                lock_key, "1", ex=lock_ttl, nx=True
            )
            return bool(lock_acquired)
        except (RedisConnectionError, RedisTimeoutError) as e:
            logger.warning(
                "Redis connection error while acquiring task lock",
                task=task_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False
        except Exception as e:
            logger.warning(
                "Failed to acquire task lock",
                task=task_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False
    
    async def check_key_exists(self, key: str) -> bool:
        """Check if Redis key exists.
        
        Args:
            key: Redis key
            
        Returns:
            True if key exists, False otherwise
        """
        redis_client = await self.get_redis_client()
        if redis_client is None:
            return False
        
        try:
            result = await redis_client.exists(key)
            return bool(result)
        except Exception as e:
            logger.warning(
                "Failed to check Redis key",
                key=key,
                error=str(e),
            )
            return False
    
    async def set_key_with_ttl(
        self,
        key: str,
        value: str,
        ttl_seconds: int,
    ) -> bool:
        """Set Redis key with TTL.
        
        Args:
            key: Redis key
            value: Value to set
            ttl_seconds: TTL in seconds
            
        Returns:
            True if key was set, False otherwise
        """
        redis_client = await self.get_redis_client()
        if redis_client is None:
            return False

    async def set_key_if_not_exists(
        self,
        key: str,
        value: str,
        ttl_seconds: int,
    ) -> bool:
        """Atomically set Redis key if it does not exist (SET NX).

        Args:
            key: Redis key
            value: Value to set
            ttl_seconds: TTL in seconds

        Returns:
            True if key was set, False if already exists or error
        """
        redis_client = await self.get_redis_client()
        if redis_client is None:
            return False

        try:
            result = await redis_client.set(key, value, ex=ttl_seconds, nx=True)
            return bool(result)
        except Exception as e:
            logger.warning(
                "Failed to set Redis key atomically",
                key=key,
                error=str(e),
            )
            return False
        
        try:
            await redis_client.setex(key, ttl_seconds, value)
            return True
        except Exception as e:
            logger.warning(
                "Failed to set Redis key",
                key=key,
                error=str(e),
            )
            return False
    
    async def get_key(self, key: str) -> Optional[str]:
        """Get Redis key value.
        
        Args:
            key: Redis key
            
        Returns:
            Value if key exists, None otherwise
        """
        redis_client = await self.get_redis_client()
        if redis_client is None:
            return None
        
        try:
            result = await redis_client.get(key)
            if result is None:
                return None
            if isinstance(result, bytes):
                return result.decode()
            return str(result)
        except Exception as e:
            logger.warning(
                "Failed to get Redis key",
                key=key,
                error=str(e),
            )
            return None
    
    async def get_redis_client(self) -> Optional[Redis]:
        """Get Redis client, creating if needed.
        
        Returns:
            Redis client instance or None if connection failed
        """
        if self._redis_client is None:
            try:
                from src.core.redis_client import create_redis_client
                self._redis_client = await create_redis_client(
                    socket_connect_timeout=10,
                    socket_timeout=30,
                )
                self._own_client = True
            except Exception as e:
                logger.warning(
                    "Redis not available for lock service",
                    error=str(e),
                )
                return None
        
        return self._redis_client
    
    async def get_last_warning_time(
        self,
        key: str,
    ) -> Optional[float]:
        """Get timestamp of last warning sent.
        
        Args:
            key: Redis key for warning timestamp
            
        Returns:
            Timestamp (Unix timestamp) if exists, None otherwise
        """
        redis_client = await self.get_redis_client()
        if redis_client is None:
            return None
        
        try:
            result = await redis_client.get(key)
            if result is None:
                return None
            if isinstance(result, bytes):
                result = result.decode()
            return float(result)
        except Exception as e:
            logger.warning(
                "Failed to get last warning time",
                key=key,
                error=str(e),
            )
            return None
    
    async def set_last_warning_time(
        self,
        key: str,
        timestamp: float,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Set timestamp of last warning sent.
        
        Args:
            key: Redis key for warning timestamp
            timestamp: Unix timestamp
            ttl_seconds: TTL in seconds (default: from settings)
            
        Returns:
            True if timestamp was set, False otherwise
        """
        redis_client = await self.get_redis_client()
        if redis_client is None:
            return False
        
        # Use TTL from settings if not provided
        if ttl_seconds is None:
            ttl_seconds = settings.warning_ttl_days * 24 * 3600
        
        try:
            await redis_client.setex(key, ttl_seconds, str(timestamp))
            return True
        except Exception as e:
            logger.warning(
                "Failed to set last warning time",
                key=key,
                error=str(e),
            )
            return False
    
    async def close(self) -> None:
        """Close Redis client if we own it."""
        if self._own_client and self._redis_client:
            try:
                await self._redis_client.aclose()
            except Exception:
                pass
            self._redis_client = None
            self._own_client = False

