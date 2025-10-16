"""Namespace package for the worker service to satisfy Poetry's package mapping.

Actual runtime modules live at top-level (flat layout under src/) such as `main.py` and `app.py`.
This file enables an editable install without restructuring the codebase.
"""

from importlib import import_module as _imp

# Re-export main entrypoint for `poetry run worker`
try:
    from main import main  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - fallback if path issues
    def main():  # noqa: D401
        """Fallback main that reports import problem."""
        raise RuntimeError("Failed to import top-level main module for worker service.")

__all__ = ["main"]
