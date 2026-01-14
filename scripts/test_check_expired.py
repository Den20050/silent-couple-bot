"""Test check_and_update_expired_subscriptions function."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.bootstrap import bootstrap
from src.core.logger import configure_logging, get_logger
from src.worker.jobs import check_and_update_expired_subscriptions

logger = get_logger(__name__)


async def test_check_expired() -> None:
    """Test checking expired subscriptions."""
    configure_logging("INFO")
    
    logger.info("=" * 60)
    logger.info("Testing check_and_update_expired_subscriptions")
    logger.info("=" * 60)
    logger.info("")
    
    try:
        container = await bootstrap()
        logger.info("Container bootstrapped")
        logger.info("")
        
        logger.info("Calling check_and_update_expired_subscriptions...")
        await check_and_update_expired_subscriptions(
            container=container,
            send_notifications=False,
        )
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ Test completed")
        logger.info("=" * 60)
        
        await container.close()
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_check_expired())

