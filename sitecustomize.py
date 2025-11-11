from __future__ import annotations

import os

# Speed up pytest startup and avoid environment-specific plugin side effects.
# Pytest reads PYTEST_DISABLE_PLUGIN_AUTOLOAD very early, before loading conftest.
# Using sitecustomize ensures the variable is set at interpreter startup.
os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

