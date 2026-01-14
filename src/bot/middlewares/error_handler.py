"""Error handling middleware for bot handlers."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from src.bot.exceptions import BotException
from src.core.logger import get_logger
from src.core.messages import get_message

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """Middleware for handling exceptions in handlers."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Handle exceptions raised by handlers.
        
        Args:
            handler: Handler function
            event: Telegram event (Message, CallbackQuery, etc.)
            data: Event data
            
        Returns:
            Handler result or None if error occurred
        """
        try:
            return await handler(event, data)
        except BotException as e:
            # Handle custom bot exceptions
            await self._handle_bot_exception(event, e)
        except Exception as e:
            # Handle unexpected exceptions
            logger.error(
                "Unexpected error in handler",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            await self._handle_unexpected_error(event)
    
    async def _handle_bot_exception(
        self,
        event: TelegramObject,
        exception: BotException,
    ) -> None:
        """Handle bot exception.
        
        Args:
            event: Telegram event
            exception: Bot exception
        """
        error_message = exception.message or get_message(exception.message_key)
        
        if isinstance(event, CallbackQuery):
            if exception.show_alert:
                await event.answer(error_message, show_alert=True)
            else:
                await event.answer(error_message)
                if event.message and exception.reply_markup:
                    try:
                        await event.message.edit_text(
                            error_message,
                            reply_markup=exception.reply_markup,
                        )
                    except Exception:
                        # Message might be already edited or deleted
                        pass
        elif isinstance(event, Message):
            await event.answer(
                error_message,
                reply_markup=exception.reply_markup,
            )
    
    async def _handle_unexpected_error(self, event: TelegramObject) -> None:
        """Handle unexpected error.
        
        Args:
            event: Telegram event
        """
        error_message = get_message("MENU_ERROR")
        
        if isinstance(event, CallbackQuery):
            await event.answer(error_message, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(error_message)

