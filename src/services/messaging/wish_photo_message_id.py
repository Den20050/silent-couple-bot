"""Redis keys for tracking wish photo message_id (so we can disable old buttons)."""

from __future__ import annotations

from datetime import date


def wish_photo_message_id_key(*, tg_id: int, pair_id: int, pic_type: str, day: date) -> str:
    """Redis key for a sent wish photo (with respond button) for a specific recipient.

    Args:
        tg_id: Recipient Telegram ID (chat_id)
        pair_id: Pair ID
        pic_type: "morning" or "evening"
        day: Day of the wish

    Returns:
        Redis key string.
    """
    return f"wish_photo_message_id:{tg_id}:{pair_id}:{pic_type}:{day.isoformat()}"

