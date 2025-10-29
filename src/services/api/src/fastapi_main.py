"""Primary FastAPI application with routers.

`app.py` provides a minimal bootstrap. This module expands the application by
including available routers, while failing gracefully if optional dependencies
are missing. Tests import `fastapi_main:app`.
"""
from __future__ import annotations

from typing import Any

from app import app  # reuse the minimal app instance

# Ensure fks_data package resolvable when running standalone (dev convenience)
import sys, os  # noqa
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _root not in sys.path:
    sys.path.append(_root)

# Router inclusion helpers -------------------------------------------------

def _include(prefix: str, import_path: str, attr: str = "router") -> None:
    try:
        module = __import__(import_path, fromlist=[attr])
        router = getattr(module, attr)
        app.include_router(router, prefix=prefix)
    except Exception as e:  # pragma: no cover - best effort
        print(f"[fastapi_main] Skipped {import_path}: {e}")

# Core routers (best-effort)
_include("/api", "routers.active_assets")
_include("/api", "routers.backtests_simple")
_include("/api", "routers.data_quality")
_include("/api", "routers.dataset")
_include("/api", "routers.signals")
_include("/api", "routers.strategies")
_include("/api", "routers.trading_sessions")
_include("/api", "routers.optimization")
_include("/api", "routers.transformer_ingest")

# Lightweight network/status endpoint (mirrors extended package version)
@app.get("/api/network/status")
async def network_status() -> dict[str, Any]:  # pragma: no cover simple status
    return {"status": "ok", "service": "fks_api", "components": ["active_assets", "strategies", "dataset"], "ts": __import__("datetime").datetime.utcnow().isoformat()}

# Legacy v1 routes if available
_include("/api/v1", "routes.v1.backtest")

# Fallback stub for /api/active-assets if real router failed to mount (avoid frontend 404 spam)
@app.get("/api/active-assets")
async def active_assets_stub() -> dict[str, Any]:  # pragma: no cover simple stub
    # If real router was mounted, this should be shadowed and never execute (FastAPI uses first match order)
    return {"items": [], "count": 0, "stub": True}

@app.get("/")
async def root() -> dict[str, Any]:
    return {"service": "fks_api", "status": "ok"}

__all__ = ["app"]
