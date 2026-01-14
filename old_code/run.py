"""Unified entry point for bot and worker."""

import asyncio
import signal
import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.logger import configure_logging, get_logger
from src.core.config import settings

logger = get_logger(__name__)


def run_bot():
    """Run bot in main process."""
    from src.bot.main import main as bot_main
    
    configure_logging(settings.log_level)
    logger.info("Starting bot process...")
    
    try:
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Bot error", error=str(e), exc_info=True)
        raise


def signal_handler(signum, frame):  # noqa: ARG001
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    """Main entry point - runs both bot and worker."""
    # Configure logging
    configure_logging(settings.log_level)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting Silent Couple Bot (Bot + Worker)")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Log level: {settings.log_level}")
    
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
            run_bot()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        return
    
    # Start worker in separate process using subprocess
    # This works better on Windows than multiprocessing
    python_exe = sys.executable
    
    worker_process = subprocess.Popen(
        [python_exe, "-m", "src.worker.main"],
        cwd=str(project_root),
    )
    logger.info(f"Worker process started (PID: {worker_process.pid})")
    
    try:
        # Run bot in main process
        run_bot()
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
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
