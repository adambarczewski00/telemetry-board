from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the repository root is importable when pytest is invoked outside it.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
root_str = str(PROJECT_ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

# Keep tests lightweight: avoid starting the worker metrics HTTP server
# on import during tests. This prevents binding a port and speeds up imports.
os.environ.setdefault("ENABLE_WORKER_METRICS", "false")
