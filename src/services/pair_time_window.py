"""Per-user time window helpers shared by scheduler, UI, and callbacks.

Each user has their own morning/evening window (users.morning/evening_window_start_hour).
Pairs do not share or override another user's schedule.

Three distinct checks:
- **prompt window** (1 hour): when the bot may send «кому отправить?»
- **delivery / send period** (wide): when wishes may be sent, delivered, or answered
- **expired**: when the opposite period has started and morning/evening wishes are void
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Literal

from src.core.config import settings

PicType = Literal["morning", "evening"]


def _get_user_local_datetime(utc_now: datetime, utc_offset: int) -> datetime:
    return utc_now + timedelta(hours=utc_offset)


def _get_user_local_time(utc_now: datetime, utc_offset: int) -> time:
    return _get_user_local_datetime(utc_now, utc_offset).time()


def _is_in_time_window(
    user_local_time: time,
    window_start: time,
    window_end: time,
) -> bool:
    if window_start <= window_end:
        return window_start <= user_local_time <= window_end
    return user_local_time >= window_start or user_local_time <= window_end


def get_user_window_bounds(user_obj: Any, pic_type: PicType) -> tuple[time, time]:
    """Return local start/end times for a user's 1-hour prompt window."""
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


def _window_start_time(user_obj: Any, pic_type: PicType) -> time:
    start, _end = get_user_window_bounds(user_obj, pic_type)
    return start


def is_user_in_prompt_window(
    user_obj: Any,
    pic_type: PicType,
    now_utc: datetime,
) -> bool:
    """True during the 1-hour window when the bot may send a send-request prompt."""
    user_local = _get_user_local_time(now_utc, user_obj.utc_offset)
    start, end = get_user_window_bounds(user_obj, pic_type)
    return _is_in_time_window(user_local, start, end)


def is_user_in_time_window(
    user_obj: Any,
    pic_type: PicType,
    now_utc: datetime,
) -> bool:
    """Alias for :func:`is_user_in_prompt_window` (backward compatibility)."""
    return is_user_in_prompt_window(user_obj, pic_type, now_utc)


def is_user_in_delivery_period(
    user_obj: Any,
    pic_type: PicType,
    now_utc: datetime,
) -> bool:
    """True while morning/evening wishes may be delivered or answered for this user."""
    user_local = _get_user_local_time(now_utc, user_obj.utc_offset)
    morning_start = _window_start_time(user_obj, "morning")
    evening_start = _window_start_time(user_obj, "evening")

    if pic_type == "morning":
        return morning_start <= user_local < evening_start
    if pic_type == "evening":
        return user_local >= evening_start or user_local < morning_start
    return False


def is_delivery_period_expired(
    user_obj: Any,
    pic_type: PicType,
    now_utc: datetime,
) -> bool:
    """True once the opposite period has started and this pic_type is no longer valid."""
    return not is_user_in_delivery_period(user_obj, pic_type, now_utc)


def can_user_send_wish(
    user_obj: Any,
    pic_type: PicType,
    now_utc: datetime,
) -> bool:
    """True while the user may press «send» for this pic_type."""
    return is_user_in_delivery_period(user_obj, pic_type, now_utc)


def should_defer_wish_delivery(
    user_obj: Any,
    pic_type: PicType,
    now_utc: datetime,
) -> bool:
    """True when the recipient's delivery period for pic_type has not started yet."""
    user_local = _get_user_local_time(now_utc, user_obj.utc_offset)
    morning_start = _window_start_time(user_obj, "morning")
    period_start = _window_start_time(user_obj, pic_type)

    if pic_type == "morning":
        return user_local < period_start
    if pic_type == "evening":
        return morning_start <= user_local < period_start
    return False


def is_wish_response_still_valid(
    user_obj: Any,
    pic_type: PicType,
    check_day: date,
    now_utc: datetime,
) -> bool:
    """True while the recipient may still tap «Отправить в ответ» for a given day."""
    local_dt = _get_user_local_datetime(now_utc, user_obj.utc_offset)
    morning_start = _window_start_time(user_obj, "morning")
    evening_start = _window_start_time(user_obj, "evening")

    if pic_type == "morning":
        if check_day != local_dt.date():
            return False
        return local_dt.time() < evening_start

    if pic_type == "evening":
        period_start = datetime.combine(check_day, evening_start)
        period_end = datetime.combine(check_day + timedelta(days=1), morning_start)
        return period_start <= local_dt.replace(tzinfo=None) < period_end

    return False
