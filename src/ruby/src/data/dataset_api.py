"""Dataset management API — list, download, generate, and monitor datasets.

Provides a FastAPI router mounted at ``/api/datasets`` with endpoints for
browsing generated datasets, triggering manual generation, downloading
files, and rendering HTMX partials for the Data workspace.

All dataset metadata is read from the ``manifest.json`` written by the
:class:`~.dataset_generator.DatasetGenerator` daemon.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from core.logging_config import get_logger

if TYPE_CHECKING:
    pass

log = get_logger(__name__)

router = APIRouter(prefix="/api/datasets", tags=["Datasets"])

# ---------------------------------------------------------------------------
# Module-level references — set by the application at startup
# ---------------------------------------------------------------------------

# These are populated by the app's lifespan or startup hook so that the
# router can access shared state without import-time coupling.
_dataset_generator: Any = None
_registry: Any = None
_redis: Any = None

_MANIFEST_PATH: Path | None = None


def configure(
    *,
    dataset_generator: Any,
    registry: Any,
    redis_client: Any,
    manifest_path: Path | str,
) -> None:
    """Wire up runtime dependencies.  Called once during app startup."""
    global _dataset_generator, _registry, _redis, _MANIFEST_PATH  # noqa: PLW0603
    _dataset_generator = dataset_generator
    _registry = registry
    _redis = redis_client
    _MANIFEST_PATH = Path(manifest_path) if isinstance(manifest_path, str) else manifest_path


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    """Body for ``POST /api/datasets/generate``."""

    symbol: str | None = Field(
        default=None,
        description="Symbol to generate datasets for.  Omit or set null for all enabled assets.",
    )


class DatasetEntry(BaseModel):
    symbol: str
    type: str
    interval: str
    path: str
    rows: int = 0
    date_range: dict[str, str | None] = Field(default_factory=dict)
    size_bytes: int = 0
    checksum_sha256: str = ""


class ManifestResponse(BaseModel):
    generated_at: str = ""
    datasets: list[DatasetEntry] = Field(default_factory=list)
    coverage_summary: dict[str, dict[str, float]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_manifest() -> dict[str, Any]:
    """Load ``manifest.json`` from disk.  Returns empty structure on failure."""
    if _MANIFEST_PATH is None:
        return {"generated_at": "", "datasets": [], "coverage_summary": {}}
    try:
        if _MANIFEST_PATH.is_file():
            return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        log.warning("dataset_api.manifest_read_failed", exc_info=True)
    return {"generated_at": "", "datasets": [], "coverage_summary": {}}


def _output_dir() -> Path:
    """Resolve the dataset output directory from the manifest path."""
    if _MANIFEST_PATH is not None:
        return _MANIFEST_PATH.parent
    return Path("data/datasets")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    summary="List all datasets",
    response_class=JSONResponse,
)
async def list_datasets(
    type: str | None = Query(default=None, description="Filter by dataset type (training|backtest|features)"),
    interval: str | None = Query(default=None, description="Filter by interval"),
) -> JSONResponse:
    """Return all dataset entries from the manifest, with optional filters."""
    manifest = _read_manifest()
    datasets: list[dict[str, Any]] = manifest.get("datasets", [])

    if type is not None:
        datasets = [d for d in datasets if d.get("type") == type]
    if interval is not None:
        datasets = [d for d in datasets if d.get("interval") == interval]

    return JSONResponse(
        content={
            "generated_at": manifest.get("generated_at", ""),
            "count": len(datasets),
            "datasets": datasets,
        }
    )


@router.get(
    "/manifest",
    summary="Full manifest",
    response_model=ManifestResponse,
)
async def get_manifest() -> JSONResponse:
    """Return the complete ``manifest.json`` contents."""
    return JSONResponse(content=_read_manifest())


@router.get(
    "/status",
    summary="Generation daemon status",
)
async def get_status() -> JSONResponse:
    """Return the dataset generator daemon's current status.

    Includes last run time, next scheduled run, and whether generation
    is currently in progress.
    """
    # Try reading state from the generator instance first
    if _dataset_generator is not None:
        state = _dataset_generator.get_state()
        return JSONResponse(content=state)

    # Fall back to Redis state key
    if _redis is not None:
        try:
            raw = await _redis.get("ruby:factory:dataset_gen:state")
            if raw is not None:
                data = json.loads(raw if isinstance(raw, str) else raw.decode())
                return JSONResponse(content=data)
        except Exception:
            log.debug("dataset_api.status_redis_failed", exc_info=True)

    return JSONResponse(
        content={
            "last_run": None,
            "next_run": None,
            "in_progress": False,
            "current_symbol": None,
            "interval_secs": None,
            "output_dir": str(_output_dir()),
            "min_coverage": None,
        }
    )


@router.get(
    "/coverage",
    summary="Coverage summary for all enabled assets",
)
async def get_coverage() -> JSONResponse:
    """Return the coverage summary from the manifest, enriched with
    live data from Redis when available."""
    manifest = _read_manifest()
    coverage = manifest.get("coverage_summary", {})

    # If we have Redis and a registry, try to build a live summary
    if _redis is not None and _registry is not None:
        try:
            assets = await _registry.enabled_assets()
            intervals = ["1m", "5m", "15m", "1h", "4h", "1d"]

            for asset in assets:
                sym = asset.symbol
                if sym not in coverage:
                    coverage[sym] = {}
                for iv in intervals:
                    try:
                        raw = await _redis.get(f"ruby:coverage:{sym}:{iv}")
                        if raw is not None:
                            data = json.loads(raw if isinstance(raw, str) else raw.decode())
                            coverage[sym][iv] = round(float(data.get("pct", 0.0)), 4)
                    except Exception:
                        pass
        except Exception:
            log.debug("dataset_api.coverage_live_failed", exc_info=True)

    return JSONResponse(content={"coverage_summary": coverage})


@router.post(
    "/prune",
    summary="Prune old dataset files",
)
async def prune_datasets(
    keep: int = Query(3, ge=1, le=100, description="Number of latest files to keep per (type, interval) group"),
) -> JSONResponse:
    """Remove old dataset files, keeping only the latest *keep* per group.

    Returns the count of deleted files.
    """
    if _dataset_generator is None:
        raise HTTPException(
            status_code=503,
            detail="Dataset generator is not available.  The daemon may not be running.",
        )

    try:
        pruned = await _dataset_generator.prune_old_datasets(keep_latest=keep)
    except Exception:
        log.exception("dataset_api.prune_failed")
        raise HTTPException(status_code=500, detail="Pruning failed — check server logs.")

    return JSONResponse(content={"pruned": pruned})


@router.post(
    "/generate",
    summary="Trigger manual dataset generation",
)
async def trigger_generate(body: GenerateRequest) -> JSONResponse:
    """Trigger dataset generation for a specific symbol or all enabled assets.

    When ``symbol`` is provided, generates datasets for that symbol only.
    When omitted, generates for all enabled assets.
    """
    if _dataset_generator is None or _registry is None:
        raise HTTPException(
            status_code=503,
            detail="Dataset generator is not available.  The daemon may not be running.",
        )

    symbol = body.symbol

    if symbol is not None:
        # Validate the symbol exists
        asset = await _registry.get(symbol)
        if asset is None:
            raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

        result = await _dataset_generator.generate_for_symbol(_registry, symbol)
        return JSONResponse(content={"status": "complete", "symbol": symbol, "result": result})

    # Generate for all
    result = await _dataset_generator.generate_all(_registry)
    return JSONResponse(content=result)


@router.get(
    "/status/html",
    summary="HTMX partial for dataset status panel",
    response_class=HTMLResponse,
)
async def status_html(request: Request) -> HTMLResponse:
    """Render an HTMX-compatible HTML partial showing dataset generation
    status, suitable for embedding in the Data workspace."""

    # Gather status
    state: dict[str, Any] = {}
    if _dataset_generator is not None:
        state = _dataset_generator.get_state()
    elif _redis is not None:
        try:
            raw = await _redis.get("ruby:factory:dataset_gen:state")
            if raw is not None:
                state = json.loads(raw if isinstance(raw, str) else raw.decode())
        except Exception:
            pass

    manifest = _read_manifest()
    datasets = manifest.get("datasets", [])
    generated_at = manifest.get("generated_at", "—")

    last_run = state.get("last_run", "—") or "—"
    next_run = state.get("next_run", "—") or "—"
    in_progress = state.get("in_progress", False)
    current_symbol = state.get("current_symbol")

    status_class = "text-yellow-400" if in_progress else "text-green-400"
    status_label = "Generating…" if in_progress else "Idle"
    if in_progress and current_symbol:
        status_label = f"Generating {current_symbol}…"

    # Group datasets by symbol for a summary table
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for ds in datasets:
        sym = ds.get("symbol", "?")
        by_symbol.setdefault(sym, []).append(ds)

    # Build HTML
    symbol_rows = ""
    for sym in sorted(by_symbol):
        ds_list = by_symbol[sym]
        total_rows = sum(d.get("rows", 0) for d in ds_list)
        total_size = sum(d.get("size_bytes", 0) for d in ds_list)
        types = sorted({d.get("type", "?") for d in ds_list})
        size_mb = f"{total_size / 1_048_576:.1f}" if total_size else "0.0"

        symbol_rows += f"""
        <tr class="border-b border-zinc-700/50">
          <td class="px-3 py-2 font-medium text-zinc-200">{_esc(sym)}</td>
          <td class="px-3 py-2 text-zinc-400">{len(ds_list)}</td>
          <td class="px-3 py-2 text-zinc-400">{", ".join(types)}</td>
          <td class="px-3 py-2 text-zinc-400 text-right">{total_rows:,}</td>
          <td class="px-3 py-2 text-zinc-400 text-right">{size_mb} MB</td>
        </tr>"""

    html = f"""
    <div id="dataset-status-panel" class="rounded-lg border border-zinc-700 bg-zinc-800/80 p-4 space-y-4"
         hx-get="/api/datasets/status/html" hx-trigger="every 30s" hx-swap="outerHTML">

      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold text-zinc-300 uppercase tracking-wide">Dataset Generator</h3>
        <span class="text-xs {status_class} font-medium">{status_label}</span>
      </div>

      <div class="grid grid-cols-3 gap-3 text-xs">
        <div>
          <span class="text-zinc-500">Last run</span>
          <p class="text-zinc-300 truncate" title="{_esc(str(last_run))}">{_fmt_ts(last_run)}</p>
        </div>
        <div>
          <span class="text-zinc-500">Next run</span>
          <p class="text-zinc-300 truncate" title="{_esc(str(next_run))}">{_fmt_ts(next_run)}</p>
        </div>
        <div>
          <span class="text-zinc-500">Datasets</span>
          <p class="text-zinc-300">{len(datasets)}</p>
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-xs">
          <thead>
            <tr class="border-b border-zinc-600 text-zinc-500 text-left">
              <th class="px-3 py-1.5">Symbol</th>
              <th class="px-3 py-1.5">Files</th>
              <th class="px-3 py-1.5">Types</th>
              <th class="px-3 py-1.5 text-right">Rows</th>
              <th class="px-3 py-1.5 text-right">Size</th>
            </tr>
          </thead>
          <tbody>
            {symbol_rows if symbol_rows else '<tr><td colspan="5" class="px-3 py-4 text-center text-zinc-500">No datasets generated yet</td></tr>'}
          </tbody>
        </table>
      </div>

      <div class="text-right">
        <button hx-post="/api/datasets/generate"
                hx-headers='{{"Content-Type": "application/json"}}'
                hx-vals='{{}}'
                hx-target="#dataset-status-panel"
                hx-swap="outerHTML"
                class="text-xs px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed"
                {"disabled" if in_progress else ""}>
          Generate All
        </button>
      </div>

      <p class="text-[10px] text-zinc-600 text-right">Manifest: {_esc(str(generated_at))}</p>
    </div>
    """

    return HTMLResponse(content=html.strip())


@router.get(
    "/{symbol}/{filename}",
    summary="Download a dataset file",
)
async def download_dataset(symbol: str, filename: str) -> FileResponse:
    """Download a specific dataset file.

    The path is validated against the output directory to prevent
    directory-traversal attacks.
    """
    output = _output_dir()

    # Sanitise inputs
    safe_symbol = symbol.replace("/", "_").replace("\\", "_").replace("..", "")
    safe_filename = Path(filename).name  # strip any directory components

    filepath = (output / safe_symbol / safe_filename).resolve()

    # Ensure resolved path is still within output directory
    try:
        filepath.relative_to(output.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not filepath.is_file():
        raise HTTPException(status_code=404, detail=f"Dataset file not found: {safe_filename}")

    media_type = "application/octet-stream"
    if filepath.suffix == ".csv":
        media_type = "text/csv"
    elif filepath.suffix == ".parquet":
        media_type = "application/vnd.apache.parquet"

    return FileResponse(
        path=filepath,
        media_type=media_type,
        filename=safe_filename,
    )


@router.get(
    "/{symbol}",
    summary="List datasets for a specific symbol",
)
async def list_symbol_datasets(symbol: str) -> JSONResponse:
    """Return all dataset entries for a given *symbol*."""
    manifest = _read_manifest()
    datasets = manifest.get("datasets", [])

    # Match by symbol (case-insensitive, also try the sanitised version)
    symbol_upper = symbol.upper()
    safe = symbol.replace("/", "_").replace("\\", "_")

    matched = [
        d
        for d in datasets
        if d.get("symbol", "").upper() == symbol_upper or d.get("symbol", "").replace("/", "_").upper() == safe.upper()
    ]

    if not matched:
        # Check whether the symbol exists at all in the registry
        if _registry is not None:
            asset = await _registry.get(symbol)
            if asset is None:
                raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")
        return JSONResponse(
            content={
                "symbol": symbol,
                "count": 0,
                "datasets": [],
                "message": "No datasets generated yet for this symbol.",
            }
        )

    return JSONResponse(
        content={
            "symbol": symbol,
            "count": len(matched),
            "datasets": matched,
        }
    )


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------


def _esc(text: str) -> str:
    """Minimal HTML escaping."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _fmt_ts(value: str) -> str:
    """Format an ISO timestamp for display, or return as-is if not parseable."""
    if value in ("—", "", None):
        return "—"
    try:
        dt = datetime.fromisoformat(str(value))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError):
        return str(value)
