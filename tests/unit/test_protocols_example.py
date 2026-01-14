"""Example tests demonstrating protocol usage for mocking.

This file demonstrates how to use protocols for dependency injection
and testing, following DIP (Dependency Inversion Principle).

Run with: pytest tests/unit/test_protocols_example.py
"""

from unittest.mock import AsyncMock, MagicMock
from typing import Optional

import pytest
from aiogram import Bot
from aiogram.types import Message, User, Chat

from src.core.protocols.bot_provider import BotProviderProtocol
from src.core.protocols.messenger import MessengerProtocol
from src.core.protocols.payment import PaymentServiceProtocol


# Example: Mock BotProviderProtocol
class MockBotProvider:
    """Mock implementation of BotProviderProtocol for testing."""
    
    def __init__(self, bot: Optional[Bot] = None):
        """Initialize mock bot provider.
        
        Args:
            bot: Optional Bot instance to provide
        """
        self._bot = bot
    
    def get_bot(self) -> Bot:
        """Get bot instance."""
        if self._bot is None:
            raise RuntimeError("Bot not initialized")
        return self._bot
    
    def has_bot(self) -> bool:
        """Check if bot is available."""
        return self._bot is not None
    
    def set_bot(self, bot: Bot) -> None:
        """Set bot instance."""
        self._bot = bot


# Example: Mock MessengerProtocol
class MockMessenger:
    """Mock implementation of MessengerProtocol for testing."""
    
    def __init__(self):
        """Initialize mock messenger."""
        self.sent_messages = []
        self.sent_photos = []
        self.edited_messages = []
        self.deleted_messages = []
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[dict] = None,
        parse_mode: Optional[str] = None,
        save_message: bool = True,
    ) -> Message:
        """Mock send_message."""
        # Avoid spec=Message here: aiogram Message fields are runtime (pydantic),
        # and strict spec can break attribute access in tests.
        message = MagicMock()
        message.chat = MagicMock(spec=Chat)
        message.chat.id = chat_id
        message.text = text
        message.message_id = len(self.sent_messages) + 1
        self.sent_messages.append({
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
            "parse_mode": parse_mode,
        })
        return message
    
    async def send_photo(
        self,
        chat_id: int,
        photo: str,
        caption: Optional[str] = None,
        reply_markup: Optional[dict] = None,
        save_message: bool = True,
    ) -> Message:
        """Mock send_photo."""
        message = MagicMock()
        message.chat = MagicMock(spec=Chat)
        message.chat.id = chat_id
        message.photo = [MagicMock(file_id=photo)]
        message.caption = caption
        message.message_id = len(self.sent_photos) + 1
        self.sent_photos.append({
            "chat_id": chat_id,
            "photo": photo,
            "caption": caption,
            "reply_markup": reply_markup,
        })
        return message
    
    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: Optional[str] = None,
        reply_markup: Optional[dict] = None,
    ) -> Optional[Message]:
        """Mock edit_message."""
        message = MagicMock()
        message.chat = MagicMock(spec=Chat)
        message.chat.id = chat_id
        message.message_id = message_id
        message.text = text
        self.edited_messages.append({
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "reply_markup": reply_markup,
        })
        return message
    
    async def remove_reply_markup(
        self,
        chat_id: int,
        message_id: int,
    ) -> Optional[Message]:
        """Mock remove_reply_markup."""
        return await self.edit_message(chat_id, message_id, reply_markup=None)
    
    async def delete_message(
        self,
        chat_id: int,
        message_id: int,
    ) -> bool:
        """Mock delete_message."""
        self.deleted_messages.append({
            "chat_id": chat_id,
            "message_id": message_id,
        })
        return True


# Example: Mock PaymentServiceProtocol
class MockPaymentService:
    """Mock implementation of PaymentServiceProtocol for testing."""
    
    def __init__(self):
        """Initialize mock payment service."""
        self.created_payments = []
        self.verified_webhooks = []
        self.processed_webhooks = []
    
    async def create_payment(
        self,
        amount: int,
        pair_id: int,
        return_url: str,
        period_days: int = 30,
        is_lifetime: bool = False,
        currency: str = "RUB",
    ) -> Optional[dict]:
        """Mock create_payment."""
        payment_data = {
            "id": f"payment_{len(self.created_payments) + 1}",
            "confirmation": {
                "confirmation_url": f"https://example.com/pay/{len(self.created_payments) + 1}",
            },
            "metadata": {
                "pair_id": pair_id,
                "period_days": period_days,
                "is_lifetime": is_lifetime,
            },
        }
        self.created_payments.append({
            "amount": amount,
            "pair_id": pair_id,
            "return_url": return_url,
            "period_days": period_days,
            "is_lifetime": is_lifetime,
            "currency": currency,
        })
        return payment_data
    
    async def verify_webhook(self, *args, **kwargs) -> bool:
        """Mock verify_webhook."""
        self.verified_webhooks.append({"args": args, "kwargs": kwargs})
        return True
    
    async def process_webhook(self, *args, **kwargs) -> Optional[dict]:
        """Mock process_webhook."""
        self.processed_webhooks.append({"args": args, "kwargs": kwargs})
        return {
            "payment_id": "test_payment_123",
            "pair_id": 1,
            "amount": "1000",
            "currency": "RUB",
            "period_days": 30,
            "is_lifetime": False,
            "status": "succeeded",
        }


# Example: Function that uses protocols (DIP compliant)
async def send_welcome_message(
    chat_id: int,
    messenger: MessengerProtocol,
) -> Message:
    """Send welcome message using messenger protocol.
    
    This function depends on MessengerProtocol, not a concrete implementation.
    This makes it easy to test with mocks.
    
    Args:
        chat_id: Telegram chat ID
        messenger: Messenger protocol implementation
        
    Returns:
        Sent message
    """
    return await messenger.send_message(
        chat_id=chat_id,
        text="Welcome!",
        parse_mode="HTML",
    )


# Example: Test using protocol mocks
@pytest.mark.asyncio
async def test_send_welcome_message_with_mock():
    """Test send_welcome_message using MockMessenger."""
    mock_messenger = MockMessenger()
    
    result = await send_welcome_message(
        chat_id=12345,
        messenger=mock_messenger,
    )
    
    assert result.chat.id == 12345
    assert result.text == "Welcome!"
    assert len(mock_messenger.sent_messages) == 1
    assert mock_messenger.sent_messages[0]["chat_id"] == 12345
    assert mock_messenger.sent_messages[0]["text"] == "Welcome!"


@pytest.mark.asyncio
async def test_mock_payment_service():
    """Test payment service protocol with mock."""
    mock_payment = MockPaymentService()
    
    payment_data = await mock_payment.create_payment(
        amount=1000,
        pair_id=1,
        return_url="https://example.com/return",
        period_days=30,
        currency="RUB",
    )
    
    assert payment_data is not None
    assert payment_data["id"].startswith("payment_")
    assert "confirmation_url" in payment_data["confirmation"]
    assert len(mock_payment.created_payments) == 1
    assert mock_payment.created_payments[0]["amount"] == 1000
    assert mock_payment.created_payments[0]["pair_id"] == 1


def test_mock_bot_provider():
    """Test bot provider protocol with mock."""
    mock_bot = MagicMock(spec=Bot)
    mock_provider = MockBotProvider(bot=mock_bot)
    
    assert mock_provider.has_bot() is True
    assert mock_provider.get_bot() == mock_bot
    
    # Test without bot
    empty_provider = MockBotProvider()
    assert empty_provider.has_bot() is False
    with pytest.raises(RuntimeError, match="Bot not initialized"):
        empty_provider.get_bot()

