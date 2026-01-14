"""Bot entry point."""

import asyncio
from typing import Optional

from src.core.bootstrap import bootstrap
from src.core.di.container import Container
from src.core.logger import get_logger
from src.bot.app import (
    create_bot_app,
    setup_bot_commands,
    verify_bot_connection,
    verify_redis_connection,
)

logger = get_logger(__name__)


async def run_bot_async(container: Container) -> None:
    """Run bot in async context.
    
    Args:
        container: Dependency injection container
    """
    logger.info("Starting bot process...")

    # Create bot application
    bot, dp = await create_bot_app(container)

    # Verify bot connection
    await verify_bot_connection(bot)

    # Set up bot commands
    await setup_bot_commands(bot, container)

    # Verify Redis connection
    await verify_redis_connection(container)

    # Start polling
    try:
        logger.info("Starting polling...")
        await dp.start_polling(
            bot, allowed_updates=dp.resolve_used_update_types()
        )
    except Exception as e:
        logger.error("Polling error", error=str(e))
        raise
    finally:
        await bot.session.close()


async def run_bot(container: Optional[Container] = None) -> None:
    """Run bot application.
    
    Args:
        container: Optional pre-initialized container. If None, will bootstrap new one.
    """
    should_close_container = False
    
    if container is None:
        container = await bootstrap()
        should_close_container = True

    try:
        await run_bot_async(container)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Bot error", error=str(e), exc_info=True)
        raise
    finally:
        if should_close_container:
            await container.close()


def main() -> None:
    """Main entry point for bot."""
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()

