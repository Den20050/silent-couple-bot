"""Use case for admin statistics."""

from sqlalchemy import func, select, union_all
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import SubscriptionStatus
from src.core.logger import get_logger
from src.db.models import Pair, Subscription, User
from src.db.repositories.pair_demo import PairDemoRepository
from src.services.demo_hash import build_pair_demo_hash

logger = get_logger(__name__)


async def get_admin_statistics(session: AsyncSession) -> dict[str, int]:
    """Get admin statistics.
    
    Args:
        session: Database session
        
    Returns:
        Dictionary with statistics:
        - total_users: Total number of users
        - total_pairs: Total number of pairs
        - single_users: Number of users without pairs
        - pairs_with_demo: Number of pairs with demo
        - users_with_subscription: Number of users with active subscriptions
    """
    try:
        pair_demo_repo = PairDemoRepository(session)

        # Get total users count
        users_count_result = await session.execute(select(func.count(User.id)))
        total_users = users_count_result.scalar() or 0

        # Get total pairs count
        pairs_count_result = await session.execute(select(func.count(Pair.id)))
        total_pairs = pairs_count_result.scalar() or 0

        # Get pairs with demo (only existing pairs)
        pair_hashes = await pair_demo_repo.get_all_hashes()
        if pair_hashes:
            user_a = aliased(User)
            user_b = aliased(User)
            pairs_result = await session.execute(
                select(user_a.tg_id, user_b.tg_id)
                .select_from(Pair)
                .join(user_a, Pair.uid_a == user_a.id)
                .join(user_b, Pair.uid_b == user_b.id)
            )
            pairs_with_demo = sum(
                1
                for tg_id_a, tg_id_b in pairs_result.all()
                if build_pair_demo_hash(tg_id_a, tg_id_b) in pair_hashes
            )
        else:
            pairs_with_demo = 0

        # Get users with active subscriptions
        active_subs_result = await session.execute(
            select(func.count(func.distinct(Subscription.payer_id))).where(
                Subscription.status == SubscriptionStatus.ACTIVE.value
            )
        )
        users_with_subscription = active_subs_result.scalar() or 0

        # Get single users
        uid_a_subquery = select(Pair.uid_a.label("user_id"))
        uid_b_subquery = select(Pair.uid_b.label("user_id"))
        users_in_pairs_union = union_all(uid_a_subquery, uid_b_subquery).subquery()
        
        users_in_pairs_result = await session.execute(
            select(func.count(func.distinct(users_in_pairs_union.c.user_id)))
        )
        users_in_pairs_count = users_in_pairs_result.scalar() or 0
        
        single_users = total_users - users_in_pairs_count

        return {
            "total_users": total_users,
            "total_pairs": total_pairs,
            "single_users": single_users,
            "pairs_with_demo": pairs_with_demo,
            "users_with_subscription": users_with_subscription,
        }
    except Exception as e:
        logger.error("Error getting admin statistics", error=str(e), exc_info=True)
        raise


# format_statistics_message moved to AdminUIService.format_statistics_message

