"""Unified sys.path bootstrap.

Adds both service local `src/` and `shared/python/src` so imports work uniformly:
  import shared_python...
  import fks_api (or other service package)

Idempotent: only inserts if directories exist and not already present.
"""
from __future__ import annotations
import sys, pathlib

root = pathlib.Path(__file__).resolve().parent
paths = [
    root / "shared" / "python" / "src",
    root / "src",
]
for p in paths:
    if p.is_dir():
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
