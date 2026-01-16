"""Run Alembic migration directly with SSH tunnel support."""

import sys
import subprocess
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command
from src.core.config import settings
from src.core.ssh_tunnel import ensure_database_tunnel


def _sanitize_database_url(database_url: str) -> str:
    """Return a copy of database_url with password masked.

    Args:
        database_url: SQLAlchemy/DB URL.

    Returns:
        URL safe to print in logs/terminal output.
    """
    try:
        parts = urlsplit(database_url)
        if not parts.username:
            return database_url

        # urlsplit puts credentials into netloc, rebuild netloc with masked password.
        host_port = parts.hostname or ""
        if parts.port is not None:
            host_port = f"{host_port}:{parts.port}"

        userinfo = parts.username
        if parts.password is not None:
            userinfo = f"{userinfo}:***"

        netloc = f"{userinfo}@{host_port}" if host_port else userinfo
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        # Never fail migrations due to logging sanitization.
        return "<redacted>"

def main():
    """Run migration with automatic SSH tunnel creation if needed."""
    tunnel_process: Optional[subprocess.Popen] = None
    
    try:
        print("=" * 60)
        print("Applying Alembic Migration")
        print("=" * 60)
        print(f"Database URL: {_sanitize_database_url(settings.database_url)}")
        print()
        
        # Try to create SSH tunnel if needed
        print("Checking SSH tunnel configuration...")
        tunnel_process = ensure_database_tunnel()
        if tunnel_process:
            print("✅ SSH tunnel for PostgreSQL created")
        else:
            print("ℹ️  No SSH tunnel needed or tunnel already exists")
        print()
        
        cfg = Config('alembic.ini')
        
        # Set database URL
        cfg.set_main_option("sqlalchemy.url", settings.database_url)
        
        print("Checking current revision...")
        try:
            current = command.current(cfg)
            print(f"Current revision: {current}")
        except Exception as e:
            print(f"Could not get current revision: {e}")
            print("This is normal if no migrations have been applied yet.")
        
        print("\nApplying migration to 'head'...")
        try:
            command.upgrade(cfg, 'head')
            print("\n✅ Migration applied successfully!")
        except Exception as e:
            print(f"\n❌ Error applying migration: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        
        print("\nChecking new revision...")
        try:
            new_current = command.current(cfg)
            print(f"New revision: {new_current}")
        except Exception as e:
            print(f"Could not get new revision: {e}")
    finally:
        # Close SSH tunnel if we created it
        if tunnel_process:
            print("\nClosing SSH tunnel...")
            try:
                tunnel_process.terminate()
                tunnel_process.wait(timeout=3)
                print("✅ SSH tunnel closed")
            except subprocess.TimeoutExpired:
                tunnel_process.kill()
                tunnel_process.wait()
                print("⚠️  SSH tunnel force-closed")
            except Exception as e:
                print(f"⚠️  Error closing SSH tunnel: {e}")

if __name__ == "__main__":
    main()
