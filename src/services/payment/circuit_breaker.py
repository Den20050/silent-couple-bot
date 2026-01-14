"""Universal circuit breaker for external services."""

from redis.asyncio import Redis

from src.core.constants import (
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_TIMEOUT_SECONDS,
)
from src.core.logger import get_logger

logger = get_logger(__name__)


class CircuitBreaker:
    """Circuit breaker for external services.
    
    Implements the circuit breaker pattern to prevent cascading failures
    when external services are unavailable. Uses Redis for distributed state.
    """

    def __init__(self, redis: Redis | None, service_name: str) -> None:
        """Initialize circuit breaker.
        
        Args:
            redis: Redis client for distributed state (optional)
            service_name: Name of the service (e.g., "robokassa", "yookassa")
        """
        self.redis = redis
        self.service_name = service_name
        self.key_prefix = f"cb:{service_name}"
        self._redis_available = redis is not None

    async def is_open(self) -> bool:
        """Check if circuit is open (blocking requests).
        
        Returns:
            True if circuit is open (blocking requests), False otherwise.
            If Redis is unavailable, returns False (allows requests).
        """
        if not self._redis_available or not self.redis:
            return False  # If Redis unavailable, circuit breaker is always closed (allows requests)
        
        try:
            key = f"{self.key_prefix}:open"
            # Use get with timeout to avoid hanging
            result = await self.redis.get(key)
            return result is not None
        except (ConnectionError, Exception) as e:
            # Catch all Redis connection errors
            logger.warning(
                "Circuit breaker Redis error, treating as closed",
                service=self.service_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            self._redis_available = False  # Disable Redis for future calls
            self.redis = None  # Clear reference to failed Redis client
            return False  # Allow request if Redis fails

    async def record_failure(self) -> None:
        """Record a failure and open circuit if threshold reached."""
        if not self._redis_available or not self.redis:
            return  # Skip if Redis unavailable
        
        try:
            key = f"{self.key_prefix}:failures"
            count = await self.redis.incr(key)
            await self.redis.expire(key, CIRCUIT_BREAKER_TIMEOUT_SECONDS)
            
            if count >= CIRCUIT_BREAKER_FAILURE_THRESHOLD:
                await self._open_circuit()
        except Exception as e:
            logger.warning(
                "Circuit breaker Redis error in record_failure",
                service=self.service_name,
                error=str(e),
            )
            self._redis_available = False  # Disable Redis for future calls

    async def _open_circuit(self) -> None:
        """Open circuit breaker (block requests)."""
        if not self._redis_available or not self.redis:
            return
        
        try:
            key = f"{self.key_prefix}:open"
            await self.redis.setex(key, CIRCUIT_BREAKER_TIMEOUT_SECONDS, "1")
            logger.error(
                "Circuit breaker opened",
                service=self.service_name,
                timeout=CIRCUIT_BREAKER_TIMEOUT_SECONDS,
            )
        except Exception as e:
            logger.warning(
                "Circuit breaker Redis error in _open_circuit",
                service=self.service_name,
                error=str(e),
            )
            self._redis_available = False

    async def record_success(self) -> None:
        """Record a success (reset failure counter)."""
        if not self._redis_available or not self.redis:
            return
        
        try:
            key = f"{self.key_prefix}:failures"
            await self.redis.delete(key)
        except Exception as e:
            logger.warning(
                "Circuit breaker Redis error in record_success",
                service=self.service_name,
                error=str(e),
            )
            self._redis_available = False
