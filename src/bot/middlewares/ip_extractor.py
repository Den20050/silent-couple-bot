"""IP extractor middleware for webhook requests."""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from fastapi import Request

logger = None


def get_logger():
    """Lazy import logger to avoid circular imports."""
    global logger
    if logger is None:
        from src.core.logger import get_logger
        logger = get_logger(__name__)
    return logger


class IPExtractorMiddleware(BaseMiddleware):
    """Middleware to extract IP address from webhook requests."""

    def __init__(self, request: Request | None = None):
        """Initialize middleware with optional FastAPI request."""
        super().__init__()
        self.request = request

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Extract IP from request and attach to event."""
        log = get_logger()

        # Extract IP from FastAPI request if available
        if self.request:
            # Try multiple headers (common proxy headers)
            ip = (
                self.request.headers.get("X-Real-IP")
                or self.request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or self.request.headers.get("CF-Connecting-IP")
                or (self.request.client.host if self.request.client else None)
            )

            if ip:
                # Attach IP to event object
                if isinstance(event, (Message, CallbackQuery)):
                    setattr(event, "ip", ip)
                    log.debug("IP extracted from request", ip=ip)

        return await handler(event, data)
