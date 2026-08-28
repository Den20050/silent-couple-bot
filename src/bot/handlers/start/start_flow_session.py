"""Track /start flow message IDs for cleanup (Redis)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)

_START_FLOW_TTL_SECONDS = 3600
_START_FLOW_KEY_PREFIX = "start_flow"


@dataclass
class StartFlowSession:
    user_start_message_id: int | None = None
    bot_message_ids: list[int] = field(default_factory=list)
    prompt_message_id: int | None = None


def _session_key(tg_id: int) -> str:
    return f"{_START_FLOW_KEY_PREFIX}:{tg_id}"


async def save_start_flow_session(
    redis: Any,
    tg_id: int,
    session: StartFlowSession,
) -> None:
    if redis is None:
        return
    try:
        await redis.set(
            _session_key(tg_id),
            json.dumps(asdict(session)),
            ex=_START_FLOW_TTL_SECONDS,
        )
    except Exception as exc:
        logger.warning("Failed to save start flow session", tg_id=tg_id, error=str(exc))


async def load_start_flow_session(redis: Any, tg_id: int) -> StartFlowSession | None:
    if redis is None:
        return None
    try:
        raw = await redis.get(_session_key(tg_id))
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        data = json.loads(raw)
        return StartFlowSession(
            user_start_message_id=data.get("user_start_message_id"),
            bot_message_ids=list(data.get("bot_message_ids") or []),
            prompt_message_id=data.get("prompt_message_id"),
        )
    except Exception as exc:
        logger.warning("Failed to load start flow session", tg_id=tg_id, error=str(exc))
        return None


async def clear_start_flow_session(redis: Any, tg_id: int) -> None:
    if redis is None:
        return
    try:
        await redis.delete(_session_key(tg_id))
    except Exception as exc:
        logger.warning("Failed to clear start flow session", tg_id=tg_id, error=str(exc))
