#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import func, select

from src.core.di.container import create_container, initialize_container
from src.db.models import User


async def main() -> None:
    c = create_container()
    await initialize_container(c)
    try:
        async with c.session_factory() as s:
            rows = await s.execute(
                select(User.utc_offset, func.count()).group_by(User.utc_offset)
            )
            for offset, count in rows.all():
                print(f"offset {offset}: {count} users")
    finally:
        await c.close()


asyncio.run(main())
