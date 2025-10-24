"""Local lightweight stand-ins for the optional shared packages.

Preference order during runtime (import resolution handled in service code):
1. `shared_python` (new canonical package)
2. `shared_python` (legacy alias – deprecated, to be removed after migration)
3. These local stubs (minimal surface just for config-like access)

These stubs allow the API service to run in standalone mode when neither
shared distribution is available (e.g., ultra-minimal CI or container builds
that intentionally omit the shared repo).
"""
from __future__ import annotations
import os
from functools import lru_cache
from typing import Any, Dict


def load_config() -> Dict[str, Any]:  # pragma: no cover - trivial
    return {
        "environment": os.getenv("APP_ENV", "development"),
        "service": os.getenv("API_SERVICE_NAME", "fks_api"),
    }


class StubSettings(dict):  # simple mapping behaving like settings object
    @property
    def environment(self) -> str:  # type: ignore
        return self.get("environment", "development")


@lru_cache
def get_settings() -> StubSettings:
    cfg = load_config()
    return StubSettings(cfg)


def get_risk_threshold() -> float:  # example helper parity with shared
    return float(os.getenv("RISK_THRESHOLD", "0.0"))

__all__ = [
    "load_config",
    "get_settings",
    "get_risk_threshold",
]
