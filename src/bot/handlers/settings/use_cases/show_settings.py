"""Use case for showing settings."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from typing import Optional

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


async def show_settings(
    tg_id: int,
    session: AsyncSession,
    settings_ui: SettingsUIService,
    subscription_status_service: SubscriptionStatusService,
) -> tuple[bool, str, Optional[dict]]:
    """Show settings screen.
    
    Args:
        tg_id: Telegram user ID
        session: Database session
        settings_ui: SettingsUIService instance
        subscription_status_service: SubscriptionStatusService instance
        
    Returns:
        Tuple of (success: bool, message_text: str, reply_markup: dict | None)
    """
    try:
        # Validate user exists
        is_valid, user, error_msg = await validate_user_exists(session, tg_id, "SETTINGS_NO_PAIR")
        if not is_valid:
            return False, error_msg, None
        
        # Get pairs and find first active
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
        
        # Check if subscription is active (trial or active)
        is_active = await subscription_status_service.is_subscription_active(pair)
        
        # Get current mode text
        mode_text = (
            get_message("SETTINGS_MODE_CHAT")
            if pair.mode == "chat"
            else get_message("SETTINGS_MODE_SILENT")
        )
        
        # Get nickname that user gave to partner (not what partner gave to user)
        partner_nickname = pairs_repo.get_my_nickname_for_partner(pair, user.id)
        nickname_text = partner_nickname if partner_nickname else "не установлено"
        
        # Build message and keyboard using UI service
        text = settings_ui.build_settings_message(
            mode_text=mode_text,
            nickname_text=nickname_text,
        )
        keyboard = settings_ui.build_settings_keyboard(
            pair_mode=pair.mode,
            is_active=is_active,
        )
        
        return True, text, keyboard.model_dump()
    except Exception as e:
        logger.error(
            "Error in show_settings",
            tg_id=tg_id,
            error=str(e),
            exc_info=True,
        )
        return False, get_message("SETTINGS_ERROR"), None

