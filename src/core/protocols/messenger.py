"""Protocol for Telegram messenger."""

from typing import Optional, Protocol

from aiogram.types import Message


class MessengerProtocol(Protocol):
    """Protocol for Telegram message operations.
    
    This protocol allows easy mocking and testing of code that sends messages.
    Implementations should handle retry logic and message storage internally.
    """
    
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
        ...
    
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
        """
        ...
    
    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: Optional[str] = None,
        reply_markup: Optional[dict] = None,
    ) -> Optional[Message]:
        """Edit message with retry logic.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Message ID to edit
            text: Optional new text
            reply_markup: Optional new reply markup
            
        Returns:
            Edited Message if successful, None otherwise
        """
        ...
    
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
        ...
    
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
        ...

