"""Script to check if database connection goes through SSH tunnel or local PostgreSQL."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
import asyncpg

logger = get_logger(__name__)


async def check_database_source() -> None:
    """Check if database connection goes to server or local PostgreSQL."""
    configure_logging("INFO")
    
    # Parse database URL
    url = settings.database_url.replace("postgresql+asyncpg://", "")
    
    if "@" not in url:
        logger.error("Invalid database URL format")
        return
    
    # Extract components
    auth_part, db_part = url.split("@", 1)
    if ":" in auth_part:
        user, password = auth_part.split(":", 1)
    else:
        user = auth_part
        password = ""
    
    if "/" in db_part:
        host_part, database = db_part.rsplit("/", 1)
        if ":" in host_part:
            host, port = host_part.split(":", 1)
            port = int(port)
        else:
            host = host_part
            port = 5432
    else:
        logger.error("Database name not found in URL")
        return
    
    logger.info("=" * 60)
    logger.info("Checking Database Connection Source")
    logger.info("=" * 60)
    logger.info(f"Connecting to: {host}:{port}/{database} as {user}")
    logger.info("")
    
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
        
        # Get PostgreSQL version
        version = await conn.fetchval("SELECT version()")
        logger.info(f"PostgreSQL version: {version[:100]}...")
        logger.info("")
        
        # Check if it's Windows PostgreSQL (local) or Linux PostgreSQL (server)
        if "windows" in version.lower() or "msvc" in version.lower():
            logger.warning("⚠️  WARNING: Connected to LOCAL PostgreSQL on Windows!")
            logger.warning("   This means you're NOT connecting to the server via SSH tunnel.")
            logger.warning("")
            logger.info("To connect to server:")
            logger.info("1. Make sure PostgreSQL is NOT running locally on port 5433")
            logger.info("2. Or stop local PostgreSQL service")
            logger.info("3. Then SSH tunnel will be created automatically")
        elif "linux" in version.lower() or "ubuntu" in version.lower():
            logger.info("✅ Connected to PostgreSQL on SERVER (Linux/Ubuntu)")
            logger.info("   SSH tunnel is working correctly!")
        else:
            logger.info(f"ℹ️  PostgreSQL version info: {version[:80]}...")
            logger.info("   Cannot determine if it's local or server PostgreSQL")
        
        # Get some additional info
        server_addr = await conn.fetchval("SELECT inet_server_addr()")
        server_port = await conn.fetchval("SELECT inet_server_port()")
        
        logger.info("")
        logger.info("Connection details:")
        logger.info(f"  Server address: {server_addr}")
        logger.info(f"  Server port: {server_port}")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(check_database_source())

