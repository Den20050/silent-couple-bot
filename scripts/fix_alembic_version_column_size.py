"""Fix alembic_version column size to accommodate longer revision names."""

import asyncio
import sys
import subprocess
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.db.base import async_session_maker
from src.core.ssh_tunnel import ensure_database_tunnel


async def fix_column_size() -> None:
    """Increase version_num column size in alembic_version table."""
    tunnel_process: Optional[subprocess.Popen] = None
    
    try:
        # Create SSH tunnel if needed
        print("Creating SSH tunnel if needed...")
        tunnel_process = ensure_database_tunnel()
        if tunnel_process:
            print("✅ SSH tunnel created")
            import time
            time.sleep(2)
        else:
            print("ℹ️  SSH tunnel already exists or not needed")
        print("")
        
        async with async_session_maker() as session:
            # Check current column type
            result = await session.execute(text("""
                SELECT data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'alembic_version'
                AND column_name = 'version_num';
            """))
            col_info = result.fetchone()
            
            if col_info:
                data_type, max_length = col_info
                print(f"Current column type: {data_type}({max_length})")
                
                if max_length and max_length < 50:
                    print(f"\n⚠️  Column size ({max_length}) is too small for revision names")
                    print("Increasing column size to VARCHAR(50)...")
                    
                    await session.execute(text("""
                        ALTER TABLE alembic_version 
                        ALTER COLUMN version_num TYPE VARCHAR(50);
                    """))
                    await session.commit()
                    print("✅ Column size increased successfully!")
                else:
                    print(f"\n✅ Column size ({max_length}) is sufficient")
            else:
                print("⚠️  Could not find alembic_version table or version_num column")
                print("   Table might not exist yet - this is OK for new database")
    finally:
        # Close SSH tunnel if we created it
        if tunnel_process:
            print("")
            print("Closing SSH tunnel...")
            try:
                tunnel_process.terminate()
                tunnel_process.wait(timeout=3)
                print("✅ SSH tunnel closed")
            except subprocess.TimeoutExpired:
                tunnel_process.kill()
                tunnel_process.wait()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(fix_column_size())
