# Protocols for Dependency Injection and Testing

## Overview

This project uses Python `Protocol` types (structural subtyping) to define interfaces for key services. This approach follows the **Dependency Inversion Principle (DIP)** and makes unit testing much easier.

## Why Protocols?

1. **Dependency Inversion**: Code depends on abstractions (protocols), not concrete implementations
2. **Easy Testing**: Mock implementations can be created without inheritance
3. **Type Safety**: Type checkers (mypy, pyright) can verify protocol compliance
4. **Flexibility**: Multiple implementations can coexist without changing dependent code

## Available Protocols

### `BotProviderProtocol`

Located in `src/core/protocols/bot_provider.py`

Provides access to the Telegram Bot instance.

**Methods:**
- `get_bot() -> Bot`: Get bot instance
- `has_bot() -> bool`: Check if bot is available
- `set_bot(bot: Bot) -> None`: Set bot instance

**Usage:**
```python
from src.core.protocols.bot_provider import BotProviderProtocol

async def my_function(bot_provider: BotProviderProtocol):
    bot = bot_provider.get_bot()
    # Use bot...
```

### `MessengerProtocol`

Located in `src/core/protocols/messenger.py`

Handles Telegram message operations (send, edit, delete).

**Methods:**
- `send_message(...) -> Message`: Send text message
- `send_photo(...) -> Message`: Send photo
- `edit_message(...) -> Optional[Message]`: Edit message
- `remove_reply_markup(...) -> Optional[Message]`: Remove buttons
- `delete_message(...) -> bool`: Delete message

**Usage:**
```python
from src.core.protocols.messenger import MessengerProtocol

async def send_notification(
    chat_id: int,
    messenger: MessengerProtocol,
):
    await messenger.send_message(
        chat_id=chat_id,
        text="Hello!",
    )
```

### `PaymentServiceProtocol`

Located in `src/core/protocols/payment.py`

Handles payment operations.

**Methods:**
- `create_payment(...) -> Optional[dict]`: Create payment link
- `verify_webhook(...) -> bool`: Verify webhook signature
- `process_webhook(...) -> Optional[dict]`: Process webhook

**Usage:**
```python
from src.core.protocols.payment import PaymentServiceProtocol

async def create_subscription(
    amount: int,
    pair_id: int,
    payment_service: PaymentServiceProtocol,
):
    payment = await payment_service.create_payment(
        amount=amount,
        pair_id=pair_id,
        return_url="https://example.com/return",
    )
```

## Testing with Protocols

### Creating Mock Implementations

You can create mock implementations that conform to protocols without inheritance:

```python
from unittest.mock import MagicMock
from src.core.protocols.messenger import MessengerProtocol

class MockMessenger:
    """Mock messenger for testing."""
    
    def __init__(self):
        self.sent_messages = []
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup=None,
        parse_mode=None,
        save_message=True,
    ):
        message = MagicMock()
        message.chat.id = chat_id
        message.text = text
        self.sent_messages.append({"chat_id": chat_id, "text": text})
        return message
    
    # Implement other protocol methods...
```

### Using Mocks in Tests

```python
import pytest
from src.core.protocols.messenger import MessengerProtocol

@pytest.mark.asyncio
async def test_my_function():
    mock_messenger = MockMessenger()
    
    await my_function(messenger=mock_messenger)
    
    assert len(mock_messenger.sent_messages) == 1
    assert mock_messenger.sent_messages[0]["text"] == "Hello!"
```

### Example Test File

See `tests/unit/test_protocols_example.py` for complete examples of:
- Mock implementations for all protocols
- Test functions using mocks
- Best practices for protocol-based testing

## Benefits

1. **No Inheritance Required**: Mocks don't need to inherit from base classes
2. **Structural Typing**: Any object with matching methods works
3. **Type Checking**: IDEs and type checkers understand protocol contracts
4. **Easy Refactoring**: Change implementations without breaking tests
5. **Clear Contracts**: Protocols document expected behavior

## Migration Guide

When updating code to use protocols:

1. **Change type hints** from concrete classes to protocols:
   ```python
   # Before
   def my_function(messenger: TelegramMessenger):
       ...
   
   # After
   def my_function(messenger: MessengerProtocol):
       ...
   ```

2. **Update imports**:
   ```python
   # Before
   from src.services.telegram.messenger import TelegramMessenger
   
   # After
   from src.core.protocols.messenger import MessengerProtocol
   ```

3. **Runtime behavior unchanged**: Concrete implementations still work because they conform to protocols

## Best Practices

1. **Use protocols in function signatures**: Depend on abstractions
2. **Keep protocols minimal**: Only include methods actually used
3. **Document protocol methods**: Use docstrings to explain expected behavior
4. **Test with mocks**: Create simple mock implementations for testing
5. **Type check**: Use mypy or pyright to verify protocol compliance

