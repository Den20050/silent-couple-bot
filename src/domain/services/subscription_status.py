"""Subscription status service - business logic for subscription status management."""

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PairStatus, SubscriptionStatus, SUBSCRIPTION_PLANS, TRIAL_PERIOD_DAYS
from src.core.logger import get_logger
from src.db.models import Pair, Subscription
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.subscriptions import SubscriptionsRepository

logger = get_logger(__name__)


class SubscriptionStatusService:
    """Service for managing subscription status and related business logic."""
    
    def __init__(self, session: AsyncSession) -> None:
        """Initialize subscription status service.
        
        Args:
            session: Database session
        """
        self._session = session
        self._pairs_repo = PairsRepository(session)
        self._subs_repo = SubscriptionsRepository(session)
    
    async def get_subscription_info(
        self,
        pair: Pair,
    ) -> tuple[bool, int, bool, Optional[str], bool]:
        """Get subscription information for a pair.
        
        Args:
            pair: Pair object
            
        Returns:
            Tuple of (is_trial: bool, days_left: int, is_expired: bool, tariff_name: Optional[str], is_lifetime: bool)
        """
        subscription = await self._subs_repo.get_by_pair_id(pair.id)
        if not subscription:
            return False, 0, True, None, False
        
        is_trial = pair.status == PairStatus.TRIAL.value
        is_expired = False
        days_left = 0
        tariff_name = None
        is_lifetime = subscription.is_lifetime
        
        if pair.status == PairStatus.ACTIVE.value:
            if subscription.period_end:
                days_left = (subscription.period_end - date.today()).days
                if days_left < 0:
                    days_left = 0
                
                # Determine tariff name for active subscription
                if not is_lifetime:
                    tariff_name = self._determine_tariff_name(subscription)
        elif pair.status == PairStatus.TRIAL.value:
            if subscription.period_end:
                days_left = (subscription.period_end - date.today()).days
            else:
                # Fallback: calculate from creation date
                subscription_start = subscription.created_at.date()
                trial_end_date = subscription_start + timedelta(days=TRIAL_PERIOD_DAYS)
                days_left = (trial_end_date - date.today()).days
            
            # Ensure days_left is within valid range
            if days_left < 0:
                days_left = 0
            elif days_left > TRIAL_PERIOD_DAYS:
                days_left = TRIAL_PERIOD_DAYS
            
            if days_left == 0:
                is_expired = True
        else:
            # Fallback for unexpected statuses - treat as trial
            if subscription.period_end:
                days_left = (subscription.period_end - date.today()).days
            else:
                subscription_start = subscription.created_at.date()
                trial_end_date = subscription_start + timedelta(days=TRIAL_PERIOD_DAYS)
                days_left = (trial_end_date - date.today()).days
            
            if days_left < 0:
                days_left = 0
            elif days_left > TRIAL_PERIOD_DAYS:
                days_left = TRIAL_PERIOD_DAYS
            
            if days_left == 0:
                is_expired = True
        
        return is_trial, days_left, is_expired, tariff_name, is_lifetime
    
    def _determine_tariff_name(self, subscription: Subscription) -> Optional[str]:
        """Determine tariff name based on subscription period.
        
        Args:
            subscription: Subscription object
            
        Returns:
            Tariff name (e.g., "1 месяц", "3 месяца") or None if cannot determine
        """
        if subscription.is_lifetime:
            return SUBSCRIPTION_PLANS["lifetime"]["name"]
        
        if not subscription.period_end:
            return None
        
        # Calculate period in days from creation to period_end
        period_start = subscription.created_at.date()
        period_days = (subscription.period_end - period_start).days
        
        # Match to closest plan
        # Try exact matches first
        for plan_id, plan_info in SUBSCRIPTION_PLANS.items():
            if plan_info.get("is_lifetime"):
                continue
            plan_days = plan_info.get("days")
            if plan_days and abs(period_days - plan_days) <= 2:  # Allow 2 days tolerance
                return plan_info["name"]
        
        # If no exact match, return None (will show days only)
        return None
    
    async def is_subscription_active(
        self,
        pair: Pair,
    ) -> bool:
        """Check if subscription is active (trial or active status).
        
        Args:
            pair: Pair object
            
        Returns:
            True if subscription is active, False otherwise
        """
        return pair.status in [PairStatus.TRIAL.value, PairStatus.ACTIVE.value]
    
    async def is_subscription_expired(
        self,
        pair: Pair,
    ) -> bool:
        """Check if subscription is expired.
        
        Args:
            pair: Pair object
            
        Returns:
            True if subscription is expired, False otherwise
        """
        if pair.status == PairStatus.PAST_DUE.value:
            return True
        
        subscription = await self._subs_repo.get_by_pair_id(pair.id)
        if not subscription:
            return True
        
        if subscription.is_lifetime:
            return False
        
        if subscription.period_end:
            return subscription.period_end < date.today()
        
        # Fallback: check based on creation date
        subscription_start = subscription.created_at.date()
        trial_end_date = subscription_start + timedelta(days=TRIAL_PERIOD_DAYS)
        return trial_end_date < date.today()
    
    async def is_lifetime_subscription(
        self,
        pair: Pair,
    ) -> bool:
        """Check if subscription is lifetime.
        
        Args:
            pair: Pair object
            
        Returns:
            True if subscription is lifetime, False otherwise
        """
        subscription = await self._subs_repo.get_by_pair_id(pair.id)
        if not subscription:
            return False
        
        return subscription.is_lifetime
    
    async def get_expiration_date(
        self,
        pair: Pair,
    ) -> Optional[date]:
        """Get subscription expiration date.
        
        Args:
            pair: Pair object
            
        Returns:
            Expiration date or None if lifetime or not found
        """
        subscription = await self._subs_repo.get_by_pair_id(pair.id)
        if not subscription:
            return None
        
        if subscription.is_lifetime:
            return None
        
        return subscription.period_end
    
    async def get_first_active_pair(
        self,
        pairs: list[Pair],
    ) -> Optional[Pair]:
        """Get first active pair from list of pairs.
        
        Args:
            pairs: List of Pair objects
            
        Returns:
            First active (trial or active) pair, or first pair if no active pairs found, or None
        """
        if not pairs:
            return None
        
        # Try to find active pair first
        for pair in pairs:
            if pair.status in [PairStatus.TRIAL.value, PairStatus.ACTIVE.value]:
                return pair
        
        # If no active pair, return first pair
        return pairs[0]
    
    async def check_subscription_for_payment(
        self,
        pair: Pair,
    ) -> tuple[bool, Optional[str]]:
        """Check if subscription can be paid (not lifetime, not active).
        
        Args:
            pair: Pair object
            
        Returns:
            Tuple of (can_pay: bool, error_message: Optional[str])
        """
        if pair.status == PairStatus.ACTIVE.value:
            subscription = await self._subs_repo.get_by_pair_id(pair.id)
            if subscription and subscription.is_lifetime:
                return False, "PAY_SUBSCRIPTION_LIFETIME"
            
            if subscription and subscription.period_end:
                period_end_str = subscription.period_end.strftime('%d.%m.%Y')
                return False, f"PAY_SUBSCRIPTION_ACTIVE_UNTIL:{period_end_str}"
        
        return True, None

