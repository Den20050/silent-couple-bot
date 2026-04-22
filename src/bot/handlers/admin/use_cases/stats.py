"""Use case for admin statistics."""

from sqlalchemy import Date, case, func, select, union_all
from sqlalchemy import cast as sa_cast
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PairStatus, SubscriptionStatus
from src.core.logger import get_logger
from src.db.models import Pair, Subscription, User

logger = get_logger(__name__)

# Thresholds for plan bucketing based on (period_end - activation_date) days.
# Ranges are intentionally wide to absorb minor day-count differences (e.g. leap
# years, months of different length, timezone offsets stored in updated_at).
_YEAR_MIN_DAYS = 300       # 365 days → bucket ≥ 300
_6MONTH_MIN_DAYS = 150     # 180 days → bucket ≥ 150
_3MONTH_MIN_DAYS = 60      # 90 days  → bucket ≥ 60
# anything below → 1 month (30 days)


async def get_admin_statistics(session: AsyncSession) -> dict:
    """Get admin statistics.

    Returns a dict with keys:
        - total_users: users who accepted consent
        - total_pairs: all pairs
        - users_without_pairs: consented users not in any pair
        - pairs_with_demo: pairs in TRIAL status
        - pairs_with_subscription: pairs with an ACTIVE subscription
        - subscriptions_by_plan: dict plan_id → pair count (active subs only)
    """
    try:
        # --- users -----------------------------------------------------------
        users_count_result = await session.execute(
            select(func.count(User.id)).where(User.consent.is_(True))
        )
        total_users = users_count_result.scalar() or 0

        # --- pairs -----------------------------------------------------------
        pairs_count_result = await session.execute(select(func.count(Pair.id)))
        total_pairs = pairs_count_result.scalar() or 0

        demo_pairs_result = await session.execute(
            select(func.count(Pair.id)).where(Pair.status == PairStatus.TRIAL.value)
        )
        pairs_with_demo = demo_pairs_result.scalar() or 0

        active_pairs_result = await session.execute(
            select(func.count(func.distinct(Pair.id)))
            .join(Subscription, Subscription.pair_id == Pair.id)
            .where(Subscription.status == SubscriptionStatus.ACTIVE.value)
        )
        pairs_with_subscription = active_pairs_result.scalar() or 0

        # --- users in pairs vs without pairs --------------------------------
        # Count DISTINCT consented users who appear in at least one pair.
        # This is different from total_pairs × 2 because:
        #   - one user can be in multiple pairs
        #   - a pair partner may not have given consent (excluded from total_users)
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
        users_in_pairs = users_in_pairs_result.scalar() or 0
        users_without_pairs = total_users - users_in_pairs

        # --- subscriptions by plan ------------------------------------------
        # Plan type is inferred from (period_end − date(updated_at)) because
        # the Subscription table has no plan_id column. updated_at is refreshed
        # every time a payment or gift activates the subscription, so the
        # difference equals the purchased period length.
        activation_date = sa_cast(Subscription.updated_at, Date)
        days_diff = Subscription.period_end - activation_date

        plan_expr = case(
            (Subscription.is_lifetime.is_(True), "lifetime"),
            (days_diff >= _YEAR_MIN_DAYS, "1_year"),
            (days_diff >= _6MONTH_MIN_DAYS, "6_months"),
            (days_diff >= _3MONTH_MIN_DAYS, "3_months"),
            else_="1_month",
        )

        plan_rows = await session.execute(
            select(plan_expr.label("plan"), func.count(func.distinct(Subscription.pair_id)))
            .where(Subscription.status == SubscriptionStatus.ACTIVE.value)
            .group_by(plan_expr)
        )

        subscriptions_by_plan: dict[str, int] = {
            "1_month": 0,
            "3_months": 0,
            "6_months": 0,
            "1_year": 0,
            "lifetime": 0,
        }
        for plan_key, count in plan_rows:
            if plan_key in subscriptions_by_plan:
                subscriptions_by_plan[plan_key] = count

        return {
            "total_users": total_users,
            "users_in_pairs": users_in_pairs,
            "users_without_pairs": users_without_pairs,
            "total_pairs": total_pairs,
            "pairs_with_demo": pairs_with_demo,
            "pairs_with_subscription": pairs_with_subscription,
            "subscriptions_by_plan": subscriptions_by_plan,
        }
    except Exception as e:
        logger.error("Error getting admin statistics", error=str(e), exc_info=True)
        raise


# format_statistics_message moved to AdminUIService.format_statistics_message

