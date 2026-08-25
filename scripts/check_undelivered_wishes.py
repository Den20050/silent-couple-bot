#!/usr/bin/env python3
"""List daily_state rows with sent but possibly undelivered wishes."""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select

from src.core.constants import PairStatus
from src.core.di.container import create_container, initialize_container
from src.db.models import DailyState, Pair
from src.services.messaging.wish_photo_message_id import wish_photo_message_id_key


async def check(since: date) -> None:
    container = create_container()
    await initialize_container(container)
    try:
        redis = container.redis
        async with container.session_factory() as session:
            for pic_type in ("morning", "evening"):
                initiator_col = getattr(DailyState, f"{pic_type}_initiator")
                responded_col = getattr(DailyState, f"{pic_type}_responded_at")
                file_col = getattr(DailyState, f"{pic_type}_file_id")

                rows = await session.execute(
                    select(DailyState, Pair)
                    .join(Pair, Pair.id == DailyState.pair_id)
                    .where(
                        DailyState.day >= since,
                        initiator_col.isnot(None),
                        responded_col.is_(None),
                        file_col.isnot(None),
                        Pair.status.in_(
                            [PairStatus.TRIAL.value, PairStatus.ACTIVE.value]
                        ),
                    )
                    .order_by(DailyState.day, DailyState.pair_id)
                )

                pending = 0
                for daily_state, pair in rows.all():
                    from src.db.models import User

                    initiator = await session.get(
                        User, getattr(daily_state, f"{pic_type}_initiator")
                    )
                    user_a = await session.get(User, pair.uid_a)
                    user_b = await session.get(User, pair.uid_b)
                    if not initiator or not user_a or not user_b:
                        continue
                    recipient = user_b if initiator.id == user_a.id else user_a
                    key = wish_photo_message_id_key(
                        tg_id=recipient.tg_id,
                        pair_id=pair.id,
                        pic_type=pic_type,
                        day=daily_state.day,
                    )
                    tracked = bool(redis and await redis.get(key))
                    if not tracked:
                        pending += 1
                        print(
                            f"{pic_type} day={daily_state.day} pair={pair.id} "
                            f"status={pair.status} recipient={recipient.tg_id}"
                        )
                print(f"=== {pic_type}: {pending} need redelivery (since {since}) ===")
    finally:
        await container.close()


def main() -> None:
    since = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 8, 24)
    asyncio.run(check(since))


if __name__ == "__main__":
    main()
