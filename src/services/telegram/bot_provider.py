"""Bot instance provider with dependency injection support."""

from typing import Optional, TYPE_CHECKING

from aiogram import Bot

from src.core.logger import get_logger
from src.core.protocols.bot_provider import BotProviderProtocol

if TYPE_CHECKING:
    from src.core.di.container import Container

logger = get_logger(__name__)

# Global container reference for accessing dependencies
_global_container: Optional["Container"] = None


def set_global_container(container: "Container") -> None:
    """Set global container reference.
    
    Args:
        container: Container instance
    """
    global _global_container
    _global_container = container


def get_global_container() -> Optional["Container"]:
    """Get global container reference.
    
    Returns:
        Container instance if set, None otherwise
    """
    return _global_container


class BotProvider:
    """Provides Bot instance via dependency injection.
    
    Replaces global singleton pattern with explicit dependency injection.
    Bot instance should be set during application initialization.
    
    Implements BotProviderProtocol for testing and dependency inversion.
    Protocol compliance is verified through structural subtyping (duck typing).
    """
    
    def __init__(self) -> None:
        """Initialize bot provider."""
        self._bot: Optional[Bot] = None
    
    def set_bot(self, bot: Bot) -> None:
        """Set bot instance.
        
        Args:
            bot: Bot instance to provide
        """
        self._bot = bot
        logger.info("Bot instance set in BotProvider")
    
    def get_bot(self) -> Bot:
        """Get bot instance.
        
        Returns:
            Bot instance
            
        Raises:
            RuntimeError: If bot is not initialized
        """
        if self._bot is None:
            raise RuntimeError("Bot not initialized. Call set_bot() first.")
        return self._bot
    
    def has_bot(self) -> bool:
        """Check if bot instance is available.
        
        Returns:
            True if bot is initialized, False otherwise
        """
        return self._bot is not None


# Global provider instance (can be replaced with DI container in future)
_bot_provider = BotProvider()


def get_bot() -> Bot:
    """Get bot instance from global provider.
    
    This function maintains backward compatibility with existing code.
    For new code, prefer injecting BotProvider directly.
    
    Returns:
        Bot instance
        
    Raises:
        RuntimeError: If bot is not initialized
    """
    return _bot_provider.get_bot()


def set_bot(bot: Bot) -> None:
    """Set bot instance in global provider.
    
    This function maintains backward compatibility with existing code.
    For new code, prefer injecting BotProvider directly.
    
    Args:
        bot: Bot instance to set
    """
    _bot_provider.set_bot(bot)
