"""Script to check database connection with optional SSH tunnel support."""

import asyncio
import sys
import subprocess
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from src.core.ssh_tunnel import ensure_database_tunnel
import asyncpg

logger = get_logger(__name__)


async def check_connection() -> bool:
    """Check database connection with automatic SSH tunnel creation if needed."""
    tunnel_process: Optional[subprocess.Popen] = None
    
    try:
        # Try to create SSH tunnel if needed
        logger.info("Checking SSH tunnel configuration...")
        tunnel_process = ensure_database_tunnel()
        if tunnel_process:
            logger.info("SSH tunnel for PostgreSQL created successfully")
        else:
            logger.debug("No SSH tunnel needed or tunnel already exists")
        
        # Parse connection string
        # Format: postgresql+asyncpg://user:password@host:port/database
        url = settings.database_url.replace("postgresql+asyncpg://", "")
        
        if "@" not in url:
            logger.error("Invalid database URL format")
            return False
        
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
            return False
        
        # If SSH tunnel is configured, always connect to localhost
        if tunnel_process or settings.database_ssh_host:
            logger.info(
                f"Connecting to PostgreSQL via SSH tunnel: localhost:{port}/{database} as {user}"
            )
            host = "127.0.0.1"
        else:
            logger.info(f"Connecting to PostgreSQL: {host}:{port}/{database} as {user}")
        
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
        
        # Test query
        version = await conn.fetchval("SELECT version()")
        logger.info(f"Connected successfully! PostgreSQL version: {version[:50]}...")
        
        # Check if database exists
        db_exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", database
        )
        if db_exists:
            logger.info(f"Database '{database}' exists")
        else:
            logger.warning(f"Database '{database}' does not exist")
        
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        logger.info("\nTroubleshooting:")
        logger.info("1. Make sure PostgreSQL is running")
        logger.info("2. Check DATABASE_URL in .env file")
        logger.info("3. Verify host, port, user, password, and database name")
        logger.info("4. If using SSH tunnel, check DATABASE_SSH_HOST, DATABASE_SSH_USER, DATABASE_SSH_PORT")
        logger.info("5. Check firewall settings")
        logger.info("6. Verify SSH keys are configured for passwordless access")
        return False
    finally:
        # Close SSH tunnel if we created it
        if tunnel_process:
            logger.info("Closing SSH tunnel...")
            try:
                tunnel_process.terminate()
                tunnel_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                tunnel_process.kill()
                tunnel_process.wait()
            except Exception as e:
                logger.warning(f"Error closing SSH tunnel: {e}")


if __name__ == "__main__":
    configure_logging("INFO")
    success = asyncio.run(check_connection())
    sys.exit(0 if success else 1)

