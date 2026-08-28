#!/usr/bin/env python3
import asyncio
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select

from src.core.constants import PairStatus
from src.core.di.container import create_container, initialize_container
from src.db.models import Pair, User
from src.services.pair_time_window import get_user_window_bounds, is_user_in_prompt_window


async def main() -> None:
    c = create_container()
    await initialize_container(c)
    try:
        async with c.session_factory() as s:
            pairs = await s.execute(
                select(Pair).where(
                    Pair.status.in_([PairStatus.TRIAL.value, PairStatus.ACTIVE.value])
                )
            )
            seen: set[int] = set()
            print("Users on active/trial pairs:")
            for pair in pairs.scalars():
                for uid in (pair.uid_a, pair.uid_b):
                    if uid in seen:
                        continue
                    seen.add(uid)
                    u = await s.get(User, uid)
                    if not u:
                        continue
                    print(
                        f"  @{u.username} id={u.id} offset={u.utc_offset} "
                        f"morning={u.morning_window_start_hour} evening={u.evening_window_start_hour}"
                    )
                    for pic in ("morning", "evening"):
                        bounds = get_user_window_bounds(u, pic)
                        print(f"    {pic} prompt bounds: {bounds[0]}-{bounds[1]}")
                        for mins in range(-20, 21, 5):
                            hour = getattr(u, f"{pic}_window_start_hour")
                            # simulate at window_start + mins
                            utc_h = hour - u.utc_offset
                            dt = datetime(2026, 8, 28, utc_h, max(0, mins), 0)
                            if mins < 0:
                                dt = datetime(2026, 8, 28, utc_h - 1, 60 + mins, 0)
                            ok = is_user_in_prompt_window(u, pic, dt)
                            local = (dt.hour + u.utc_offset) % 24
                            local_m = dt.minute
                            mark = " <-- FIRST IN" if ok and mins <= 0 and (
                                not is_user_in_prompt_window(
                                    u,
                                    pic,
                                    datetime(2026, 8, 28, utc_h - 1 if mins == -5 else utc_h, 0, 0),
                                )
                                if mins == 0
                                else True
                            ) else (" IN" if ok else "")
                            if -15 <= mins <= 15:
                                print(
                                    f"      offset {mins:+3d}min -> local ~{local:02d}:{local_m:02d} "
                                    f"utc={dt.strftime('%H:%M')}{mark}"
                                )
    finally:
        await c.close()


asyncio.run(main())
