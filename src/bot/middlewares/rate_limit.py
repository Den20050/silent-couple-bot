"""Rate limiting middleware."""

import time
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from redis.asyncio import Redis

from src.core.config import settings
from src.core.constants import RATE_LIMIT_MESSAGES_PER_USER_PER_MINUTE, RATE_LIMIT_BAN_DURATION_SECONDS
from src.core.logger import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Rate limiting middleware."""

    def __init__(self, redis: Redis):
        """Initialize rate limiter."""
        self.redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Check rate limit."""
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id
        key = f"rate_limit:{user_id}"
        
        # Check if user is banned
        banned = await self.redis.get(f"ban:{user_id}")
        if banned:
            logger.warning("User rate limit ban active", user_id=user_id)
            return  # Silently ignore

        # Check rate limit
        count = await self.redis.incr(key)
        await self.redis.expire(key, 60)  # 1 minute window

        if count == 1:
            # First message in window
            return await handler(event, data)

        if count > RATE_LIMIT_MESSAGES_PER_USER_PER_MINUTE:
            # Ban user
            await self.redis.setex(f"ban:{user_id}", RATE_LIMIT_BAN_DURATION_SECONDS, "1")
            logger.warning(
                "User rate limit exceeded, banned",
                user_id=user_id,
                count=count,
            )
            return  # Silently ignore

        # Check minimum interval (1 message per 2 seconds)
        last_message_key = f"last_msg:{user_id}"
        last_time = await self.redis.get(last_message_key)
        if last_time:
            elapsed = time.time() - float(last_time)
            if elapsed < 2:
                logger.debug("Message too frequent", user_id=user_id, elapsed=elapsed)
                return  # Silently ignore

        await self.redis.setex(last_message_key, 2, str(time.time()))
        return await handler(event, data)

