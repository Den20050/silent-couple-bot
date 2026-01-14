"""Telegram message sending/editing/deleting with retry logic."""

from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import Message

from typing import TYPE_CHECKING

from src.services.telegram.message_store import MessageStore
from src.services.telegram.retry import retry_telegram_api
from src.core.logger import get_logger
from src.core.protocols.messenger import MessengerProtocol
from src.core.protocols.bot_provider import BotProviderProtocol

if TYPE_CHECKING:
    from src.services.telegram.bot_provider import BotProvider

logger = get_logger(__name__)


class TelegramMessenger:
    """Handles Telegram message operations with retry logic.
    
    Implements MessengerProtocol for testing and dependency inversion.
    Protocol compliance is verified through structural subtyping (duck typing).
    """
    
    def __init__(
        self,
        bot_provider: BotProviderProtocol,
        message_store: MessageStore,
    ) -> None:
        """Initialize messenger.
        
        Args:
            bot_provider: Bot instance provider
            message_store: Message store for saving message IDs
        """
        self._bot_provider = bot_provider
        self._message_store = message_store
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[dict] = None,
        parse_mode: Optional[str] = None,
        save_message: bool = True,
    ) -> Message:
        """Send message with retry logic.
        
        Args:
            chat_id: Telegram chat ID
            text: Message text
            reply_markup: Optional inline keyboard
            parse_mode: Optional parse mode (HTML, Markdown, etc.)
            save_message: Whether to save message_id for cleanup (default: True)
            
        Returns:
            Sent Message object
        """
        bot = self._bot_provider.get_bot()
        
        async def _send() -> Message:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
        
        message = await retry_telegram_api(
            operation=_send,
            operation_name="send_message",
            context={"chat_id": chat_id},
        )
        
        # Save message_id for cleanup if requested
        if save_message:
            await self._message_store.save_message(
                chat_id=chat_id,
                message_id=message.message_id,
            )
        
        return message
    
    async def send_photo(
        self,
        chat_id: int,
        photo: str,  # file_id
        caption: Optional[str] = None,
        reply_markup: Optional[dict] = None,
        save_message: bool = True,
    ) -> Message:
        """Send photo with retry logic.
        
        Args:
            chat_id: Telegram chat ID
            photo: Telegram file_id
            caption: Optional photo caption
            reply_markup: Optional inline keyboard
            save_message: Whether to save message_id for cleanup (default: True)
            
        Returns:
            Sent Message object
            
        Note:
            All pictures are sent via main bot (TG_BOT_TOKEN).
            file_ids are bot-specific, so we must use the same bot that uploaded them.
        """
        bot = self._bot_provider.get_bot()
        
        async def _send() -> Message:
            return await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
            )
        
        message = await retry_telegram_api(
            operation=_send,
            operation_name="send_photo",
            context={"chat_id": chat_id},
        )
        
        # Save message_id for cleanup if requested
        if save_message:
            await self._message_store.save_message(
                chat_id=chat_id,
                message_id=message.message_id,
            )
        
        return message
    
    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: Optional[str] = None,
        reply_markup: Optional[dict] = None,
    ) -> Optional[Message]:
        """Edit message with retry logic.
        
        Handles both text messages and photo messages.
        For photo messages, removes reply_markup if text editing fails.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Message ID to edit
            text: Optional new text
            reply_markup: Optional new reply markup
            
        Returns:
            Edited Message if successful, None otherwise
        """
        bot = self._bot_provider.get_bot()
        
        async def _edit_text() -> Message:
            return await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
            )
        
        try:
            return await retry_telegram_api(
                operation=_edit_text,
                operation_name="edit_message_text",
                context={"chat_id": chat_id, "message_id": message_id},
            )
        except TelegramBadRequest as e:
            # If message has no text (e.g., photo message), try editing caption or reply_markup only
            error_message = str(e).lower()
            if "no text" in error_message or "message to edit" in error_message:
                # Message is likely a photo without text
                # Try to edit only reply_markup (remove button)
                if reply_markup is not None:
                    try:
                        return await self._edit_reply_markup(
                            chat_id=chat_id,
                            message_id=message_id,
                            reply_markup=reply_markup,
                        )
                    except TelegramAPIError:
                        # If that also fails, try removing the markup
                        try:
                            return await self._edit_reply_markup(
                                chat_id=chat_id,
                                message_id=message_id,
                                reply_markup=None,
                            )
                        except TelegramAPIError:
                            logger.warning(
                                "Could not edit photo message, skipping",
                                chat_id=chat_id,
                                message_id=message_id,
                                error=str(e),
                            )
                            return None
                else:
                    # No reply_markup to edit, just log and return None
                    logger.warning(
                        "Cannot edit photo message without text, skipping",
                        chat_id=chat_id,
                        message_id=message_id,
                        error=str(e),
                    )
                    return None
            # Other BadRequest errors - re-raise
            raise
    
    async def _edit_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        reply_markup: Optional[dict] = None,
    ) -> Message:
        """Edit message reply markup.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Message ID to edit
            reply_markup: New reply markup (None to remove)
            
        Returns:
            Edited Message object
        """
        bot = self._bot_provider.get_bot()
        
        async def _edit() -> Message:
            return await bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
            )
        
        return await retry_telegram_api(
            operation=_edit,
            operation_name="edit_message_reply_markup",
            context={"chat_id": chat_id, "message_id": message_id},
        )
    
    async def remove_reply_markup(
        self,
        chat_id: int,
        message_id: int,
    ) -> Optional[Message]:
        """Remove reply markup (buttons) from message with retry logic.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Message ID to edit
            
        Returns:
            Edited Message if successful, None otherwise
        """
        try:
            return await self._edit_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=None,
            )
        except TelegramAPIError as e:
            logger.warning(
                "Failed to remove reply markup after retries",
                chat_id=chat_id,
                message_id=message_id,
                error=str(e),
            )
            return None
    
    async def delete_message(
        self,
        chat_id: int,
        message_id: int,
    ) -> bool:
        """Delete message with retry logic.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Message ID to delete
            
        Returns:
            True if message was deleted successfully, False otherwise
        """
        bot = self._bot_provider.get_bot()
        
        async def _delete() -> None:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        
        try:
            await retry_telegram_api(
                operation=_delete,
                operation_name="delete_message",
                context={"chat_id": chat_id, "message_id": message_id},
            )
            return True
        except TelegramAPIError as e:
            # Message might already be deleted or not found - that's okay
            error_str = str(e).lower()
            if "message to delete not found" in error_str or "message can't be deleted" in error_str:
                logger.debug(
                    "Message already deleted or can't be deleted",
                    chat_id=chat_id,
                    message_id=message_id,
                )
                return True  # Consider it successful
            
            logger.warning(
                "Failed to delete message after retries",
                chat_id=chat_id,
                message_id=message_id,
                error=str(e),
            )
            return False
