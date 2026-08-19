"""Per-user time window helpers shared by scheduler, UI, and callbacks.

Each user has their own morning/evening window (users.morning/evening_window_start_hour).
Pairs do not share or override another user's schedule.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, Literal

from src.core.config import settings

PicType = Literal["morning", "evening"]


def _get_user_local_time(utc_now: datetime, utc_offset: int) -> time:
    return (utc_now + timedelta(hours=utc_offset)).time()


def _is_in_time_window(
    user_local_time: time,
    window_start: time,
    window_end: time,
) -> bool:
    if window_start <= window_end:
        return window_start <= user_local_time <= window_end
    return user_local_time >= window_start or user_local_time <= window_end


def get_user_window_bounds(user_obj: Any, pic_type: PicType) -> tuple[time, time]:
    """Return local start/end times for a user's morning or evening window."""
    if pic_type == "morning":
        start_hour = getattr(user_obj, "morning_window_start_hour", None)
    else:
        start_hour = getattr(user_obj, "evening_window_start_hour", None)

    if start_hour is None:
        if pic_type == "morning":
            return settings.morning_start_time, settings.morning_end_time
        return settings.evening_start_time, settings.evening_end_time

    start = time(int(start_hour), 0)
    end = time((int(start_hour) + 1) % 24, 0)
    return start, end


def format_window_range(start_hour: int) -> str:
    """Format a 1-hour window as «07–08»."""
    end_hour = (int(start_hour) + 1) % 24
    return f"{int(start_hour):02d}–{end_hour:02d}"


def is_user_in_time_window(
    user_obj: Any,
    pic_type: PicType,
    now_utc: datetime,
) -> bool:
    """True when the user's local time is inside their own window."""
    user_local = _get_user_local_time(now_utc, user_obj.utc_offset)
    start, end = get_user_window_bounds(user_obj, pic_type)
    return _is_in_time_window(user_local, start, end)


def _window_start_time(user_obj: Any, pic_type: PicType) -> time:
    start, _end = get_user_window_bounds(user_obj, pic_type)
    return start


def can_user_send_wish(
    user_obj: Any,
    pic_type: PicType,
    now_utc: datetime,
) -> bool:
    """True while the user may still press «send» for this pic_type today.

    Morning wishes can be sent until the evening window starts.
    Evening wishes can be sent until the morning window starts (next day included).
    """
    user_local = _get_user_local_time(now_utc, user_obj.utc_offset)
    morning_start = _window_start_time(user_obj, "morning")
    evening_start = _window_start_time(user_obj, "evening")

    if pic_type == "morning":
        return user_local < evening_start
    if pic_type == "evening":
        return user_local < morning_start or user_local >= evening_start
    return False
