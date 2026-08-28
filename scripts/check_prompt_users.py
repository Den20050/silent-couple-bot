#!/usr/bin/env python3
"""Correlate worker prompt sends with user window settings."""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select

from src.core.di.container import create_container, initialize_container
from src.db.models import User
from src.services.pair_time_window import get_user_window_bounds, is_user_in_prompt_window


async def main() -> None:
    log_path = Path("/home/telegram-bot/logs/bot.log")
    if len(sys.argv) > 1:
        log_path = Path(sys.argv[1])

    c = create_container()
    await initialize_container(c)
    try:
        async with c.session_factory() as s:
            users = {
                u.tg_id: u
                for u in (await s.execute(select(User))).scalars().all()
            }

        pat = re.compile(
            r'"sent_count": (\d+).*Morning sender completed.*"timestamp": "([^"]+)"'
        )
        print("Morning sends with eligible users (from worker log pattern):")
        print("(Check journalctl for precise timing)\n")

        for pic in ("morning", "evening"):
            print(f"=== Active users {pic} windows ===")
            for u in sorted(users.values(), key=lambda x: x.id):
                if u.username:
                    bounds = get_user_window_bounds(u, pic)
                    print(
                        f"  @{u.username} offset={u.utc_offset} "
                        f"hour={getattr(u, f'{pic}_window_start_hour')} "
                        f"prompt {bounds[0]}-{bounds[1]}"
                    )
    finally:
        await c.close()


asyncio.run(main())
