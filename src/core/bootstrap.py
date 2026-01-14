"""Application bootstrap using dependency injection container."""

from typing import Optional

from src.core.di.container import (
    Container,
    create_container,
    initialize_container,
)
from src.core.logger import get_logger

logger = get_logger(__name__)


async def bootstrap(log_level: Optional[str] = None) -> Container:
    """Bootstrap application: configure logging, load settings, create and initialize container.

    Args:
        log_level: Optional log level override (defaults to settings.log_level)

    Returns:
        Initialized container with all dependencies
    """
    # Create container (loads settings and configures logging)
    container = create_container(log_level=log_level)

    # Initialize container resources (Redis, etc.)
    await initialize_container(container)

    logger.info("Application bootstrapped successfully")

    return container
