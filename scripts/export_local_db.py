"""Script to export local database to file."""

import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger

logger = get_logger(__name__)


def export_local_database(local_port: int | None = None) -> None:
    """Export local database to dump file.
    
    Args:
        local_port: Port of local PostgreSQL (default: try 5433, then 5432)
    """
    configure_logging("INFO")
    
    logger.info("=" * 60)
    logger.info("Export Local Database")
    logger.info("=" * 60)
    logger.info("")
    
    # Parse database URL to get connection info
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
            host, _ = host_part.split(":", 1)
        else:
            host = host_part
    else:
        logger.error("Database name not found in URL")
        return
    
    # Use provided port or try common local ports
    if local_port:
        port = local_port
    else:
        # Try 5433 first (common Windows PostgreSQL port), then 5432
        port = 5433
    
    logger.info("Connection settings:")
    logger.info(f"  Host: {host}")
    logger.info(f"  Port: {port} (local PostgreSQL)")
    logger.info(f"  Database: {database}")
    logger.info(f"  User: {user}")
    logger.info("")
    
    # Force localhost for export
    host = "localhost"
    
    logger.info("⚠️  This script exports from LOCAL PostgreSQL database")
    logger.info("   Make sure local PostgreSQL is running on port " + str(port))
    logger.info("")
    
    # Try to export
    output_file = Path(__file__).parent.parent / "local_db_backup.dump"
    
    logger.info(f"Exporting to: {output_file}")
    logger.info("")
    
    # Build pg_dump command
    # Note: pg_dump doesn't support password in command line for security
    # User will need to enter password or use PGPASSWORD environment variable
    cmd = [
        "pg_dump",
        "-h", host,
        "-p", str(port),
        "-U", user,
        "-d", database,
        "-F", "c",  # Custom format
        "-f", str(output_file),
    ]
    
    logger.info("Running command:")
    logger.info(f"  {' '.join(cmd)}")
    logger.info("")
    logger.info("Note: You may be prompted for database password")
    logger.info("")
    
    try:
        # Set PGPASSWORD if password is available
        env = None
        if password:
            import os
            env = os.environ.copy()
            env["PGPASSWORD"] = password
        
        result = subprocess.run(
            cmd,
            env=env,
            timeout=300,  # 5 minutes timeout
        )
        
        if result.returncode == 0:
            if output_file.exists():
                file_size = output_file.stat().st_size
                logger.info("")
                logger.info("=" * 60)
                logger.info("✅ Export completed successfully!")
                logger.info("=" * 60)
                logger.info(f"File: {output_file}")
                logger.info(f"Size: {file_size / 1024 / 1024:.2f} MB")
                logger.info("")
                logger.info("Next steps:")
                logger.info("  1. Import to server: python scripts/import_to_server.py")
                logger.info("  2. Or use pg_restore manually")
            else:
                logger.error("❌ Export command succeeded but file not found")
        else:
            logger.error(f"❌ Export failed with exit code {result.returncode}")
            logger.error("Check error messages above")
            
    except FileNotFoundError:
        logger.error("❌ pg_dump command not found!")
        logger.error("")
        logger.error("PostgreSQL client tools are not installed or not in PATH.")
        logger.error("")
        logger.error("Install PostgreSQL client tools:")
        logger.error("  - Windows: Download from https://www.postgresql.org/download/windows/")
        logger.error("  - Or use PostgreSQL installed with your local PostgreSQL server")
        logger.error("")
        logger.error("Manual export:")
        logger.error(f"  pg_dump -h {host} -p {port} -U {user} -d {database} -F c -f local_db_backup.dump")
    except subprocess.TimeoutExpired:
        logger.error("❌ Export timed out (took more than 5 minutes)")
    except Exception as e:
        logger.error(f"❌ Export failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())


if __name__ == "__main__":
    import sys
    local_port = int(sys.argv[1]) if len(sys.argv) > 1 else None
    export_local_database(local_port=local_port)

