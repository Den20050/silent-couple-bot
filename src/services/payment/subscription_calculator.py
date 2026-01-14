"""Subscription period calculation utilities."""

from datetime import date, timedelta
from typing import Optional

from src.core.constants import SUBSCRIPTION_PERIOD_DAYS
from src.core.logger import get_logger
from src.db.models import Subscription

logger = get_logger(__name__)


def calculate_subscription_period_end(
    subscription: Subscription,
    new_period_days: int,
    is_lifetime: bool = False,
    standard_month_days: int = 30,
) -> date:
    """Calculate new subscription period_end with remaining days added.
    
    If subscription is still active (not expired), remaining days are added
    to the new period. Calculation uses standard month (30 days) for simplicity.
    
    For lifetime subscriptions, remaining days are NOT added - lifetime is activated
    immediately regardless of current subscription status.
    
    Args:
        subscription: Current subscription object
        new_period_days: Days for new subscription period (ignored if is_lifetime=True)
        is_lifetime: Whether new subscription is lifetime
        standard_month_days: Standard month length in days (default: 30)
        
    Returns:
        New period_end date (2099-12-31 for lifetime, calculated date otherwise)
    """
    # Lifetime subscriptions always use far future date immediately
    # Remaining days from current subscription are NOT added
    if is_lifetime:
        logger.info(
            "Lifetime subscription activated immediately",
            subscription_id=subscription.id,
            current_period_end=subscription.period_end.isoformat(),
        )
        return date(2099, 12, 31)
    
    today = date.today()
    current_period_end = subscription.period_end
    
    # If subscription is expired, start from today
    if current_period_end < today:
        logger.info(
            "Subscription expired, starting new period from today",
            subscription_id=subscription.id,
            current_period_end=current_period_end.isoformat(),
            new_period_days=new_period_days,
        )
        return today + timedelta(days=new_period_days)
    
    # Subscription is still active - calculate remaining days
    remaining_days = (current_period_end - today).days
    
    if remaining_days <= 0:
        # Should not happen, but handle edge case
        logger.warning(
            "Remaining days <= 0 but period_end >= today, using today as start",
            subscription_id=subscription.id,
            current_period_end=current_period_end.isoformat(),
            remaining_days=remaining_days,
        )
        return today + timedelta(days=new_period_days)
    
    # Add remaining days to new period
    # Calculation: new_period = new_period_days + remaining_days
    total_days = new_period_days + remaining_days
    
    # Calculate new period_end from today (not from current_period_end)
    # This ensures we add the full remaining days to the new period
    new_period_end = today + timedelta(days=total_days)
    
    logger.info(
        "Calculated subscription period with remaining days",
        subscription_id=subscription.id,
        current_period_end=current_period_end.isoformat(),
        remaining_days=remaining_days,
        new_period_days=new_period_days,
        total_days=total_days,
        new_period_end=new_period_end.isoformat(),
    )
    
    return new_period_end

