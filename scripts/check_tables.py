"""Script to check created tables."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
import asyncpg

logger = get_logger(__name__)


async def check_tables() -> None:
    """Check created tables."""
    try:
        # Parse connection string
        url = settings.database_url.replace("postgresql+asyncpg://", "")
        auth_part, db_part = url.split("@", 1)
        user, password = auth_part.split(":", 1)
        host_part, database = db_part.rsplit("/", 1)
        host, port = host_part.split(":", 1)
        
        conn = await asyncpg.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
        )
        
        # Get tables
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        
        print("\n✅ Созданные таблицы в БД:")
        for table in tables:
            # Get row count
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table['tablename']}")
            print(f"  - {table['tablename']} ({count} строк)")
        
        print(f"\nВсего таблиц: {len(tables)}")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    configure_logging("INFO")
    asyncio.run(check_tables())

