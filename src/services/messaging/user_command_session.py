"""Track the user's command message for cleanup when pressing Back."""

from __future__ import annotations

from typing import Any

from aiogram.types import CallbackQuery, Message

from src.core.logger import get_logger
from src.services.telegram.messenger import TelegramMessenger

logger = get_logger(__name__)

_TRIGGER_TTL_SECONDS = 3600
_TRIGGER_KEY_PREFIX = "user_command_trigger"


def _trigger_key(tg_id: int) -> str:
    return f"{_TRIGGER_KEY_PREFIX}:{tg_id}"


async def save_user_command_message(redis: Any, tg_id: int, message_id: int) -> None:
    if redis is None:
        return
    try:
        await redis.set(_trigger_key(tg_id), str(message_id), ex=_TRIGGER_TTL_SECONDS)
    except Exception as exc:
        logger.warning(
            "Failed to save user command message",
            tg_id=tg_id,
            error=str(exc),
        )


async def delete_user_command_message(
    messenger: TelegramMessenger,
    redis: Any,
    tg_id: int,
) -> None:
    if redis is None:
        return
    try:
        raw = await redis.get(_trigger_key(tg_id))
        if raw:
            if isinstance(raw, bytes):
                raw = raw.decode()
            await messenger.delete_message(tg_id, int(raw))
        await redis.delete(_trigger_key(tg_id))
    except Exception as exc:
        logger.debug(
            "Failed to delete user command message (ignored)",
            tg_id=tg_id,
            error=str(exc),
        )


async def track_user_command(message: Message, redis: Any | None = None) -> None:
    """Remember the user's command message id for later Back cleanup."""
    if not message.from_user or redis is None:
        return
    await save_user_command_message(redis, message.from_user.id, message.message_id)


async def cleanup_back_to_chat(
    callback: CallbackQuery,
    messenger: TelegramMessenger,
    *,
    redis: Any | None = None,
    delete_bot_message: bool = True,
) -> None:
    """Delete bot UI message and the user's command that opened this flow."""
    tg_id = callback.from_user.id
    if delete_bot_message:
        try:
            await callback.message.delete()
        except Exception as exc:
            logger.debug(
                "Failed to delete bot message on back (ignored)",
                tg_id=tg_id,
                error=str(exc),
            )
    if redis is not None:
        await delete_user_command_message(messenger, redis, tg_id)
