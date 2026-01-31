"""Pair onboarding service - business logic for pair creation and onboarding."""

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import (
    DeliveryChat,
    PairStatus,
    SubscriptionStatus,
    TRIAL_PERIOD_DAYS,
)
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.models import LifetimePairHistory, Pair, Subscription
from src.db.repositories.pair_demo import PairDemoRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.subscriptions import SubscriptionsRepository

logger = get_logger(__name__)


class PairOnboardingService:
    """Service for managing pair creation and onboarding logic."""
    
    def __init__(self, session: AsyncSession) -> None:
        """Initialize pair onboarding service.
        
        Args:
            session: Database session
        """
        self._session = session
        self._pairs_repo = PairsRepository(session)
        self._subs_repo = SubscriptionsRepository(session)
        self._pair_demo_repo = PairDemoRepository(session)
        from src.db.repositories.users import UsersRepository

        self._users_repo = UsersRepository(session)
    
    async def validate_pair_creation(
        self,
        user_id: int,
        partner_id: int,
    ) -> tuple[bool, Optional[str]]:
        """Validate if pair can be created between two users.
        
        Args:
            user_id: User ID
            partner_id: Partner user ID
            
        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        # Check if pair already exists
        existing_pair = await self._pairs_repo.get_by_user_ids(user_id, partner_id)
        if existing_pair:
            return False, get_message("START_PAIR_ALREADY_CREATED")
        
        # Check if this pair was previously broken with lifetime subscription
        uid_a, uid_b = (
            (user_id, partner_id) if user_id < partner_id else (partner_id, user_id)
        )
        lifetime_history = await self._session.execute(
            select(LifetimePairHistory).where(
                LifetimePairHistory.uid_a == uid_a,
                LifetimePairHistory.uid_b == uid_b,
            )
        )
        if lifetime_history.scalar_one_or_none():
            # Lifetime pairs can be restored without demo restrictions.
            return True, None
        
        user = await self._users_repo.get_by_id(user_id)
        partner = await self._users_repo.get_by_id(partner_id)
        if not user or not partner:
            return False, get_message("MENU_USER_NOT_FOUND")

        # Check if THIS PAIR already used demo
        pair_used_demo = await self._pair_demo_repo.is_used(
            user.tg_id,
            partner.tg_id,
        )
        if not pair_used_demo and await self._pair_demo_repo.is_used_legacy(
            user_id,
            partner_id,
        ):
            await self._pair_demo_repo.mark_pair(user.tg_id, partner.tg_id)
            pair_used_demo = True
        if pair_used_demo:
            return False, get_message("START_BOTH_DEMO_USED")
        
        return True, None
    
    async def create_pair_from_invite(
        self,
        inviter_id: int,
        invited_id: int,
        inviter_mode: str,
        delivery_chat: str = DeliveryChat.BOT_DM.value,
    ) -> Pair:
        """Create pair from invite link.
        
        Args:
            inviter_id: Inviter user ID (User A)
            invited_id: Invited user ID (User B)
            inviter_mode: Inviter's preferred mode
            delivery_chat: Delivery chat type
            
        Returns:
            Created Pair object
        """
        uid_a, uid_b = (
            (inviter_id, invited_id)
            if inviter_id < invited_id
            else (invited_id, inviter_id)
        )
        lifetime_history = await self._session.execute(
            select(LifetimePairHistory).where(
                LifetimePairHistory.uid_a == uid_a,
                LifetimePairHistory.uid_b == uid_b,
            )
        )
        restore_lifetime = lifetime_history.scalar_one_or_none() is not None

        # Create pair with inviter's preferred mode
        pair = await self._pairs_repo.create(
            uid_a=inviter_id,  # Inviter is uid_a
            uid_b=invited_id,  # Invited is uid_b
            mode=inviter_mode,
            delivery_chat=delivery_chat,
        )
        
        # Create subscription (trial) - 7 days
        trial_end = date.today() + timedelta(days=TRIAL_PERIOD_DAYS)
        subscription = await self._subs_repo.create(
            pair_id=pair.id,
            payer_id=inviter_id,  # Inviter is the payer
            period_end=trial_end,
        )

        if restore_lifetime and subscription:
            # Restore lifetime subscription for re-registered pair.
            await self._subs_repo.update_payment(
                subscription_id=subscription.id,
                yoo_id=f"lifetime_restore_{pair.id}",
                period_end=date(2099, 12, 31),
                is_lifetime=True,
            )
            await self._pairs_repo.update_status(pair.id, PairStatus.ACTIVE)
        else:
            inviter = await self._users_repo.get_by_id(inviter_id)
            invited = await self._users_repo.get_by_id(invited_id)
            if inviter and invited:
                # Mark this pair as demo used (by tg_id hash)
                await self._pair_demo_repo.mark_pair(
                    invited.tg_id,
                    inviter.tg_id,
                )
        
        # Explicitly commit to ensure pair is saved before sending messages
        await self._session.commit()
        
        logger.info(
            "Pair created and committed",
            inviter_id=inviter_id,
            invited_id=invited_id,
            pair_id=pair.id,
        )
        
        return pair
    
    async def find_existing_pair(
        self,
        user_id: int,
    ) -> Optional[Pair]:
        """Find existing pair for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Pair object if found, None otherwise
        """
        try:
            from sqlalchemy import select
            from src.db.models import Pair
            
            result = await self._session.execute(
                select(Pair).where(
                    (Pair.uid_a == user_id) | (Pair.uid_b == user_id)
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                "Error finding existing pair",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return None
    
    async def check_and_restore_demo(
        self,
        pair: Pair,
        user_id: int,
        partner_id: int,
    ) -> bool:
        """Check if demo was reset by admin and restore it if needed.
        
        Args:
            pair: Pair object
            user_id: Current user ID
            partner_id: Partner user ID
            
        Returns:
            True if demo was restored, False otherwise
        """
        # Check if demo was reset by admin (pair status is PAST_DUE and no demo record exists)
        user = await self._users_repo.get_by_id(user_id)
        partner = await self._users_repo.get_by_id(partner_id)
        if not user or not partner:
            return False

        demo_used = await self._pair_demo_repo.is_used(user.tg_id, partner.tg_id)
        if not demo_used and await self._pair_demo_repo.is_used_legacy(
            user_id,
            partner_id,
        ):
            await self._pair_demo_repo.mark_pair(user.tg_id, partner.tg_id)
            demo_used = True

        demo_was_reset = pair.status == PairStatus.PAST_DUE.value and not demo_used
        
        if not demo_was_reset:
            return False
        
        # Admin reset demo - restore trial period
        logger.info(
            "Demo was reset by admin - restoring trial period",
            pair_id=pair.id,
        )
        
        # Get subscription
        subscription = await self._subs_repo.get_by_pair_id(pair.id)
        
        if subscription:
            # Update subscription with new trial period
            trial_end = date.today() + timedelta(days=TRIAL_PERIOD_DAYS)
            
            from sqlalchemy import update
            await self._session.execute(
                update(Subscription)
                .where(Subscription.id == subscription.id)
                .values(
                    status=SubscriptionStatus.TRIAL.value,
                    period_end=trial_end,
                    is_lifetime=False,
                )
            )
        
        # Update pair status to trial
        await self._pairs_repo.update_status(pair.id, PairStatus.TRIAL)
        
        # Create new demo record
        await self._pair_demo_repo.mark_pair(user.tg_id, partner.tg_id)
        
        await self._session.commit()
        
        return True

