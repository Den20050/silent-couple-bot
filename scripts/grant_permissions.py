"""Script to grant permissions to bot_user."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
import asyncpg

logger = get_logger(__name__)


async def grant_permissions() -> bool:
    """Grant permissions to bot_user."""
    try:
        # Parse connection string to get admin credentials
        # You need to connect as postgres superuser
        print("Для выдачи прав нужно подключиться как суперпользователь PostgreSQL.")
        print("Введите данные суперпользователя (postgres):")
        
        admin_user = input("Username [postgres]: ").strip() or "postgres"
        admin_password = input("Password: ").strip()
        admin_host = input("Host [localhost]: ").strip() or "localhost"
        admin_port = input("Port [5433]: ").strip() or "5433"
        
        # Connect as admin
        conn = await asyncpg.connect(
            host=admin_host,
            port=int(admin_port),
            user=admin_user,
            password=admin_password,
            database="postgres",  # Connect to default database
        )
        
        logger.info("Connected as admin, granting permissions...")
        
        # Grant permissions
        await conn.execute("""
            GRANT ALL ON SCHEMA public TO bot_user;
            GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bot_user;
            GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bot_user;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO bot_user;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO bot_user;
            GRANT USAGE ON SCHEMA public TO bot_user;
            GRANT CREATE ON SCHEMA public TO bot_user;
        """)
        
        logger.info("Permissions granted successfully!")
        
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to grant permissions: {e}")
        logger.info("\nАльтернативный способ:")
        logger.info("1. Подключитесь к PostgreSQL как суперпользователь:")
        logger.info("   psql -h localhost -p 5433 -U postgres -d postgres")
        logger.info("2. Выполните команды из scripts/grant_permissions.sql")
        return False


if __name__ == "__main__":
    configure_logging("INFO")
    success = asyncio.run(grant_permissions())
    sys.exit(0 if success else 1)

