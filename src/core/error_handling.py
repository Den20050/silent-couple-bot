"""Common error handling utilities."""

from typing import Callable, Awaitable, TypeVar, ParamSpec
from functools import wraps

from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


async def send_error_to_user(
    message_or_callback: Message | CallbackQuery,
    error_key: str = "START_ERROR",
    show_alert: bool = False,
) -> None:
    """Send error message to user.
    
    Args:
        message_or_callback: Message or CallbackQuery object
        error_key: Message key from messages.py
        show_alert: Whether to show alert (for CallbackQuery)
    """
    try:
        error_text = get_message(error_key)
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer(error_text, show_alert=show_alert)
        else:
            await message_or_callback.answer(error_text)
    except Exception as e:
        logger.error("Failed to send error message to user", error=str(e))


def handle_errors(
    error_key: str = "START_ERROR",
    show_alert: bool = False,
    reraise: bool = False,
):
    """Decorator for error handling in handlers.
    
    Args:
        error_key: Message key for error message
        show_alert: Whether to show alert (for CallbackQuery)
        reraise: Whether to re-raise exception after handling
        
    Example:
        @handle_errors(error_key="PAY_ERROR", show_alert=True)
        async def my_handler(message: Message, session: AsyncSession):
            # handler code
    """
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T | None]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error in {func.__name__}",
                    error=str(e),
                    exc_info=True,
                )
                
                # Try to find Message or CallbackQuery in args/kwargs
                message_or_callback = None
                for arg in args:
                    if isinstance(arg, (Message, CallbackQuery)):
                        message_or_callback = arg
                        break
                
                if message_or_callback:
                    await send_error_to_user(
                        message_or_callback,
                        error_key=error_key,
                        show_alert=show_alert,
                    )
                
                if reraise:
                    raise
                return None
        
        return wrapper
    return decorator
