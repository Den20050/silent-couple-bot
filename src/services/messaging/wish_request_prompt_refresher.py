"""Best-effort refresher for aggregated wish request prompts.

We store one aggregated prompt message_id per user/day/pic_type in Redis.
When a wish is sent for a specific pair, we want to immediately refresh the
partner's prompt so the "send wish" CTA is no longer available for that pair.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.protocols.messenger import MessengerProtocol
from src.services.messaging.ui.wish_request_ui import WishRequestUIService

logger = get_logger(__name__)


def _prompt_message_id_key(tg_id: int, pic_type: str, day: date) -> str:
    return f"wish_request_prompt_message_id:{tg_id}:{pic_type}:{day.isoformat()}"


async def refresh_aggregated_wish_prompt(
    *,
    session: AsyncSession,
    telegram_messenger: MessengerProtocol,
    tg_id: int,
    pic_type: str,
    day: date,
) -> None:
    """Refresh aggregated wish prompt for a user (best-effort).

    If the message is not found/was deleted, this is a no-op.

    Args:
        session: DB session.
        telegram_messenger: Messenger for editing messages.
        tg_id: Recipient tg_id whose prompt should be updated.
        pic_type: "morning" or "evening".
        day: Day of the prompt.
    """
    if pic_type not in ("morning", "evening"):
        return

    try:
        from src.core.redis_client import create_redis_client

        redis_client = await create_redis_client(socket_connect_timeout=2, socket_timeout=2)
        if redis_client is None:
            return

        key = _prompt_message_id_key(tg_id=tg_id, pic_type=pic_type, day=day)
        msg_id_raw = await redis_client.get(key)
        await redis_client.aclose()

        if not msg_id_raw:
            return

        try:
            message_id = int(msg_id_raw)
        except (TypeError, ValueError):
            return

        ui_builder = WishRequestUIService(session)
        ui = await ui_builder.build_for_user(user_tg_id=tg_id, pic_type=pic_type, day=day)

        await telegram_messenger.edit_message(
            chat_id=tg_id,
            message_id=message_id,
            text=ui.text,
            reply_markup=ui.reply_markup,
        )
    except Exception as e:
        logger.debug(
            "Failed to refresh aggregated wish prompt (ignored)",
            tg_id=tg_id,
            pic_type=pic_type,
            day=str(day),
            error=str(e),
        )

