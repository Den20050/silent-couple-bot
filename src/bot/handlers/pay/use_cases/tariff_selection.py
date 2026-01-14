"""Use case for showing tariff selection."""

from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.logger import get_logger
from src.core.messages import get_message
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.messaging.ui.payment_ui import PaymentUIService
from src.bot.handlers.pay.validators import (
    validate_user_exists,
    validate_user_has_pair,
    validate_subscription_exists,
)

logger = get_logger(__name__)


async def show_tariffs(
    tg_id: int,
    currency_code: str,
    session: AsyncSession,
    payment_ui: PaymentUIService,
    subscription_status_service: SubscriptionStatusService,
) -> tuple[bool, str, InlineKeyboardMarkup | None]:
    """Show tariffs selection for specific currency.
    
    Args:
        tg_id: Telegram user ID
        currency_code: Currency code (e.g., "RUB", "USD")
        session: Database session
        payment_ui: PaymentUIService instance
        subscription_status_service: SubscriptionStatusService instance
        
    Returns:
        Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
    """
    try:
        # Validate user exists
        is_valid, user, error_msg = await validate_user_exists(session, tg_id, "PAY_START_REQUIRED")
        if not is_valid:
            return False, error_msg, None

        # Validate user has pair
        is_valid, pair, error_msg = await validate_user_has_pair(session, tg_id, "PAY_NO_PAIR")
        if not is_valid:
            return False, error_msg, None

        # Validate subscription exists
        is_valid, subscription, error_msg = await validate_subscription_exists(session, pair)
        if not is_valid:
            return False, error_msg, None

        # Check current status using domain service
        can_pay, error_key = await subscription_status_service.check_subscription_for_payment(pair)
        if not can_pay:
            if error_key == "PAY_SUBSCRIPTION_LIFETIME":
                return False, get_message("PAY_SUBSCRIPTION_LIFETIME"), None
            elif error_key and error_key.startswith("PAY_SUBSCRIPTION_ACTIVE_UNTIL:"):
                period_end_str = error_key.split(":")[1]
                return False, get_message("PAY_SUBSCRIPTION_ACTIVE_UNTIL", period_text=period_end_str), None
            else:
                return False, get_message("PAY_ERROR"), None

        # Show tariffs using UI service
        message_text = payment_ui.build_tariffs_message(currency_code)
        keyboard = payment_ui.build_tariffs_keyboard(currency_code)
        return True, message_text, keyboard
    except Exception as e:
        logger.error(
            "Error in show_tariffs",
            tg_id=tg_id,
            currency_code=currency_code,
            error=str(e),
            exc_info=True,
        )
        return False, get_message("PAY_ERROR"), None

