from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from src.services.pair_time_window import can_user_send_wish, is_user_in_time_window


def _user(*, utc_offset: int = 3, evening_hour: int = 21, morning_hour: int = 7):
    return SimpleNamespace(
        utc_offset=utc_offset,
        morning_window_start_hour=morning_hour,
        evening_window_start_hour=evening_hour,
    )


def test_is_user_in_time_window_evening() -> None:
    user = _user(evening_hour=21)
    assert is_user_in_time_window(user, "evening", datetime(2026, 8, 12, 18, 5, 0))
    assert not is_user_in_time_window(user, "evening", datetime(2026, 8, 12, 17, 30, 0))


def test_is_user_in_time_window_morning() -> None:
    user = _user(morning_hour=7)
    assert is_user_in_time_window(user, "morning", datetime(2026, 8, 12, 4, 30, 0))
    assert not is_user_in_time_window(user, "morning", datetime(2026, 8, 12, 10, 30, 0))


def test_users_with_different_windows_are_independent() -> None:
    early = _user(evening_hour=20)
    late = _user(evening_hour=21)
    now = datetime(2026, 8, 12, 17, 30, 0)  # 20:30 MSK
    assert is_user_in_time_window(early, "evening", now)
    assert not is_user_in_time_window(late, "evening", now)


def test_can_send_morning_until_evening_window_starts() -> None:
    user = _user(morning_hour=7, evening_hour=21)
    # 10:00 MSK — after morning prompt window, before evening
    assert can_user_send_wish(user, "morning", datetime(2026, 8, 12, 7, 0, 0))
    # 21:00 MSK — evening window started, morning send closed
    assert not can_user_send_wish(user, "morning", datetime(2026, 8, 12, 18, 0, 0))


def test_can_send_evening_until_morning_window_starts() -> None:
    user = _user(morning_hour=7, evening_hour=21)
    # 22:00 MSK — after evening prompt hour, still same calendar evening period
    assert can_user_send_wish(user, "evening", datetime(2026, 8, 12, 19, 0, 0))
    # 05:00 MSK — before morning, still evening send period from previous day
    assert can_user_send_wish(user, "evening", datetime(2026, 8, 12, 2, 0, 0))
    # 10:00 MSK — between morning and evening, evening send closed
    assert not can_user_send_wish(user, "evening", datetime(2026, 8, 12, 7, 0, 0))
