"""Application service for subscription management."""

from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.messaging.ui.menu_ui import MenuUIService

logger = get_logger(__name__)


class SubscriptionApplicationService:
    """Application service for subscription-related use cases.
    
    Coordinates domain services, repositories, and UI services
    to implement subscription management use cases.
    """
    
    def __init__(
        self,
        session: AsyncSession,
        subscription_status_service: SubscriptionStatusService,
        menu_ui: MenuUIService,
    ) -> None:
        """Initialize subscription application service.
        
        Args:
            session: Database session
            subscription_status_service: Domain service for subscription status
            menu_ui: UI service for menu-related messages
        """
        self._session = session
        self._subscription_status_service = subscription_status_service
        self._menu_ui = menu_ui
    
    async def show_subscription_info(
        self,
        callback: CallbackQuery,
    ) -> tuple[bool, str, InlineKeyboardMarkup | None]:
        """Show subscription information for user.
        
        If user has multiple active pairs, shows info for each pair separately.
        
        Args:
            callback: Callback query from user
            
        Returns:
            Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
            
        Raises:
            UserNotFoundError: If user is not found
            PairNotFoundError: If user has no pair
        """
        tg_id = callback.from_user.id

        # Validate user exists (raises UserNotFoundError if not found)
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id)

        # Get all pairs for user (handles multiple pairs)
        from src.db.repositories.pairs import PairsRepository
        from src.db.repositories.users import UsersRepository
        from src.bot.handlers.start.services.pair_service import format_partner_text
        
        pairs_repo = PairsRepository(self._session)
        users_repo = UsersRepository(self._session)
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
            is_trial, days_left, is_expired, tariff_name, is_lifetime = await self._subscription_status_service.get_subscription_info(pair)
            
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
            text = self._menu_ui.build_subscription_info_message(
                days_left=info["days_left"],
                is_trial=info["is_trial"],
                is_expired=info["is_expired"],
                partner_text=info["partner_text"],
                tariff_name=info.get("tariff_name"),
                is_lifetime=info.get("is_lifetime", False),
            )
        else:
            # Multiple pairs - show info for each
            text = self._menu_ui.build_multiple_subscriptions_info_message(subscriptions_info)
        
        keyboard = self._menu_ui.build_subscription_keyboard()

        return True, text, keyboard

