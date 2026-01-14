"""Worker entry point."""

import asyncio
from typing import Optional

from src.core.bootstrap import bootstrap
from src.core.di.container import Container
from src.core.logger import get_logger
from src.worker.app import create_worker

logger = get_logger(__name__)


async def run_worker_async(container: Container) -> None:
    """Run worker in async context.
    
    Args:
        container: Dependency injection container
    """
    logger.info("Starting worker process...")
    
    # Create worker (Worker.__init__ calls asyncio.get_event_loop())
    # This must be done while event loop is active
    worker = create_worker(container)
    
    # Run worker (this is blocking and manages its own event loop)
    worker.run()


async def run_worker(container: Optional[Container] = None) -> None:
    """Run worker application.
    
    Args:
        container: Optional pre-initialized container. If None, will bootstrap new one.
    """
    should_close_container = False
    
    if container is None:
        container = await bootstrap()
        should_close_container = True

    try:
        await run_worker_async(container)
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error("Worker error", error=str(e), exc_info=True)
        raise
    finally:
        if should_close_container:
            await container.close()


def main() -> None:
    """Main entry point for worker."""
    # Create and set event loop for worker process
    # Worker needs an active event loop during initialization
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Bootstrap and create worker (both need active event loop)
        worker = loop.run_until_complete(bootstrap_and_create_worker())
        
        # Run worker (this is blocking and manages its own event loop)
        worker.run()
    finally:
        # Clean up (though worker.run() is blocking, so this may not be reached)
        try:
            loop.close()
        except Exception:
            pass


async def bootstrap_and_create_worker():
    """Bootstrap application and create worker in async context.
    
    Returns:
        Worker instance
    """
    container = await bootstrap()
    worker = create_worker(container)
    return worker


if __name__ == "__main__":
    main()

