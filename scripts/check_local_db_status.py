"""Script to check local database status."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logger import configure_logging, get_logger
import asyncpg

logger = get_logger(__name__)


async def check_local_database_status() -> None:
    """Check local database status."""
    configure_logging("INFO")
    
    # Try to connect to local PostgreSQL on port 5433 (Windows default)
    logger.info("=" * 60)
    logger.info("Checking Local Database Status")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Trying to connect to local PostgreSQL...")
    logger.info("")
    
    # Try common local ports
    ports_to_try = [5433, 5432, 5434]
    
    for port in ports_to_try:
        try:
            logger.info(f"Trying port {port}...")
            conn = await asyncpg.connect(
                host="127.0.0.1",
                port=port,
                user="postgres",  # Try default user
                password="",  # Empty password
                database="silent_couple_bot",
                timeout=1.0,
            )
            
            # Get version
            version = await conn.fetchval("SELECT version()")
            logger.info(f"✅ Connected to PostgreSQL on port {port}")
            logger.info(f"Version: {version[:80]}...")
            logger.info("")
            
            # Check if it's Windows PostgreSQL
            if "windows" in version.lower() or "msvc" in version.lower():
                logger.info("This is LOCAL Windows PostgreSQL")
                logger.info("")
                
                # Count tables
                table_count = await conn.fetchval("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                
                logger.info(f"Total tables: {table_count}")
                
                if table_count > 0:
                    # List tables with row counts
                    result = await conn.fetch("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                        ORDER BY table_name
                    """)
                    
                    logger.info("")
                    logger.info("Tables and row counts:")
                    for row in result:
                        table_name = row['table_name']
                        try:
                            count = await conn.fetchval(f'SELECT COUNT(*) FROM "{table_name}"')
                            logger.info(f"  - {table_name}: {count} rows")
                        except Exception:
                            logger.info(f"  - {table_name}: (could not count)")
                    
                    logger.info("")
                    logger.info("⚠️  Local database has data!")
                    logger.info("   You need to export and import this data to server.")
                else:
                    logger.info("")
                    logger.info("ℹ️  Local database is empty (no tables)")
                
            await conn.close()
            return
            
        except Exception as e:
            logger.debug(f"Port {port}: {str(e)[:50]}...")
            continue
    
    logger.warning("⚠️  Could not connect to local PostgreSQL")
    logger.warning("   Local database might not be running or accessible")
    logger.info("")
    logger.info("This is OK if:")
    logger.info("  - You don't have local PostgreSQL")
    logger.info("  - You're starting fresh on server")
    logger.info("  - Data was already migrated")


if __name__ == "__main__":
    asyncio.run(check_local_database_status())

