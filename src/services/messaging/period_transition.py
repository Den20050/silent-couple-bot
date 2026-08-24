"""Expire stale prompts and wishes when a user's day period switches."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.protocols.messenger import MessengerProtocol
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.services.messaging.active_action_message import (
    ActionKind,
    clear_active_message_if_matches,
    get_active_message_id,
)
from src.services.messaging.pending_wish_delivery import annul_pending_for_recipient
from src.services.messaging.wish_photo_message_id import wish_photo_message_id_key
from src.services.messaging.wish_request_prompt_refresher import prompt_message_id_key
from src.services.pair_time_window import is_delivery_period_expired

logger = get_logger(__name__)

_DEDUP_TTL_SECONDS = 48 * 3600


def _dedup_key(user_id: int, pic_type: str, local_date: date) -> str:
    return f"period_expired:{user_id}:{pic_type}:{local_date.isoformat()}"


async def _delete_or_strip_message(
    messenger: MessengerProtocol,
    *,
    chat_id: int,
    message_id: int,
    delete: bool,
) -> None:
    try:
        if delete:
            await messenger.delete_message(chat_id=chat_id, message_id=message_id)
        else:
            await messenger.remove_reply_markup(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.debug(
            "Failed to clean up period message (ignored)",
            chat_id=chat_id,
            message_id=message_id,
            delete=delete,
            error=str(e),
        )


async def _clear_wish_prompt(
    messenger: MessengerProtocol,
    redis: Redis,
    *,
    tg_id: int,
    pic_type: str,
    day: date,
    delete_message: bool,
) -> None:
    key = prompt_message_id_key(tg_id, pic_type, day)
    raw = await redis.get(key)
    if not raw:
        return
    if isinstance(raw, bytes):
        raw = raw.decode()
    try:
        message_id = int(raw)
    except (TypeError, ValueError):
        await redis.delete(key)
        return

    await _delete_or_strip_message(
        messenger,
        chat_id=tg_id,
        message_id=message_id,
        delete=delete_message,
    )
    await redis.delete(key)

    active_id = await get_active_message_id(redis, tg_id, kind=ActionKind.PROMPT)
    if active_id == message_id:
        await clear_active_message_if_matches(
            redis, tg_id, kind=ActionKind.PROMPT, message_id=message_id
        )


async def _strip_wish_photos_for_days(
    messenger: MessengerProtocol,
    redis: Redis,
    *,
    tg_id: int,
    pair_ids: list[int],
    pic_type: str,
    days: list[date],
) -> None:
    for pair_id in pair_ids:
        for day in days:
            key = wish_photo_message_id_key(
                tg_id=tg_id,
                pair_id=pair_id,
                pic_type=pic_type,
                day=day,
            )
            raw = await redis.get(key)
            if not raw:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode()
            try:
                message_id = int(raw)
            except (TypeError, ValueError):
                await redis.delete(key)
                continue
            await _delete_or_strip_message(
                messenger,
                chat_id=tg_id,
                message_id=message_id,
                delete=False,
            )
            await redis.delete(key)


async def _expire_period_for_user(
    *,
    session: AsyncSession,
    messenger: MessengerProtocol,
    redis: Redis,
    user,
    pic_type: str,
    now_utc: datetime,
    delete_prompt: bool,
    wish_photo_days: list[date],
) -> None:
    local_date = (now_utc + timedelta(hours=user.utc_offset)).date()
    dedup = _dedup_key(user.id, pic_type, local_date)
    if await redis.get(dedup):
        return

    pairs_repo = PairsRepository(session)
    pair_ids = [
        p.id
        for p in await pairs_repo.get_all_by_user_tg_id(user.tg_id)
    ]

    await _clear_wish_prompt(
        messenger,
        redis,
        tg_id=user.tg_id,
        pic_type=pic_type,
        day=local_date,
        delete_message=delete_prompt,
    )
    if pic_type == "evening":
        await _clear_wish_prompt(
            messenger,
            redis,
            tg_id=user.tg_id,
            pic_type=pic_type,
            day=local_date - timedelta(days=1),
            delete_message=delete_prompt,
        )

    removed = await annul_pending_for_recipient(
        redis,
        recipient_user_id=user.id,
        pic_type=pic_type,
    )
    await _strip_wish_photos_for_days(
        messenger,
        redis,
        tg_id=user.tg_id,
        pair_ids=pair_ids,
        pic_type=pic_type,
        days=wish_photo_days,
    )

    await redis.setex(dedup, _DEDUP_TTL_SECONDS, "1")
    logger.info(
        "Period artifacts expired",
        user_id=user.id,
        tg_id=user.tg_id,
        pic_type=pic_type,
        local_date=str(local_date),
        pending_removed=removed,
    )


async def run_period_transitions(
    *,
    session: AsyncSession,
    messenger: MessengerProtocol,
    redis: Redis | None,
    now_utc: datetime,
) -> None:
    """Expire morning/evening artifacts when the opposite period has started."""
    if redis is None:
        return

    pairs_repo = PairsRepository(session)
    users_repo = UsersRepository(session)
    pairs = await pairs_repo.get_active_pairs()

    seen_ids: set[int] = set()
    users = []
    for pair in pairs:
        for uid in (pair.uid_a, pair.uid_b):
            if uid in seen_ids:
                continue
            seen_ids.add(uid)
            user = await users_repo.get_by_id(uid)
            if user is not None:
                users.append(user)

    for user in users:
        local_date = (now_utc + timedelta(hours=user.utc_offset)).date()
        try:
            if is_delivery_period_expired(user, "morning", now_utc):
                await _expire_period_for_user(
                    session=session,
                    messenger=messenger,
                    redis=redis,
                    user=user,
                    pic_type="morning",
                    now_utc=now_utc,
                    delete_prompt=True,
                    wish_photo_days=[local_date],
                )
            if is_delivery_period_expired(user, "evening", now_utc):
                await _expire_period_for_user(
                    session=session,
                    messenger=messenger,
                    redis=redis,
                    user=user,
                    pic_type="evening",
                    now_utc=now_utc,
                    delete_prompt=True,
                    wish_photo_days=[local_date, local_date - timedelta(days=1)],
                )
        except Exception as e:
            logger.warning(
                "Failed period transition for user",
                user_id=user.id,
                error=str(e),
                exc_info=True,
            )
