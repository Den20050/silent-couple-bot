"""Admin command handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.logger import get_logger
from src.core.messages import get_message
from src.bot.handlers.admin.utils import is_admin
from src.services.application.admin import AdminApplicationService

logger = get_logger(__name__)

router = Router(name="admin_commands")


@router.message(Command("admin"))
async def cmd_admin(
    message: Message,
    settings: Settings,
    admin_application_service: AdminApplicationService,
) -> None:
    """Show admin statistics (admin only)."""
    if not is_admin(message.from_user.id, settings):
        await message.answer(get_message("MENU_ADMIN_ONLY"))
        return

    try:
        success, stats_message = await admin_application_service.get_statistics()

        if success:
            await message.answer(stats_message, parse_mode="HTML")
        else:
            await message.answer(stats_message)
    except Exception as e:
        logger.error("Error getting admin statistics", error=str(e), exc_info=True)
        await message.answer(get_message("ADMIN_STATS_ERROR"))
        raise


@router.message(Command("reset_demo"))
async def cmd_reset_demo(
    message: Message,
    settings: Settings,
    admin_application_service: AdminApplicationService,
) -> None:
    """Reset demo mode for user (admin only)."""
    if not is_admin(message.from_user.id, settings):
        await message.answer(get_message("MENU_ADMIN_ONLY"))
        return

    try:
        # Get tg_id from command args or use message sender
        args = message.text.split()[1:] if message.text else []

        if not args:
            admin_id = message.from_user.id
            await message.answer(
                get_message("ADMIN_RESET_DEMO_USAGE", admin_id=admin_id)
            )
            return

        try:
            tg_id = int(args[0])
        except ValueError:
            await message.answer(get_message("ADMIN_INVALID_TG_ID_FORMAT"))
            return

        success, message_text = await admin_application_service.reset_demo_for_user(tg_id=tg_id)
        
        await message.answer(message_text)
        
        if not success:
            # Error message already included in message_text
            return
    except Exception as e:
        logger.error("Error resetting demo", error=str(e), exc_info=True)
        await message.answer(get_message("ADMIN_RESET_DEMO_ERROR"))
        raise

