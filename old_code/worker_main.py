"""Worker main entry point."""

import asyncio

from arq import create_pool
from arq.worker import Worker

from src.core.config import settings
from src.core.logger import configure_logging
from src.worker.jobs import WorkerSettings

if __name__ == "__main__":
    configure_logging(settings.log_level)
    
    worker = Worker(
        functions=WorkerSettings.functions,
        cron_jobs=WorkerSettings.cron_jobs,
        redis_settings=WorkerSettings.redis_settings,
    )
    worker.run()
