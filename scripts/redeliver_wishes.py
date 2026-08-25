#!/usr/bin/env python3
"""Redeliver morning/evening wishes recorded in daily_state but never received."""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select

from src.bot.bootstrap.bot_factory import create_bot_and_dispatcher
from src.core.constants import PairStatus
from src.core.di.container import create_container, initialize_container
from src.core.logger import get_logger
from src.db.models import DailyState, Pair, User
from src.services.messaging.caption_service import CaptionService
from src.services.messaging.pending_wish_delivery import (
    PendingWishDelivery,
    deliver_pending_wish,
)
from src.services.messaging.wish_photo_message_id import wish_photo_message_id_key

logger = get_logger(__name__)

_ACTIVE_PAIR_STATUSES = (PairStatus.TRIAL.value, PairStatus.ACTIVE.value)


async def _redeliver_rows(
    *,
    session,
    messenger,
    redis,
    rows: list[tuple[DailyState, Pair]],
    pic_type: str,
) -> int:
    delivered = 0
    caption_service = CaptionService(session)
    for daily_state, pair in rows:
        target_day = daily_state.day
        initiator = await session.get(User, getattr(daily_state, f"{pic_type}_initiator"))
        if not initiator:
            continue
        user_a = await session.get(User, pair.uid_a)
        user_b = await session.get(User, pair.uid_b)
        if not user_a or not user_b:
            continue
        recipient = user_b if initiator.id == user_a.id else user_a
        file_id = getattr(daily_state, f"{pic_type}_file_id")
        if not file_id:
            continue

        key = wish_photo_message_id_key(
            tg_id=recipient.tg_id,
            pair_id=pair.id,
            pic_type=pic_type,
            day=target_day,
        )
        if await redis.get(key):
            logger.info(
                "Skip pair: wish photo already tracked",
                pair_id=pair.id,
                recipient_tg_id=recipient.tg_id,
                day=str(target_day),
            )
            continue

        caption = await caption_service.build_wish_caption(
            pair=pair,
            sender_user_id=initiator.id,
            pic_type=pic_type,
        )
        pending = PendingWishDelivery(
            pair_id=pair.id,
            pic_type=pic_type,
            day=target_day,
            file_id=file_id,
            initiator_user_id=initiator.id,
            initiator_tg_id=initiator.tg_id,
            recipient_tg_id=recipient.tg_id,
            recipient_user_id=recipient.id,
            caption=caption,
        )
        await deliver_pending_wish(
            session=session,
            messenger=messenger,
            redis=redis,
            pending=pending,
        )
        delivered += 1
        logger.info(
            "Redelivered wish",
            pair_id=pair.id,
            pic_type=pic_type,
            day=str(target_day),
            recipient_tg_id=recipient.tg_id,
        )
    return delivered


async def _fetch_rows(
    session,
    *,
    pic_type: str,
    day: date | None,
    since: date | None,
) -> list[tuple[DailyState, Pair]]:
    file_col = (
        DailyState.morning_file_id
        if pic_type == "morning"
        else DailyState.evening_file_id
    )
    initiator_col = (
        DailyState.morning_initiator
        if pic_type == "morning"
        else DailyState.evening_initiator
    )
    responded_col = (
        DailyState.morning_responded_at
        if pic_type == "morning"
        else DailyState.evening_responded_at
    )

    filters = [
        initiator_col.isnot(None),
        responded_col.is_(None),
        file_col.isnot(None),
        Pair.status.in_(_ACTIVE_PAIR_STATUSES),
    ]
    if day is not None:
        filters.append(DailyState.day == day)
    if since is not None:
        filters.append(DailyState.day >= since)

    result = await session.execute(
        select(DailyState, Pair)
        .join(Pair, Pair.id == DailyState.pair_id)
        .where(*filters)
        .order_by(DailyState.day, DailyState.pair_id)
    )
    return list(result.all())


async def redeliver(
    *,
    day: date | None = None,
    since: date | None = None,
    pic_type: str = "morning",
) -> int:
    if day is None and since is None:
        day = date.today()

    pic_types = ("morning", "evening") if pic_type == "all" else (pic_type,)
    container = create_container()
    await initialize_container(container)
    create_bot_and_dispatcher(container)
    delivered = 0
    try:
        async with container.session_factory() as session:
            messenger = container.telegram_messenger
            redis = container.redis
            if redis is None:
                raise RuntimeError("Redis required")

            for current_pic_type in pic_types:
                rows = await _fetch_rows(
                    session,
                    pic_type=current_pic_type,
                    day=day,
                    since=since,
                )
                delivered += await _redeliver_rows(
                    session=session,
                    messenger=messenger,
                    redis=redis,
                    rows=rows,
                    pic_type=current_pic_type,
                )
    finally:
        await container.close()
    return delivered


def main() -> None:
    args = sys.argv[1:]
    day: date | None = None
    since: date | None = None
    pic_type = "morning"

    if not args:
        day = date.today()
    elif args[0] == "--since":
        since = date.fromisoformat(args[1])
        pic_type = args[2] if len(args) > 2 else "all"
    else:
        day = date.fromisoformat(args[0])
        pic_type = args[1] if len(args) > 1 else "morning"

    count = asyncio.run(redeliver(day=day, since=since, pic_type=pic_type))
    if since is not None:
        print(f"Redelivered {count} wish(es) since {since} ({pic_type})")
    else:
        print(f"Redelivered {count} {pic_type} wish(es) for {day}")


if __name__ == "__main__":
    main()
