"""Telegram service module with retry logic and dependency injection support.

This module provides:
- BotProvider: Dependency injection for Bot instance
- TelegramMessenger: Message sending/editing/deleting with retry logic
- MessageStore: Interface for saving message IDs
- Retry utilities: Common retry policy for Telegram API calls

For backward compatibility, the module exports functions that maintain
the same interface as the original telegram.py module.
"""

from typing import Optional

from aiogram import Bot
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.telegram.bot_provider import (
    BotProvider,
    get_bot,
    set_bot,
    set_global_container,
    get_global_container,
)
from src.services.telegram.messenger import TelegramMessenger
from src.services.telegram.message_store import (
    BotMessagesMessageStore,
    MessageStore,
    NullMessageStore,
)

# Export for backward compatibility and new code
__all__ = [
    # Bot provider
    "BotProvider",
    "get_bot",
    "set_bot",
    "set_global_container",
    "get_global_container",
    # Messenger
    "TelegramMessenger",
    # Message store
    "MessageStore",
    "BotMessagesMessageStore",
    "NullMessageStore",
    # Backward compatibility functions
    "send_message_with_retry",
    "send_photo_with_retry",
    "edit_message_with_retry",
    "remove_reply_markup_with_retry",
    "delete_message_with_retry",
]

def _get_messenger(session: Optional[AsyncSession] = None) -> TelegramMessenger:
    """Get or create messenger instance with proper session.
    
    Args:
        session: Optional database session for message store
        
    Returns:
        TelegramMessenger instance
        
    Note:
        Creates a new messenger instance each time to ensure proper session handling.
        The bot_provider is shared (from global _bot_provider).
        If session is None, uses NullMessageStore (messages won't be saved).
    """
    from src.services.telegram.bot_provider import _bot_provider
    
    if session is not None:
        message_store: MessageStore = BotMessagesMessageStore(session)
    else:
        # Use NullMessageStore when no session provided (for backward compatibility)
        message_store = NullMessageStore()
    
    return TelegramMessenger(
        bot_provider=_bot_provider,
        message_store=message_store,
    )


async def send_message_with_retry(
    chat_id: int,
    text: str,
    reply_markup: Optional[dict] = None,
    parse_mode: Optional[str] = None,
    save_message: bool = True,
    session: Optional[AsyncSession] = None,
) -> Message:
    """Send message with retry logic (backward compatibility).
    
    Args:
        chat_id: Telegram chat ID
        text: Message text
        reply_markup: Optional inline keyboard
        parse_mode: Optional parse mode (HTML, Markdown, etc.)
        save_message: Whether to save message_id for cleanup (default: True)
        session: Optional database session for saving message_id
        
    Returns:
        Sent Message object
    """
    messenger = _get_messenger(session=session)
    return await messenger.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        save_message=save_message,
    )


async def send_photo_with_retry(
    chat_id: int,
    photo: str,  # file_id
    caption: Optional[str] = None,
    reply_markup: Optional[dict] = None,
    save_message: bool = True,
    session: Optional[AsyncSession] = None,
    pic_type: Optional[str] = None,  # Kept for compatibility, not used
) -> Message:
    """Send photo with retry logic (backward compatibility).
    
    Args:
        chat_id: Telegram chat ID
        photo: Telegram file_id
        caption: Optional photo caption
        reply_markup: Optional inline keyboard
        save_message: Whether to save message_id for cleanup (default: True)
        session: Optional database session for saving message_id
        pic_type: Picture type ("morning" or "evening") - kept for compatibility, not used
        
    Returns:
        Sent Message object
        
    Note:
        All pictures are sent via main bot (TG_BOT_TOKEN).
        file_ids are bot-specific, so we must use the same bot that uploaded them.
    """
    messenger = _get_messenger(session=session)
    return await messenger.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=caption,
        reply_markup=reply_markup,
        save_message=save_message,
    )


async def edit_message_with_retry(
    chat_id: int,
    message_id: int,
    text: Optional[str] = None,
    reply_markup: Optional[dict] = None,
) -> Optional[Message]:
    """Edit message with retry logic (backward compatibility).
    
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
    messenger = _get_messenger()
    return await messenger.edit_message(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=reply_markup,
    )


async def remove_reply_markup_with_retry(
    chat_id: int,
    message_id: int,
) -> Optional[Message]:
    """Remove reply markup (buttons) from message with retry logic (backward compatibility).
    
    Args:
        chat_id: Telegram chat ID
        message_id: Message ID to edit
        
    Returns:
        Edited Message if successful, None otherwise
    """
    messenger = _get_messenger()
    return await messenger.remove_reply_markup(
        chat_id=chat_id,
        message_id=message_id,
    )


async def delete_message_with_retry(
    chat_id: int,
    message_id: int,
) -> bool:
    """Delete message with retry logic (backward compatibility).
    
    Args:
        chat_id: Telegram chat ID
        message_id: Message ID to delete
        
    Returns:
        True if message was deleted successfully, False otherwise
    """
    messenger = _get_messenger()
    return await messenger.delete_message(
        chat_id=chat_id,
        message_id=message_id,
    )
