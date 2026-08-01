"""Helpers for resolving subscription plan from payment metadata."""

from src.core.constants import SUBSCRIPTION_PLANS


def plan_id_from_period_days(period_days: int | None, is_lifetime: bool) -> str:
    """Map payment period metadata to a subscription plan id."""
    if is_lifetime:
        return "lifetime"
    if period_days is None:
        return "1_month"

    for plan_id, plan in SUBSCRIPTION_PLANS.items():
        days = plan.get("days")
        if days and days == period_days:
            return plan_id

    for plan_id, plan in SUBSCRIPTION_PLANS.items():
        days = plan.get("days")
        if days and abs(period_days - days) <= 2:
            return plan_id

    return "1_month"
