"""Retry policy for Telegram API calls."""

import asyncio
from typing import Callable, TypeVar, Awaitable, cast

from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from src.core.constants import TELEGRAM_RETRY_ATTEMPTS, TELEGRAM_RETRY_DELAYS
from src.core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


async def retry_telegram_api(
    operation: Callable[[], Awaitable[T]],
    operation_name: str,
    context: dict | None = None,
) -> T:
    """Execute Telegram API operation with retry logic.
    
    Args:
        operation: Async function to execute
        operation_name: Name of operation for logging (e.g., "send_message")
        context: Optional context dict for logging (e.g., {"chat_id": 123})
        
    Returns:
        Result of the operation
        
    Raises:
        TelegramAPIError: If operation fails after all retries
        RuntimeError: If retry loop exits unexpectedly
    """
    context = context or {}
    
    for attempt in range(TELEGRAM_RETRY_ATTEMPTS):
        try:
            return await operation()
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            logger.warning(
                f"Telegram rate limit hit during {operation_name}",
                wait_time=wait_time,
                attempt=attempt + 1,
                **context,
            )
            await asyncio.sleep(wait_time)
        except TelegramAPIError as e:
            error_lower = str(e).lower()
            # Permanent failures — do not retry
            if "message is not modified" in error_lower:
                logger.debug(
                    f"Telegram {operation_name} is a no-op (message is not modified)",
                    **context,
                )
                return cast(T, None)
            if any(
                phrase in error_lower
                for phrase in (
                    "message to delete not found",
                    "message can't be deleted",
                    "message identifier is not specified",
                )
            ):
                logger.debug(
                    f"Telegram {operation_name} skipped (message gone or not deletable)",
                    error=str(e),
                    **context,
                )
                return cast(T, None)
            if attempt == TELEGRAM_RETRY_ATTEMPTS - 1:
                logger.error(
                    f"Failed {operation_name} after retries",
                    error=str(e),
                    **context,
                )
                raise
            delay = TELEGRAM_RETRY_DELAYS[attempt]
            logger.warning(
                f"Telegram API error during {operation_name}, retrying",
                error=str(e),
                attempt=attempt + 1,
                delay=delay,
                **context,
            )
            await asyncio.sleep(delay)
    
    raise RuntimeError(f"Unexpected retry loop exit for {operation_name}")
