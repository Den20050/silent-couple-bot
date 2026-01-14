"""Subscriptions repository."""

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import SUBSCRIPTION_PERIOD_DAYS, SubscriptionStatus
from src.db.models import Subscription


class SubscriptionsRepository:
    """Repository for subscriptions."""

    def __init__(self, session: AsyncSession):
        """Initialize repository."""
        self.session = session

    async def get_by_pair_id(self, pair_id: int) -> Optional[Subscription]:
        """Get subscription by pair ID."""
        result = await self.session.execute(select(Subscription).where(Subscription.pair_id == pair_id))
        return result.scalar_one_or_none()

    async def get_by_yoo_id(self, yoo_id: str) -> Optional[Subscription]:
        """Get subscription by payment ID (yoo_id для совместимости, хранит inv_id от Robokassa)."""
        result = await self.session.execute(select(Subscription).where(Subscription.yoo_id == yoo_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        pair_id: int,
        payer_id: int,
        period_end: Optional[date] = None,
    ) -> Subscription:
        """Create new subscription."""
        if period_end is None:
            period_end = date.today() + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)

        subscription = Subscription(
            pair_id=pair_id,
            payer_id=payer_id,
            status=SubscriptionStatus.TRIAL.value,
            period_end=period_end,
        )
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def update_payment(
        self,
        subscription_id: int,
        yoo_id: str,
        period_end: Optional[date] = None,
        is_lifetime: bool = False,
    ) -> Optional[Subscription]:
        """Update subscription with payment info."""
        if period_end is None:
            period_end = date.today() + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)

        stmt = (
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(
                yoo_id=yoo_id,
                status=SubscriptionStatus.ACTIVE.value,
                period_end=period_end,
                is_lifetime=is_lifetime,
            )
            .returning(Subscription)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def extend_period(self, subscription_id: int, days: int = SUBSCRIPTION_PERIOD_DAYS) -> Optional[Subscription]:
        """Extend subscription period."""
        stmt = (
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(period_end=Subscription.period_end + timedelta(days=days))
            .returning(Subscription)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def get_past_due(self) -> list[Subscription]:
        """Get past due subscriptions (excluding lifetime subscriptions)."""
        today = date.today()
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.period_end < today,
                Subscription.status.in_([SubscriptionStatus.TRIAL.value, SubscriptionStatus.ACTIVE.value]),
                Subscription.is_lifetime == False,  # Exclude lifetime subscriptions
            )
        )
        return list(result.scalars().all())
    
    async def get_active_expiring_before(self, expiry_date: date) -> list[Subscription]:
        """Get active subscriptions expiring before specified date (excluding lifetime).
        
        Args:
            expiry_date: Date threshold - subscriptions expiring before this date
            
        Returns:
            List of subscriptions expiring before threshold
        """
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.ACTIVE.value,
                Subscription.period_end <= expiry_date,
                Subscription.period_end >= date.today(),  # Not expired yet
                Subscription.is_lifetime == False,  # Exclude lifetime subscriptions
            )
        )
        return list(result.scalars().all())
    
    async def get_payment_ids_by_payer(self, payer_id: int, months: int = 6) -> list[str]:
        """Get payment IDs (yoo_id) for a payer within the last N months.
        
        Args:
            payer_id: User ID who paid
            months: Number of months to look back (default: 6)
            
        Returns:
            List of payment IDs (yoo_id) that are not None
        """
        cutoff_date = date.today() - timedelta(days=months * 30)
        result = await self.session.execute(
            select(Subscription.yoo_id).where(
                Subscription.payer_id == payer_id,
                Subscription.created_at >= cutoff_date,
                Subscription.yoo_id.isnot(None),  # Only paid subscriptions
            )
        )
        payment_ids = [row[0] for row in result.all() if row[0]]
        return payment_ids
    
    async def update_last_past_due_notification_date(
        self,
        subscription_id: int,
        notification_date: date,
    ) -> Optional[Subscription]:
        """Update last past due notification date for a subscription.
        
        Args:
            subscription_id: Subscription ID
            notification_date: Date when notification was sent
            
        Returns:
            Updated Subscription object or None if not found
        """
        stmt = (
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(last_past_due_notification_date=notification_date)
            .returning(Subscription)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

