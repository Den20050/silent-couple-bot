"""Script to check database connection via SSH tunnel."""

import asyncio
import sys
import subprocess
import time
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from src.core.ssh_tunnel import (
    ensure_database_tunnel,
    check_postgresql_connection,
    get_ssh_config_from_env,
)
import asyncpg

logger = get_logger(__name__)


async def check_tunnel_and_connection() -> bool:
    """Check SSH tunnel and database connection."""
    tunnel_process: Optional[subprocess.Popen] = None
    
    try:
        # Check SSH configuration
        logger.info("=" * 60)
        logger.info("Checking SSH Tunnel Configuration")
        logger.info("=" * 60)
        
        ssh_config = get_ssh_config_from_env("DATABASE")
        if ssh_config:
            ssh_host, ssh_user, ssh_port = ssh_config
            logger.info(f"SSH Host: {ssh_host}")
            logger.info(f"SSH User: {ssh_user}")
            logger.info(f"SSH Port: {ssh_port}")
        else:
            logger.warning("DATABASE_SSH_HOST not configured in .env")
            logger.info("Skipping SSH tunnel check")
            return False
        
        # Parse database URL to get port
        db_url = settings.database_url
        db_port = 5432  # default
        if "@" in db_url and ":" in db_url:
            parts = db_url.split("@")
            if len(parts) > 1:
                host_part = parts[1].split("/")[0]
                if ":" in host_part:
                    _, port_str = host_part.rsplit(":", 1)
                    try:
                        db_port = int(port_str)
                    except ValueError:
                        pass
        
        # Check if PostgreSQL is already accessible
        logger.info(f"\nChecking if PostgreSQL is already accessible on localhost:{db_port}...")
        if check_postgresql_connection("127.0.0.1", db_port):
            logger.info(f"✅ PostgreSQL is already accessible on localhost:{db_port}")
            logger.info("SSH tunnel may already be running")
        else:
            logger.info(f"PostgreSQL is not accessible locally on port {db_port}, creating SSH tunnel...")
        
        # Create SSH tunnel
        logger.info("\nCreating SSH tunnel...")
        tunnel_process = ensure_database_tunnel()
        
        if tunnel_process:
            logger.info("✅ SSH tunnel created successfully")
            # Wait a bit for tunnel to stabilize
            time.sleep(2)
        else:
            logger.info("SSH tunnel already exists or not needed")
        
        # Verify tunnel is working
        logger.info(f"\nVerifying tunnel connection on port {db_port}...")
        if check_postgresql_connection("127.0.0.1", db_port):
            logger.info(f"✅ Tunnel is working - PostgreSQL port {db_port} is accessible")
        else:
            logger.error(f"❌ Tunnel is not working - PostgreSQL port {db_port} is not accessible")
            return False
        
        # Parse database URL
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
                _, port = host_part.rsplit(":", 1)
                port = int(port)
            else:
                port = 5432
        else:
            logger.error("Database name not found in URL")
            return False
        
        # Connect through tunnel (always use localhost)
        logger.info("\n" + "=" * 60)
        logger.info("Testing Database Connection via Tunnel")
        logger.info("=" * 60)
        logger.info(f"Connecting to: localhost:{port}/{database} as {user}")
        
        conn = await asyncpg.connect(
            host="127.0.0.1",
            port=port,
            user=user,
            password=password,
            database=database,
        )
        
        # Test query
        version = await conn.fetchval("SELECT version()")
        logger.info(f"✅ Connected successfully!")
        logger.info(f"PostgreSQL version: {version[:80]}...")
        
        # Check database info
        db_exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", database
        )
        if db_exists:
            logger.info(f"✅ Database '{database}' exists")
        else:
            logger.warning(f"⚠️  Database '{database}' does not exist")
        
        # Get some database stats
        table_count = await conn.fetchval(
            """
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            """
        )
        logger.info(f"📊 Tables in database: {table_count}")
        
        await conn.close()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ All checks passed!")
        logger.info("=" * 60)
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Connection failed: {e}")
        logger.info("\nTroubleshooting:")
        logger.info("1. Verify SSH credentials and host")
        logger.info("2. Check DATABASE_URL in .env file")
        logger.info("3. Ensure SSH keys are configured for passwordless access")
        logger.info("4. Verify PostgreSQL is running on the remote server")
        logger.info("5. Check firewall settings on remote server")
        import traceback
        logger.debug(traceback.format_exc())
        return False
    finally:
        # Close SSH tunnel if we created it
        if tunnel_process:
            logger.info("\nClosing SSH tunnel...")
            try:
                tunnel_process.terminate()
                tunnel_process.wait(timeout=3)
                logger.info("✅ SSH tunnel closed")
            except subprocess.TimeoutExpired:
                tunnel_process.kill()
                tunnel_process.wait()
                logger.warning("⚠️  SSH tunnel force-closed")
            except Exception as e:
                logger.warning(f"⚠️  Error closing SSH tunnel: {e}")


if __name__ == "__main__":
    configure_logging("INFO")
    success = asyncio.run(check_tunnel_and_connection())
    sys.exit(0 if success else 1)

