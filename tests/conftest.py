"""Pytest configuration.

Ensures the project root is importable so tests can `import src.*` without
requiring editable installs or PYTHONPATH tweaks.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

