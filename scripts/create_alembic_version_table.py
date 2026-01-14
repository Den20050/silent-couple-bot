"""Create alembic_version table with correct column size."""

import asyncio
import sys
import subprocess
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.db.base import async_session_maker
from src.core.ssh_tunnel import ensure_database_tunnel

async def create_alembic_version_table() -> None:
    """Create alembic_version table with VARCHAR(50) for version_num."""
    tunnel_process: Optional[subprocess.Popen] = None
    
    try:
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
            # Check if table exists
            result = await session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                )
            """))
            table_exists = result.scalar()
            
            if table_exists:
                print("✅ alembic_version table already exists")
                
                # Check column size
                result = await session.execute(text("""
                    SELECT character_maximum_length
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'alembic_version'
                    AND column_name = 'version_num'
                """))
                max_length = result.scalar()
                
                if max_length and max_length < 50:
                    print(f"⚠️  Column size ({max_length}) is too small")
                    print("Increasing to VARCHAR(50)...")
                    await session.execute(text("""
                        ALTER TABLE alembic_version 
                        ALTER COLUMN version_num TYPE VARCHAR(50)
                    """))
                    await session.commit()
                    print("✅ Column size increased")
                else:
                    print(f"✅ Column size ({max_length}) is sufficient")
            else:
                print("Creating alembic_version table with VARCHAR(50)...")
                await session.execute(text("""
                    CREATE TABLE alembic_version (
                        version_num VARCHAR(50) NOT NULL,
                        CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                    )
                """))
                await session.commit()
                print("✅ alembic_version table created successfully!")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
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
    asyncio.run(create_alembic_version_table())

