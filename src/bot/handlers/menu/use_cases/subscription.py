"""Use case for showing subscription info."""

from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.logger import get_logger
from src.core.messages import get_message
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.messaging.ui.menu_ui import MenuUIService
from src.bot.handlers.menu.validators import (
    validate_user_exists,
    validate_user_has_pair,
)

logger = get_logger(__name__)


async def show_subscription_info(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    menu_ui: MenuUIService,
    subscription_status_service: SubscriptionStatusService,
) -> tuple[bool, str, InlineKeyboardMarkup | None]:
    """Show subscription information.
    
    If user has multiple active pairs, shows info for each pair separately.
    
    Args:
        callback: Callback query
        session: Database session
        settings: Settings instance
        menu_ui: MenuUIService instance
        subscription_status_service: SubscriptionStatusService instance
        
    Returns:
        Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
    """
    tg_id = callback.from_user.id

    # Validate user exists (raises UserNotFoundError if not found)
    from src.bot.validators.user import validate_user_exists
    user = await validate_user_exists(session, tg_id)

    # Get all pairs for user (handles multiple pairs)
    from src.db.repositories.pairs import PairsRepository
    from src.db.repositories.users import UsersRepository
    from src.bot.handlers.start.services.pair_service import format_partner_text
    
    pairs_repo = PairsRepository(session)
    users_repo = UsersRepository(session)
    all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
    
    if not all_pairs:
        from src.bot.exceptions import PairNotFoundError
        raise PairNotFoundError(
            tg_id=tg_id,
            message_key="MENU_NO_PAIR_ALERT",
            message=get_message("MENU_NO_PAIR_ALERT"),
        )

    # Filter active pairs (trial or active status)
    active_pairs = [
        p for p in all_pairs 
        if p.status in ("trial", "active")
    ]
    
    if not active_pairs:
        # No active pairs - show info for first pair anyway
        active_pairs = [all_pairs[0]]

    # Collect subscription info for each active pair
    subscriptions_info = []
    for pair in active_pairs:
        # Get partner info
        partner_id = pair.uid_b if pair.uid_a == user.id else pair.uid_a
        partner = await users_repo.get_by_id(partner_id)
        
        partner_nickname = pairs_repo.get_my_nickname_for_partner(pair, user.id)
        partner_text = format_partner_text(
            partner.username if partner else None,
            partner_nickname,
        )
        
        # Get subscription info using domain service
        is_trial, days_left, is_expired, tariff_name, is_lifetime = await subscription_status_service.get_subscription_info(pair)
        
        subscriptions_info.append({
            "partner_text": partner_text,
            "days_left": days_left,
            "is_trial": is_trial,
            "is_expired": is_expired,
            "tariff_name": tariff_name,
            "is_lifetime": is_lifetime,
        })

    # Build message using UI service
    if len(subscriptions_info) == 1:
        # Single pair - use simple format
        info = subscriptions_info[0]
        text = menu_ui.build_subscription_info_message(
            days_left=info["days_left"],
            is_trial=info["is_trial"],
            is_expired=info["is_expired"],
            partner_text=info["partner_text"],
            tariff_name=info.get("tariff_name"),
            is_lifetime=info.get("is_lifetime", False),
        )
    else:
        # Multiple pairs - show info for each
        text = menu_ui.build_multiple_subscriptions_info_message(subscriptions_info)
    
    keyboard = menu_ui.build_subscription_keyboard()

    return True, text, keyboard

