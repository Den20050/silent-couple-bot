"""Use case for sharing bot."""

from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.services.messaging.ui.menu_ui import MenuUIService

logger = get_logger(__name__)


async def show_share_menu(
    callback: CallbackQuery,
    session: AsyncSession,  # noqa: ARG001
    menu_ui: MenuUIService,
) -> tuple[bool, str, InlineKeyboardMarkup | None]:
    """Show share bot menu.
    
    Args:
        callback: Callback query
        session: Database session (unused)
        menu_ui: MenuUIService instance
        
    Returns:
        Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
    """
    try:
        text, share_url = await menu_ui.build_share_menu_message()
        keyboard = menu_ui.build_share_menu_keyboard(share_url)
        
        return True, text, keyboard
    except Exception as e:
        logger.error(
            "Error in show_share_menu",
            error=str(e),
            exc_info=True,
        )
        return False, get_message("MENU_ERROR"), None


async def show_share_copy(
    callback: CallbackQuery,
    session: AsyncSession,  # noqa: ARG001
    menu_ui: MenuUIService,
) -> tuple[bool, str, InlineKeyboardMarkup | None]:
    """Show bot link for copying.
    
    Args:
        callback: Callback query
        session: Database session (unused)
        menu_ui: MenuUIService instance
        
    Returns:
        Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
    """
    try:
        bot = menu_ui._bot_provider.get_bot()
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        if not bot_username:
            bot_id = bot_info.id
            bot_url = f"https://t.me/bot{bot_id}"
        else:
            bot_url = f"https://t.me/{bot_username}"
        
        text = menu_ui.build_share_copy_message(bot_url)
        keyboard = await menu_ui.build_share_copy_keyboard()
        
        return True, text, keyboard
    except Exception as e:
        logger.error(
            "Error in show_share_copy",
            error=str(e),
            exc_info=True,
        )
        return False, get_message("MENU_ERROR"), None

