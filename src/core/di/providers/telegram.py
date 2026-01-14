"""Telegram service providers."""

from src.services.telegram.bot_provider import BotProvider
from src.services.telegram.messenger import TelegramMessenger
from src.services.telegram.message_store import BotMessagesMessageStore, MessageStore
from src.core.protocols.bot_provider import BotProviderProtocol
from src.core.protocols.messenger import MessengerProtocol


def provide_bot_provider() -> BotProviderProtocol:
    """Provide bot provider.

    Returns:
        BotProviderProtocol implementation
    """
    return BotProvider()


def provide_telegram_messenger(
    bot_provider: BotProviderProtocol,
    session_factory,
) -> MessengerProtocol:
    """Provide Telegram messenger.

    Args:
        bot_provider: Bot provider instance (protocol-compatible)
        session_factory: Database session factory

    Returns:
        MessengerProtocol implementation
    """
    # Create message store wrapper that gets session from factory when needed
    class SessionMessageStore(MessageStore):
        """Message store that gets session from factory."""
        
        async def save_message(
            self,
            chat_id: int,
            message_id: int,
        ) -> None:
            """Save message using session from factory."""
            async with session_factory() as session:
                store = BotMessagesMessageStore(session)
                await store.save_message(chat_id, message_id)
    
    message_store = SessionMessageStore()
    return TelegramMessenger(
        bot_provider=bot_provider,
        message_store=message_store,
    )

