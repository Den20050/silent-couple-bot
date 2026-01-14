"""IP injector middleware for webhook server."""

from typing import Callable, Dict, Any, Awaitable
from contextvars import ContextVar

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.core.logger import get_logger

logger = get_logger(__name__)

# Context variable to store IP address per request
ip_context: ContextVar[str | None] = ContextVar("ip_context", default=None)


class IPInjectorMiddleware(BaseMiddleware):
    """Middleware to inject IP address into data dict for handlers."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Inject IP from context into data dict."""
        ip = ip_context.get()
        if ip:
            data["ip"] = ip
        return await handler(event, data)
