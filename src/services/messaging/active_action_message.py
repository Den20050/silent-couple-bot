"""Keep only the latest interactive message active (remove buttons from previous ones).

Motivation:
- Users can receive multiple actionable messages (e.g., "Тебя ждут ❤️" reminder with a
  respond button and later a morning/evening wish request prompt).
- If old messages keep their buttons, users may press an outdated action and get confused.

This module stores the current active interactive message_id per user (tg_id) in Redis and
best-effort removes reply_markup (buttons) from the previous message when a new one becomes active.
"""

from __future__ import annotations

from typing import Optional

from redis.asyncio import Redis

from src.core.config import settings
from src.core.logger import get_logger
from src.core.protocols.messenger import MessengerProtocol

logger = get_logger(__name__)

_ACTIVE_TTL_SECONDS = 72 * 3600


def _active_key(tg_id: int) -> str:
    return f"{settings.redis_key_prefix_active_action_message}:{tg_id}"


async def get_active_message_id(redis: Optional[Redis], tg_id: int) -> int | None:
    """Get currently active interactive message_id for a user (if stored)."""
    if redis is None:
        return None
    try:
        raw = await redis.get(_active_key(tg_id))
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return int(raw)
    except Exception:
        return None


async def activate_message(
    *,
    redis: Optional[Redis],
    messenger: MessengerProtocol,
    tg_id: int,
    message_id: int,
    ttl_seconds: int = _ACTIVE_TTL_SECONDS,
) -> None:
    """Mark message as active and disable buttons on the previous active message (best-effort)."""
    if redis is None:
        return

    try:
        prev_id = await get_active_message_id(redis, tg_id)
        if prev_id and prev_id != message_id:
            try:
                await messenger.remove_reply_markup(chat_id=tg_id, message_id=prev_id)
            except Exception as e:
                logger.debug(
                    "Failed to remove reply markup from previous interactive message (ignored)",
                    tg_id=tg_id,
                    prev_message_id=prev_id,
                    error=str(e),
                )

        await redis.setex(_active_key(tg_id), ttl_seconds, str(message_id))
    except Exception as e:
        logger.debug(
            "Failed to update active interactive message (ignored)",
            tg_id=tg_id,
            message_id=message_id,
            error=str(e),
        )


async def is_message_active(
    *,
    redis: Optional[Redis],
    tg_id: int,
    message_id: int,
) -> bool:
    """Check whether the given message_id is currently active for user."""
    active_id = await get_active_message_id(redis, tg_id)
    if active_id is None:
        # If we don't know, don't block (backward-compatible).
        return True
    return active_id == message_id

