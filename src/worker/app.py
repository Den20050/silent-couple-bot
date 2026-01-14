"""Worker application factory."""

from arq.worker import Worker

from src.core.di.container import Container
from src.core.logger import get_logger
from src.worker.jobs import WorkerSettings

logger = get_logger(__name__)


def create_worker(container: Container) -> Worker:  # noqa: ARG001
    """Create arq worker instance.

    Args:
        container: Dependency injection container (reserved for future use)

    Returns:
        Worker instance configured with functions and cron jobs
    """
    logger.info("Creating worker application")

    worker = Worker(
        functions=WorkerSettings.functions,
        cron_jobs=WorkerSettings.cron_jobs,
        redis_settings=WorkerSettings.redis_settings,
    )

    logger.info(
        "Worker created",
        functions_count=len(WorkerSettings.functions),
        cron_jobs_count=len(WorkerSettings.cron_jobs),
    )

    return worker
