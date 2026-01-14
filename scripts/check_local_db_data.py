"""Check if local database has data."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import configure_logging, get_logger

logger = get_logger(__name__)


async def check_local_db_data(port: int = 5433) -> None:
    """Check if local database has data."""
    configure_logging("INFO")
    
    logger.info("=" * 60)
    logger.info("Checking Local Database Data")
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"Trying to connect to localhost:{port}...")
    logger.info("")
    
    try:
        import asyncpg
        
        conn = await asyncpg.connect(
            host="localhost",
            port=port,
            user="bot_user",
            password="10nrWSP__ipeS2J8",
            database="silent_couple_bot"
        )
        
        # Check table counts
        tables = [
            "users",
            "pairs",
            "subscriptions",
            "daily_state",
            "pics_pool",
            "bot_messages",
        ]
        
        logger.info("Table row counts:")
        total_rows = 0
        
        for table in tables:
            try:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                logger.info(f"  {table}: {count} rows")
                total_rows += count
            except Exception as e:
                logger.warning(f"  {table}: Error - {e}")
        
        await conn.close()
        
        logger.info("")
        logger.info("=" * 60)
        if total_rows > 0:
            logger.info(f"✅ Local database has {total_rows} total rows")
            logger.info("   You should export this data before switching to server")
        else:
            logger.info("ℹ️  Local database is empty")
            logger.info("   No export needed")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Could not connect to local database on port {port}")
        logger.error(f"   Error: {e}")
        logger.error("")
        logger.info("Possible reasons:")
        logger.info("  1. Local PostgreSQL is not running")
        logger.info("  2. Wrong port (try 5432 or 5433)")
        logger.info("  3. Database/user doesn't exist")


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5433
    asyncio.run(check_local_db_data(port))

