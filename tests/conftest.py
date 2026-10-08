"""Pytest configuration.

Ensures the project root is importable so tests can `import src.*` without
requiring editable installs or PYTHONPATH tweaks.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Settings requires these before any `import src.*`; unit tests never use real values.
# setdefault keeps real values from .env / CI secrets when present.
os.environ.setdefault("DEMO_PAIR_HASH_SALT", "test-demo-salt")
os.environ.setdefault("TG_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("ROBOKASSA_MERCHANT_LOGIN", "test-merchant")
os.environ.setdefault("ROBOKASSA_PASSWORD_1", "test-password-1")
os.environ.setdefault("ROBOKASSA_PASSWORD_2", "test-password-2")

