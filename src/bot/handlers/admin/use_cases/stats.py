"""Use case for admin statistics."""

from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PairStatus, SubscriptionStatus
from src.core.logger import get_logger
from src.db.models import Pair, Subscription, User

logger = get_logger(__name__)


async def get_admin_statistics(session: AsyncSession) -> dict[str, int]:
    """Get admin statistics.
    
    Args:
        session: Database session
        
    Returns:
        Dictionary with statistics:
        - total_users: Total number of users who accepted consent
        - total_pairs: Total number of pairs
        - users_without_pairs: Number of users without pairs
        - pairs_with_demo: Number of pairs with demo
        - pairs_with_subscription: Number of pairs with active subscriptions
    """
    try:
        # Get total users count (only users who accepted consent)
        users_count_result = await session.execute(
            select(func.count(User.id)).where(User.consent.is_(True))
        )
        total_users = users_count_result.scalar() or 0

        # Get total pairs count
        pairs_count_result = await session.execute(select(func.count(Pair.id)))
        total_pairs = pairs_count_result.scalar() or 0

        # Get pairs with demo (current trial pairs)
        demo_pairs_result = await session.execute(
            select(func.count(Pair.id)).where(Pair.status == PairStatus.TRIAL.value)
        )
        pairs_with_demo = demo_pairs_result.scalar() or 0

        # Get pairs with active subscriptions
        active_pairs_result = await session.execute(
            select(func.count(func.distinct(Pair.id)))
            .join(Subscription, Subscription.pair_id == Pair.id)
            .where(Subscription.status == SubscriptionStatus.ACTIVE.value)
        )
        pairs_with_subscription = active_pairs_result.scalar() or 0

        # Get single users (only users who accepted consent)
        uid_a_subquery = (
            select(Pair.uid_a.label("user_id"))
            .join(User, User.id == Pair.uid_a)
            .where(User.consent.is_(True))
        )
        uid_b_subquery = (
            select(Pair.uid_b.label("user_id"))
            .join(User, User.id == Pair.uid_b)
            .where(User.consent.is_(True))
        )
        users_in_pairs_union = union_all(uid_a_subquery, uid_b_subquery).subquery()
        
        users_in_pairs_result = await session.execute(
            select(func.count(func.distinct(users_in_pairs_union.c.user_id)))
        )
        users_in_pairs_count = users_in_pairs_result.scalar() or 0
        
        users_without_pairs = total_users - users_in_pairs_count

        return {
            "total_users": total_users,
            "total_pairs": total_pairs,
            "users_without_pairs": users_without_pairs,
            "pairs_with_demo": pairs_with_demo,
            "pairs_with_subscription": pairs_with_subscription,
        }
    except Exception as e:
        logger.error("Error getting admin statistics", error=str(e), exc_info=True)
        raise


# format_statistics_message moved to AdminUIService.format_statistics_message

