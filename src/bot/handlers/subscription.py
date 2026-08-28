"""Subscription command handler."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.messages import get_message
from src.core.logger import get_logger
from src.db.repositories.users import UsersRepository
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.messaging.ui.menu_ui import MenuUIService
from src.services.messaging.user_command_session import track_user_command

logger = get_logger(__name__)

router = Router(name="subscription")


@router.message(Command("subscription"))
async def cmd_subscription(
    message: Message,
    session: AsyncSession,
    subscription_status_service: SubscriptionStatusService,
    menu_ui: MenuUIService,
) -> None:
    """Handle /subscription command."""
    try:
        tg_id = message.from_user.id

        # Validate user exists
        users_repo = UsersRepository(session)
        user = await users_repo.get_by_tg_id(tg_id)
        if not user:
            await message.answer(get_message("SUBSCRIPTION_START_REQUIRED"))
            return

        await track_user_command(message)

        # Get all pairs for user (handles multiple pairs)
        from src.db.repositories.pairs import PairsRepository
        from src.bot.handlers.start.services.pair_service import format_partner_text
        
        pairs_repo = PairsRepository(session)
        all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
        
        if not all_pairs:
            await message.answer(get_message("SUBSCRIPTION_NO_PAIR"))
            return

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

        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(
            "Error in cmd_subscription", error=str(e), exc_info=True
        )
        await message.answer(get_message("MENU_ERROR"))


