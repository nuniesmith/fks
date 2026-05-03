"""
Pine Script Generator integration.

Provides a modular Pine Script assembly engine that stitches individual
``.pine`` module files from ``modules/`` into complete TradingView
indicator scripts, substituting parameter values from ``params.yaml``.

Public API
----------
- ``get_generator()`` — singleton ``PineScriptGenerator`` instance
- ``reset_generator()`` — force re-init after config change
- ``PineScriptGenerator`` — the generator class itself
- ``BASE_DIR`` / ``OUTPUT_DIR`` — directory paths
"""

from integrations.pine.main import (
    BASE_DIR,
    OUTPUT_DIR,
    PineScriptGenerator,
    get_generator,
    reset_generator,
)

__all__ = [
    "BASE_DIR",
    "OUTPUT_DIR",
    "PineScriptGenerator",
    "get_generator",
    "reset_generator",
]
