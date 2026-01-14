"""Clear all data from server database (keep structure)."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.db.base import async_session_maker
from src.core.ssh_tunnel import ensure_database_tunnel
from src.core.logger import configure_logging, get_logger
import subprocess
from typing import Optional

logger = get_logger(__name__)


async def clear_server_db_data() -> None:
    """Clear all data from server database."""
    configure_logging("INFO")
    
    logger.info("=" * 60)
    logger.info("Clear Server Database Data")
    logger.info("=" * 60)
    logger.info("")
    logger.warning("⚠️  WARNING: This will DELETE ALL DATA from server database!")
    logger.warning("   Database structure will be preserved.")
    logger.info("")
    
    tunnel_process: Optional[subprocess.Popen] = None
    
    try:
        logger.info("Creating SSH tunnel...")
        tunnel_process = ensure_database_tunnel()
        if tunnel_process:
            logger.info("✅ SSH tunnel created")
            import time
            time.sleep(2)
        else:
            logger.info("ℹ️  SSH tunnel already exists or not needed")
        logger.info("")
        
        async with async_session_maker() as session:
            # Get list of tables
            result = await session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            
            logger.info(f"Found {len(tables)} tables")
            logger.info("")
            
            # Truncate all tables in correct order (respecting foreign keys)
            # Order: child tables first, then parent tables
            # But CASCADE should handle it automatically
            logger.info("Truncating tables...")
            
            # Exclude alembic_version to keep migration state
            tables_to_truncate = [t for t in tables if t != 'alembic_version']
            
            for table in tables_to_truncate:
                try:
                    await session.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))
                    logger.info(f"  ✅ {table}")
                except Exception as e:
                    logger.warning(f"  ⚠️  {table}: {e}")
            
            await session.commit()
            
            logger.info("")
            logger.info("=" * 60)
            logger.info("✅ All data cleared successfully!")
            logger.info("=" * 60)
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
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
    asyncio.run(clear_server_db_data())

