"""Pytest configuration for ASMBTR strategy tests."""

import sys
from pathlib import Path

# Add source directory to Python path
# For Docker container: /app/src
# For local: <workspace>/src/services/app/src
src_path = Path('/app/src')
if not src_path.exists():
    # Fall back to local path
    src_path = Path(__file__).parent.parent.parent.parent / 'src' / 'services' / 'app' / 'src'

sys.path.insert(0, str(src_path))
