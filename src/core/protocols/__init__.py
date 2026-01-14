"""Protocols for dependency injection and testing (DIP compliance).

All protocols use typing.Protocol to enable structural subtyping,
allowing easy mocking and testing without tight coupling to concrete implementations.
"""

from src.core.protocols.bot_provider import BotProviderProtocol
from src.core.protocols.messenger import MessengerProtocol
from src.core.protocols.payment import PaymentServiceProtocol

__all__ = [
    "BotProviderProtocol",
    "MessengerProtocol",
    "PaymentServiceProtocol",
]
