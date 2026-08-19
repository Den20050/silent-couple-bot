"""Build notification window selection prompt texts."""

from __future__ import annotations

from typing import Any

from src.core.messages import get_message
from src.services.pair_time_window import format_window_range


def notif_time_morning_prompt_text(user: Any) -> str:
    current = format_window_range(getattr(user, "morning_window_start_hour", 7))
    return get_message("NOTIF_TIME_MORNING_PROMPT", current_range=current)


def notif_time_evening_prompt_text(user: Any) -> str:
    current = format_window_range(getattr(user, "evening_window_start_hour", 21))
    return get_message("NOTIF_TIME_EVENING_PROMPT", current_range=current)
