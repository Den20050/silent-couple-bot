#!/usr/bin/env python3
import asyncio
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select

from src.core.di.container import create_container, initialize_container
from src.db.models import DailyState, Pair, User
from src.services.messaging.wish_photo_message_id import wish_photo_message_id_key


async def main() -> None:
    c = create_container()
    await initialize_container(c)
    try:
        redis = c.redis
        async with c.session_factory() as s:
            for uname in ["eonubis", "alexia_ray", "Den20050", "Benyablack"]:
                r = await s.execute(select(User).where(User.username.ilike(uname)))
                u = r.scalar_one_or_none()
                if u:
                    print(
                        f"User @{uname}: id={u.id} tg={u.tg_id} "
                        f"morning={u.morning_window_start_hour} "
                        f"evening={u.evening_window_start_hour} offset={u.utc_offset}"
                    )
            print()
            for pid in [14, 17, 18]:
                p = await s.get(Pair, pid)
                ds_r = await s.execute(
                    select(DailyState).where(
                        DailyState.pair_id == pid, DailyState.day == date(2026, 8, 25)
                    )
                )
                d = ds_r.scalar_one_or_none()
                print(f"Pair {pid} status={p.status if p else None}")
                if d:
                    print(
                        f"  morning: init={d.morning_initiator} resp={d.morning_responded_at} "
                        f"sent_at={d.morning_sent_at} file={bool(d.morning_file_id)}"
                    )
                    print(
                        f"  evening: init={d.evening_initiator} resp={d.evening_responded_at} "
                        f"sent_at={d.evening_sent_at} file={bool(d.evening_file_id)}"
                    )
                ua = await s.get(User, p.uid_a) if p else None
                ub = await s.get(User, p.uid_b) if p else None
                for u in (ua, ub):
                    if not u:
                        continue
                    for pic in ("morning", "evening"):
                        key = wish_photo_message_id_key(
                            tg_id=u.tg_id, pair_id=pid, pic_type=pic, day=date(2026, 8, 25)
                        )
                        tracked = await redis.get(key) if redis else None
                        print(
                            f"  redis {pic} @{u.username} tg={u.tg_id}: "
                            f"{'delivered msg_id=' + str(tracked) if tracked else 'NOT tracked'}"
                        )
                pending_key = f"pending_wish_delivery:{pid}:evening:2026-08-25"
                pending = await redis.get(pending_key) if redis else None
                print(f"  pending evening: {bool(pending)}")
            idx = await redis.smembers("pending_wish_delivery:index") if redis else set()
            print(f"\nPending index ({len(idx)}):")
            for item in sorted(idx):
                print(f"  {item}")
    finally:
        await c.close()


asyncio.run(main())
