"""Application service for settings management."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.pairs import PairsRepository
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.messaging.ui.settings_ui import SettingsUIService

logger = get_logger(__name__)


class SettingsApplicationService:
    """Application service for settings-related use cases.
    
    Coordinates domain services, repositories, and UI services
    to implement settings management use cases.
    """
    
    def __init__(
        self,
        session: AsyncSession,
        subscription_status_service: SubscriptionStatusService,
        settings_ui: SettingsUIService,
    ) -> None:
        """Initialize settings application service.
        
        Args:
            session: Database session
            subscription_status_service: Domain service for subscription status
            settings_ui: UI service for settings-related messages
        """
        self._session = session
        self._subscription_status_service = subscription_status_service
        self._settings_ui = settings_ui
        self._pairs_repo = PairsRepository(session)
    
    async def show_settings(
        self,
        tg_id: int,
    ) -> tuple[bool, str, Optional[dict]]:
        """Show settings screen.
        
        If user has multiple active pairs, shows pair selection screen.
        If user has single active pair, shows settings directly.
        
        Args:
            tg_id: Telegram user ID
            
        Returns:
            Tuple of (success: bool, message_text: str, reply_markup: dict | None)
        """
        # Validate user exists (raises UserNotFoundError if not found)
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id, "SETTINGS_NO_PAIR")
        
        # Get all pairs for user
        all_pairs = await self._pairs_repo.get_all_by_user_tg_id(tg_id)
        
        if not all_pairs:
            from src.bot.exceptions import PairNotFoundError
            raise PairNotFoundError(
                tg_id=tg_id,
                message_key="SETTINGS_NO_PAIR",
                message=get_message("SETTINGS_NO_PAIR"),
            )
        
        # Filter active pairs (trial or active status)
        active_pairs = [
            p for p in all_pairs
            if p.status in ("trial", "active")
        ]
        
        # If no active pairs, check if we have any pairs with active subscription
        if not active_pairs:
            # Check subscriptions for all pairs
            for pair in all_pairs:
                if await self._subscription_status_service.is_subscription_active(pair):
                    active_pairs.append(pair)
        
        # If still no active pairs, use first pair (will show subscription expired message)
        if not active_pairs:
            active_pairs = [all_pairs[0]]
        
        # If user has multiple active pairs, show pair selection
        if len(active_pairs) > 1:
            from src.bot.handlers.start.services.pair_service import format_partner_text
            from src.db.repositories.users import UsersRepository

            users_repo = UsersRepository(self._session)
            pairs_with_labels: list[tuple[Pair, str]] = []
            for pair in active_pairs:
                partner_id = pair.uid_b if pair.uid_a == user.id else pair.uid_a
                partner = await users_repo.get_by_id(partner_id)
                nickname = self._pairs_repo.get_my_nickname_for_partner(pair, user.id)
                partner_text = format_partner_text(
                    partner.username if partner else None,
                    nickname,
                )
                pairs_with_labels.append((pair, partner_text))
            
            text = "Выберите пару для настройки:"
            keyboard = self._settings_ui.build_pair_selection_keyboard(pairs_with_labels)
            return True, text, keyboard.model_dump()
        
        # Single active pair - show settings directly
        pair = active_pairs[0]
        return await self.show_settings_for_pair(tg_id, pair.id)
    
    async def show_settings_for_pair(
        self,
        tg_id: int,
        pair_id: int,
    ) -> tuple[bool, str, Optional[dict]]:
        """Show settings screen for specific pair.
        
        Args:
            tg_id: Telegram user ID
            pair_id: Pair ID
            
        Returns:
            Tuple of (success: bool, message_text: str, reply_markup: dict | None)
        """
        # Validate user exists
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id, "SETTINGS_NO_PAIR")
        
        # Get pair
        pair = await self._pairs_repo.get_by_id(pair_id)
        if not pair:
            from src.bot.exceptions import PairNotFoundError
            raise PairNotFoundError(
                tg_id=tg_id,
                message_key="SETTINGS_NO_PAIR",
                message=get_message("SETTINGS_NO_PAIR"),
            )
        
        # Validate pair access
        from src.bot.validators.pair import validate_pair_access
        await validate_pair_access(self._session, pair, user.id, tg_id)
        
        # Validate subscription is active (raises SubscriptionExpiredError if expired)
        from src.bot.validators.subscription import validate_subscription_active
        await validate_subscription_active(self._session, pair, show_pay_button=True)
        
        # Check if subscription is active (trial or active)
        is_active = await self._subscription_status_service.is_subscription_active(pair)
        
        # Get current mode text
        mode_text = (
            get_message("SETTINGS_MODE_CHAT")
            if pair.mode == "chat"
            else get_message("SETTINGS_MODE_SILENT")
        )
        
        # Get nickname that user gave to partner (not what partner gave to user)
        partner_nickname = self._pairs_repo.get_my_nickname_for_partner(pair, user.id)
        nickname_text = partner_nickname if partner_nickname else "не установлено"
        
        # Build message and keyboard using UI service
        text = self._settings_ui.build_settings_message(
            mode_text=mode_text,
            nickname_text=nickname_text,
        )
        keyboard = self._settings_ui.build_settings_keyboard(
            pair_mode=pair.mode,
            is_active=is_active,
            pair_id=pair_id,
        )
        
        return True, text, keyboard.model_dump()
    
    async def show_mode_selection(
        self,
        tg_id: int,
        pair_id: int | None = None,
    ) -> tuple[bool, str, Optional[dict]]:
        """Show mode selection screen.
        
        Args:
            tg_id: Telegram user ID
            pair_id: Pair ID (optional, if None will use first active pair)
            
        Returns:
            Tuple of (success: bool, message_text: str, reply_markup: dict | None)
        """
        # Validate user exists
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id, "SETTINGS_NO_PAIR")
        
        # Get pair
        if pair_id:
            pair = await self._pairs_repo.get_by_id(pair_id)
            if not pair:
                from src.bot.exceptions import PairNotFoundError
                raise PairNotFoundError(
                    tg_id=tg_id,
                    message_key="SETTINGS_NO_PAIR",
                    message=get_message("SETTINGS_NO_PAIR"),
                )
            # Validate pair access
            from src.bot.validators.pair import validate_pair_access
            await validate_pair_access(self._session, pair, user.id, tg_id)
        else:
            # Get first active pair if pair_id not provided
            from src.bot.validators.pair import validate_user_has_any_pair
            all_pairs = await validate_user_has_any_pair(self._session, tg_id, "SETTINGS_NO_PAIR")
            pair = await self._subscription_status_service.get_first_active_pair(all_pairs)
            if not pair:
                from src.bot.exceptions import PairNotFoundError
                raise PairNotFoundError(
                    tg_id=tg_id,
                    message_key="SETTINGS_NO_PAIR",
                    message=get_message("SETTINGS_NO_PAIR"),
                )
        
        # Validate subscription is active
        from src.bot.validators.subscription import validate_subscription_active
        await validate_subscription_active(self._session, pair, show_pay_button=True)
        
        # Check if subscription is active
        if not await self._subscription_status_service.is_subscription_active(pair):
            from src.bot.exceptions import SubscriptionExpiredError
            raise SubscriptionExpiredError(
                pair_id=pair.id,
                message_key="SETTINGS_SUBSCRIPTION_EXPIRED",
                reply_markup=self._settings_ui.build_pay_keyboard().model_dump(),
            )
        
        text = "Выберите режим общения:"
        keyboard = self._settings_ui.build_mode_selection_keyboard(pair_id=pair.id)
        
        return True, text, keyboard.model_dump()
    
    async def update_pair_mode(
        self,
        tg_id: int,
        selected_mode: str,
        pair_id: int | None = None,
    ) -> tuple[bool, str, Optional[dict]]:
        """Update pair mode.
        
        Args:
            tg_id: Telegram user ID
            selected_mode: Selected mode ("chat" or "silent")
            pair_id: Pair ID (optional, if None will use first active pair)
            
        Returns:
            Tuple of (success: bool, message_text: str, reply_markup: dict | None)
        """
        # Validate mode
        from src.bot.validators.mode import validate_mode
        validate_mode(selected_mode, "SETTINGS_ERROR")
        
        # Validate user exists
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id, "SETTINGS_NO_PAIR")
        
        # Get pair
        if pair_id:
            pair = await self._pairs_repo.get_by_id(pair_id)
            if not pair:
                from src.bot.exceptions import PairNotFoundError
                raise PairNotFoundError(
                    tg_id=tg_id,
                    message_key="SETTINGS_NO_PAIR",
                    message=get_message("SETTINGS_NO_PAIR"),
                )
            # Validate pair access
            from src.bot.validators.pair import validate_pair_access
            await validate_pair_access(self._session, pair, user.id, tg_id)
        else:
            # Get first active pair if pair_id not provided
            from src.bot.validators.pair import validate_user_has_any_pair
            all_pairs = await validate_user_has_any_pair(self._session, tg_id, "SETTINGS_NO_PAIR")
            pair = await self._subscription_status_service.get_first_active_pair(all_pairs)
            if not pair:
                from src.bot.exceptions import PairNotFoundError
                raise PairNotFoundError(
                    tg_id=tg_id,
                    message_key="SETTINGS_NO_PAIR",
                    message=get_message("SETTINGS_NO_PAIR"),
                )
        
        # Validate subscription is active
        from src.bot.validators.subscription import validate_subscription_active
        await validate_subscription_active(self._session, pair, show_pay_button=True)
        
        # Check if subscription is active
        if not await self._subscription_status_service.is_subscription_active(pair):
            from src.bot.exceptions import SubscriptionExpiredError
            raise SubscriptionExpiredError(
                pair_id=pair.id,
                message_key="SETTINGS_SUBSCRIPTION_EXPIRED",
                reply_markup=self._settings_ui.build_pay_keyboard().model_dump(),
            )
        
        # Update mode
        await self._pairs_repo.update_mode(pair.id, selected_mode)
        await self._session.commit()
        
        # Refresh pair to get updated mode
        refreshed_pair = await self._pairs_repo.get_by_id(pair.id)
        if not refreshed_pair:
            from src.bot.exceptions import BusinessLogicError
            raise BusinessLogicError(
                message_key="SETTINGS_ERROR",
                message=get_message("SETTINGS_ERROR"),
            )
        
        # Get updated mode text
        refreshed_mode_text = (
            get_message("SETTINGS_MODE_CHAT")
            if refreshed_pair.mode == "chat"
            else get_message("SETTINGS_MODE_SILENT")
        )
        
        partner_nickname = self._pairs_repo.get_my_nickname_for_partner(refreshed_pair, user.id)
        nickname_text = partner_nickname if partner_nickname else "не установлено"
        
        # Build message and keyboard using UI service
        text = self._settings_ui.build_settings_message(
            mode_text=refreshed_mode_text,
            nickname_text=nickname_text,
        )
        keyboard = self._settings_ui.build_settings_keyboard(
            pair_mode=refreshed_pair.mode,
            is_active=True,  # We already checked it's active
            pair_id=pair.id,
        )
        
        return True, text, keyboard.model_dump()
    
    async def show_partner_selection_for_nickname(
        self,
        tg_id: int,
    ) -> tuple[bool, str, Optional[dict], Optional[tuple[int, int]]]:
        """Show partner selection screen for nickname change.
        
        Args:
            tg_id: Telegram user ID
            
        Returns:
            Tuple of (success: bool, message_text: str, reply_markup: dict | None, state_data: tuple[pair_id, user_id] | None)
            state_data is returned only if single pair (for FSM state setup)
        """
        # Validate user exists
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id, "SETTINGS_NO_PAIR")
        
        # Validate user has pairs
        from src.bot.validators.pair import validate_user_has_any_pair
        all_pairs = await validate_user_has_any_pair(self._session, tg_id, "SETTINGS_NO_PAIR")
        
        # If single pair, proceed directly to nickname input
        if len(all_pairs) == 1:
            pair = all_pairs[0]
            
            # Validate subscription is active
            from src.bot.validators.subscription import validate_subscription_active
            await validate_subscription_active(self._session, pair, show_pay_button=True)
            
            # Check if subscription is active
            if not await self._subscription_status_service.is_subscription_active(pair):
                from src.bot.exceptions import SubscriptionExpiredError
                raise SubscriptionExpiredError(
                    pair_id=pair.id,
                    message_key="SETTINGS_SUBSCRIPTION_EXPIRED",
                    reply_markup=self._settings_ui.build_pay_keyboard().model_dump(),
                )
            
            # Get current nickname
            current_nickname = self._pairs_repo.get_my_nickname_for_partner(pair, user.id)
            
            # Build message and keyboard
            text = self._settings_ui.build_nickname_input_message(current_nickname)
            keyboard = self._settings_ui.build_nickname_input_keyboard()
            
            # Return state data for FSM
            return True, text, keyboard.model_dump(), (pair.id, user.id)
        
        # Multiple pairs - show partner selection
        # Build partner labels with username and current nickname (if any)
        from src.bot.handlers.start.services.pair_service import format_partner_text
        from src.db.repositories.users import UsersRepository

        users_repo = UsersRepository(self._session)
        pairs_with_labels: list[tuple[Pair, str]] = []
        for pair in all_pairs:
            partner_id = pair.uid_b if pair.uid_a == user.id else pair.uid_a
            partner = await users_repo.get_by_id(partner_id)
            nickname = self._pairs_repo.get_my_nickname_for_partner(pair, user.id)
            partner_text = format_partner_text(
                partner.username if partner else None,
                nickname,
            )
            pairs_with_labels.append((pair, partner_text))
        
        text = "Выберите партнёра, для которого хотите изменить имя:"
        keyboard = self._settings_ui.build_partner_selection_keyboard(pairs_with_labels)
        
        return True, text, keyboard.model_dump(), None
    
    async def show_nickname_input_for_pair(
        self,
        tg_id: int,
        pair_id: int,
    ) -> tuple[bool, str, Optional[dict]]:
        """Show nickname input prompt for specific pair.
        
        Args:
            tg_id: Telegram user ID
            pair_id: Pair ID
            
        Returns:
            Tuple of (success: bool, message_text: str, reply_markup: dict | None)
        """
        # Validate user exists
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id, "SETTINGS_NO_PAIR")
        
        # Validate pair exists
        from src.bot.validators.pair import validate_pair_exists
        pair = await validate_pair_exists(self._session, pair_id, "SETTINGS_NO_PAIR")
        
        # Validate pair access
        from src.bot.validators.pair import validate_pair_access
        await validate_pair_access(self._session, pair, user.id, tg_id)
        
        # Validate subscription is active
        from src.bot.validators.subscription import validate_subscription_active
        await validate_subscription_active(self._session, pair, show_pay_button=True)
        
        # Check if subscription is active
        if not await self._subscription_status_service.is_subscription_active(pair):
            from src.bot.exceptions import SubscriptionExpiredError
            raise SubscriptionExpiredError(
                pair_id=pair.id,
                message_key="SETTINGS_SUBSCRIPTION_EXPIRED",
                reply_markup=self._settings_ui.build_pay_keyboard().model_dump(),
            )
        
        # Get current nickname
        current_nickname = self._pairs_repo.get_my_nickname_for_partner(pair, user.id)
        
        # Build message and keyboard
        text = self._settings_ui.build_nickname_input_message(current_nickname)
        keyboard = self._settings_ui.build_nickname_input_keyboard()
        
        return True, text, keyboard.model_dump()
    
    async def update_nickname(
        self,
        tg_id: int,
        pair_id: int,
        nickname: str | None,
    ) -> tuple[bool, str, Optional[dict]]:
        """Update partner nickname.
        
        Args:
            tg_id: Telegram user ID
            pair_id: Pair ID
            nickname: New nickname (None to clear)
            
        Returns:
            Tuple of (success: bool, message_text: str, reply_markup: dict | None)
        """
        # Validate user exists
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id, "SETTINGS_NO_PAIR")
        
        # Validate pair exists
        from src.bot.validators.pair import validate_pair_exists
        pair = await validate_pair_exists(self._session, pair_id, "SETTINGS_NO_PAIR")
        
        # Validate pair access
        from src.bot.validators.pair import validate_pair_access
        await validate_pair_access(self._session, pair, user.id, tg_id)
        
        # Validate nickname format if provided
        if nickname is not None:
            from src.bot.validators.nickname import validate_nickname_format
            nickname = nickname.strip()
            validate_nickname_format(nickname)
        
        # Update nickname
        if nickname is None:
            updated_pair = await self._pairs_repo.clear_nickname(pair_id, user.id)
        else:
            updated_pair = await self._pairs_repo.set_nickname(pair_id, user.id, nickname)
        
        if not updated_pair:
            from src.bot.exceptions import BusinessLogicError
            raise BusinessLogicError(
                message_key="SETTINGS_ERROR",
                message=get_message("SETTINGS_ERROR"),
            )
        
        # Commit changes to database
        await self._session.commit()
        
        # Refresh pair from database to verify changes were saved
        await self._session.refresh(updated_pair)
        
        # Get updated nickname for confirmation
        updated_nickname = self._pairs_repo.get_my_nickname_for_partner(updated_pair, user.id)
        nickname_text = updated_nickname if updated_nickname else "не установлено"
        
        logger.info(
            "Nickname update committed",
            tg_id=tg_id,
            pair_id=pair_id,
            user_id=user.id,
            nickname=nickname,
            saved_nickname=updated_nickname,
            nickname_text=nickname_text,
        )
        
        # Get mode text
        mode_text = (
            get_message("SETTINGS_MODE_CHAT")
            if updated_pair.mode == "chat"
            else get_message("SETTINGS_MODE_SILENT")
        )
        
        # Build message and keyboard
        text = self._settings_ui.build_settings_message(
            mode_text=mode_text,
            nickname_text=nickname_text,
        )
        keyboard = self._settings_ui.build_settings_keyboard(
            pair_mode=updated_pair.mode,
            is_active=True,
            pair_id=pair_id,
        )
        
        logger.info(
            "Nickname updated",
            tg_id=tg_id,
            pair_id=pair_id,
            user_id=user.id,
            nickname=nickname,
        )
        
        return True, text, keyboard.model_dump()

