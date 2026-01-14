"""Pair service - pair finding, creation, status checks, demo restoration."""

from datetime import date, timedelta
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import (
    DeliveryChat,
    PairStatus,
    SubscriptionStatus,
    TRIAL_PERIOD_DAYS,
)
from src.core.logger import get_logger
from src.core.messages import get_message, get_days_text
from src.db.models import LifetimePairHistory, Pair, Subscription
from src.db.repositories.pair_demo import PairDemoRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.db.repositories.users import UsersRepository
from src.services.telegram import get_bot, send_message_with_retry

logger = get_logger(__name__)


async def find_existing_pair(
    user_id: int, session: AsyncSession
) -> Pair | None:
    """
    Find existing active pair for user.
    If user has multiple pairs, returns the first active one.
    
    Args:
        user_id: User ID
        session: Database session
        
    Returns:
        Pair object if found, None otherwise
    """
    try:
        pair_result = await session.execute(
            select(Pair).where(
                ((Pair.uid_a == user_id) | (Pair.uid_b == user_id))
                & (Pair.status.in_([PairStatus.TRIAL.value, PairStatus.ACTIVE.value]))
            ).order_by(Pair.created_at.desc())
        )
        # Get first active pair if multiple exist
        pairs = pair_result.scalars().all()
        if pairs:
            return pairs[0]
        return None
    except Exception as e:
        logger.error(
            "Error in pair check SQL query",
            user_id=user_id,
            error=str(e),
            exc_info=True,
        )
        return None


async def check_and_restore_demo(
    pair: Pair,
    user_id: int,
    partner_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if demo was reset by admin and restore it if needed.
    
    Args:
        pair: Pair object
        user_id: Current user ID
        partner_id: Partner user ID
        session: Database session
        
    Returns:
        True if demo was restored, False otherwise
    """
    # Check if demo was reset by admin (pair status is PAST_DUE and no demo record exists)
    pair_demo_repo = PairDemoRepository(session)
    demo_was_reset = (
        pair.status == PairStatus.PAST_DUE.value
        and not await pair_demo_repo.is_used(user_id, partner_id)
    )
    
    if not demo_was_reset:
        return False
    
    # Admin reset demo - restore trial period
    logger.info(
        "Demo was reset by admin - restoring trial period",
        pair_id=pair.id,
    )
    
    # Get subscription
    subs_repo = SubscriptionsRepository(session)
    subscription = await subs_repo.get_by_pair_id(pair.id)
    
    if subscription:
        # Update subscription with new trial period
        trial_end = date.today() + timedelta(days=TRIAL_PERIOD_DAYS)
        
        await session.execute(
            update(Subscription)
            .where(Subscription.id == subscription.id)
            .values(
                status=SubscriptionStatus.TRIAL.value,
                period_end=trial_end,
                is_lifetime=False,
            )
        )
    
    # Update pair status to trial
    pairs_repo = PairsRepository(session)
    await pairs_repo.update_status(pair.id, PairStatus.TRIAL)
    
    # Create new demo record
    await pair_demo_repo.mark_pair(user_id, partner_id)
    
    await session.commit()
    
    return True


async def validate_pair_creation(
    user_id: int,
    partner_id: int,
    session: AsyncSession,
) -> tuple[bool, str | None]:
    """
    Validate if pair can be created between two users.
    
    Args:
        user_id: User ID
        partner_id: Partner user ID
        session: Database session
        
    Returns:
        tuple: (is_valid, error_message)
    """
    pairs_repo = PairsRepository(session)
    pair_demo_repo = PairDemoRepository(session)
    
    # Check if pair already exists
    existing_pair = await pairs_repo.get_by_user_ids(user_id, partner_id)
    if existing_pair:
        return False, get_message("START_PAIR_ALREADY_CREATED")
    
    # Check if this pair was previously broken with lifetime subscription
    uid_a, uid_b = (
        (user_id, partner_id) if user_id < partner_id else (partner_id, user_id)
    )
    lifetime_history = await session.execute(
        select(LifetimePairHistory).where(
            LifetimePairHistory.uid_a == uid_a,
            LifetimePairHistory.uid_b == uid_b,
        )
    )
    if lifetime_history.scalar_one_or_none():
        return False, get_message("START_LIFETIME_PAIR_BROKEN")
    
    # Check if THIS PAIR already used demo
    pair_used_demo = await pair_demo_repo.is_used(user_id, partner_id)
    if pair_used_demo:
        return False, get_message("START_BOTH_DEMO_USED")
    
    return True, None


async def create_pair_from_invite(
    inviter_id: int,
    invited_id: int,
    inviter_mode: str,
    delivery_chat: str,
    session: AsyncSession,
) -> Pair:
    """
    Create pair from invite link.
    
    Args:
        inviter_id: Inviter user ID (User A)
        invited_id: Invited user ID (User B)
        inviter_mode: Inviter's preferred mode
        delivery_chat: Delivery chat type
        session: Database session
        
    Returns:
        Created Pair object
    """
    pairs_repo = PairsRepository(session)
    subs_repo = SubscriptionsRepository(session)
    pair_demo_repo = PairDemoRepository(session)
    
    # Create pair with inviter's preferred mode
    pair = await pairs_repo.create(
        uid_a=inviter_id,  # Inviter is uid_a
        uid_b=invited_id,  # Invited is uid_b
        mode=inviter_mode,
        delivery_chat=delivery_chat,
    )
    
    # Create subscription (trial) - 7 days
    trial_end = date.today() + timedelta(days=TRIAL_PERIOD_DAYS)
    await subs_repo.create(
        pair_id=pair.id,
        payer_id=inviter_id,  # Inviter is the payer
        period_end=trial_end,
    )
    
    # Mark this pair as demo used
    await pair_demo_repo.mark_pair(invited_id, inviter_id)
    
    # Explicitly commit to ensure pair is saved before sending messages
    await session.commit()
    
    logger.info(
        "Pair created and committed",
        inviter_id=inviter_id,
        invited_id=invited_id,
        pair_id=pair.id,
    )
    
    return pair


def format_partner_text(
    partner_username: str | None,
    partner_nickname: str | None = None,
) -> str:
    """Format partner text for display.
    
    Args:
        partner_username: Partner's Telegram username (optional)
        partner_nickname: Nickname that user gave to partner (optional)
        
    Returns:
        Formatted text like "@username, никнейм" or "@username" or "никнейм" or fallback
    """
    parts = []
    
    if partner_username:
        parts.append(f"@{partner_username}")
    
    if partner_nickname:
        parts.append(partner_nickname)
    
    if parts:
        return ", ".join(parts)
    
    return get_message("START_PARTNER_FALLBACK")
