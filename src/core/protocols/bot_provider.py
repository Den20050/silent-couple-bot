"""Protocol for bot provider."""

from typing import Protocol

from aiogram import Bot


class BotProviderProtocol(Protocol):
    """Protocol for bot instance provider.
    
    This protocol allows easy mocking and testing of code that depends on Bot.
    Implementations should provide Bot instance via dependency injection.
    """
    
    def get_bot(self) -> Bot:
        """Get bot instance.
        
        Returns:
            Bot instance
            
        Raises:
            RuntimeError: If bot is not initialized
        """
        ...
    
    def has_bot(self) -> bool:
        """Check if bot instance is available.
        
        Returns:
            True if bot is initialized, False otherwise
        """
        ...
    
    def set_bot(self, bot: Bot) -> None:
        """Set bot instance.
        
        Args:
            bot: Bot instance to provide
        """
        ...

