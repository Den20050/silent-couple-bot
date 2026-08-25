from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from src.services.pair_time_window import (
    can_user_send_wish,
    is_delivery_period_expired,
    is_user_in_delivery_period,
    is_user_in_prompt_window,
    is_user_in_time_window,
    is_wish_period_annulled,
    is_wish_response_still_valid,
    should_defer_wish_delivery,
)


def _user(*, utc_offset: int = 3, evening_hour: int = 21, morning_hour: int = 7):
    return SimpleNamespace(
        utc_offset=utc_offset,
        morning_window_start_hour=morning_hour,
        evening_window_start_hour=evening_hour,
    )


def test_is_user_in_prompt_window_evening() -> None:
    user = _user(evening_hour=21)
    assert is_user_in_prompt_window(user, "evening", datetime(2026, 8, 12, 18, 5, 0))
    assert not is_user_in_prompt_window(user, "evening", datetime(2026, 8, 12, 17, 30, 0))


def test_is_user_in_prompt_window_morning() -> None:
    user = _user(morning_hour=7)
    assert is_user_in_prompt_window(user, "morning", datetime(2026, 8, 12, 4, 30, 0))
    assert not is_user_in_prompt_window(user, "morning", datetime(2026, 8, 12, 10, 30, 0))


def test_is_user_in_time_window_alias() -> None:
    user = _user(morning_hour=7)
    assert is_user_in_time_window(user, "morning", datetime(2026, 8, 12, 4, 30, 0))


def test_users_with_different_prompt_windows_are_independent() -> None:
    early = _user(evening_hour=20)
    late = _user(evening_hour=21)
    now = datetime(2026, 8, 12, 17, 30, 0)  # 20:30 MSK
    assert is_user_in_prompt_window(early, "evening", now)
    assert not is_user_in_prompt_window(late, "evening", now)


def test_delivery_period_morning_wide_window() -> None:
    user = _user(morning_hour=7, evening_hour=21)
    # 07:30 MSK — inside prompt and delivery
    assert is_user_in_delivery_period(user, "morning", datetime(2026, 8, 12, 4, 30, 0))
    # 10:00 MSK — after prompt hour, still morning delivery period
    assert is_user_in_delivery_period(user, "morning", datetime(2026, 8, 12, 7, 0, 0))
    # 21:00 MSK — evening started, morning delivery closed
    assert not is_user_in_delivery_period(user, "morning", datetime(2026, 8, 12, 18, 0, 0))


def test_should_defer_morning_before_window_only() -> None:
    user = _user(morning_hour=7, evening_hour=21)
    # 06:20 MSK — defer
    assert should_defer_wish_delivery(user, "morning", datetime(2026, 8, 12, 3, 20, 0))
    # 10:08 MSK — deliver immediately
    assert not should_defer_wish_delivery(user, "morning", datetime(2026, 8, 12, 7, 8, 0))


def test_can_send_morning_until_evening_window_starts() -> None:
    user = _user(morning_hour=7, evening_hour=21)
    # 06:00 MSK — before morning window, cannot send yet
    assert not can_user_send_wish(user, "morning", datetime(2026, 8, 12, 3, 0, 0))
    # 10:00 MSK — after morning prompt window, before evening
    assert can_user_send_wish(user, "morning", datetime(2026, 8, 12, 7, 0, 0))
    # 21:00 MSK — evening window started, morning send closed
    assert not can_user_send_wish(user, "morning", datetime(2026, 8, 12, 18, 0, 0))


def test_can_send_evening_until_morning_window_starts() -> None:
    user = _user(morning_hour=7, evening_hour=21)
    assert can_user_send_wish(user, "evening", datetime(2026, 8, 12, 19, 0, 0))
    assert can_user_send_wish(user, "evening", datetime(2026, 8, 12, 2, 0, 0))
    assert not can_user_send_wish(user, "evening", datetime(2026, 8, 12, 7, 0, 0))


def test_morning_response_valid_until_evening_same_day() -> None:
    user = _user(morning_hour=7, evening_hour=21)
    day = date(2026, 8, 24)
    assert is_wish_response_still_valid(
        user, "morning", day, datetime(2026, 8, 24, 7, 8, 0)
    )
    assert not is_wish_response_still_valid(
        user, "morning", day, datetime(2026, 8, 24, 18, 0, 0)
    )
    assert not is_wish_response_still_valid(
        user, "morning", date(2026, 8, 23), datetime(2026, 8, 24, 7, 0, 0)
    )


def test_evening_response_valid_until_next_morning() -> None:
    user = _user(morning_hour=7, evening_hour=21)
    day = date(2026, 8, 23)
    assert is_wish_response_still_valid(
        user, "evening", day, datetime(2026, 8, 23, 19, 0, 0)
    )
    assert is_wish_response_still_valid(
        user, "evening", day, datetime(2026, 8, 24, 3, 59, 0)
    )
    assert not is_wish_response_still_valid(
        user, "evening", day, datetime(2026, 8, 24, 4, 0, 0)
    )


def test_is_wish_period_annulled_only_after_opposite_period() -> None:
    user = _user(morning_hour=7, evening_hour=21)
    # 06:46 MSK — before morning delivery, must NOT annul deferred morning wish
    assert not is_wish_period_annulled(user, "morning", datetime(2026, 8, 25, 3, 46, 0))
    # 10:00 MSK — inside morning delivery period
    assert not is_wish_period_annulled(user, "morning", datetime(2026, 8, 25, 7, 0, 0))
    # 21:00 MSK — evening started, morning annulled
    assert is_wish_period_annulled(user, "morning", datetime(2026, 8, 25, 18, 0, 0))
    # 10:00 MSK — daytime, evening wishes annulled
    assert is_wish_period_annulled(user, "evening", datetime(2026, 8, 25, 7, 0, 0))
    # 22:00 MSK — evening delivery period active
    assert not is_wish_period_annulled(user, "evening", datetime(2026, 8, 25, 19, 0, 0))


def test_is_delivery_period_expired_matches_annulled() -> None:
    user = _user(morning_hour=7, evening_hour=21)
    now = datetime(2026, 8, 25, 18, 0, 0)
    assert is_delivery_period_expired(user, "morning", now)
    assert not is_delivery_period_expired(user, "evening", now)
