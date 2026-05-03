"""Dataset generator daemon — auto-creates pre-built datasets from historical bars.

Runs on a configurable schedule (default: every hour) and produces three
dataset types for each enabled asset that has sufficient coverage:

1. **Training datasets** — multi-interval merged OHLCV for ML model training.
2. **Backtest datasets** — clean sequential bars for strategy backtesting.
3. **Feature datasets** — bars with pre-computed technical indicators.

Generated files land under ``data/datasets/{symbol}/`` and a manifest is
written to ``data/datasets/manifest.json`` after every cycle.

Environment variables
---------------------
- ``DATASET_GEN_INTERVAL_SECS`` — sleep between generation cycles (default 3600).
- ``DATASET_OUTPUT_DIR`` — root output directory (default ``data/datasets``).
- ``DATASET_MIN_COVERAGE`` — minimum coverage ratio to generate (default 0.80).

Redis keys read
---------------
- ``ruby:coverage:{symbol}:{interval}`` — JSON coverage report from WindowManager.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.logging_config import get_logger

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncEngine

    from .registry.asset_registry import AssetRegistry

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATASET_GEN_INTERVAL_SECS: int = int(os.getenv("DATASET_GEN_INTERVAL_SECS", "3600"))
DATASET_OUTPUT_DIR: str = os.getenv("DATASET_OUTPUT_DIR", "data/datasets")
DATASET_MIN_COVERAGE: float = float(os.getenv("DATASET_MIN_COVERAGE", "0.80"))

_COVERAGE_KEY_PREFIX: str = "ruby:coverage"

# Intervals used for training datasets (merged multi-interval)
_TRAINING_INTERVALS: list[str] = ["1m", "5m", "1h", "1d"]

# Intervals for which backtest / feature datasets are generated
_BACKTEST_INTERVALS: list[str] = ["1m", "5m", "15m", "1h", "1d"]
_FEATURE_INTERVALS: list[str] = ["5m", "15m", "1h", "1d"]

# Redis key for daemon state (visible to the API)
_STATE_KEY: str = "ruby:factory:dataset_gen:state"
_STATE_TTL: int = 86400  # 24 h

# ---------------------------------------------------------------------------
# Try to import optional heavy deps
# ---------------------------------------------------------------------------

try:
    import pyarrow as pa  # noqa: F401
    import pyarrow.parquet as pq

    _HAS_PARQUET = True
except ImportError:
    _HAS_PARQUET = False

# ---------------------------------------------------------------------------
# Pure-Python technical indicator helpers
# ---------------------------------------------------------------------------


def _ema(values: list[float], period: int) -> list[float | None]:
    """Exponential moving average.  Returns list aligned with *values*."""
    if len(values) < period:
        return [None] * len(values)
    result: list[float | None] = [None] * (period - 1)
    k = 2.0 / (period + 1)
    # Seed with SMA of first *period* values
    sma = sum(values[:period]) / period
    result.append(sma)
    prev = sma
    for v in values[period:]:
        cur = v * k + prev * (1 - k)
        result.append(cur)
        prev = cur
    return result


def _rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """RSI using Wilder's smoothing method."""
    if len(closes) < period + 1:
        return [None] * len(closes)

    result: list[float | None] = [None] * period

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100.0 - 100.0 / (1.0 + rs))

    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - 100.0 / (1.0 + rs))

    return result


def _atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[float | None]:
    """Average True Range using Wilder's smoothing."""
    n = len(highs)
    if n < period + 1:
        return [None] * n

    true_ranges: list[float] = [highs[0] - lows[0]]
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)

    result: list[float | None] = [None] * (period - 1)
    atr_val = sum(true_ranges[:period]) / period
    result.append(atr_val)

    for i in range(period, n):
        atr_val = (atr_val * (period - 1) + true_ranges[i]) / period
        result.append(atr_val)

    return result


def _vwap_daily(
    timestamps: list[str],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
) -> list[float | None]:
    """Volume-weighted average price with daily reset.

    Uses the typical price ``(H+L+C)/3`` weighted by volume.
    Resets cumulative sums at each new calendar day boundary.
    """
    n = len(timestamps)
    result: list[float | None] = []
    cum_vol = 0.0
    cum_tp_vol = 0.0
    prev_day: str | None = None

    for i in range(n):
        ts = timestamps[i]
        # Extract date part (first 10 chars of ISO timestamp)
        day = ts[:10] if len(ts) >= 10 else ts

        if day != prev_day:
            cum_vol = 0.0
            cum_tp_vol = 0.0
            prev_day = day

        tp = (highs[i] + lows[i] + closes[i]) / 3.0
        cum_vol += volumes[i]
        cum_tp_vol += tp * volumes[i]

        if cum_vol > 0:
            result.append(cum_tp_vol / cum_vol)
        else:
            result.append(None)

    return result


def _bollinger_bands(
    closes: list[float],
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Bollinger Bands: SMA(period) ± num_std × σ.

    Returns (upper, middle, lower) lists aligned with *closes*.
    """
    n = len(closes)
    upper: list[float | None] = [None] * (period - 1)
    middle: list[float | None] = [None] * (period - 1)
    lower: list[float | None] = [None] * (period - 1)

    for i in range(period - 1, n):
        window = closes[i - period + 1 : i + 1]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        std = math.sqrt(variance)
        middle.append(sma)
        upper.append(sma + num_std * std)
        lower.append(sma - num_std * std)

    return upper, middle, lower


# ---------------------------------------------------------------------------
# DatasetGenerator
# ---------------------------------------------------------------------------


class DatasetGenerator:
    """Background daemon that auto-generates pre-built datasets.

    Parameters
    ----------
    redis:
        An async Redis client (``redis.asyncio.Redis`` or compatible).
    engine:
        An async SQLAlchemy engine connected to the Postgres database
        that holds the ``historical_bars`` table.
    """

    def __init__(
        self,
        redis: aioredis.Redis,  # type: ignore[name-defined]
        engine: AsyncEngine,
    ) -> None:
        self._redis = redis
        self._engine = engine
        self._sem = asyncio.Semaphore(1)

        # Resolve output directory relative to project root
        self._output_dir = Path(DATASET_OUTPUT_DIR)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Generation state (exposed via API)
        self._last_run: str | None = None
        self._next_run: str | None = None
        self._in_progress: bool = False
        self._current_symbol: str | None = None

        # Incremental generation / pruning stats for the last cycle
        self._incremental_skipped: int = 0
        self._total_pruned: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, registry: AssetRegistry) -> None:
        """Main loop — generate datasets every ``DATASET_GEN_INTERVAL_SECS``.

        Parameters
        ----------
        registry:
            The :class:`~.registry.asset_registry.AssetRegistry` used to
            discover which symbols are currently enabled.
        """
        log.info(
            "dataset_generator.starting",
            interval_secs=DATASET_GEN_INTERVAL_SECS,
            output_dir=str(self._output_dir),
            min_coverage=DATASET_MIN_COVERAGE,
        )

        while True:
            self._next_run = (datetime.now(UTC) + timedelta(seconds=DATASET_GEN_INTERVAL_SECS)).isoformat()
            await self._publish_state()

            try:
                await self._run_cycle(registry)
            except Exception:
                log.exception("dataset_generator.cycle_failed")

            await asyncio.sleep(DATASET_GEN_INTERVAL_SECS)

    async def generate_for_symbol(
        self,
        registry: AssetRegistry,
        symbol: str,
    ) -> dict[str, Any]:
        """Trigger manual generation for a single *symbol*.

        Returns a summary dict suitable for JSON serialisation.
        """
        asset = await registry.get(symbol)
        if asset is None:
            return {"error": f"Unknown symbol: {symbol}"}

        coverage = await self._get_all_coverage(symbol)
        results = await self._generate_asset(asset, coverage)
        await self._write_manifest(registry)
        return results

    async def generate_all(self, registry: AssetRegistry) -> dict[str, Any]:
        """Trigger manual generation for all enabled assets."""
        await self._run_cycle(registry)
        return {"status": "complete", "last_run": self._last_run}

    def get_state(self) -> dict[str, Any]:
        """Return current daemon state (for the status API endpoint)."""
        return {
            "last_run": self._last_run,
            "next_run": self._next_run,
            "in_progress": self._in_progress,
            "current_symbol": self._current_symbol,
            "interval_secs": DATASET_GEN_INTERVAL_SECS,
            "output_dir": str(self._output_dir),
            "min_coverage": DATASET_MIN_COVERAGE,
            "incremental_skipped": self._incremental_skipped,
            "total_pruned": self._total_pruned,
        }

    # ------------------------------------------------------------------
    # Cycle orchestration
    # ------------------------------------------------------------------

    async def _run_cycle(self, registry: AssetRegistry) -> None:
        """Execute a single generation cycle across all enabled assets."""
        self._in_progress = True
        self._incremental_skipped = 0
        self._total_pruned = 0
        await self._publish_state()
        cycle_start = datetime.now(UTC)

        log.info("dataset_generator.cycle_start")

        assets = await registry.enabled_assets()
        if not assets:
            log.info("dataset_generator.no_enabled_assets")
            self._in_progress = False
            self._last_run = cycle_start.isoformat()
            await self._publish_state()
            return

        total_datasets = 0

        # Process one asset at a time to limit memory
        for asset in assets:
            self._current_symbol = asset.symbol
            await self._publish_state()

            try:
                coverage = await self._get_all_coverage(asset.symbol)
                result = await self._generate_asset(asset, coverage)
                generated = result.get("generated", 0)
                total_datasets += generated
                self._incremental_skipped += result.get("incremental_skipped", 0)

                log.info(
                    "dataset_generator.asset_complete",
                    symbol=asset.symbol,
                    generated=generated,
                    skipped=result.get("skipped", 0),
                    incremental_skipped=result.get("incremental_skipped", 0),
                )
            except Exception:
                log.exception(
                    "dataset_generator.asset_failed",
                    symbol=asset.symbol,
                )

        self._current_symbol = None

        # Write manifest after all assets are done
        await self._write_manifest(registry)

        # Prune old datasets at the end of each cycle
        try:
            pruned = await self.prune_old_datasets(keep_latest=3)
            self._total_pruned = pruned
            if pruned > 0:
                log.info("dataset_generator.pruned_old_datasets", pruned=pruned)
                # Re-write manifest after pruning to reflect deleted files
                await self._write_manifest(registry)
        except Exception:
            log.exception("dataset_generator.prune_failed")

        elapsed = (datetime.now(UTC) - cycle_start).total_seconds()
        self._last_run = cycle_start.isoformat()
        self._in_progress = False
        await self._publish_state()

        log.info(
            "dataset_generator.cycle_complete",
            assets=len(assets),
            total_datasets=total_datasets,
            incremental_skipped=self._incremental_skipped,
            total_pruned=self._total_pruned,
            elapsed_secs=round(elapsed, 2),
        )

    async def _publish_state(self) -> None:
        """Publish daemon state to Redis for the API to read."""
        try:
            state = self.get_state()
            await self._redis.setex(
                _STATE_KEY,
                _STATE_TTL,
                json.dumps(state),
            )
        except Exception:
            log.debug("dataset_generator.state_publish_failed", exc_info=True)

    # ------------------------------------------------------------------
    # Coverage helpers
    # ------------------------------------------------------------------

    async def _get_all_coverage(self, symbol: str) -> dict[str, float]:
        """Read coverage ratios for all intervals of *symbol* from Redis.

        Returns a dict mapping interval string to coverage percentage (0-1).
        """
        coverage: dict[str, float] = {}
        all_intervals = list({*_TRAINING_INTERVALS, *_BACKTEST_INTERVALS, *_FEATURE_INTERVALS})

        for interval in all_intervals:
            try:
                raw = await self._redis.get(f"{_COVERAGE_KEY_PREFIX}:{symbol}:{interval}")
                if raw is None:
                    coverage[interval] = 0.0
                    continue

                data = json.loads(raw if isinstance(raw, str) else raw.decode())
                pct = data.get("pct", 0.0)
                coverage[interval] = float(pct)
            except Exception:
                log.debug(
                    "dataset_generator.coverage_read_failed",
                    symbol=symbol,
                    interval=interval,
                    exc_info=True,
                )
                coverage[interval] = 0.0

        return coverage

    def _has_sufficient_coverage(
        self,
        symbol: str,
        interval: str,
        coverage: dict[str, float],
    ) -> bool:
        """Return True if *interval* has >= DATASET_MIN_COVERAGE for *symbol*."""
        pct = coverage.get(interval, 0.0)
        if pct < DATASET_MIN_COVERAGE:
            log.debug(
                "dataset_generator.insufficient_coverage",
                symbol=symbol,
                interval=interval,
                coverage=round(pct, 4),
                required=DATASET_MIN_COVERAGE,
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Per-asset generation
    # ------------------------------------------------------------------

    async def _generate_asset(
        self,
        asset: Any,
        coverage: dict[str, float],
    ) -> dict[str, Any]:
        """Generate all applicable datasets for a single asset.

        Returns a summary dict with counts of generated / skipped datasets.
        """
        symbol = asset.symbol
        symbol_dir = self._output_dir / _safe_filename(symbol)
        symbol_dir.mkdir(parents=True, exist_ok=True)

        generated = 0
        skipped = 0
        incremental_skipped = 0
        today = datetime.now(UTC).strftime("%Y%m%d")

        # 1. Training dataset (needs multiple intervals)
        training_intervals_ok = [
            iv for iv in _TRAINING_INTERVALS if self._has_sufficient_coverage(symbol, iv, coverage)
        ]
        if len(training_intervals_ok) >= 2:
            # Check incremental: use the finest available interval for the check
            finest_iv = sorted(training_intervals_ok, key=_interval_sort_key)[0]
            needs_regen = await self._needs_regeneration(
                symbol,
                "training",
                finest_iv,
                symbol_dir,
            )
            if not needs_regen:
                log.debug(
                    "dataset_generator.training_incremental_skip",
                    symbol=symbol,
                    reason="no_new_data",
                )
                incremental_skipped += 1
            else:
                try:
                    ok = await self._generate_training(symbol, symbol_dir, today, training_intervals_ok)
                    if ok:
                        generated += 1
                    else:
                        skipped += 1
                except Exception:
                    log.exception("dataset_generator.training_failed", symbol=symbol)
                    skipped += 1
        else:
            log.debug(
                "dataset_generator.training_skipped",
                symbol=symbol,
                reason="insufficient_interval_coverage",
                ok_intervals=training_intervals_ok,
            )
            skipped += 1

        # 2. Backtest datasets (one per interval)
        for interval in _BACKTEST_INTERVALS:
            if not self._has_sufficient_coverage(symbol, interval, coverage):
                skipped += 1
                continue
            needs_regen = await self._needs_regeneration(
                symbol,
                "backtest",
                interval,
                symbol_dir,
            )
            if not needs_regen:
                log.debug(
                    "dataset_generator.backtest_incremental_skip",
                    symbol=symbol,
                    interval=interval,
                    reason="no_new_data",
                )
                incremental_skipped += 1
                continue
            try:
                ok = await self._generate_backtest(symbol, interval, symbol_dir, today)
                if ok:
                    generated += 1
                else:
                    skipped += 1
            except Exception:
                log.exception(
                    "dataset_generator.backtest_failed",
                    symbol=symbol,
                    interval=interval,
                )
                skipped += 1

        # 3. Feature datasets (one per interval)
        for interval in _FEATURE_INTERVALS:
            if not self._has_sufficient_coverage(symbol, interval, coverage):
                skipped += 1
                continue
            needs_regen = await self._needs_regeneration(
                symbol,
                "features",
                interval,
                symbol_dir,
            )
            if not needs_regen:
                log.debug(
                    "dataset_generator.features_incremental_skip",
                    symbol=symbol,
                    interval=interval,
                    reason="no_new_data",
                )
                incremental_skipped += 1
                continue
            try:
                ok = await self._generate_features(symbol, interval, symbol_dir, today)
                if ok:
                    generated += 1
                else:
                    skipped += 1
            except Exception:
                log.exception(
                    "dataset_generator.features_failed",
                    symbol=symbol,
                    interval=interval,
                )
                skipped += 1

        return {
            "symbol": symbol,
            "generated": generated,
            "skipped": skipped,
            "incremental_skipped": incremental_skipped,
            "coverage": coverage,
        }

    # ------------------------------------------------------------------
    # DB queries (guarded by semaphore)
    # ------------------------------------------------------------------

    async def _get_latest_bar_info(self, symbol: str, interval: str) -> tuple[str | None, int]:
        """Returns (latest_timestamp_iso, total_row_count) for the given symbol+interval."""
        from sqlalchemy import text

        query = text(
            """
            SELECT MAX(timestamp) AS latest_ts, COUNT(*) AS total_rows
              FROM historical_bars
             WHERE symbol   = :symbol
               AND interval = :interval;
            """
        )

        async with self._sem:
            async with self._engine.connect() as conn:
                result = await conn.execute(
                    query,
                    {"symbol": symbol, "interval": interval},
                )
                row = result.fetchone()

        if row is None:
            return None, 0

        latest_ts, total_rows = row
        if latest_ts is None:
            return None, 0

        ts_iso = latest_ts.isoformat() if hasattr(latest_ts, "isoformat") else str(latest_ts)
        return ts_iso, int(total_rows)

    async def _needs_regeneration(
        self,
        symbol: str,
        dataset_type: str,  # "training", "backtest", "features"
        interval: str | None,  # None for training (multi-interval)
        symbol_dir: Path,
    ) -> bool:
        """Check whether a dataset needs to be regenerated.

        Reads the existing manifest, compares the latest DB bar timestamp
        and row count against what was previously recorded.  Returns True
        if regeneration is needed.
        """
        # Read existing manifest
        manifest_path = self._output_dir / "manifest.json"
        if not manifest_path.is_file():
            return True

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return True

        datasets = manifest.get("datasets", [])

        # Find matching entry: match by symbol, type, and interval
        ds_interval = "multi" if dataset_type == "training" else (interval or "unknown")
        matching = [
            d
            for d in datasets
            if d.get("symbol") == symbol and d.get("type") == dataset_type and d.get("interval") == ds_interval
        ]

        if not matching:
            return True

        # Use the most recent entry (last in list, since manifest is rebuilt each cycle)
        entry = matching[-1]
        entry_end_date = (entry.get("date_range") or {}).get("end")
        entry_rows = entry.get("rows", 0)

        if not entry_end_date:
            return True

        # Determine which DB interval to query
        query_interval = interval if interval else "1m"

        try:
            latest_ts, db_rows = await self._get_latest_bar_info(symbol, query_interval)
        except Exception:
            log.debug(
                "dataset_generator.needs_regen_db_error",
                symbol=symbol,
                dataset_type=dataset_type,
                exc_info=True,
            )
            # On error, regenerate to be safe
            return True

        if latest_ts is None:
            # No data in DB at all — nothing to generate
            return False

        # Compare timestamps: if DB has newer data, regenerate
        if latest_ts > entry_end_date:
            log.debug(
                "dataset_generator.needs_regen_newer_data",
                symbol=symbol,
                dataset_type=dataset_type,
                interval=ds_interval,
                db_latest=latest_ts,
                manifest_end=entry_end_date,
            )
            return True

        # Compare row counts: if DB has >5% more rows, regenerate
        if entry_rows > 0 and db_rows > entry_rows * 1.05:
            log.debug(
                "dataset_generator.needs_regen_more_rows",
                symbol=symbol,
                dataset_type=dataset_type,
                interval=ds_interval,
                db_rows=db_rows,
                manifest_rows=entry_rows,
            )
            return True

        return False

    async def _fetch_bars(
        self,
        symbol: str,
        interval: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch historical bars from Postgres, oldest-first.

        Uses the semaphore to serialise DB access during generation.
        """
        from sqlalchemy import text

        limit_clause = f"LIMIT {int(limit)}" if limit else ""

        query = text(
            f"""
            SELECT timestamp, open, high, low, close, volume
              FROM historical_bars
             WHERE symbol   = :symbol
               AND interval = :interval
             ORDER BY timestamp ASC
             {limit_clause};
            """
        )

        async with self._sem:
            async with self._engine.connect() as conn:
                result = await conn.execute(
                    query,
                    {"symbol": symbol, "interval": interval},
                )
                rows = result.fetchall()

        bars: list[dict[str, Any]] = []
        for row in rows:
            ts, open_, high, low, close, volume = row
            bars.append(
                {
                    "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                    "open": float(open_),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                    "volume": float(volume),
                }
            )

        return bars

    # ------------------------------------------------------------------
    # Training dataset generation
    # ------------------------------------------------------------------

    async def _generate_training(
        self,
        symbol: str,
        symbol_dir: Path,
        date_str: str,
        intervals: list[str],
    ) -> bool:
        """Generate a merged multi-interval training dataset.

        Combines bars from all available intervals into a single dataset
        with columns prefixed by interval (e.g. ``1m_open``, ``5m_close``).
        Falls back to CSV when pyarrow is not available.
        """
        all_bars: dict[str, list[dict[str, Any]]] = {}

        for interval in intervals:
            bars = await self._fetch_bars(symbol, interval)
            if bars:
                all_bars[interval] = bars

        if not all_bars:
            log.debug("dataset_generator.training_no_data", symbol=symbol)
            return False

        # Build rows: each interval's bars become columns with prefixed keys
        # Use the finest-grain interval as the primary timeline
        sorted_intervals = sorted(
            all_bars.keys(),
            key=lambda iv: _interval_sort_key(iv),
        )
        primary = sorted_intervals[0]
        primary_bars = all_bars[primary]

        header = ["timestamp"]
        for iv in sorted_intervals:
            header.extend(
                [
                    f"{iv}_open",
                    f"{iv}_high",
                    f"{iv}_low",
                    f"{iv}_close",
                    f"{iv}_volume",
                ]
            )

        # Build timestamp indexes for non-primary intervals for alignment
        interval_indexes: dict[str, dict[str, dict[str, Any]]] = {}
        for iv in sorted_intervals:
            if iv == primary:
                continue
            index: dict[str, dict[str, Any]] = {}
            for bar in all_bars[iv]:
                index[bar["timestamp"]] = bar
            interval_indexes[iv] = index

        rows: list[list[str]] = []
        # Track latest aligned bar for each non-primary interval
        latest_aligned: dict[str, dict[str, Any] | None] = {iv: None for iv in sorted_intervals if iv != primary}

        for bar in primary_bars:
            ts = bar["timestamp"]
            row: list[str] = [ts]

            # Primary interval values
            row.extend(
                [
                    str(bar["open"]),
                    str(bar["high"]),
                    str(bar["low"]),
                    str(bar["close"]),
                    str(bar["volume"]),
                ]
            )

            # Other intervals: find aligned or most recent bar
            for iv in sorted_intervals:
                if iv == primary:
                    continue
                idx = interval_indexes[iv]
                if ts in idx:
                    latest_aligned[iv] = idx[ts]

                aligned = latest_aligned[iv]
                if aligned is not None:
                    row.extend(
                        [
                            str(aligned["open"]),
                            str(aligned["high"]),
                            str(aligned["low"]),
                            str(aligned["close"]),
                            str(aligned["volume"]),
                        ]
                    )
                else:
                    row.extend(["", "", "", "", ""])

            rows.append(row)

        if not rows:
            return False

        # Write files — Parquet first (primary), CSV as secondary/fallback
        safe_sym = _safe_filename(symbol)
        if _HAS_PARQUET:
            parquet_filename = f"training_{safe_sym}_{date_str}.parquet"
            parquet_path = symbol_dir / parquet_filename
            _write_parquet(parquet_path, header, rows)

            csv_filename = f"training_{safe_sym}_{date_str}.csv"
            csv_path = symbol_dir / csv_filename
            _write_csv(csv_path, header, rows)

            log.info(
                "dataset_generator.training_generated",
                symbol=symbol,
                rows=len(rows),
                intervals=sorted_intervals,
                format="parquet+csv",
                path=str(parquet_path),
            )
        else:
            log.warning(
                "dataset_generator.pyarrow_unavailable",
                symbol=symbol,
                dataset_type="training",
                fallback="csv_only",
            )
            csv_filename = f"training_{safe_sym}_{date_str}.csv"
            csv_path = symbol_dir / csv_filename
            _write_csv(csv_path, header, rows)

            log.info(
                "dataset_generator.training_generated",
                symbol=symbol,
                rows=len(rows),
                intervals=sorted_intervals,
                format="csv",
                path=str(csv_path),
            )
        return True

    # ------------------------------------------------------------------
    # Backtest dataset generation
    # ------------------------------------------------------------------

    async def _generate_backtest(
        self,
        symbol: str,
        interval: str,
        symbol_dir: Path,
        date_str: str,
    ) -> bool:
        """Generate a gap-filled backtest dataset for a single interval.

        Missing bars are forward-filled from the previous bar's close.
        """
        bars = await self._fetch_bars(symbol, interval)
        if not bars:
            log.debug(
                "dataset_generator.backtest_no_data",
                symbol=symbol,
                interval=interval,
            )
            return False

        # Forward-fill gaps
        filled = _forward_fill_gaps(bars, interval)

        header = ["timestamp", "open", "high", "low", "close", "volume"]
        rows: list[list[str]] = []
        for bar in filled:
            rows.append(
                [
                    bar["timestamp"],
                    str(bar["open"]),
                    str(bar["high"]),
                    str(bar["low"]),
                    str(bar["close"]),
                    str(bar["volume"]),
                ]
            )

        if not rows:
            return False

        safe_sym = _safe_filename(symbol)
        if _HAS_PARQUET:
            parquet_filename = f"backtest_{safe_sym}_{interval}_{date_str}.parquet"
            parquet_path = symbol_dir / parquet_filename
            _write_parquet(parquet_path, header, rows)

            csv_filename = f"backtest_{safe_sym}_{interval}_{date_str}.csv"
            csv_path = symbol_dir / csv_filename
            _write_csv(csv_path, header, rows)

            log.info(
                "dataset_generator.backtest_generated",
                symbol=symbol,
                interval=interval,
                rows=len(rows),
                format="parquet+csv",
                path=str(parquet_path),
            )
        else:
            log.warning(
                "dataset_generator.pyarrow_unavailable",
                symbol=symbol,
                dataset_type="backtest",
                interval=interval,
                fallback="csv_only",
            )
            csv_filename = f"backtest_{safe_sym}_{interval}_{date_str}.csv"
            csv_path = symbol_dir / csv_filename
            _write_csv(csv_path, header, rows)

            log.info(
                "dataset_generator.backtest_generated",
                symbol=symbol,
                interval=interval,
                rows=len(rows),
                format="csv",
                path=str(csv_path),
            )
        return True

    # ------------------------------------------------------------------
    # Feature dataset generation
    # ------------------------------------------------------------------

    async def _generate_features(
        self,
        symbol: str,
        interval: str,
        symbol_dir: Path,
        date_str: str,
    ) -> bool:
        """Generate a dataset with pre-computed technical indicators."""
        bars = await self._fetch_bars(symbol, interval)
        if not bars:
            log.debug(
                "dataset_generator.features_no_data",
                symbol=symbol,
                interval=interval,
            )
            return False

        if len(bars) < 21:
            log.debug(
                "dataset_generator.features_insufficient_bars",
                symbol=symbol,
                interval=interval,
                bar_count=len(bars),
            )
            return False

        # Extract price arrays
        timestamps = [b["timestamp"] for b in bars]
        opens = [b["open"] for b in bars]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        closes = [b["close"] for b in bars]
        volumes = [b["volume"] for b in bars]

        # Compute indicators
        ema9 = _ema(closes, 9)
        ema21 = _ema(closes, 21)
        rsi14 = _rsi(closes, 14)
        atr14 = _atr(highs, lows, closes, 14)
        vwap = _vwap_daily(timestamps, highs, lows, closes, volumes)
        bb_upper, bb_middle, bb_lower = _bollinger_bands(closes, 20, 2.0)

        header = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "ema9",
            "ema21",
            "rsi14",
            "atr14",
            "vwap",
            "bb_upper",
            "bb_middle",
            "bb_lower",
        ]
        rows: list[list[str]] = []

        for i in range(len(bars)):
            rows.append(
                [
                    timestamps[i],
                    str(opens[i]),
                    str(highs[i]),
                    str(lows[i]),
                    str(closes[i]),
                    str(volumes[i]),
                    _fmt(ema9[i]),
                    _fmt(ema21[i]),
                    _fmt(rsi14[i]),
                    _fmt(atr14[i]),
                    _fmt(vwap[i]),
                    _fmt(bb_upper[i]),
                    _fmt(bb_middle[i]),
                    _fmt(bb_lower[i]),
                ]
            )

        safe_sym = _safe_filename(symbol)
        if _HAS_PARQUET:
            parquet_filename = f"features_{safe_sym}_{interval}_{date_str}.parquet"
            parquet_path = symbol_dir / parquet_filename
            _write_parquet(parquet_path, header, rows)

            csv_filename = f"features_{safe_sym}_{interval}_{date_str}.csv"
            csv_path = symbol_dir / csv_filename
            _write_csv(csv_path, header, rows)

            log.info(
                "dataset_generator.features_generated",
                symbol=symbol,
                interval=interval,
                rows=len(rows),
                format="parquet+csv",
                path=str(parquet_path),
            )
        else:
            log.warning(
                "dataset_generator.pyarrow_unavailable",
                symbol=symbol,
                dataset_type="features",
                interval=interval,
                fallback="csv_only",
            )
            csv_filename = f"features_{safe_sym}_{interval}_{date_str}.csv"
            csv_path = symbol_dir / csv_filename
            _write_csv(csv_path, header, rows)

            log.info(
                "dataset_generator.features_generated",
                symbol=symbol,
                interval=interval,
                rows=len(rows),
                format="csv",
                path=str(csv_path),
            )
        return True

    # ------------------------------------------------------------------
    # Manifest generation
    # ------------------------------------------------------------------

    async def prune_old_datasets(self, keep_latest: int = 3) -> int:
        """Remove old dataset files, keeping only the latest *keep_latest* per group.

        Groups files by (symbol, type, interval) and sorts by the date
        component in the filename.  Returns the total count of deleted files.
        """
        deleted_count = 0

        if not self._output_dir.is_dir():
            return 0

        for symbol_dir in sorted(self._output_dir.iterdir()):
            if not symbol_dir.is_dir() or symbol_dir.name == "__pycache__":
                continue

            # Collect dataset files
            groups: dict[tuple[str, str], list[Path]] = {}

            for filepath in sorted(symbol_dir.iterdir()):
                if not filepath.is_file():
                    continue
                if filepath.suffix not in (".csv", ".parquet"):
                    continue
                if not (
                    filepath.name.startswith("training_")
                    or filepath.name.startswith("backtest_")
                    or filepath.name.startswith("features_")
                ):
                    continue

                ds_type, ds_interval = _parse_filename(filepath.name)
                key = (ds_type, ds_interval)
                groups.setdefault(key, []).append(filepath)

            # For each group, sort by date in filename and prune
            for (ds_type, ds_interval), files in groups.items():
                # Sort by filename — since date is the last component before
                # the extension (YYYYMMDD), lexicographic sort works correctly.
                files_sorted = sorted(files, key=lambda p: p.stem)

                if len(files_sorted) <= keep_latest:
                    continue

                to_delete = files_sorted[: len(files_sorted) - keep_latest]
                for fp in to_delete:
                    try:
                        fp.unlink()
                        deleted_count += 1
                        log.debug(
                            "dataset_generator.pruned_file",
                            path=str(fp),
                            type=ds_type,
                            interval=ds_interval,
                        )
                    except Exception:
                        log.warning(
                            "dataset_generator.prune_delete_failed",
                            path=str(fp),
                            exc_info=True,
                        )

        return deleted_count

    async def _write_manifest(self, registry: AssetRegistry) -> None:
        """Scan output directory and write ``manifest.json``."""
        datasets: list[dict[str, Any]] = []
        coverage_summary: dict[str, dict[str, float]] = {}

        assets = await registry.enabled_assets()

        for asset in assets:
            symbol = asset.symbol
            safe_sym = _safe_filename(symbol)
            symbol_dir = self._output_dir / safe_sym

            # Collect coverage for this symbol
            sym_coverage: dict[str, float] = {}
            all_intervals = list({*_TRAINING_INTERVALS, *_BACKTEST_INTERVALS, *_FEATURE_INTERVALS})
            for interval in all_intervals:
                try:
                    raw = await self._redis.get(f"{_COVERAGE_KEY_PREFIX}:{symbol}:{interval}")
                    if raw:
                        data = json.loads(raw if isinstance(raw, str) else raw.decode())
                        sym_coverage[interval] = round(float(data.get("pct", 0.0)), 4)
                    else:
                        sym_coverage[interval] = 0.0
                except Exception:
                    sym_coverage[interval] = 0.0
            coverage_summary[symbol] = sym_coverage

            if not symbol_dir.is_dir():
                continue

            # Scan files in the symbol directory
            for filepath in sorted(symbol_dir.iterdir()):
                if not filepath.is_file():
                    continue
                if not (
                    filepath.suffix in (".csv", ".parquet")
                    and (
                        filepath.name.startswith("training_")
                        or filepath.name.startswith("backtest_")
                        or filepath.name.startswith("features_")
                    )
                ):
                    continue

                # Determine dataset type and interval
                ds_type, ds_interval = _parse_filename(filepath.name)
                size_bytes = filepath.stat().st_size
                checksum = _sha256(filepath)
                row_count, date_range = _count_rows_and_range(filepath)

                rel_path = str(filepath.relative_to(self._output_dir))

                # Determine primary format
                is_parquet = filepath.suffix == ".parquet"
                fmt = "parquet" if is_parquet else "csv"

                datasets.append(
                    {
                        "symbol": symbol,
                        "type": ds_type,
                        "interval": ds_interval,
                        "path": rel_path,
                        "format": fmt,
                        "rows": row_count,
                        "date_range": date_range,
                        "size_bytes": size_bytes,
                        "checksum_sha256": checksum,
                    }
                )

        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "datasets": datasets,
            "coverage_summary": coverage_summary,
        }

        manifest_path = self._output_dir / "manifest.json"
        try:
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            log.info(
                "dataset_generator.manifest_written",
                path=str(manifest_path),
                datasets=len(datasets),
            )
        except Exception:
            log.exception("dataset_generator.manifest_write_failed")


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------


def _write_csv(filepath: Path, header: list[str], rows: list[list[str]]) -> None:
    """Write a CSV file with the given header and rows."""
    lines: list[str] = [",".join(header)]
    for row in rows:
        lines.append(",".join(row))
    filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")


# Columns that should use float64 in Parquet (OHLCV + indicators)
_FLOAT_COLUMNS: set[str] = {
    "open",
    "high",
    "low",
    "close",
    "volume",
    "ema9",
    "ema21",
    "rsi14",
    "atr14",
    "vwap",
    "bb_upper",
    "bb_middle",
    "bb_lower",
}

# Columns that should be stored as strings (use dictionary encoding)
_STRING_COLUMNS: set[str] = {"timestamp"}


def _write_parquet(filepath: Path, header: list[str], rows: list[list[str]]) -> None:
    """Write a Parquet file using pyarrow with snappy compression.

    Uses typed Arrow schema: ``pa.float64()`` for OHLCV / indicator columns,
    ``pa.string()`` for timestamps and other text.  Enables dictionary
    encoding on string columns and writes column-level statistics for
    efficient filtering.

    Falls back to CSV if pyarrow fails or is unavailable.
    """
    if not _HAS_PARQUET:
        csv_path = filepath.with_suffix(".csv")
        _write_csv(csv_path, header, rows)
        return

    try:
        # Build typed columns
        arrow_columns: list[pa.Array] = []  # type: ignore[name-defined]
        arrow_fields: list[pa.field] = []  # type: ignore[name-defined]

        for col_idx, col_name in enumerate(header):
            raw_values = [row[col_idx] if col_idx < len(row) else "" for row in rows]

            # Determine if this is a float column (exact name or interval-prefixed)
            is_float = False
            base_name = col_name
            # Handle interval-prefixed columns like "1m_open", "5m_close"
            if "_" in col_name:
                parts = col_name.split("_", 1)
                if len(parts) == 2:
                    base_name = parts[1]

            if col_name in _FLOAT_COLUMNS or base_name in _FLOAT_COLUMNS:
                is_float = True

            if is_float:
                # Parse to float, treating empty strings as None
                float_values: list[float | None] = []
                for v in raw_values:
                    if v == "" or v is None:
                        float_values.append(None)
                    else:
                        try:
                            float_values.append(float(v))
                        except (ValueError, TypeError):
                            float_values.append(None)
                arrow_columns.append(pa.array(float_values, type=pa.float64()))  # type: ignore[name-defined]
                arrow_fields.append(pa.field(col_name, pa.float64()))  # type: ignore[name-defined]
            else:
                # String column
                arrow_columns.append(pa.array(raw_values, type=pa.string()))  # type: ignore[name-defined]
                arrow_fields.append(pa.field(col_name, pa.string()))  # type: ignore[name-defined]

        schema = pa.schema(arrow_fields)  # type: ignore[name-defined]
        table = pa.table(  # type: ignore[name-defined]
            {header[i]: arrow_columns[i] for i in range(len(header))},
            schema=schema,
        )

        # Determine which columns get dictionary encoding
        use_dictionary = [col_name in _STRING_COLUMNS or col_name == "timestamp" for col_name in header]

        pq.write_table(  # type: ignore[name-defined]
            table,
            str(filepath),
            compression="snappy",
            use_dictionary=use_dictionary,
            write_statistics=True,
        )
    except Exception:
        log.warning(
            "dataset_generator.parquet_fallback_csv",
            path=str(filepath),
            exc_info=True,
        )
        csv_path = filepath.with_suffix(".csv")
        _write_csv(csv_path, header, rows)


def _sha256(filepath: Path) -> str:
    """Return hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_rows_and_range(
    filepath: Path,
) -> tuple[int, dict[str, str | None]]:
    """Count data rows and extract date range from a CSV/Parquet file.

    Returns ``(row_count, {"start": ..., "end": ...})``.
    """
    date_range: dict[str, str | None] = {"start": None, "end": None}

    if filepath.suffix == ".parquet" and _HAS_PARQUET:
        try:
            table = pq.read_table(str(filepath))  # type: ignore[name-defined]
            n = table.num_rows
            if n > 0 and "timestamp" in table.column_names:
                ts_col = table.column("timestamp").to_pylist()
                date_range["start"] = str(ts_col[0]) if ts_col else None
                date_range["end"] = str(ts_col[-1]) if ts_col else None
            return n, date_range
        except Exception:
            pass

    # CSV fallback
    try:
        text = filepath.read_text(encoding="utf-8")
        lines = text.strip().split("\n")
        if len(lines) <= 1:
            return 0, date_range

        row_count = len(lines) - 1  # exclude header
        # First column of first/last data row is the timestamp
        first_row = lines[1].split(",")
        last_row = lines[-1].split(",")
        date_range["start"] = first_row[0] if first_row else None
        date_range["end"] = last_row[0] if last_row else None

        return row_count, date_range
    except Exception:
        return 0, date_range


def _parse_filename(name: str) -> tuple[str, str]:
    """Extract dataset type and interval from a filename.

    Expected patterns:
    - ``training_{symbol}_{date}.csv``
    - ``backtest_{symbol}_{interval}_{date}.csv``
    - ``features_{symbol}_{interval}_{date}.csv``
    """
    stem = Path(name).stem
    parts = stem.split("_")

    ds_type = parts[0] if parts else "unknown"

    # For backtest/features: interval is second-to-last part
    if ds_type in ("backtest", "features") and len(parts) >= 4:
        ds_interval = parts[-2]
    elif ds_type == "training":
        ds_interval = "multi"
    else:
        ds_interval = "unknown"

    return ds_type, ds_interval


# ---------------------------------------------------------------------------
# Gap-filling helper
# ---------------------------------------------------------------------------

_INTERVAL_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


def _forward_fill_gaps(
    bars: list[dict[str, Any]],
    interval: str,
) -> list[dict[str, Any]]:
    """Forward-fill missing bars using the previous bar's close.

    Produces a sequential bar series with no timestamp gaps.
    """
    step = _INTERVAL_SECONDS.get(interval)
    if step is None or len(bars) < 2:
        return bars

    filled: list[dict[str, Any]] = [bars[0]]
    prev = bars[0]

    for i in range(1, len(bars)):
        cur = bars[i]

        try:
            prev_dt = datetime.fromisoformat(prev["timestamp"])
            cur_dt = datetime.fromisoformat(cur["timestamp"])
        except (ValueError, TypeError):
            filled.append(cur)
            prev = cur
            continue

        # Ensure timezone-aware comparison
        if prev_dt.tzinfo is None:
            prev_dt = prev_dt.replace(tzinfo=UTC)
        if cur_dt.tzinfo is None:
            cur_dt = cur_dt.replace(tzinfo=UTC)

        gap_secs = (cur_dt - prev_dt).total_seconds()
        expected_gap = step

        # Fill missing bars
        if gap_secs > expected_gap * 1.5:
            n_missing = int(gap_secs / expected_gap) - 1
            # Cap to avoid creating absurdly large fills (e.g. weekends)
            n_missing = min(n_missing, 500)

            for j in range(1, n_missing + 1):
                fill_dt = prev_dt + timedelta(seconds=step * j)
                filled.append(
                    {
                        "timestamp": fill_dt.isoformat(),
                        "open": prev["close"],
                        "high": prev["close"],
                        "low": prev["close"],
                        "close": prev["close"],
                        "volume": 0.0,
                    }
                )

        filled.append(cur)
        prev = cur

    return filled


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


def _safe_filename(symbol: str) -> str:
    """Sanitise a symbol name for use as a directory/file name component."""
    return symbol.replace("/", "_").replace("\\", "_").replace(" ", "_")


def _fmt(value: float | None) -> str:
    """Format an indicator value to string, empty for None."""
    if value is None:
        return ""
    return f"{value:.6f}"


def _interval_sort_key(interval: str) -> int:
    """Return a numeric sort key for interval strings (finest first)."""
    return _INTERVAL_SECONDS.get(interval, 999999)
