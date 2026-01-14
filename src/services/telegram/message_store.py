"""Message store interface and implementation for saving message IDs."""

from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger

logger = get_logger(__name__)


class MessageStore(ABC):
    """Interface for storing message IDs in database."""
    
    @abstractmethod
    async def save_message(
        self,
        chat_id: int,
        message_id: int,
    ) -> None:
        """Save message ID for cleanup.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Telegram message ID
        """
        pass


class BotMessagesMessageStore(MessageStore):
    """Implementation using BotMessagesRepository."""
    
    def __init__(self, session: AsyncSession) -> None:
        """Initialize message store.
        
        Args:
            session: Database session
        """
        self.session = session
    
    async def save_message(
        self,
        chat_id: int,
        message_id: int,
    ) -> None:
        """Save message ID using BotMessagesRepository.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Telegram message ID
        """
        try:
            from src.db.repositories.bot_messages import BotMessagesRepository
            bot_messages_repo = BotMessagesRepository(self.session)
            await bot_messages_repo.create(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.warning(
                "Failed to save message_id for cleanup",
                chat_id=chat_id,
                message_id=message_id,
                error=str(e),
            )


class NullMessageStore(MessageStore):
    """Null implementation that does nothing (for testing or when saving is disabled)."""
    
    async def save_message(
        self,
        chat_id: int,
        message_id: int,
    ) -> None:
        """Do nothing."""
        pass
