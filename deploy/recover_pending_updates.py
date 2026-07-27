#!/usr/bin/env python3
"""Recover Telegram updates stuck in webhook pending queue.

Run from cron/healthcheck when getWebhookInfo reports pending updates or errors.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.bot.webhook_server import setup_bot  # noqa: E402
from src.core.config import settings  # noqa: E402
from src.core.logger import get_logger  # noqa: E402
from src.services.telegram.bot_factory import create_bot  # noqa: E402

logger = get_logger(__name__)


async def recover() -> int:
    """Fetch and process pending updates via getUpdates fallback."""
    bot = create_bot(settings.tg_bot_token, proxy_url=settings.telegram_proxy_url)
    try:
        info = await bot.get_webhook_info()
        pending = info.pending_update_count or 0
        last_error = info.last_error_message

        if pending <= 0:
            if last_error:
                logger.warning("Clearing stale webhook error", last_error=last_error)
                await bot.set_webhook(
                    url=settings.webhook_url,
                    secret_token=settings.webhook_secret_token,
                    allowed_updates=["message", "callback_query"],
                    max_connections=40,
                    drop_pending_updates=False,
                )
            else:
                logger.info("No pending webhook updates to recover")
            return 0

        logger.warning(
            "Recovering pending webhook updates",
            pending=pending,
            last_error=last_error,
        )

        _, dp = await setup_bot()
        await bot.delete_webhook(drop_pending_updates=False)
        await asyncio.sleep(1)

        updates = await bot.get_updates(timeout=10, limit=100)
        if not updates:
            logger.info("Pending counter set but no updates fetched")
        else:
            for update in updates:
                await dp.feed_update(bot, update)
                logger.info("Recovered update", update_id=update.update_id)

        await bot.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.webhook_secret_token,
            allowed_updates=["message", "callback_query"],
            max_connections=40,
            drop_pending_updates=False,
        )
        info_after = await bot.get_webhook_info()
        logger.info(
            "Webhook restored after recovery",
            pending=info_after.pending_update_count,
            last_error=info_after.last_error_message,
        )
        return len(updates)
    finally:
        await bot.session.close()


def main() -> None:
    recovered = asyncio.run(recover())
    if recovered:
        print(f"recovered={recovered}")


if __name__ == "__main__":
    main()
