"""Build notification window selection prompt texts."""

from __future__ import annotations

from typing import Any, Literal

from src.core.messages import get_message
from src.services.pair_time_window import format_window_range

PicType = Literal["morning", "evening"]


def partner_id_for_pair(pair: Any, user_id: int) -> int:
    return pair.uid_b if pair.uid_a == user_id else pair.uid_a


def _partner_info_block(partner: Any | None, pic_type: PicType) -> str:
    if partner is None:
        return ""
    if pic_type == "morning":
        start_hour = getattr(partner, "morning_window_start_hour", 7)
    else:
        start_hour = getattr(partner, "evening_window_start_hour", 21)
    partner_range = format_window_range(int(start_hour))
    return get_message("NOTIF_TIME_PARTNER_WINDOW_INFO", partner_range=partner_range)


def notif_time_morning_prompt_text(user: Any, partner: Any | None = None) -> str:
    current = format_window_range(getattr(user, "morning_window_start_hour", 7))
    return get_message(
        "NOTIF_TIME_MORNING_PROMPT",
        current_range=current,
        partner_info=_partner_info_block(partner, "morning"),
    )


def notif_time_evening_prompt_text(user: Any, partner: Any | None = None) -> str:
    current = format_window_range(getattr(user, "evening_window_start_hour", 21))
    return get_message(
        "NOTIF_TIME_EVENING_PROMPT",
        current_range=current,
        partner_info=_partner_info_block(partner, "evening"),
    )
