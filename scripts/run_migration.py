"""Run Alembic migration directly with SSH tunnel support."""

import sys
import subprocess
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command
from src.core.config import settings
from src.core.ssh_tunnel import ensure_database_tunnel

def main():
    """Run migration with automatic SSH tunnel creation if needed."""
    tunnel_process: Optional[subprocess.Popen] = None
    
    try:
        print("=" * 60)
        print("Applying Alembic Migration")
        print("=" * 60)
        print(f"Database URL: {settings.database_url}")
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
