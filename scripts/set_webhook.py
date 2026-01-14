"""Script to set Telegram webhook."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from src.bot.webhook_server import set_webhook, delete_webhook

logger = get_logger(__name__)


async def main():
    """Set or delete webhook."""
    configure_logging(settings.log_level)

    if len(sys.argv) > 1 and sys.argv[1] == "delete":
        logger.info("Deleting webhook...")
        success = await delete_webhook()
        if success:
            logger.info("✅ Webhook deleted successfully")
        else:
            logger.error("❌ Failed to delete webhook")
        return

    if not settings.webhook_url:
        logger.error("❌ WEBHOOK_URL not configured in .env")
        logger.info("Please set WEBHOOK_URL in your .env file")
        return

    logger.info(f"Setting webhook to: {settings.webhook_url}")
    success = await set_webhook()

    if success:
        logger.info("✅ Webhook set successfully")
    else:
        logger.error("❌ Failed to set webhook")


if __name__ == "__main__":
    asyncio.run(main())
