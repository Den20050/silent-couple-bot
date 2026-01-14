"""Unified entry point for bot and worker (CLI wrapper).

Этот файл запускает бота в режиме polling (для локальной разработки).
Для production на сервере используйте webhook режим:
    python -m src.entrypoints.webhook
"""

import asyncio
import signal
import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.bootstrap import bootstrap
from src.core.logger import get_logger
from src.entrypoints.bot import run_bot

logger = get_logger(__name__)


def signal_handler(signum, frame):  # noqa: ARG001
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


async def main_async():
    """Main entry point - runs both bot and worker (async)."""
    # Try to ensure SSH tunnels are available for Redis and Database
    tunnel_processes = []
    
    # Create Redis tunnel if needed
    try:
        from src.core.ssh_tunnel import ensure_redis_tunnel, check_redis_accessible
        redis_tunnel = ensure_redis_tunnel()
        if redis_tunnel:
            logger.info("SSH tunnel for Redis created automatically")
            tunnel_processes.append(("Redis", redis_tunnel))
        else:
            if check_redis_accessible():
                logger.debug("Redis is accessible, no tunnel needed")
            else:
                logger.warning(
                    "Redis is not accessible and tunnel was not created. "
                    "Check REDIS_SSH_HOST in .env if you need SSH tunnel."
                )
    except Exception as e:
        logger.warning(f"Failed to create Redis SSH tunnel: {e}")
        logger.info("Continuing without Redis tunnel (Redis might not be available)")
    
    # Create Database tunnel if needed
    try:
        from src.core.ssh_tunnel import ensure_database_tunnel
        db_tunnel = ensure_database_tunnel()
        if db_tunnel:
            logger.info("SSH tunnel for PostgreSQL created automatically")
            tunnel_processes.append(("PostgreSQL", db_tunnel))
        else:
            # Check if DATABASE_SSH_HOST is configured
            from src.core.config import settings
            if settings.database_ssh_host:
                logger.info(
                    "PostgreSQL is accessible (tunnel may already exist or local PostgreSQL)"
                )
            else:
                logger.debug("PostgreSQL is accessible, no tunnel needed")
    except Exception as e:
        logger.warning(f"Failed to create Database SSH tunnel: {e}")
        logger.info("Continuing without Database tunnel (Database might not be available)")
    
    # Bootstrap application
    container = await bootstrap()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Check and update expired subscriptions on startup
    # This ensures status is updated even if bot is not running constantly
    try:
        logger.info("Checking expired subscriptions on startup...")
        from src.worker.tasks.past_due import check_and_update_expired_subscriptions
        from src.worker.di.context import create_worker_context
        
        # Create worker context for the function
        worker_context = create_worker_context(
            settings=container.settings,
            session_factory=container.session_factory,
            redis=container.redis,
            messenger=container.telegram_messenger,
            bot_provider=container.bot_provider,
        )
        
        await check_and_update_expired_subscriptions(
            worker_context=worker_context,
            send_notifications=False,
        )
        logger.info("Expired subscriptions check completed")
    except Exception as e:
        logger.warning(
            "Failed to check expired subscriptions on startup",
            error=str(e),
            exc_info=True,
        )
        logger.info("Continuing with bot startup...")

    logger.info("Starting Silent Couple Bot (Bot + Worker)")

    # Check if arq is available before starting worker
    try:
        import arq  # noqa: F401
    except ImportError:
        logger.error(
            "Module 'arq' not found. Please install dependencies: "
            "pip install -r requirements.txt"
        )
        logger.error("Worker will not start without arq module.")
        logger.info("Starting bot only (without worker)...")
        # Start only bot if arq is not available
        try:
            await run_bot(container=container)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await container.close()
        return

    # Check if Redis is available before starting worker
    # Arq worker requires Redis to function
    redis_available = container.redis is not None
    if not redis_available:
        logger.warning(
            "Redis is not available. Worker requires Redis to function."
        )
        logger.warning("Starting bot only (without worker)...")
        # Start only bot if Redis is not available
        try:
            await run_bot(container=container)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await container.close()
        return

    # Start worker in separate process using subprocess
    # This works better on Windows than multiprocessing
    python_exe = sys.executable

    worker_process = subprocess.Popen(
        [python_exe, "-m", "src.entrypoints.worker"],
        cwd=str(project_root),
    )
    logger.info(f"Worker process started (PID: {worker_process.pid})")

    try:
        # Run bot in main process (reuse container from bootstrap)
        await run_bot(container=container)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        # Terminate worker process
        logger.info("Terminating worker process...")
        worker_process.terminate()
        try:
            worker_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning(
                "Worker process did not terminate gracefully, forcing..."
            )
            worker_process.kill()
            worker_process.wait()
        
        # Close container
        await container.close()
        
        # Close SSH tunnels if created
        for service_name, tunnel_process in tunnel_processes:
            if tunnel_process:
                logger.info(f"Closing SSH tunnel for {service_name}...")
                try:
                    tunnel_process.terminate()
                    tunnel_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    tunnel_process.kill()
                    tunnel_process.wait()
                except Exception as e:
                    logger.warning(f"Error closing SSH tunnel for {service_name}: {e}")
        
        logger.info("Shutdown complete")


def main():
    """Main entry point wrapper."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
