"""Use case for admin statistics."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Date, and_, case, func, or_, select, union_all
from sqlalchemy import cast as sa_cast
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PairStatus, SubscriptionStatus
from src.core.logger import get_logger
from src.db.models import Pair, PairPayment, Subscription, User

logger = get_logger(__name__)

DEFAULT_ADMIN_STATS_PERIOD_DAYS = 30
DEFAULT_ADMIN_STATS_TAB = "users"

# Thresholds for plan bucketing based on (period_end - activation_date) days.
_YEAR_MIN_DAYS = 300
_6MONTH_MIN_DAYS = 150
_3MONTH_MIN_DAYS = 60

_PLAN_ORDER = ("1_month", "3_months", "6_months", "1_year", "lifetime")


def stats_period_label(period_days: int | None) -> str:
    """Human-readable label for the selected stats period."""
    if period_days is None:
        return "всё время"
    if period_days == 1:
        return "1 день"
    if period_days in (7, 14, 30, 90):
        return f"{period_days} дн."
    return f"{period_days} дн."


def _period_start(period_days: int | None) -> datetime | None:
    if period_days is None:
        return None
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=period_days)


def _users_in_pairs_subquery():
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
    return union_all(uid_a_subquery, uid_b_subquery).subquery()


def _empty_plan_dict() -> dict[str, int]:
    return {plan_id: 0 for plan_id in _PLAN_ORDER}


def _plan_expr():
    activation_date = sa_cast(Subscription.updated_at, Date)
    days_diff = Subscription.period_end - activation_date
    return case(
        (Subscription.is_lifetime.is_(True), "lifetime"),
        (days_diff >= _YEAR_MIN_DAYS, "1_year"),
        (days_diff >= _6MONTH_MIN_DAYS, "6_months"),
        (days_diff >= _3MONTH_MIN_DAYS, "3_months"),
        else_="1_month",
    )


def _payment_period_filter(period_start: datetime | None):
    if period_start is None:
        return True
    return PairPayment.paid_at >= period_start


def _gift_period_filter(period_start: datetime | None):
    if period_start is None:
        return True
    return Subscription.updated_at >= period_start


def _is_real_payment_yoo_id():
    return and_(
        Subscription.yoo_id.isnot(None),
        ~Subscription.yoo_id.like("admin_gift_%"),
        ~Subscription.yoo_id.like("lifetime_restore_%"),
        Subscription.yoo_id.op("~")("^[0-9]+$"),
    )


async def get_admin_user_statistics(
    session: AsyncSession,
    period_days: int | None = DEFAULT_ADMIN_STATS_PERIOD_DAYS,
) -> dict:
    """User-centric admin statistics for the selected period."""
    try:
        period_start = _period_start(period_days)
        users_in_pairs_union = _users_in_pairs_subquery()

        def _user_joined_in_period():
            if period_start is None:
                return User.consent.is_(True)
            return and_(
                User.consent.is_(True),
                or_(
                    User.consent_dt >= period_start,
                    and_(User.consent_dt.is_(None), User.created_at >= period_start),
                ),
            )

        pair_period_filter = True if period_start is None else Pair.created_at >= period_start

        total_users = (
            await session.execute(
                select(func.count(User.id)).where(User.consent.is_(True))
            )
        ).scalar() or 0

        new_users = (
            await session.execute(
                select(func.count(User.id)).where(_user_joined_in_period())
            )
        ).scalar() or 0

        users_in_pairs = (
            await session.execute(
                select(func.count(func.distinct(users_in_pairs_union.c.user_id)))
            )
        ).scalar() or 0
        users_without_pairs = total_users - users_in_pairs

        not_in_pair = ~User.id.in_(
            select(func.distinct(users_in_pairs_union.c.user_id))
        )

        solo_no_mode = (
            await session.execute(
                select(func.count(User.id)).where(
                    User.consent.is_(True),
                    not_in_pair,
                    User.preferred_mode.is_(None),
                )
            )
        ).scalar() or 0

        solo_waiting_partner = (
            await session.execute(
                select(func.count(User.id)).where(
                    User.consent.is_(True),
                    not_in_pair,
                    User.preferred_mode.isnot(None),
                )
            )
        ).scalar() or 0

        new_solo_in_period = (
            await session.execute(
                select(func.count(User.id)).where(
                    _user_joined_in_period(),
                    not_in_pair,
                )
            )
        ).scalar() or 0

        total_pairs = (
            await session.execute(
                select(func.count(Pair.id)).where(pair_period_filter)
            )
        ).scalar() or 0

        pairs_using_bot = (
            await session.execute(
                select(func.count(Pair.id)).where(
                    pair_period_filter,
                    Pair.status.in_([PairStatus.TRIAL.value, PairStatus.ACTIVE.value]),
                )
            )
        ).scalar() or 0

        pairs_past_due = (
            await session.execute(
                select(func.count(Pair.id)).where(
                    pair_period_filter,
                    Pair.status == PairStatus.PAST_DUE.value,
                )
            )
        ).scalar() or 0

        pairs_cancelled = (
            await session.execute(
                select(func.count(Pair.id)).where(
                    pair_period_filter,
                    Pair.status == PairStatus.CANCELLED.value,
                )
            )
        ).scalar() or 0

        pairs_with_demo = (
            await session.execute(
                select(func.count(Pair.id)).where(
                    pair_period_filter,
                    Pair.status == PairStatus.TRIAL.value,
                )
            )
        ).scalar() or 0

        pairs_with_subscription = (
            await session.execute(
                select(func.count(func.distinct(Pair.id)))
                .join(Subscription, Subscription.pair_id == Pair.id)
                .where(
                    pair_period_filter,
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                )
            )
        ).scalar() or 0

        return {
            "stats_tab": "users",
            "period_days": period_days,
            "period_label": stats_period_label(period_days),
            "total_users": total_users,
            "new_users": new_users,
            "users_in_pairs": users_in_pairs,
            "users_without_pairs": users_without_pairs,
            "solo_no_mode": solo_no_mode,
            "solo_waiting_partner": solo_waiting_partner,
            "new_solo_in_period": new_solo_in_period,
            "total_pairs": total_pairs,
            "pairs_using_bot": pairs_using_bot,
            "pairs_past_due": pairs_past_due,
            "pairs_cancelled": pairs_cancelled,
            "pairs_with_demo": pairs_with_demo,
            "pairs_with_subscription": pairs_with_subscription,
        }
    except Exception as e:
        logger.error("Error getting admin user statistics", error=str(e), exc_info=True)
        raise


async def get_admin_payment_statistics(
    session: AsyncSession,
    period_days: int | None = DEFAULT_ADMIN_STATS_PERIOD_DAYS,
) -> dict:
    """Payment-centric admin statistics. Counts are per pair, not per payer."""
    try:
        period_start = _period_start(period_days)
        payment_period_filter = _payment_period_filter(period_start)
        gift_period_filter = _gift_period_filter(period_start)
        plan_expr = _plan_expr()
        is_gift = Subscription.yoo_id.like("admin_gift_%")

        paid_pairs_result = await session.execute(
            select(func.count(func.distinct(PairPayment.pair_id))).where(
                payment_period_filter
            )
        )
        paid_pairs_from_records = paid_pairs_result.scalar() or 0

        paid_transactions = (
            await session.execute(
                select(func.count(PairPayment.id)).where(payment_period_filter)
            )
        ).scalar() or 0

        payment_pair_ids_subq = (
            select(PairPayment.pair_id).where(payment_period_filter).distinct()
        )
        legacy_pairs = (
            await session.execute(
                select(func.count(func.distinct(Subscription.pair_id))).where(
                    _is_real_payment_yoo_id(),
                    gift_period_filter,
                    ~Subscription.pair_id.in_(payment_pair_ids_subq),
                )
            )
        ).scalar() or 0

        paid_pairs = paid_pairs_from_records + legacy_pairs

        by_plan = _empty_plan_dict()
        plan_rows = await session.execute(
            select(
                PairPayment.plan_id,
                func.count(func.distinct(PairPayment.pair_id)),
            )
            .where(payment_period_filter)
            .group_by(PairPayment.plan_id)
        )
        for plan_key, count in plan_rows:
            if plan_key in by_plan:
                by_plan[plan_key] = count

        currency_rows = await session.execute(
            select(
                PairPayment.currency,
                func.count(func.distinct(PairPayment.pair_id)),
                func.sum(PairPayment.amount),
            )
            .where(payment_period_filter)
            .group_by(PairPayment.currency)
            .order_by(PairPayment.currency)
        )
        by_currency: dict[str, dict[str, Decimal | int]] = {}
        total_revenue: dict[str, Decimal] = {}
        for currency, pair_count, amount_sum in currency_rows:
            code = (currency or "RUB").upper()
            revenue = Decimal(amount_sum or 0)
            by_currency[code] = {
                "pairs": pair_count or 0,
                "revenue": revenue,
            }
            total_revenue[code] = revenue

        gifted_by_plan = _empty_plan_dict()
        gift_rows = await session.execute(
            select(plan_expr.label("plan"), func.count(func.distinct(Subscription.pair_id)))
            .join(Pair, Pair.id == Subscription.pair_id)
            .where(
                Subscription.status == SubscriptionStatus.ACTIVE.value,
                is_gift,
                gift_period_filter,
            )
            .group_by(plan_expr)
        )
        for plan_key, count in gift_rows:
            if plan_key in gifted_by_plan:
                gifted_by_plan[plan_key] = count

        gifted_pairs = sum(gifted_by_plan.values())
        has_detailed_payments = paid_pairs_from_records > 0 or paid_transactions > 0

        return {
            "stats_tab": "payments",
            "period_days": period_days,
            "period_label": stats_period_label(period_days),
            "paid_pairs": paid_pairs,
            "paid_transactions": paid_transactions,
            "payments_by_plan": by_plan,
            "payments_by_currency": by_currency,
            "total_revenue": total_revenue,
            "gifted_pairs": gifted_pairs,
            "gifted_by_plan": gifted_by_plan,
            "has_detailed_payments": has_detailed_payments,
            "legacy_pairs_only": legacy_pairs if legacy_pairs and not has_detailed_payments else 0,
        }
    except Exception as e:
        logger.error("Error getting admin payment statistics", error=str(e), exc_info=True)
        raise


async def get_admin_statistics(
    session: AsyncSession,
    period_days: int | None = DEFAULT_ADMIN_STATS_PERIOD_DAYS,
    stats_tab: str = DEFAULT_ADMIN_STATS_TAB,
) -> dict:
    """Get admin statistics for the selected tab and period."""
    if stats_tab == "payments":
        return await get_admin_payment_statistics(session, period_days=period_days)
    return await get_admin_user_statistics(session, period_days=period_days)
