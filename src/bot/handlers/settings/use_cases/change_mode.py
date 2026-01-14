"""Use case for changing pair mode."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.messaging.ui.settings_ui import SettingsUIService
from src.bot.handlers.settings.validators import (
    validate_user_exists,
    validate_subscription_active,
)

logger = get_logger(__name__)


async def show_mode_selection(
    tg_id: int,
    session: AsyncSession,
    settings_ui: SettingsUIService,
    subscription_status_service: SubscriptionStatusService,
) -> tuple[bool, str, dict | None]:
    """Show mode selection screen.
    
    Args:
        tg_id: Telegram user ID
        session: Database session
        
    Returns:
        Tuple of (success: bool, message_text: str, reply_markup: dict | None)
    """
    try:
        pairs_repo = PairsRepository(session)
        all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
        pair = await subscription_status_service.get_first_active_pair(all_pairs)
        
        if not pair:
            return False, get_message("SETTINGS_NO_PAIR"), None
        
        # Validate subscription is active
        is_valid, error_msg, reply_markup = await validate_subscription_active(
            session, pair, show_pay_button=True
        )
        if not is_valid:
            return False, error_msg, reply_markup
        
        # Check if subscription is active
        if not await subscription_status_service.is_subscription_active(pair):
            return False, "Подписка неактивна", None
        
        text = "Выберите режим общения:"
        keyboard = settings_ui.build_mode_selection_keyboard()
        
        return True, text, keyboard.model_dump()
    except Exception as e:
        logger.error(
            "Error in show_mode_selection",
            tg_id=tg_id,
            error=str(e),
            exc_info=True,
        )
        return False, get_message("SETTINGS_ERROR"), None


async def update_pair_mode(
    tg_id: int,
    selected_mode: str,
    session: AsyncSession,
    settings_ui: SettingsUIService,
    subscription_status_service: SubscriptionStatusService,
) -> tuple[bool, str, dict | None]:
    """Update pair mode.
    
    Args:
        tg_id: Telegram user ID
        selected_mode: Selected mode ("chat" or "silent")
        session: Database session
        
    Returns:
        Tuple of (success: bool, message_text: str, reply_markup: dict | None)
    """
    try:
        if selected_mode not in ["chat", "silent"]:
            return False, get_message("SETTINGS_ERROR"), None
        
        pairs_repo = PairsRepository(session)
        all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
        pair = await subscription_status_service.get_first_active_pair(all_pairs)
        
        if not pair:
            return False, get_message("SETTINGS_NO_PAIR"), None
        
        # Validate subscription is active
        is_valid, error_msg, reply_markup = await validate_subscription_active(
            session, pair, show_pay_button=True
        )
        if not is_valid:
            return False, error_msg, reply_markup
        
        # Check if subscription is active
        if not await subscription_status_service.is_subscription_active(pair):
            return False, "Подписка неактивна", None
        
        # Update mode
        await pairs_repo.update_mode(pair.id, selected_mode)
        await session.commit()
        
        # Refresh pair to get updated mode
        refreshed_pair = await pairs_repo.get_by_id(pair.id)
        if not refreshed_pair:
            return False, get_message("SETTINGS_ERROR"), None
        
        # Get updated mode text
        refreshed_mode_text = (
            get_message("SETTINGS_MODE_CHAT")
            if refreshed_pair.mode == "chat"
            else get_message("SETTINGS_MODE_SILENT")
        )
        
        # Get partner nickname for display
        is_valid, user, error_msg = await validate_user_exists(session, tg_id, "SETTINGS_NO_PAIR")
        if not is_valid:
            return False, error_msg, None
        
        partner_nickname = pairs_repo.get_my_nickname_for_partner(refreshed_pair, user.id)
        nickname_text = partner_nickname if partner_nickname else "не установлено"
        
        # Build message and keyboard using UI service
        text = settings_ui.build_settings_message(
            mode_text=refreshed_mode_text,
            nickname_text=nickname_text,
        )
        keyboard = settings_ui.build_settings_keyboard(
            pair_mode=refreshed_pair.mode,
            is_active=True,  # We already checked it's active
        )
        
        return True, text, keyboard.model_dump()
    except Exception as e:
        logger.error(
            "Error in update_pair_mode",
            tg_id=tg_id,
            selected_mode=selected_mode,
            error=str(e),
            exc_info=True,
        )
        await session.rollback()
        return False, get_message("SETTINGS_ERROR"), None

