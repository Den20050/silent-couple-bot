"""Script to check which database the running bot is connected to."""

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
from src.db.base import async_session_maker
from sqlalchemy import text
import asyncpg

logger = get_logger(__name__)


async def check_database_connection() -> None:
    """Check which database bot is connected to."""
    configure_logging("INFO")
    
    tunnel_process: Optional[subprocess.Popen] = None
    
    try:
        logger.info("=" * 60)
        logger.info("Checking Bot Database Connection")
        logger.info("=" * 60)
        logger.info("")
        
        # Create SSH tunnel if needed (as bot does)
        logger.info("Creating SSH tunnel if needed...")
        tunnel_process = ensure_database_tunnel()
        if tunnel_process:
            logger.info("✅ SSH tunnel created")
            # Wait a bit for tunnel to stabilize
            import time
            time.sleep(2)
        else:
            logger.info("ℹ️  SSH tunnel already exists or not needed")
        logger.info("")
        
        # Parse database URL
        url = settings.database_url.replace("postgresql+asyncpg://", "")
    
        if "@" not in url:
            logger.error("Invalid database URL format")
            return
        
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
        
        logger.info(f"Connection settings:")
        logger.info(f"  Host: {host}")
        logger.info(f"  Port: {port}")
        logger.info(f"  Database: {database}")
        logger.info(f"  User: {user}")
        logger.info("")
        
        # Check SSH tunnel configuration
        if settings.database_ssh_host:
            logger.info("SSH Tunnel Configuration:")
            logger.info(f"  SSH Host: {settings.database_ssh_host}")
            logger.info(f"  SSH User: {settings.database_ssh_user}")
            logger.info(f"  SSH Port: {settings.database_ssh_port}")
            logger.info("")
        
        # Try to connect using asyncpg (direct connection)
        logger.info("Connecting to database...")
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
        
        # Get PostgreSQL version
        version = await conn.fetchval("SELECT version()")
        logger.info("")
        logger.info("=" * 60)
        logger.info("Database Connection Info")
        logger.info("=" * 60)
        logger.info(f"PostgreSQL version: {version[:100]}...")
        logger.info("")
        
        # Determine if it's server or local
        if "windows" in version.lower() or "msvc" in version.lower():
            logger.error("❌ WARNING: Connected to LOCAL PostgreSQL on Windows!")
            logger.error("   Bot is NOT using server database via SSH tunnel.")
            logger.error("")
            logger.info("Possible reasons:")
            logger.info("  1. Local PostgreSQL is running on port 5432")
            logger.info("  2. SSH tunnel was not created")
            logger.info("  3. DATABASE_URL points to local PostgreSQL")
            logger.info("")
            logger.info("Solution:")
            logger.info("  1. Stop local PostgreSQL: Stop-Service postgresql-x64-18")
            logger.info("  2. Or use different port in DATABASE_URL")
            logger.info("  3. Check SSH tunnel configuration in .env")
        elif "linux" in version.lower() or "ubuntu" in version.lower() or "debian" in version.lower():
            logger.info("✅ Connected to PostgreSQL on SERVER (Linux/Ubuntu)")
            logger.info("   SSH tunnel is working correctly!")
            logger.info("   Bot is using server database.")
        else:
            logger.info(f"ℹ️  PostgreSQL version: {version[:80]}...")
            logger.info("   Cannot determine if it's local or server PostgreSQL")
        
        # Get server address and port
        server_addr = await conn.fetchval("SELECT inet_server_addr()")
        server_port = await conn.fetchval("SELECT inet_server_port()")
        
        logger.info("")
        logger.info("Connection details:")
        logger.info(f"  Server address: {server_addr}")
        logger.info(f"  Server port: {server_port}")
        
        # Get some database info
        logger.info("")
        logger.info("Database information:")
        
        # Count tables
        table_count = await conn.fetchval(
            """
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            """
        )
        logger.info(f"  Tables: {table_count}")
        
        # Check if alembic_version table exists (indicates migrations applied)
        alembic_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'alembic_version'
            )
            """
        )
        logger.info(f"  Migrations applied: {alembic_exists}")
        
        # Get current migration version if exists
        if alembic_exists:
            try:
                migration_version = await conn.fetchval("SELECT version_num FROM alembic_version")
                logger.info(f"  Current migration: {migration_version}")
            except Exception:
                pass
        
        await conn.close()
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ Connection check completed")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        logger.info("")
        logger.info("Possible reasons:")
        logger.info("  1. Database is not accessible")
        logger.info("  2. SSH tunnel is not created")
        logger.info("  3. Wrong credentials in DATABASE_URL")
        logger.info("  4. PostgreSQL is not running on server")
        logger.info("")
        logger.info("Check:")
        logger.info("  python scripts/check_db_tunnel.py")
        import traceback
        logger.debug(traceback.format_exc())
    finally:
        # Close SSH tunnel if we created it
        if tunnel_process:
            logger.info("")
            logger.info("Closing SSH tunnel...")
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


async def check_via_sqlalchemy() -> None:
    """Check database connection via SQLAlchemy (as bot does)."""
    tunnel_process: Optional[subprocess.Popen] = None
    
    try:
        logger.info("")
        logger.info("=" * 60)
        logger.info("Checking via SQLAlchemy (as bot does)")
        logger.info("=" * 60)
        logger.info("")
        
        # Create SSH tunnel if needed (as bot does)
        logger.info("Creating SSH tunnel if needed...")
        tunnel_process = ensure_database_tunnel()
        if tunnel_process:
            logger.info("✅ SSH tunnel created")
            import time
            time.sleep(2)
        else:
            logger.info("ℹ️  SSH tunnel already exists or not needed")
        logger.info("")
        
        async with async_session_maker() as session:
            # Get PostgreSQL version
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()
            
            logger.info(f"PostgreSQL version: {version[:100]}...")
            logger.info("")
            
            if "windows" in version.lower() or "msvc" in version.lower():
                logger.error("❌ WARNING: SQLAlchemy connected to LOCAL PostgreSQL!")
            elif "linux" in version.lower() or "ubuntu" in version.lower():
                logger.info("✅ SQLAlchemy connected to SERVER PostgreSQL!")
            
            # Get server info
            result = await session.execute(text("SELECT inet_server_addr(), inet_server_port()"))
            server_info = result.fetchone()
            if server_info:
                logger.info(f"Server address: {server_info[0]}")
                logger.info(f"Server port: {server_info[1]}")
            
    except Exception as e:
        logger.error(f"SQLAlchemy connection failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
    finally:
        # Close SSH tunnel if we created it
        if tunnel_process:
            logger.info("")
            logger.info("Closing SSH tunnel...")
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


async def main():
    """Main function."""
    # Check direct connection
    await check_database_connection()
    
    # Check via SQLAlchemy (as bot does)
    await check_via_sqlalchemy()


if __name__ == "__main__":
    asyncio.run(main())

