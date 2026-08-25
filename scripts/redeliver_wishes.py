#!/usr/bin/env python3
"""Redeliver morning/evening wishes recorded in daily_state but never received."""

from __future__ import annotations

import asyncio
from datetime import date, datetime

from sqlalchemy import select

from src.bot.bootstrap.bot_factory import create_bot_and_dispatcher
from src.core.di.container import create_container, initialize_container
from src.core.logger import get_logger
from src.db.models import DailyState, Pair, User
from src.services.messaging.caption_service import CaptionService
from src.services.messaging.pending_wish_delivery import deliver_pending_wish, PendingWishDelivery
from src.services.messaging.wish_photo_message_id import wish_photo_message_id_key

logger = get_logger(__name__)


async def redeliver_for_day(target_day: date, pic_type: str = "morning") -> int:
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

            rows = await session.execute(
                select(DailyState, Pair)
                .join(Pair, Pair.id == DailyState.pair_id)
                .where(
                    DailyState.day == target_day,
                    initiator_col.isnot(None),
                    responded_col.is_(None),
                    file_col.isnot(None),
                )
            )

            caption_service = CaptionService(session)
            for daily_state, pair in rows.all():
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
    finally:
        await container.close()
    return delivered


def main() -> None:
    import sys

    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    pic_type = sys.argv[2] if len(sys.argv) > 2 else "morning"
    count = asyncio.run(redeliver_for_day(day, pic_type))
    print(f"Redelivered {count} {pic_type} wish(es) for {day}")


if __name__ == "__main__":
    main()
