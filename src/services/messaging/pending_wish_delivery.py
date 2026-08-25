"""Store and flush wish photo deliveries deferred until recipient's time window."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.core.protocols.messenger import MessengerProtocol
from src.db.repositories.users import UsersRepository
from src.services.messaging.wish_photo_message_id import wish_photo_message_id_key
from src.services.messaging.wish_request_prompt_refresher import refresh_aggregated_wish_prompt
from src.services.pair_time_window import (
    is_user_in_delivery_period,
    is_wish_period_annulled,
)

logger = get_logger(__name__)

_PENDING_INDEX_KEY = "pending_wish_delivery:index"
_PENDING_TTL_SECONDS = 48 * 3600
_WISH_PHOTO_MESSAGE_ID_TTL_SECONDS = 72 * 3600


def _pending_key(pair_id: int, pic_type: str, day: date) -> str:
    return f"pending_wish_delivery:{pair_id}:{pic_type}:{day.isoformat()}"


@dataclass(frozen=True)
class PendingWishDelivery:
    pair_id: int
    pic_type: str
    day: date
    file_id: str
    initiator_user_id: int
    initiator_tg_id: int
    recipient_tg_id: int
    recipient_user_id: int
    caption: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "pair_id": self.pair_id,
                "pic_type": self.pic_type,
                "day": self.day.isoformat(),
                "file_id": self.file_id,
                "initiator_user_id": self.initiator_user_id,
                "initiator_tg_id": self.initiator_tg_id,
                "recipient_tg_id": self.recipient_tg_id,
                "recipient_user_id": self.recipient_user_id,
                "caption": self.caption,
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> PendingWishDelivery:
        data = json.loads(raw)
        return cls(
            pair_id=int(data["pair_id"]),
            pic_type=str(data["pic_type"]),
            day=date.fromisoformat(str(data["day"])),
            file_id=str(data["file_id"]),
            initiator_user_id=int(data["initiator_user_id"]),
            initiator_tg_id=int(data["initiator_tg_id"]),
            recipient_tg_id=int(data["recipient_tg_id"]),
            recipient_user_id=int(data["recipient_user_id"]),
            caption=str(data["caption"]),
        )


async def store_pending_delivery(redis: Redis | None, pending: PendingWishDelivery) -> None:
    """Persist a wish waiting for the recipient's time window."""
    if redis is None:
        raise RuntimeError("Redis is required for deferred wish delivery")

    key = _pending_key(pending.pair_id, pending.pic_type, pending.day)
    await redis.setex(key, _PENDING_TTL_SECONDS, pending.to_json())
    await redis.sadd(_PENDING_INDEX_KEY, key)
    await redis.expire(_PENDING_INDEX_KEY, _PENDING_TTL_SECONDS)


async def get_pending_delivery(
    redis: Redis | None, pair_id: int, pic_type: str, day: date
) -> PendingWishDelivery | None:
    if redis is None:
        return None
    raw = await redis.get(_pending_key(pair_id, pic_type, day))
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode()
    return PendingWishDelivery.from_json(raw)


async def _remove_pending(redis: Redis, key: str) -> None:
    await redis.delete(key)
    await redis.srem(_PENDING_INDEX_KEY, key)


async def deliver_pending_wish(
    *,
    session: AsyncSession,
    messenger: MessengerProtocol,
    redis: Redis,
    pending: PendingWishDelivery,
) -> bool:
    """Send a previously deferred wish photo to the recipient."""
    button_text = get_message("RESPOND_BUTTON")
    callback_prefix = (
        "tap_morning" if pending.pic_type == "morning" else "tap_evening"
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": button_text,
                    "callback_data": (
                        f"{callback_prefix}_{pending.pair_id}_"
                        f"{pending.initiator_tg_id}|{pending.day.isoformat()}"
                    ),
                },
            ],
        ],
    }

    msg = await messenger.send_photo(
        chat_id=pending.recipient_tg_id,
        photo=pending.file_id,
        caption=pending.caption,
        reply_markup=reply_markup,
    )

    try:
        key = wish_photo_message_id_key(
            tg_id=pending.recipient_tg_id,
            pair_id=pending.pair_id,
            pic_type=pending.pic_type,
            day=pending.day,
        )
        await redis.setex(
            key, _WISH_PHOTO_MESSAGE_ID_TTL_SECONDS, str(msg.message_id)
        )
    except Exception as e:
        logger.debug(
            "Failed to store wish photo message_id after deferred delivery",
            pair_id=pending.pair_id,
            error=str(e),
        )

    await refresh_aggregated_wish_prompt(
        session=session,
        telegram_messenger=messenger,
        tg_id=pending.recipient_tg_id,
        pic_type=pending.pic_type,
        day=pending.day,
    )
    return True


async def annul_pending_for_recipient(
    redis: Redis,
    *,
    recipient_user_id: int,
    pic_type: str,
) -> int:
    """Drop pending deliveries for a recipient when a period expires."""
    raw_keys = await redis.smembers(_PENDING_INDEX_KEY)
    if not raw_keys:
        return 0

    removed = 0
    for raw_key in raw_keys:
        key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
        raw_payload = await redis.get(key)
        if not raw_payload:
            await redis.srem(_PENDING_INDEX_KEY, key)
            continue
        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode()
        try:
            pending = PendingWishDelivery.from_json(raw_payload)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            await _remove_pending(redis, key)
            removed += 1
            continue
        if (
            pending.pic_type == pic_type
            and pending.recipient_user_id == recipient_user_id
        ):
            await _remove_pending(redis, key)
            removed += 1
    return removed


async def flush_pending_deliveries(
    *,
    session: AsyncSession,
    messenger: MessengerProtocol,
    redis: Redis | None,
    now_utc: datetime,
    pic_type: str,
    schedule_reminders_fn: Any | None = None,
    settings: Any | None = None,
) -> int:
    """Deliver deferred wishes whose recipients are now inside their window."""
    if redis is None:
        return 0

    raw_keys = await redis.smembers(_PENDING_INDEX_KEY)
    if not raw_keys:
        return 0

    users_repo = UsersRepository(session)
    delivered_count = 0

    for raw_key in raw_keys:
        key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
        raw_payload = await redis.get(key)
        if not raw_payload:
            await redis.srem(_PENDING_INDEX_KEY, key)
            continue

        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode()

        try:
            pending = PendingWishDelivery.from_json(raw_payload)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning("Invalid pending wish payload, dropping", key=key, error=str(e))
            await _remove_pending(redis, key)
            continue

        if pending.pic_type != pic_type:
            continue

        recipient = await users_repo.get_by_id(pending.recipient_user_id)
        if not recipient:
            await _remove_pending(redis, key)
            continue

        if is_wish_period_annulled(recipient, pending.pic_type, now_utc):  # type: ignore[arg-type]
            await _remove_pending(redis, key)
            logger.debug(
                "Annulled expired pending wish",
                pair_id=pending.pair_id,
                pic_type=pending.pic_type,
                day=str(pending.day),
            )
            continue

        if not is_user_in_delivery_period(recipient, pending.pic_type, now_utc):  # type: ignore[arg-type]
            continue

        try:
            await deliver_pending_wish(
                session=session,
                messenger=messenger,
                redis=redis,
                pending=pending,
            )
            await _remove_pending(redis, key)
            delivered_count += 1

            if schedule_reminders_fn is not None and settings is not None:
                await schedule_reminders_fn(
                    pair_id=pending.pair_id,
                    initiator_tg_id=pending.initiator_tg_id,
                    recipient_tg_id=pending.recipient_tg_id,
                    recipient_user_id=pending.recipient_user_id,
                    pic_type=pending.pic_type,
                    settings=settings,
                )
        except Exception as e:
            logger.error(
                "Failed to deliver deferred wish",
                pair_id=pending.pair_id,
                pic_type=pending.pic_type,
                error=str(e),
                exc_info=True,
            )

    return delivered_count
