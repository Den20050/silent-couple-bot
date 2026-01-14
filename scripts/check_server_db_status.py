"""Script to check database status on server."""

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

logger = get_logger(__name__)


async def check_server_database_status() -> None:
    """Check database status on server."""
    configure_logging("INFO")
    
    tunnel_process: Optional[subprocess.Popen] = None
    
    try:
        logger.info("=" * 60)
        logger.info("Checking Server Database Status")
        logger.info("=" * 60)
        logger.info("")
        
        # Create SSH tunnel if needed
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
            # Check PostgreSQL version
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()
            
            logger.info("PostgreSQL version:")
            logger.info(f"  {version[:100]}...")
            logger.info("")
            
            # Check if it's server or local
            if "windows" in version.lower() or "msvc" in version.lower():
                logger.error("❌ WARNING: Connected to LOCAL PostgreSQL!")
                logger.error("   This is NOT the server database!")
                return
            elif "linux" in version.lower() or "ubuntu" in version.lower():
                logger.info("✅ Connected to SERVER PostgreSQL (Linux/Ubuntu)")
            logger.info("")
            
            # Check database name
            result = await session.execute(text("SELECT current_database()"))
            db_name = result.scalar()
            logger.info(f"Database name: {db_name}")
            logger.info("")
            
            # Check if alembic_version table exists
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                )
            """))
            alembic_exists = result.scalar()
            
            logger.info("=" * 60)
            logger.info("Migration Status")
            logger.info("=" * 60)
            logger.info(f"Migrations applied: {alembic_exists}")
            
            if alembic_exists:
                result = await session.execute(text("SELECT version_num FROM alembic_version"))
                migration_version = result.scalar()
                logger.info(f"Current migration: {migration_version}")
            else:
                logger.warning("⚠️  No migrations applied yet!")
                logger.warning("   Run: python scripts/run_migration.py")
            logger.info("")
            
            # Count tables
            result = await session.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            table_count = result.scalar()
            
            logger.info("=" * 60)
            logger.info("Database Tables")
            logger.info("=" * 60)
            logger.info(f"Total tables: {table_count}")
            logger.info("")
            
            if table_count > 0:
                # List all tables
                result = await session.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """))
                tables = [row[0] for row in result.fetchall()]
                
                logger.info("Tables:")
                for table in tables:
                    # Count rows in each table
                    try:
                        count_result = await session.execute(
                            text(f'SELECT COUNT(*) FROM "{table}"')
                        )
                        row_count = count_result.scalar()
                        logger.info(f"  - {table}: {row_count} rows")
                    except Exception:
                        logger.info(f"  - {table}: (could not count rows)")
                
                logger.info("")
                
                # Check for key tables
                key_tables = ['users', 'pairs', 'subscriptions', 'daily_state', 'pics_pool']
                logger.info("Key tables status:")
                for table in key_tables:
                    exists = table in tables
                    if exists:
                        try:
                            count_result = await session.execute(
                                text(f'SELECT COUNT(*) FROM "{table}"')
                            )
                            row_count = count_result.scalar()
                            logger.info(f"  ✅ {table}: {row_count} rows")
                        except Exception:
                            logger.info(f"  ✅ {table}: exists")
                    else:
                        logger.warning(f"  ❌ {table}: NOT FOUND")
            else:
                logger.warning("⚠️  Database is EMPTY!")
                logger.warning("   No tables found in database.")
                logger.warning("")
                logger.warning("To migrate database:")
                logger.warning("  1. Apply migrations: python scripts/run_migration.py")
                logger.warning("  2. Export data from local DB (if needed)")
                logger.warning("  3. Import data to server DB")
            
            logger.info("")
            logger.info("=" * 60)
            logger.info("Summary")
            logger.info("=" * 60)
            
            if not alembic_exists and table_count == 0:
                logger.warning("⚠️  Database is EMPTY - migrations not applied")
                logger.warning("   Database migration is NOT complete!")
            elif alembic_exists and table_count > 0:
                logger.info("✅ Database structure exists (migrations applied)")
                logger.info("   Check table row counts above to verify data migration")
            elif alembic_exists and table_count == 0:
                logger.warning("⚠️  Migrations applied but tables are empty")
                logger.warning("   Database structure exists but no data")
            else:
                logger.info("ℹ️  Database status unclear - check details above")
            
    except Exception as e:
        logger.error(f"❌ Error checking database: {e}")
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
    asyncio.run(check_server_database_status())

