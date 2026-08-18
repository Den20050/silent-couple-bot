"""First payment promo: +1 month (30 days) once per tg_id pair combination."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.db.repositories.pair_first_payment_bonus import PairFirstPaymentBonusRepository

FIRST_PAYMENT_BONUS_DAYS = 30

# Human-readable effective duration labels (paid period + 1 bonus month).
BONUS_EFFECTIVE_PLAN_NAMES: dict[str, str] = {
    "1_month": "2 месяца",
    "3_months": "4 месяца",
    "6_months": "7 месяцев",
    "1_year": "13 месяцев",
}


async def is_first_payment_bonus_eligible(
    bonus_repo: PairFirstPaymentBonusRepository,
    tg_id_a: int,
    tg_id_b: int,
    *,
    is_lifetime: bool = False,
) -> bool:
    """True when this pair combo can still receive +1 month on payment."""
    if is_lifetime:
        return False
    return not await bonus_repo.is_used(tg_id_a, tg_id_b)


async def resolve_first_payment_bonus_days(
    bonus_repo: PairFirstPaymentBonusRepository,
    tg_id_a: int,
    tg_id_b: int,
    *,
    is_lifetime: bool,
) -> tuple[int, bool]:
    """Return (bonus_days_to_add, is_first_payment_for_combo).

    The combo is marked used after any first successful payment (even lifetime).
    Bonus days apply only when eligible and not lifetime.
    """
    already_used = await bonus_repo.is_used(tg_id_a, tg_id_b)
    if already_used:
        return 0, False

    bonus_days = 0 if is_lifetime else FIRST_PAYMENT_BONUS_DAYS
    return bonus_days, True


def bonus_effective_plan_name(plan_id: str) -> str | None:
    """Display name for tariff with bonus applied, or None if not applicable."""
    return BONUS_EFFECTIVE_PLAN_NAMES.get(plan_id)


def bonus_tariff_button_label(plan_id: str, base_name: str) -> str:
    """Short tariff label for payment keyboard when bonus is active."""
    effective = bonus_effective_plan_name(plan_id)
    if effective:
        return f"{base_name} → {effective} 🎁"
    return base_name


def total_period_days_with_bonus(base_period_days: int, bonus_days: int) -> int:
    return base_period_days + bonus_days
