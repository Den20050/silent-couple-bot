"""Application service for menu operations."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.protocols.bot_provider import BotProviderProtocol
from src.services.messaging.ui.menu_ui import MenuUIService

logger = get_logger(__name__)


class MenuApplicationService:
    """Application service for menu-related use cases.
    
    Coordinates domain services, repositories, and UI services
    to implement menu operations.
    """
    
    def __init__(
        self,
        session: AsyncSession,
        menu_ui: MenuUIService,
    ) -> None:
        """Initialize menu application service.
        
        Args:
            session: Database session (unused, kept for consistency)
            menu_ui: UI service for menu-related messages
        """
        self._session = session
        self._menu_ui = menu_ui
    
    async def show_share_menu(self) -> tuple[bool, str, dict | None]:
        """Show share bot menu.
        
        Returns:
            Tuple of (success: bool, message_text: str, keyboard: dict | None)
        """
        try:
            text, share_url = await self._menu_ui.build_share_menu_message()
            keyboard = self._menu_ui.build_share_menu_keyboard(share_url)
            
            return True, text, keyboard.model_dump()
        except Exception as e:
            logger.error(
                "Error in show_share_menu",
                error=str(e),
                exc_info=True,
            )
            from src.core.messages import get_message
            return False, get_message("MENU_ERROR"), None
    
    async def show_share_copy(self) -> tuple[bool, str, dict | None]:
        """Show bot link for copying.
        
        Returns:
            Tuple of (success: bool, message_text: str, keyboard: dict | None)
        """
        try:
            bot = self._menu_ui._bot_provider.get_bot()
            bot_info = await bot.get_me()
            bot_username = bot_info.username
            
            if not bot_username:
                bot_id = bot_info.id
                bot_url = f"https://t.me/bot{bot_id}"
            else:
                bot_url = f"https://t.me/{bot_username}"
            
            text = self._menu_ui.build_share_copy_message(bot_url)
            keyboard = await self._menu_ui.build_share_copy_keyboard()
            
            return True, text, keyboard.model_dump()
        except Exception as e:
            logger.error(
                "Error in show_share_copy",
                error=str(e),
                exc_info=True,
            )
            from src.core.messages import get_message
            return False, get_message("MENU_ERROR"), None

