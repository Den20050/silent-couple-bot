"""Unit tests for first payment bonus promo."""

from unittest.mock import AsyncMock

import pytest

from src.services.payment.first_payment_bonus import (
    BONUS_EFFECTIVE_PLAN_NAMES,
    FIRST_PAYMENT_BONUS_DAYS,
    bonus_effective_plan_name,
    bonus_tariff_button_label,
    is_first_payment_bonus_eligible,
    resolve_first_payment_bonus_days,
    total_period_days_with_bonus,
)


@pytest.fixture
def bonus_repo_unused():
    repo = AsyncMock()
    repo.is_used = AsyncMock(return_value=False)
    return repo


@pytest.fixture
def bonus_repo_used():
    repo = AsyncMock()
    repo.is_used = AsyncMock(return_value=True)
    return repo


@pytest.mark.parametrize(
    ("plan_id", "expected"),
    [
        ("1_month", "2 месяца"),
        ("3_months", "4 месяца"),
        ("6_months", "7 месяцев"),
        ("1_year", "13 месяцев"),
        ("lifetime", None),
    ],
)
def test_bonus_effective_plan_name(plan_id, expected):
    assert bonus_effective_plan_name(plan_id) == expected


def test_bonus_tariff_button_label():
    assert bonus_tariff_button_label("1_month", "1 месяц") == "1 месяц → 2 месяца 🎁"
    assert bonus_tariff_button_label("lifetime", "Навсегда") == "Навсегда"


@pytest.mark.asyncio
async def test_is_eligible_when_unused(bonus_repo_unused):
    assert await is_first_payment_bonus_eligible(
        bonus_repo_unused, 111, 222
    ) is True


@pytest.mark.asyncio
async def test_not_eligible_when_used(bonus_repo_used):
    assert await is_first_payment_bonus_eligible(
        bonus_repo_used, 111, 222
    ) is False


@pytest.mark.asyncio
async def test_not_eligible_for_lifetime(bonus_repo_unused):
    assert await is_first_payment_bonus_eligible(
        bonus_repo_unused, 111, 222, is_lifetime=True
    ) is False


@pytest.mark.asyncio
async def test_resolve_bonus_days_for_first_regular_payment(bonus_repo_unused):
    bonus_days, is_first = await resolve_first_payment_bonus_days(
        bonus_repo_unused, 111, 222, is_lifetime=False
    )
    assert bonus_days == FIRST_PAYMENT_BONUS_DAYS
    assert is_first is True


@pytest.mark.asyncio
async def test_resolve_no_bonus_for_repeat_payment(bonus_repo_used):
    bonus_days, is_first = await resolve_first_payment_bonus_days(
        bonus_repo_used, 111, 222, is_lifetime=False
    )
    assert bonus_days == 0
    assert is_first is False


@pytest.mark.asyncio
async def test_resolve_lifetime_first_payment_consumes_promo_no_bonus(bonus_repo_unused):
    bonus_days, is_first = await resolve_first_payment_bonus_days(
        bonus_repo_unused, 111, 222, is_lifetime=True
    )
    assert bonus_days == 0
    assert is_first is True


def test_total_period_days_with_bonus():
    assert total_period_days_with_bonus(30, FIRST_PAYMENT_BONUS_DAYS) == 60
    assert total_period_days_with_bonus(90, 0) == 90


def test_bonus_effective_names_cover_all_non_lifetime_plans():
    non_lifetime_plans = ("1_month", "3_months", "6_months", "1_year")
    for plan_id in non_lifetime_plans:
        assert plan_id in BONUS_EFFECTIVE_PLAN_NAMES
