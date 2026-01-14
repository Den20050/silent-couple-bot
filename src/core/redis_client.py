"""Redis client utilities with proper connection handling."""

import asyncio
from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,  # noqa: F401
)

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


async def create_redis_client(
    url: Optional[str] = None,
    db: Optional[int] = None,
    decode_responses: bool = True,
    socket_connect_timeout: int = 10,
    socket_timeout: int = 30,
    retry_on_timeout: bool = True,
    health_check_interval: int = 30,
) -> Optional[Redis]:
    """
    Create Redis client with proper configuration and connection testing.
    
    Args:
        url: Redis URL (defaults to settings.redis_url)
        db: Redis database number (defaults to settings.redis_db)
        decode_responses: Decode responses as strings
        socket_connect_timeout: Timeout for socket connection in seconds (default: 10)
        socket_timeout: Timeout for socket operations in seconds (default: 30)
        retry_on_timeout: Retry on timeout errors
        health_check_interval: Health check interval in seconds
        
    Returns:
        Redis client instance or None if connection failed
    """
    redis_url = url or settings.redis_url
    redis_db = db if db is not None else settings.redis_db
    
    try:
        # Parse URL to extract host and port for better error messages
        if redis_url.startswith("redis://"):
            # Extract host:port from URL
            parts = redis_url.replace("redis://", "").split("/")
            host_port = parts[0] if parts else "localhost:6379"
            logger.debug(f"Connecting to Redis at {host_port}, db={redis_db}")
        
        client = Redis.from_url(
            redis_url,
            db=redis_db,
            decode_responses=decode_responses,
            socket_connect_timeout=socket_connect_timeout,
            socket_timeout=socket_timeout,
            retry_on_timeout=retry_on_timeout,
            health_check_interval=health_check_interval,
            # Connection pool settings
            max_connections=50,
            retry_on_error=[RedisConnectionError, RedisTimeoutError],
            # Auto-reconnect on connection loss
            auto_close_connection_pool=False,
        )
        
        # Test connection immediately
        await client.ping()
        logger.info(
            f"Redis connected successfully at {redis_url}, db={redis_db}"
        )
        return client
        
    except (RedisConnectionError, RedisTimeoutError) as e:
        logger.warning(
            f"Redis connection failed: {e}",
            redis_url=redis_url,
            redis_db=redis_db,
            error_type=type(e).__name__,
        )
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error connecting to Redis: {e}",
            redis_url=redis_url,
            redis_db=redis_db,
            error_type=type(e).__name__,
            exc_info=True,
        )
        return None


async def test_redis_connection(client: Optional[Redis]) -> bool:
    """
    Test Redis connection with retry logic.
    
    Args:
        client: Redis client instance
        
    Returns:
        True if connection is working, False otherwise
    """
    if not client:
        return False
    
    try:
        await client.ping()
        return True
    except (RedisConnectionError, RedisTimeoutError) as e:
        logger.warning(f"Redis ping failed: {e}")
        return False
    except Exception as e:
        logger.warning(f"Redis ping failed with unexpected error: {e}")
        return False


async def ensure_redis_connection(client: Optional[Redis], max_retries: int = 3) -> bool:
    """
    Ensure Redis connection is alive, reconnecting if needed.
    
    Args:
        client: Redis client instance
        max_retries: Maximum number of reconnection attempts
        
    Returns:
        True if connection is working, False otherwise
    """
    if not client:
        return False
    
    for attempt in range(max_retries):
        try:
            await client.ping()
            return True
        except (RedisConnectionError, RedisTimeoutError) as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Redis connection lost, attempting reconnect ({attempt + 1}/{max_retries}): {e}"
                )
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
            else:
                logger.error(f"Redis connection failed after {max_retries} attempts: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error testing Redis connection: {e}")
            return False
    
    return False

