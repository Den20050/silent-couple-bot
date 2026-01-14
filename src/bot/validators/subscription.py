"""Subscription validation utilities."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.exceptions import SubscriptionExpiredError, SubscriptionNotFoundError
from src.core.constants import SubscriptionStatus
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.models import Pair, Subscription
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.messaging.ui.settings_ui import SettingsUIService

logger = get_logger(__name__)


async def validate_subscription_exists(
    session: AsyncSession,
    pair: Pair,
    error_message_key: str = "PAY_SUBSCRIPTION_NOT_FOUND",
) -> Subscription:
    """Validate subscription exists for pair.
    
    Args:
        session: Database session
        pair: Pair object
        error_message_key: Message key for error (default: "PAY_SUBSCRIPTION_NOT_FOUND")
        
    Returns:
        Subscription object if found
        
    Raises:
        SubscriptionNotFoundError: If subscription is not found
    """
    subs_repo = SubscriptionsRepository(session)
    subscription = await subs_repo.get_by_pair_id(pair.id)
    
    if not subscription:
        logger.warning(
            "Subscription not found",
            pair_id=pair.id,
        )
        raise SubscriptionNotFoundError(
            pair_id=pair.id,
            message_key=error_message_key,
            message=get_message(error_message_key),
        )
    
    return subscription


async def validate_subscription_active(
    session: AsyncSession,
    pair: Pair,
    error_message_key: str = "SETTINGS_SUBSCRIPTION_EXPIRED",
    show_pay_button: bool = True,
) -> None:
    """Validate subscription is active (not expired).
    
    Args:
        session: Database session
        pair: Pair object
        error_message_key: Message key for error (default: "SETTINGS_SUBSCRIPTION_EXPIRED")
        show_pay_button: Whether to include pay keyboard in error response
        
    Raises:
        SubscriptionExpiredError: If subscription is expired
    """
    subscription_status_service = SubscriptionStatusService(session)
    
    if await subscription_status_service.is_subscription_expired(pair):
        logger.warning(
            "Subscription expired",
            pair_id=pair.id,
        )
        
        # Determine specific error message
        subs_repo = SubscriptionsRepository(session)
        subscription = await subs_repo.get_by_pair_id(pair.id)
        
        if subscription and subscription.status == SubscriptionStatus.TRIAL.value:
            error_message = get_message("SETTINGS_TRIAL_EXPIRED")
        else:
            error_message = get_message(error_message_key)
        
        reply_markup = None
        if show_pay_button:
            settings_ui = SettingsUIService()
            reply_markup = settings_ui.build_pay_keyboard().model_dump()
        
        raise SubscriptionExpiredError(
            pair_id=pair.id,
            message_key=error_message_key,
            message=error_message,
            show_pay_button=show_pay_button,
            reply_markup=reply_markup,
        )

