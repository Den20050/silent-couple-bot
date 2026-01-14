"""Script to import database dump to server via SSH tunnel."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from src.core.ssh_tunnel import ensure_database_tunnel

logger = get_logger(__name__)


def import_to_server() -> None:
    """Import database dump to server via SSH tunnel."""
    configure_logging("INFO")
    
    logger.info("=" * 60)
    logger.info("Import Database to Server")
    logger.info("=" * 60)
    logger.info("")
    
    # Check for dump file
    dump_file = Path(__file__).parent.parent / "local_db_backup.dump"
    
    if not dump_file.exists():
        logger.error(f"❌ Dump file not found: {dump_file}")
        logger.error("")
        logger.info("First, export local database:")
        logger.info("  python scripts/export_local_db.py")
        logger.info("")
        logger.info("Or create dump file manually:")
        logger.info("  pg_dump -h localhost -p 5433 -U bot_user -d silent_couple_bot -F c -f local_db_backup.dump")
        return
    
    file_size = dump_file.stat().st_size
    logger.info(f"Found dump file: {dump_file}")
    logger.info(f"Size: {file_size / 1024 / 1024:.2f} MB")
    logger.info("")
    
    # Parse database URL
    db_url = settings.database_url.replace("postgresql+asyncpg://", "")
    
    if "@" not in db_url:
        logger.error("Invalid database URL format")
        return
    
    auth_part, db_part = db_url.split("@", 1)
    if ":" in auth_part:
        user, password = auth_part.split(":", 1)
    else:
        user = auth_part
        password = ""
    
    if "/" in db_part:
        host_part, database = db_part.rsplit("/", 1)
        if ":" in host_part:
            _, port = host_part.split(":", 1)
            port = int(port)
        else:
            port = 5432
    else:
        logger.error("Database name not found in URL")
        return
    
    # Get remote port
    remote_port = settings.database_remote_port if settings.database_remote_port else port
    
    logger.info("Server connection:")
    logger.info(f"  Host: localhost (via SSH tunnel)")
    logger.info(f"  Port: {port} (local) -> {remote_port} (server)")
    logger.info(f"  Database: {database}")
    logger.info(f"  User: {user}")
    logger.info("")
    
    if not settings.database_ssh_host:
        logger.error("❌ DATABASE_SSH_HOST not configured!")
        logger.error("   Cannot create SSH tunnel for import.")
        return
    
    logger.info("SSH tunnel:")
    logger.info(f"  SSH Host: {settings.database_ssh_host}")
    logger.info(f"  SSH User: {settings.database_ssh_user}")
    logger.info(f"  SSH Port: {settings.database_ssh_port}")
    logger.info("")
    
    logger.warning("⚠️  IMPORTANT:")
    logger.warning("  1. This will import data to SERVER database")
    logger.warning("  2. Existing data may be overwritten")
    logger.warning("  3. Make sure migrations are applied first!")
    logger.warning("")
    
    # Check for --yes flag
    auto_confirm = "--yes" in sys.argv or "-y" in sys.argv
    
    if not auto_confirm:
        try:
            response = input("Continue with import? (yes/no): ")
            if response.lower() not in ["yes", "y"]:
                logger.info("Import cancelled")
                return
        except (EOFError, KeyboardInterrupt):
            logger.info("")
            logger.info("Import cancelled (use --yes flag for non-interactive mode)")
            return
    
    logger.info("")
    logger.info("Creating SSH tunnel...")
    tunnel_process: Optional[subprocess.Popen] = None
    
    tunnel_process = ensure_database_tunnel()
    if tunnel_process:
        logger.info("✅ SSH tunnel created")
        import time
        time.sleep(2)  # Wait for tunnel to be ready
    else:
        logger.info("ℹ️  SSH tunnel already exists or not needed")
    logger.info("")
    
    # Build pg_restore command
    # Use --data-only since tables already exist from migrations
    # Use --disable-triggers to avoid foreign key constraint issues during import
    cmd = [
        "pg_restore",
        "-h", "localhost",
        "-p", str(port),
        "-U", user,
        "-d", database,
        "--data-only",  # Only import data, not schema
        "--no-owner",  # Don't try to set ownership
        "--no-privileges",  # Don't try to set privileges
        "--disable-triggers",  # Disable triggers (including FK checks) during import
        "-v",  # Verbose
        str(dump_file),
    ]
    
    logger.info("Command:")
    logger.info(f"  {' '.join(cmd)}")
    logger.info("")
    
    try:
        # Set PGPASSWORD if password is available
        env = None
        if password:
            import os
            env = os.environ.copy()
            env["PGPASSWORD"] = password
        
        logger.info("Starting import (this may take a while)...")
        result = subprocess.run(
            cmd,
            env=env,
            timeout=600,  # 10 minutes timeout
        )
        
        if result.returncode == 0:
            logger.info("")
            logger.info("=" * 60)
            logger.info("✅ Import completed successfully!")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Verify import:")
            logger.info("  python scripts/check_server_db_status.py")
        else:
            logger.error(f"❌ Import failed with exit code {result.returncode}")
            logger.error("Check error messages above")
            
    except FileNotFoundError:
        logger.error("❌ pg_restore command not found!")
        logger.error("")
        logger.error("PostgreSQL client tools are not installed or not in PATH.")
        logger.error("")
        logger.error("Install PostgreSQL client tools:")
        logger.error("  - Windows: Download from https://www.postgresql.org/download/windows/")
        logger.error("")
        logger.error("Manual import:")
        logger.error(f"  1. Create SSH tunnel: ssh -L {port}:localhost:{remote_port} {settings.database_ssh_user}@{settings.database_ssh_host}")
        logger.error(f"  2. In another terminal: pg_restore -h localhost -p {port} -U {user} -d {database} {dump_file}")
    except subprocess.TimeoutExpired:
        logger.error("❌ Import timed out (took more than 10 minutes)")
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
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
            except Exception:
                pass


if __name__ == "__main__":
    import_to_server()

