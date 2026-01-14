"""Webhook server entry point.

ВНИМАНИЕ: Этот файл используется только для production на сервере.
Для локальной разработки используйте run.py (polling режим).

Запуск webhook сервера:
    python -m src.entrypoints.webhook

Или через systemd service (на сервере):
    sudo systemctl start silent-couple-bot-webhook
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import uvicorn
from src.core.bootstrap import bootstrap
from src.core.config import settings
from src.core.logger import get_logger
from src.bot.webhook_server import app, set_webhook

logger = get_logger(__name__)


def signal_handler(signum, frame):  # noqa: ARG001
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


async def setup_webhook_on_startup():
    """Set webhook URL in Telegram on startup."""
    if settings.webhook_url:
        logger.info("Setting webhook URL on startup...")
        success = await set_webhook()
        if success:
            logger.info("✅ Webhook set successfully", url=settings.webhook_url)
        else:
            logger.error("❌ Failed to set webhook")
    else:
        logger.warning("WEBHOOK_URL not configured, webhook will not be set automatically")


def main():
    """Main entry point for webhook server."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Bootstrap application (for SSH tunnels, etc.)
    logger.info("Bootstrapping application...")
    try:
        container = asyncio.run(bootstrap())
        logger.info("Application bootstrapped successfully")
        # Container will be closed when webhook server stops
    except Exception as e:
        logger.warning(f"Bootstrap failed (may be expected): {e}")
        logger.info("Continuing with webhook server startup...")
    
    # Set webhook on startup
    asyncio.run(setup_webhook_on_startup())
    
    # Get webhook port from settings
    port = settings.webhook_port
    host = "127.0.0.1"  # Listen only on localhost (nginx will proxy)
    
    logger.info(
        "Starting webhook server",
        host=host,
        port=port,
        webhook_path=settings.webhook_path,
        webhook_url=settings.webhook_url,
    )
    
    # Run uvicorn server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()

