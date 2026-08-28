"""Container middleware for explicit dependency injection."""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.core.di.container import Container


class ContainerMiddleware(BaseMiddleware):
    """Middleware for explicit dependency injection.

    Injects dependencies into handler function parameters.
    Handlers can receive dependencies directly as function parameters:
    
    Example:
        async def handler(
            message: Message,
            session: AsyncSession,
            telegram_messenger: TelegramMessenger,
            payment_service: RobokassaService,
        ) -> None:
            ...
    """

    def __init__(self, container: Container) -> None:
        """Initialize container middleware.

        Args:
            container: Dependency injection container
        """
        super().__init__()
        self.container = container

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Inject dependencies into event context for explicit wiring."""
        # Add container to context
        data["container"] = self.container

        # Inject dependencies for explicit wiring
        # These will be automatically injected into handler function parameters
        # if the parameter name matches the key in data dict
        data["settings"] = self.container.settings
        data["session_factory"] = self.container.session_factory
        data["telegram_messenger"] = self.container.telegram_messenger
        data["payment_service"] = self.container.payment_service
        data["bot_provider"] = self.container.bot_provider
        data["redis"] = self.container.redis
        
        # Inject UI services
        from src.services.messaging.ui.admin_ui import AdminUIService
        from src.services.messaging.ui.menu_ui import MenuUIService
        from src.services.messaging.ui.payment_ui import PaymentUIService
        from src.services.messaging.ui.settings_ui import SettingsUIService
        
        data["menu_ui"] = MenuUIService(
            bot_provider=self.container.bot_provider,
            settings=self.container.settings,
        )
        data["payment_ui"] = PaymentUIService(settings=self.container.settings)
        data["settings_ui"] = SettingsUIService()
        data["admin_ui"] = AdminUIService()
        
        # Inject domain services (created per request with session)
        # These will be created in DatabaseMiddleware after session is available

        return await handler(event, data)
