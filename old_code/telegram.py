"""Telegram API service with retry logic."""

import asyncio
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramRetryAfter
from aiogram.types import Message

from src.core.config import settings
from src.core.constants import TELEGRAM_RETRY_ATTEMPTS, TELEGRAM_RETRY_DELAYS
from src.core.logger import get_logger

logger = get_logger(__name__)

# Global bot instance (will be initialized in bot/main.py)
_bot_instance: Optional[Bot] = None


def get_bot() -> Bot:
    """Get bot instance."""
    if _bot_instance is None:
        raise RuntimeError("Bot not initialized. Call set_bot() first.")
    return _bot_instance


def set_bot(bot: Bot) -> None:
    """Set bot instance."""
    global _bot_instance
    _bot_instance = bot


async def send_message_with_retry(
    chat_id: int,
    text: str,
    reply_markup: Optional[dict] = None,
    parse_mode: Optional[str] = None,
    save_message: bool = True,
    session: Optional[object] = None,
) -> Message:
    """Send message with retry logic.
    
    Args:
        chat_id: Telegram chat ID
        text: Message text
        reply_markup: Optional inline keyboard
        parse_mode: Optional parse mode (HTML, Markdown, etc.)
        save_message: Whether to save message_id for cleanup (default: True)
        session: Optional database session for saving message_id
    """
    bot = get_bot()
    
    for attempt in range(TELEGRAM_RETRY_ATTEMPTS):
        try:
            message = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            
            # Save message_id for cleanup if requested
            if save_message and session is not None:
                try:
                    from src.db.repositories.bot_messages import BotMessagesRepository
                    bot_messages_repo = BotMessagesRepository(session)
                    await bot_messages_repo.create(chat_id=chat_id, message_id=message.message_id)
                except Exception as e:
                    logger.warning(
                        "Failed to save message_id for cleanup",
                        chat_id=chat_id,
                        message_id=message.message_id,
                        error=str(e),
                    )
            
            return message
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            logger.warning(
                "Telegram rate limit hit",
                chat_id=chat_id,
                wait_time=wait_time,
                attempt=attempt + 1,
            )
            await asyncio.sleep(wait_time)
        except TelegramAPIError as e:
            if attempt == TELEGRAM_RETRY_ATTEMPTS - 1:
                logger.error(
                    "Failed to send message after retries",
                    chat_id=chat_id,
                    error=str(e),
                )
                raise
            delay = TELEGRAM_RETRY_DELAYS[attempt]
            logger.warning(
                "Telegram API error, retrying",
                chat_id=chat_id,
                error=str(e),
                attempt=attempt + 1,
                delay=delay,
            )
            await asyncio.sleep(delay)
    
    raise RuntimeError("Unexpected retry loop exit")


async def delete_message_with_retry(
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
    bot = get_bot()
    
    for attempt in range(TELEGRAM_RETRY_ATTEMPTS):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            return True
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            logger.warning(
                "Telegram rate limit hit while deleting",
                chat_id=chat_id,
                message_id=message_id,
                wait_time=wait_time,
                attempt=attempt + 1,
            )
            await asyncio.sleep(wait_time)
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
            
            if attempt == TELEGRAM_RETRY_ATTEMPTS - 1:
                logger.warning(
                    "Failed to delete message after retries",
                    chat_id=chat_id,
                    message_id=message_id,
                    error=str(e),
                )
                return False
            
            delay = TELEGRAM_RETRY_DELAYS[attempt]
            logger.warning(
                "Telegram API error while deleting, retrying",
                chat_id=chat_id,
                message_id=message_id,
                error=str(e),
                attempt=attempt + 1,
                delay=delay,
            )
            await asyncio.sleep(delay)
    
    return False


async def send_photo_with_retry(
    chat_id: int,
    photo: str,  # file_id
    caption: Optional[str] = None,
    reply_markup: Optional[dict] = None,
    save_message: bool = True,
    session: Optional[object] = None,
    pic_type: Optional[str] = None,  # "morning" or "evening" (kept for compatibility, not used)
) -> Message:
    """Send photo with retry logic.
    
    Args:
        chat_id: Telegram chat ID
        photo: Telegram file_id
        caption: Optional photo caption
        reply_markup: Optional inline keyboard
        save_message: Whether to save message_id for cleanup (default: True)
        session: Optional database session for saving message_id
        pic_type: Picture type ("morning" or "evening") - kept for compatibility, always uses main bot
    
    Note:
        - All pictures are sent via main bot (TG_BOT_TOKEN)
        - file_ids are bot-specific, so we must use the same bot that uploaded them
    """
    # Always use main bot for all pictures
    bot = get_bot()
    
    for attempt in range(TELEGRAM_RETRY_ATTEMPTS):
        try:
            message = await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
            )
            
            # Save message_id for cleanup if requested
            if save_message and session is not None:
                try:
                    from src.db.repositories.bot_messages import BotMessagesRepository
                    bot_messages_repo = BotMessagesRepository(session)
                    await bot_messages_repo.create(chat_id=chat_id, message_id=message.message_id)
                except Exception as e:
                    logger.warning(
                        "Failed to save message_id for cleanup",
                        chat_id=chat_id,
                        message_id=message.message_id,
                        error=str(e),
                    )
            
            return message
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            logger.warning(
                "Telegram rate limit hit",
                chat_id=chat_id,
                wait_time=wait_time,
                attempt=attempt + 1,
            )
            await asyncio.sleep(wait_time)
        except TelegramAPIError as e:
            if attempt == TELEGRAM_RETRY_ATTEMPTS - 1:
                logger.error(
                    "Failed to send photo after retries",
                    chat_id=chat_id,
                    error=str(e),
                )
                raise
            delay = TELEGRAM_RETRY_DELAYS[attempt]
            logger.warning(
                "Telegram API error, retrying",
                chat_id=chat_id,
                error=str(e),
                attempt=attempt + 1,
                delay=delay,
            )
            await asyncio.sleep(delay)
    
    raise RuntimeError("Unexpected retry loop exit")


async def delete_message_with_retry(
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
    bot = get_bot()
    
    for attempt in range(TELEGRAM_RETRY_ATTEMPTS):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            return True
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            logger.warning(
                "Telegram rate limit hit while deleting",
                chat_id=chat_id,
                message_id=message_id,
                wait_time=wait_time,
                attempt=attempt + 1,
            )
            await asyncio.sleep(wait_time)
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
            
            if attempt == TELEGRAM_RETRY_ATTEMPTS - 1:
                logger.warning(
                    "Failed to delete message after retries",
                    chat_id=chat_id,
                    message_id=message_id,
                    error=str(e),
                )
                return False
            
            delay = TELEGRAM_RETRY_DELAYS[attempt]
            logger.warning(
                "Telegram API error while deleting, retrying",
                chat_id=chat_id,
                message_id=message_id,
                error=str(e),
                attempt=attempt + 1,
                delay=delay,
            )
            await asyncio.sleep(delay)
    
    return False


async def edit_message_with_retry(
    chat_id: int,
    message_id: int,
    text: Optional[str] = None,
    reply_markup: Optional[dict] = None,
) -> Optional[Message]:
    """Edit message with retry logic.
    
    Handles both text messages and photo messages.
    For photo messages, removes reply_markup if text editing fails.
    """
    bot = get_bot()
    
    for attempt in range(TELEGRAM_RETRY_ATTEMPTS):
        try:
            # Try to edit as text message first
            return await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
            )
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            logger.warning(
                "Telegram rate limit hit",
                chat_id=chat_id,
                wait_time=wait_time,
                attempt=attempt + 1,
            )
            await asyncio.sleep(wait_time)
        except TelegramBadRequest as e:
            # If message has no text (e.g., photo message), try editing caption or reply_markup only
            error_message = str(e).lower()
            if "no text" in error_message or "message to edit" in error_message:
                # Message is likely a photo without text
                # Try to edit only reply_markup (remove button)
                if reply_markup is not None:
                    try:
                        return await bot.edit_message_reply_markup(
                            chat_id=chat_id,
                            message_id=message_id,
                            reply_markup=reply_markup,
                        )
                    except TelegramAPIError:
                        # If that also fails, just remove the markup
                        try:
                            return await bot.edit_message_reply_markup(
                                chat_id=chat_id,
                                message_id=message_id,
                                reply_markup=None,
                            )
                        except TelegramAPIError:
                            # If everything fails, log and return None
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
            if attempt == TELEGRAM_RETRY_ATTEMPTS - 1:
                logger.error(
                    "Failed to edit message after retries",
                    chat_id=chat_id,
                    error=str(e),
                )
                raise
            delay = TELEGRAM_RETRY_DELAYS[attempt]
            logger.warning(
                "Telegram API error, retrying",
                chat_id=chat_id,
                error=str(e),
                attempt=attempt + 1,
                delay=delay,
            )
            await asyncio.sleep(delay)
        except TelegramAPIError as e:
            if attempt == TELEGRAM_RETRY_ATTEMPTS - 1:
                logger.error(
                    "Failed to edit message after retries",
                    chat_id=chat_id,
                    error=str(e),
                )
                raise
            delay = TELEGRAM_RETRY_DELAYS[attempt]
            logger.warning(
                "Telegram API error, retrying",
                chat_id=chat_id,
                error=str(e),
                attempt=attempt + 1,
                delay=delay,
            )
            await asyncio.sleep(delay)
    
    raise RuntimeError("Unexpected retry loop exit")


async def remove_reply_markup_with_retry(
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
    bot = get_bot()
    
    for attempt in range(TELEGRAM_RETRY_ATTEMPTS):
        try:
            return await bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=None,
            )
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            logger.warning(
                "Telegram rate limit hit while removing reply markup",
                chat_id=chat_id,
                message_id=message_id,
                wait_time=wait_time,
                attempt=attempt + 1,
            )
            await asyncio.sleep(wait_time)
        except TelegramAPIError as e:
            if attempt == TELEGRAM_RETRY_ATTEMPTS - 1:
                logger.warning(
                    "Failed to remove reply markup after retries",
                    chat_id=chat_id,
                    message_id=message_id,
                    error=str(e),
                )
                return None
            delay = TELEGRAM_RETRY_DELAYS[attempt]
            logger.warning(
                "Telegram API error while removing reply markup, retrying",
                chat_id=chat_id,
                message_id=message_id,
                error=str(e),
                attempt=attempt + 1,
                delay=delay,
            )
            await asyncio.sleep(delay)
    
    return None


async def delete_message_with_retry(
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
    bot = get_bot()
    
    for attempt in range(TELEGRAM_RETRY_ATTEMPTS):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            return True
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            logger.warning(
                "Telegram rate limit hit while deleting",
                chat_id=chat_id,
                message_id=message_id,
                wait_time=wait_time,
                attempt=attempt + 1,
            )
            await asyncio.sleep(wait_time)
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
            
            if attempt == TELEGRAM_RETRY_ATTEMPTS - 1:
                logger.warning(
                    "Failed to delete message after retries",
                    chat_id=chat_id,
                    message_id=message_id,
                    error=str(e),
                )
                return False
            
            delay = TELEGRAM_RETRY_DELAYS[attempt]
            logger.warning(
                "Telegram API error while deleting, retrying",
                chat_id=chat_id,
                message_id=message_id,
                error=str(e),
                attempt=attempt + 1,
                delay=delay,
            )
            await asyncio.sleep(delay)
    
    return False
