"""Apply Alembic migration for last_past_due_notification_date."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory

def main():
    """Apply migration."""
    cfg = Config('alembic.ini')
    
    # Check current revision
    print("Checking current revision...")
    try:
        current = command.current(cfg)
        print(f"Current revision: {current}")
    except Exception as e:
        print(f"Error getting current revision: {e}")
        current = None
    
    # Get available revisions
    script = ScriptDirectory.from_config(cfg)
    print("\nAvailable revisions:")
    for rev in script.walk_revisions():
        print(f"  {rev.revision}: {rev.doc}")
    
    # Apply migration
    print("\nApplying migration...")
    try:
        command.upgrade(cfg, 'head')
        print("Migration applied successfully!")
    except Exception as e:
        print(f"Error applying migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Check new revision
    print("\nChecking new revision...")
    try:
        new_current = command.current(cfg)
        print(f"New revision: {new_current}")
    except Exception as e:
        print(f"Error getting new revision: {e}")

if __name__ == "__main__":
    main()
