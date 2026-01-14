"""Clear accumulated Arq jobs from Redis.

This script removes all Arq job queues, scheduled jobs, and results from Redis.
Use this after fixing issues with task accumulation to start fresh.

Usage:
    python scripts/clear_arq_jobs.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from src.core.redis_client import create_redis_client

logger = get_logger(__name__)


async def clear_arq_jobs() -> int:
    """Clear all Arq jobs from Redis.
    
    Returns:
        Number of keys deleted
    """
    redis_client = None
    try:
        sys.stdout.write("Connecting to Redis...\n")
        sys.stdout.flush()
        redis_client = await create_redis_client(
            socket_connect_timeout=5, socket_timeout=5
        )
        
        if not redis_client:
            sys.stdout.write("ERROR: Failed to connect to Redis\n")
            sys.stdout.flush()
            return 0
        
        sys.stdout.write("Connected to Redis successfully\n")
        sys.stdout.flush()
        
        # Arq uses keys with prefix "arq:"
        # Common patterns:
        # - arq:queue:* - job queues
        # - arq:job:* - individual jobs
        # - arq:in_progress:* - jobs in progress
        # - arq:result:* - job results
        # - arq:cron:* - cron job schedules
        
        sys.stdout.write("Scanning for Arq keys in Redis...\n")
        sys.stdout.flush()
        logger.info("Scanning for Arq keys in Redis...")
        
        # First, let's check if there are any keys
        all_keys = await redis_client.keys("arq:*")
        sys.stdout.write(f"Found {len(all_keys)} Arq keys in Redis\n")
        sys.stdout.flush()
        logger.info(f"Found {len(all_keys)} Arq keys in Redis")
        
        if all_keys:
            sys.stdout.write(f"Sample keys: {all_keys[:10]}\n")
            sys.stdout.flush()
            logger.info("Sample keys", sample_keys=all_keys[:10])
        
        deleted_count = 0
        cursor = 0
        
        while True:
            cursor, keys = await redis_client.scan(
                cursor=cursor,
                match="arq:*",
                count=1000
            )
            
            if keys:
                deleted = await redis_client.delete(*keys)
                deleted_count += deleted
                sys.stdout.write(
                    f"Deleted {deleted} keys (batch size: {len(keys)}, "
                    f"total: {deleted_count})\n"
                )
                sys.stdout.flush()
                logger.info(
                    "Deleted Arq keys",
                    batch_size=len(keys),
                    deleted=deleted,
                    total_deleted=deleted_count,
                )
            
            if cursor == 0:
                break
        
        sys.stdout.write(
            f"Arq jobs cleared successfully. Total keys deleted: {deleted_count}\n"
        )
        sys.stdout.flush()
        logger.info(
            "Arq jobs cleared successfully",
            total_keys_deleted=deleted_count,
        )
        
        return deleted_count
        
    except Exception as e:
        sys.stdout.write(f"ERROR: Failed to clear Arq jobs: {e}\n")
        sys.stdout.flush()
        logger.error(
            "Failed to clear Arq jobs",
            error=str(e),
            exc_info=True,
        )
        raise
    finally:
        if redis_client:
            try:
                await redis_client.aclose()
            except Exception:
                pass


if __name__ == "__main__":
    configure_logging(settings.log_level)
    
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("Arq Jobs Cleanup Script\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(f"Redis URL: {settings.redis_url}\n")
    sys.stdout.write("\n")
    sys.stdout.flush()
    
    logger.info("Starting Arq jobs cleanup...")
    logger.info(f"Redis URL: {settings.redis_url}")
    
    try:
        deleted = asyncio.run(clear_arq_jobs())
        sys.stdout.write("\n")
        sys.stdout.write("Cleanup completed successfully\n")
        sys.stdout.flush()
        logger.info("Cleanup completed successfully", total_deleted=deleted)
    except KeyboardInterrupt:
        sys.stdout.write("\nCleanup interrupted by user\n")
        sys.stdout.flush()
        logger.info("Cleanup interrupted by user")
        sys.exit(1)
    except Exception as e:
        sys.stdout.write(f"\nERROR: Cleanup failed: {e}\n")
        sys.stdout.flush()
        logger.error("Cleanup failed", error=str(e), exc_info=True)
        sys.exit(1)
