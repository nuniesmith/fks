"""
Entrypoint for the DataFactory supervisord process.

Usage:
    python -m entrypoints.factory
    # or
    python entrypoints/factory.py
"""

from __future__ import annotations

import asyncio

from lib.data_factory.coordinator import main

if __name__ == "__main__":
    asyncio.run(main())
