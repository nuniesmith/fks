#!/usr/bin/env python3
"""
bracket_sweep.py — RETRAIN-I2: TP/SL Optimization per Asset Group
==================================================================
Sweeps all combinations of SL/TP ATR multipliers across asset groups to
find the BracketConfig that maximises trade expectancy for each group.

Parameter grid (144 total combinations):
  sl_atr_mult:  [1.0, 1.25, 1.5, 2.0]
  tp1_atr_mult: [1.5, 2.0, 2.5, 3.0]
  tp2_atr_mult: [2.5, 3.0, 4.0]
  tp3_atr_mult: [3.5, 4.5, 6.0]

For each (symbol, BracketConfig) pair:
  - Runs simulate_batch() (ORB) or all 13 breakout types (--breakout-type all)
  - Filters to actual trades (result.is_trade)
  - Computes win_rate, avg_r, expectancy = win_rate × avg_r
  - Aggregates per group → finds the bracket config with highest expectancy

Bar sources (mutually exclusive, engine-url takes precedence):
  --engine-url   GET /bars/{symbol}?interval=1m&days_back=N  (default)
  --csv-dir      {csv_dir}/{symbol}_1m.csv  (offline / pre-fetched)

Usage:
    # Full sweep against local engine:
    python scripts/bracket_sweep.py

    # Use pre-fetched CSVs, metals only, 8 workers:
    python scripts/bracket_sweep.py --csv-dir data/bars --group metals --jobs 8

    # Point at remote engine, print optimal config code:
    python scripts/bracket_sweep.py --engine-url http://oryx:8050 --update-config

    # Sweep all 13 breakout types:
    python scripts/bracket_sweep.py --breakout-type all

    # Dry run — show plan without running:
    python scripts/bracket_sweep.py --dry-run

    # Override symbols:
    python scripts/bracket_sweep.py --symbols MGC,MES --top-n 10

Exit codes:
    0 — sweep completed (even if some symbols had no data)
    1 — fatal error (no data at all, bad args, etc.)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# sys.path bootstrap — insert src/ruby/src so lib.* imports work
# ---------------------------------------------------------------------------
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)  # fks/
_SRUSTCODE_DIR = os.path.join(_PROJECT_ROOT, "src", "ruby", "src")
if _SRUSTCODE_DIR not in sys.path:
    sys.path.insert(0, _SRUSTCODE_DIR)

# ---------------------------------------------------------------------------
# Standard library
# ---------------------------------------------------------------------------
import argparse  # noqa: E402
import concurrent.futures  # noqa: E402
import contextlib  # noqa: E402
import itertools  # noqa: E402
import json  # noqa: E402
import textwrap  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any  # noqa: E402

# ---------------------------------------------------------------------------
# Third-party (must be available in the trainer/script venv)
# ---------------------------------------------------------------------------
import pandas as pd  # noqa: E402
import requests  # noqa: E402

# ---------------------------------------------------------------------------
# Project imports — deferred until after sys.path is set
# ---------------------------------------------------------------------------
from lib.services.training.rb_simulator import (  # noqa: E402
    BracketConfig,
    simulate_batch,
    simulate_batch_asian,
    simulate_batch_bollinger_squeeze,
    simulate_batch_consolidation,
    simulate_batch_fibonacci,
    simulate_batch_gap_rejection,
    simulate_batch_ib,
    simulate_batch_inside_day,
    simulate_batch_monthly,
    simulate_batch_pivot_points,
    simulate_batch_prev_day,
    simulate_batch_value_area,
    simulate_batch_weekly,
)

# ---------------------------------------------------------------------------
# Terminal colours — match existing scripts/ style
# ---------------------------------------------------------------------------
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
DIM = "\033[2m"
RESET = "\033[0m"

# ---------------------------------------------------------------------------
# Asset groups — mirrors ASSET_GROUPS in trainer_server.py
# ---------------------------------------------------------------------------
ASSET_GROUPS: dict[str, list[str]] = {
    "metals": ["MGC", "SIL"],
    "equity_micros": ["MES", "MNQ", "M2K", "MYM"],
}

ALL_SYMBOLS: list[str] = sorted({s for syms in ASSET_GROUPS.values() for s in syms})

# ---------------------------------------------------------------------------
# Parameter grid
# ---------------------------------------------------------------------------
SL_ATR_MULTS: list[float] = [1.0, 1.25, 1.5, 2.0]
TP1_ATR_MULTS: list[float] = [1.5, 2.0, 2.5, 3.0]
TP2_ATR_MULTS: list[float] = [2.5, 3.0, 4.0]
TP3_ATR_MULTS: list[float] = [3.5, 4.5, 6.0]

# Total = 4 × 4 × 3 × 3 = 144
PARAM_GRID: list[tuple[float, float, float, float]] = list(
    itertools.product(SL_ATR_MULTS, TP1_ATR_MULTS, TP2_ATR_MULTS, TP3_ATR_MULTS)
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_ENGINE_URL = "http://localhost:8050"
DEFAULT_DAYS_BACK = 90
DEFAULT_OUTPUT = "bracket_sweep_results.json"
DEFAULT_TOP_N = 5
DEFAULT_JOBS = 4

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def _log(msg: str, color: str = "") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{DIM}[{ts}]{RESET} {color}{msg}{RESET}", flush=True)


def _ok(msg: str) -> None:
    _log(f"✓ {msg}", GREEN)


def _fail(msg: str) -> None:
    _log(f"✗ {msg}", RED)


def _info(msg: str) -> None:
    _log(f"  {msg}", CYAN)


def _warn(msg: str) -> None:
    _log(f"⚠ {msg}", YELLOW)


def _dim(msg: str) -> None:
    _log(f"  {msg}", DIM)


def _head(msg: str) -> None:
    print(f"\n{BOLD}{CYAN}{msg}{RESET}", flush=True)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class SweepResult:
    """Metrics for one (symbol, BracketConfig) evaluation."""

    symbol: str
    sl: float
    tp1: float
    tp2: float
    tp3: float
    n_windows: int = 0  # total simulation windows
    n_trades: int = 0  # windows that produced a trade
    n_wins: int = 0  # winning trades
    win_rate: float = 0.0
    avg_r: float = 0.0
    expectancy: float = 0.0  # win_rate × avg_r
    error: str = ""

    def bracket_key(self) -> tuple[float, float, float, float]:
        return (self.sl, self.tp1, self.tp2, self.tp3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "sl": self.sl,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "tp3": self.tp3,
            "n_windows": self.n_windows,
            "n_trades": self.n_trades,
            "n_wins": self.n_wins,
            "win_rate": round(self.win_rate, 4),
            "avg_r": round(self.avg_r, 4),
            "expectancy": round(self.expectancy, 4),
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Bar loading
# ---------------------------------------------------------------------------


def _bars_from_csv(symbol: str, csv_dir: str) -> pd.DataFrame | None:
    """Load 1-minute bars from a pre-fetched CSV file.

    Expected filename: {csv_dir}/{symbol}_1m.csv
    Expected columns (case-insensitive): open, high, low, close, volume
    The first column (or 'timestamp'/'datetime') is used as the DatetimeIndex.
    """
    path = os.path.join(csv_dir, f"{symbol}_1m.csv")
    if not os.path.isfile(path):
        _warn(f"CSV not found: {path}")
        return None

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        _warn(f"Failed to read {path}: {exc}")
        return None

    # Normalise column names to title-case (Open, High, Low, Close, Volume)
    rename: dict[str, str] = {}
    for col in df.columns:
        low = col.lower().strip()
        if low in ("open", "o"):
            rename[col] = "Open"
        elif low in ("high", "h"):
            rename[col] = "High"
        elif low in ("low", "l"):
            rename[col] = "Low"
        elif low in ("close", "c"):
            rename[col] = "Close"
        elif low in ("volume", "vol", "v"):
            rename[col] = "Volume"
    df = df.rename(columns=rename)

    # Try to find the timestamp column and set it as index
    ts_col = None
    for col in df.columns:
        low = col.lower().strip()
        if low in ("timestamp", "datetime", "date", "time", "ts", "index"):
            ts_col = col
            break

    if ts_col is None and df.index.dtype == object:
        # The CSV index column might already be the timestamp
        with contextlib.suppress(Exception):
            df.index = pd.to_datetime(df.index)
    elif ts_col is not None:
        try:
            df[ts_col] = pd.to_datetime(df[ts_col])
            df = df.set_index(ts_col)
        except Exception as exc:
            _warn(f"Could not parse timestamp column '{ts_col}' in {path}: {exc}")
            return None

    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
        except Exception as exc:
            _warn(f"Could not create DatetimeIndex for {symbol}: {exc}")
            return None

    required = {"Open", "High", "Low", "Close"}
    missing = required - set(df.columns)
    if missing:
        _warn(f"CSV {path} missing columns: {missing}")
        return None

    return df


def _bars_from_engine(
    symbol: str,
    engine_url: str,
    days_back: int,
) -> pd.DataFrame | None:
    """Fetch 1-minute bars from the engine HTTP API.

    Endpoint: GET {engine_url}/bars/{symbol}?interval=1m&days_back={days_back}

    The engine may return JSON in one of two shapes:
      {"bars": [...]}   — list of OHLCV dicts
      {"data": [...]}   — same
      [...]             — bare list

    Each element is expected to have keys (case-insensitive):
      timestamp / time / t   → DatetimeIndex
      open  / o
      high  / h
      low   / l
      close / c
      volume / vol / v       → optional
    """
    url = f"{engine_url.rstrip('/')}/bars/{symbol}"
    params = {"interval": "1m", "days_back": days_back}

    try:
        resp = requests.get(url, params=params, timeout=30)  # type: ignore[arg-type]
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        _warn(f"Cannot reach engine at {engine_url} — is it running?")
        return None
    except requests.exceptions.HTTPError as exc:
        _warn(f"Engine HTTP error for {symbol}: {exc}")
        return None
    except Exception as exc:
        _warn(f"Engine request failed for {symbol}: {exc}")
        return None

    try:
        payload = resp.json()
    except Exception as exc:
        _warn(f"Engine returned non-JSON for {symbol}: {exc}")
        return None

    # Unwrap the list from the response envelope
    if isinstance(payload, dict):
        records = payload.get("bars") or payload.get("data") or []
    elif isinstance(payload, list):
        records = payload
    else:
        _warn(f"Unexpected engine payload type for {symbol}: {type(payload)}")
        return None

    if not records:
        _warn(f"Engine returned 0 bars for {symbol}")
        return None

    try:
        df = pd.DataFrame(records)
    except Exception as exc:
        _warn(f"Failed to build DataFrame from engine bars for {symbol}: {exc}")
        return None

    # Normalise column names
    rename: dict[str, str] = {}
    for col in df.columns:
        low = col.lower().strip()
        if low in ("open", "o"):
            rename[col] = "Open"
        elif low in ("high", "h"):
            rename[col] = "High"
        elif low in ("low", "l"):
            rename[col] = "Low"
        elif low in ("close", "c"):
            rename[col] = "Close"
        elif low in ("volume", "vol", "v"):
            rename[col] = "Volume"
        elif low in ("timestamp", "time", "datetime", "ts", "t", "date"):
            rename[col] = "_ts"
    df = df.rename(columns=rename)

    # Set the DatetimeIndex
    if "_ts" in df.columns:
        try:
            df["_ts"] = pd.to_datetime(df["_ts"])
            df = df.set_index("_ts")
            df.index.name = None
        except Exception as exc:
            _warn(f"Could not parse timestamp column from engine bars for {symbol}: {exc}")
            return None
    else:
        _warn(f"No timestamp column found in engine bars for {symbol}")
        return None

    required = {"Open", "High", "Low", "Close"}
    missing = required - set(df.columns)
    if missing:
        _warn(f"Engine bars for {symbol} missing columns: {missing}")
        return None

    return df


def load_bars(
    symbol: str,
    *,
    engine_url: str | None = None,
    csv_dir: str | None = None,
    days_back: int = DEFAULT_DAYS_BACK,
) -> pd.DataFrame | None:
    """Load 1-minute bars for *symbol* from CSV or the engine HTTP API.

    If *csv_dir* is provided it takes precedence.  Otherwise *engine_url*
    is used (defaulting to DEFAULT_ENGINE_URL).
    """
    if csv_dir:
        return _bars_from_csv(symbol, csv_dir)
    url = engine_url or DEFAULT_ENGINE_URL
    return _bars_from_engine(symbol, url, days_back)


# ---------------------------------------------------------------------------
# All 13 breakout-type batch runners
# ---------------------------------------------------------------------------

_ALL_BATCH_RUNNERS = [
    ("ORB", simulate_batch),
    ("PrevDay", simulate_batch_prev_day),
    ("InitialBalance", simulate_batch_ib),
    ("Consolidation", simulate_batch_consolidation),
    ("Weekly", simulate_batch_weekly),
    ("Monthly", simulate_batch_monthly),
    ("Asian", simulate_batch_asian),
    ("BollingerSqueeze", simulate_batch_bollinger_squeeze),
    ("ValueArea", simulate_batch_value_area),
    ("InsideDay", simulate_batch_inside_day),
    ("GapRejection", simulate_batch_gap_rejection),
    ("PivotPoints", simulate_batch_pivot_points),
    ("Fibonacci", simulate_batch_fibonacci),
]

_ORB_ONLY_RUNNERS = [("ORB", simulate_batch)]

# ---------------------------------------------------------------------------
# Core evaluation — runs in a worker process
# ---------------------------------------------------------------------------


def _evaluate_one(
    symbol: str,
    sl: float,
    tp1: float,
    tp2: float,
    tp3: float,
    bars_pkl: bytes,  # pickled DataFrame (avoids re-fetching per worker)
    breakout_type: str = "orb",
) -> SweepResult:
    """Evaluate a single (symbol, BracketConfig) pair.

    This function is designed to be called from a ProcessPoolExecutor worker.
    The bars DataFrame is passed as a pickle blob to avoid shared-memory
    issues across process boundaries.

    Returns a SweepResult with the aggregated trade metrics.
    """
    import pickle

    result = SweepResult(symbol=symbol, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3)

    try:
        bars_1m: pd.DataFrame = pickle.loads(bars_pkl)
    except Exception as exc:
        result.error = f"Failed to unpickle bars: {exc}"
        return result

    cfg = BracketConfig(
        sl_atr_mult=sl,
        tp1_atr_mult=tp1,
        tp2_atr_mult=tp2,
        tp3_atr_mult=tp3,
    )

    runners = _ALL_BATCH_RUNNERS if breakout_type == "all" else _ORB_ONLY_RUNNERS

    all_pnl_r: list[float] = []
    n_wins = 0
    n_windows = 0

    for _name, batch_fn in runners:
        try:
            sim_results = batch_fn(bars_1m, symbol=symbol, config=cfg)  # type: ignore[operator]
        except Exception:
            # One breakout type failing should not abort the whole evaluation
            continue

        n_windows += len(sim_results)

        for r in sim_results:
            if not r.is_trade:
                continue
            all_pnl_r.append(r.pnl_r)
            if r.is_winner:
                n_wins += 1

    n_trades = len(all_pnl_r)
    result.n_windows = n_windows
    result.n_trades = n_trades
    result.n_wins = n_wins

    if n_trades == 0:
        result.error = "no trades"
        return result

    win_rate = n_wins / n_trades
    avg_r = sum(all_pnl_r) / n_trades
    expectancy = win_rate * avg_r

    result.win_rate = round(win_rate, 4)
    result.avg_r = round(avg_r, 4)
    result.expectancy = round(expectancy, 4)

    return result


# ---------------------------------------------------------------------------
# Bar pre-fetch (single-threaded, before the sweep)
# ---------------------------------------------------------------------------


def prefetch_bars(
    symbols: list[str],
    *,
    engine_url: str | None,
    csv_dir: str | None,
    days_back: int,
) -> dict[str, pd.DataFrame]:
    """Fetch bars for all symbols and return a symbol → DataFrame map.

    Any symbols that cannot be loaded are skipped with a warning.
    """

    bars: dict[str, pd.DataFrame] = {}
    _head("Pre-fetching bars …")

    for sym in symbols:
        df = load_bars(sym, engine_url=engine_url, csv_dir=csv_dir, days_back=days_back)
        if df is None or df.empty:
            _warn(f"No bars loaded for {sym} — symbol will be skipped in sweep")
            continue
        bars[sym] = df
        _ok(f"{sym}: {len(df):,} bars ({days_back}d of 1m data)")

    return bars


# ---------------------------------------------------------------------------
# Per-group aggregation
# ---------------------------------------------------------------------------


def _aggregate_group(
    group_symbols: list[str],
    sweep_results: list[SweepResult],
) -> list[dict[str, Any]]:
    """Average expectancy across group symbols for every bracket config.

    Returns a list of dicts (one per bracket combo) sorted by avg_expectancy
    descending.  Only symbols that actually produced trades are included in
    the average (missing symbols are skipped, not zero-filled).
    """
    # Group results by bracket key
    from collections import defaultdict

    bucket: dict[tuple, list[SweepResult]] = defaultdict(list)

    for r in sweep_results:
        if r.symbol in group_symbols and r.n_trades > 0:
            bucket[r.bracket_key()].append(r)

    aggregated: list[dict[str, Any]] = []
    for key, results in bucket.items():
        sl, tp1, tp2, tp3 = key

        # Only use results from symbols that had trades
        valid = [r for r in results if r.n_trades > 0]
        if not valid:
            continue

        avg_expectancy = sum(r.expectancy for r in valid) / len(valid)
        avg_win_rate = sum(r.win_rate for r in valid) / len(valid)
        avg_r = sum(r.avg_r for r in valid) / len(valid)
        total_trades = sum(r.n_trades for r in valid)
        total_wins = sum(r.n_wins for r in valid)
        symbols_used = [r.symbol for r in valid]

        aggregated.append(
            {
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "tp3": tp3,
                "avg_expectancy": round(avg_expectancy, 4),
                "avg_win_rate": round(avg_win_rate, 4),
                "avg_r": round(avg_r, 4),
                "total_trades": total_trades,
                "total_wins": total_wins,
                "symbols_used": symbols_used,
                "n_symbols": len(symbols_used),
            }
        )

    aggregated.sort(key=lambda d: d["avg_expectancy"], reverse=True)
    return aggregated


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

_SEP_WIDE = "═" * 70
_SEP_GROUP = "─" * 68


def _print_group_table(
    group_name: str,
    ranked: list[dict[str, Any]],
    top_n: int,
) -> None:
    """Print a ranked table of bracket configs for one asset group."""
    print(f"\n{BOLD}── {group_name} {_SEP_GROUP[: max(0, 65 - len(group_name))]}{RESET}")
    header = (
        f"  {'Rank':>4}  {'sl':>5}  {'tp1':>5}  {'tp2':>5}  {'tp3':>5}  "
        f"{'WinRate':>7}  {'AvgR':>6}  {'Expectancy':>10}  {'Trades':>7}"
    )
    print(f"{DIM}{header}{RESET}")
    print(
        f"{DIM}  {'─' * 4}  {'─' * 5}  {'─' * 5}  {'─' * 5}  {'─' * 5}  {'─' * 7}  {'─' * 6}  {'─' * 10}  {'─' * 7}{RESET}"
    )

    for rank, row in enumerate(ranked[:top_n], start=1):
        win_pct = f"{row['avg_win_rate'] * 100:.1f}%"
        color = GREEN if rank == 1 else (CYAN if rank <= 3 else RESET)
        line = (
            f"  {rank:>4}  "
            f"{row['sl']:>5.2f}  "
            f"{row['tp1']:>5.2f}  "
            f"{row['tp2']:>5.2f}  "
            f"{row['tp3']:>5.2f}  "
            f"{win_pct:>7}  "
            f"{row['avg_r']:>6.3f}  "
            f"{row['avg_expectancy']:>10.4f}  "
            f"{row['total_trades']:>7,}"
        )
        print(f"{color}{line}{RESET}")


def _print_summary(
    group_rankings: dict[str, list[dict[str, Any]]],
    top_n: int,
    update_config: bool,
) -> None:
    """Print the final summary table and (optionally) Python BracketConfig code."""
    print(f"\n{BOLD}{CYAN}{_SEP_WIDE}{RESET}")
    print(f"{BOLD}{CYAN}  Bracket Sweep Results — Best Config per Group{RESET}")
    print(f"{BOLD}{CYAN}{_SEP_WIDE}{RESET}")

    for group_name, ranked in group_rankings.items():
        _print_group_table(group_name, ranked, top_n)

    # Summary line: optimal config per group
    print(f"\n{BOLD}Optimal BracketConfig per group:{RESET}")
    max_name_len = max(len(g) for g in group_rankings)
    for group_name, ranked in group_rankings.items():
        if not ranked:
            _warn(f"  {group_name}: no results")
            continue
        best = ranked[0]
        pad = " " * (max_name_len - len(group_name))
        print(
            f"  {BOLD}{group_name}{RESET}{pad}  "
            f"sl={best['sl']:.2f}, tp1={best['tp1']:.2f}, "
            f"tp2={best['tp2']:.2f}, tp3={best['tp3']:.2f}  "
            f"{DIM}(expectancy={best['avg_expectancy']:.4f}, "
            f"{best['total_trades']:,} trades){RESET}"
        )

    if update_config:
        print(f"\n{BOLD}{MAGENTA}── Python BracketConfig code to copy into your config ────────────{RESET}")
        for group_name, ranked in group_rankings.items():
            if not ranked:
                continue
            best = ranked[0]
            code = textwrap.dedent(f"""\
                # {group_name} — best bracket (expectancy={best["avg_expectancy"]:.4f})
                {group_name.upper()}_BRACKET = BracketConfig(
                    sl_atr_mult  = {best["sl"]},
                    tp1_atr_mult = {best["tp1"]},
                    tp2_atr_mult = {best["tp2"]},
                    tp3_atr_mult = {best["tp3"]},
                )
            """)
            print(f"{MAGENTA}{code}{RESET}")


# ---------------------------------------------------------------------------
# Main sweep orchestration
# ---------------------------------------------------------------------------


def run_sweep(
    symbols: list[str],
    bars_map: dict[str, pd.DataFrame],
    *,
    breakout_type: str = "orb",
    jobs: int = DEFAULT_JOBS,
) -> list[SweepResult]:
    """Run the full parameter sweep over all (symbol, bracket_config) pairs.

    Uses ProcessPoolExecutor to parallelise across *jobs* workers.  The bars
    DataFrames are pickled once per symbol and reused for every bracket combo,
    avoiding repeated network or I/O calls from worker processes.

    Args:
        symbols:       Symbols to sweep (already loaded into bars_map).
        bars_map:      symbol → 1-minute bars DataFrame.
        breakout_type: "orb" (ORB only) or "all" (all 13 breakout types).
        jobs:          Number of parallel worker processes.

    Returns:
        Flat list of SweepResult, one per (symbol, bracket_config) pair.
    """
    import pickle

    # Pre-pickle all bars once (saves repeated serialisation overhead)
    bars_pkl_map: dict[str, bytes] = {sym: pickle.dumps(df) for sym, df in bars_map.items()}

    valid_symbols = [s for s in symbols if s in bars_pkl_map]
    if not valid_symbols:
        _fail("No symbols with bar data — aborting sweep")
        return []

    n_combos = len(PARAM_GRID)
    n_symbols = len(valid_symbols)
    total = n_combos * n_symbols

    _head(f"Running sweep: {n_symbols} symbols × {n_combos} bracket combos = {total:,} evaluations")
    _info(f"Parallel workers: {jobs}  |  breakout type: {breakout_type}")

    # Build the full task list
    tasks: list[tuple[str, float, float, float, float, bytes, str]] = []
    for sym in valid_symbols:
        pkl = bars_pkl_map[sym]
        for sl, tp1, tp2, tp3 in PARAM_GRID:
            tasks.append((sym, sl, tp1, tp2, tp3, pkl, breakout_type))

    results: list[SweepResult] = []
    completed = 0
    t0 = time.monotonic()

    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as executor:
        future_map = {executor.submit(_evaluate_one, *task): task for task in tasks}

        for future in concurrent.futures.as_completed(future_map):
            completed += 1
            task = future_map[future]
            sym, sl, tp1, tp2, tp3 = task[0], task[1], task[2], task[3], task[4]

            try:
                res = future.result()
            except Exception as exc:
                res = SweepResult(
                    symbol=sym,
                    sl=sl,
                    tp1=tp1,
                    tp2=tp2,
                    tp3=tp3,
                    error=str(exc),
                )

            results.append(res)

            # Progress update every 10 completions or on the last one
            if completed % 10 == 0 or completed == total:
                elapsed = time.monotonic() - t0
                rate = completed / elapsed if elapsed > 0 else 0.0
                eta = (total - completed) / rate if rate > 0 else 0.0
                pct = completed / total * 100
                bar_len = 30
                filled = int(bar_len * completed / total)
                bar = "█" * filled + "░" * (bar_len - filled)
                print(
                    f"\r{DIM}  [{bar}] {pct:5.1f}%  "
                    f"{completed:>{len(str(total))}}/{total}  "
                    f"~{eta:.0f}s remaining{RESET}",
                    end="",
                    flush=True,
                )

    print()  # newline after progress bar

    elapsed_total = time.monotonic() - t0
    _ok(
        f"Sweep complete: {len(results):,} evaluations in {elapsed_total:.1f}s "
        f"({elapsed_total / len(results) * 1000:.1f}ms each)"
    )

    return results


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def save_results(
    output_path: str,
    sweep_results: list[SweepResult],
    group_rankings: dict[str, list[dict[str, Any]]],
    args_dict: dict[str, Any],
) -> None:
    """Persist full sweep results and per-group rankings to a JSON file."""
    optimal: dict[str, dict[str, Any]] = {}
    for group_name, ranked in group_rankings.items():
        if ranked:
            best = ranked[0]
            optimal[group_name] = {
                "sl": best["sl"],
                "tp1": best["tp1"],
                "tp2": best["tp2"],
                "tp3": best["tp3"],
                "avg_expectancy": best["avg_expectancy"],
                "avg_win_rate": best["avg_win_rate"],
                "total_trades": best["total_trades"],
            }

    payload = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "total_evaluations": len(sweep_results),
            "args": args_dict,
        },
        "optimal_brackets": optimal,
        "group_rankings": {g: ranked for g, ranked in group_rankings.items()},
        "raw_results": [r.to_dict() for r in sweep_results],
    }

    try:
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        _ok(f"Results saved → {output_path}")
    except Exception as exc:
        _warn(f"Could not save results to {output_path}: {exc}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bracket_sweep.py",
        description="RETRAIN-I2: TP/SL Optimization per Asset Group via parameter sweep",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              # Full sweep (144 combos × all symbols) against local engine:
              python scripts/bracket_sweep.py

              # Pre-fetched CSVs, metals group only, 8 parallel workers:
              python scripts/bracket_sweep.py --csv-dir data/bars --group metals --jobs 8

              # Remote engine, print Python BracketConfig after sweep:
              python scripts/bracket_sweep.py --engine-url http://oryx:8050 --update-config

              # Sweep all 13 breakout types:
              python scripts/bracket_sweep.py --breakout-type all

              # Override symbols, show top 10 configs:
              python scripts/bracket_sweep.py --symbols MGC,MES --top-n 10
        """),
    )

    # Bar source
    src = p.add_mutually_exclusive_group()
    src.add_argument(
        "--engine-url",
        default=DEFAULT_ENGINE_URL,
        metavar="URL",
        help=f"Base URL of the engine/data service (default: {DEFAULT_ENGINE_URL})",
    )
    src.add_argument(
        "--csv-dir",
        metavar="DIR",
        help="Directory containing pre-fetched CSV bar files ({DIR}/{SYMBOL}_1m.csv)",
    )

    p.add_argument(
        "--days-back",
        type=int,
        default=DEFAULT_DAYS_BACK,
        metavar="N",
        help=f"Days of 1-minute bar history to use (default: {DEFAULT_DAYS_BACK})",
    )

    # Symbol / group selection
    scope = p.add_mutually_exclusive_group()
    scope.add_argument(
        "--group",
        choices=list(ASSET_GROUPS.keys()),
        metavar="GROUP",
        help="Run only one asset group (metals|equity_micros)",
    )
    scope.add_argument(
        "--symbols",
        metavar="SYM1,SYM2,…",
        help="Comma-separated list of symbols (overrides --group)",
    )

    # Output
    p.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        metavar="FILE",
        help=f"Output JSON file path (default: {DEFAULT_OUTPUT})",
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        metavar="N",
        help=f"Show top N configs in per-group summary (default: {DEFAULT_TOP_N})",
    )

    # Sweep options
    p.add_argument(
        "--breakout-type",
        choices=["orb", "all"],
        default="orb",
        metavar="TYPE",
        help="Breakout types to simulate: orb (ORB only) or all (all 13 types, default: orb)",
    )
    p.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_JOBS,
        metavar="N",
        help=f"Parallel worker processes for the sweep (default: {DEFAULT_JOBS})",
    )

    # Flags
    p.add_argument(
        "--update-config",
        action="store_true",
        help="Print optimal BracketConfig per group as copy-paste Python code",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the sweep plan without running any simulations",
    )

    return p


# ---------------------------------------------------------------------------
# Dry-run plan display
# ---------------------------------------------------------------------------


def _print_dry_run_plan(
    symbols: list[str],
    groups: dict[str, list[str]],
    days_back: int,
    jobs: int,
    breakout_type: str,
    engine_url: str | None,
    csv_dir: str | None,
) -> None:
    """Print what the sweep would do without actually running it."""
    n_combos = len(PARAM_GRID)
    n_symbols = len(symbols)
    total = n_combos * n_symbols
    n_runners = len(_ALL_BATCH_RUNNERS) if breakout_type == "all" else 1

    print(f"\n{BOLD}{YELLOW}── Dry Run — Sweep Plan ─────────────────────────────────────────{RESET}")
    _info(f"Symbols ({n_symbols}):       {', '.join(symbols)}")
    _info("Asset groups:")
    for g, syms in groups.items():
        members = ", ".join(syms)
        _info(f"  {g:<18} {members}")
    _info(f"Days of history:    {days_back}d")
    _info(
        f"Bar source:         {'CSV dir: ' + csv_dir if csv_dir else 'Engine: ' + (engine_url or DEFAULT_ENGINE_URL)}"
    )
    _info(f"Breakout type(s):   {breakout_type}  ({n_runners} runner{'s' if n_runners > 1 else ''})")
    _info(f"Parallel workers:   {jobs}")
    _info("")
    _info(f"Parameter grid ({n_combos} combos):")
    _info(f"  sl_atr_mult:  {SL_ATR_MULTS}")
    _info(f"  tp1_atr_mult: {TP1_ATR_MULTS}")
    _info(f"  tp2_atr_mult: {TP2_ATR_MULTS}")
    _info(f"  tp3_atr_mult: {TP3_ATR_MULTS}")
    _info(
        f"  Total combos: {len(SL_ATR_MULTS)} × {len(TP1_ATR_MULTS)} × {len(TP2_ATR_MULTS)} × {len(TP3_ATR_MULTS)} = {n_combos}"
    )
    _info("")
    _info(f"Total evaluations:  {n_symbols} symbols × {n_combos} combos = {total:,}")
    _info("  (Each evaluation runs simulate_batch on ~90 days of 1m data)")
    est_secs = total * 0.05 / max(1, jobs)  # rough estimate
    _info(f"  Estimated wall-time (rough): ~{est_secs:.0f}s with {jobs} workers")
    print(f"\n{YELLOW}  Use without --dry-run to execute.{RESET}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    # Resolve symbols and groups
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        # Build a synthetic group map for aggregation
        groups: dict[str, list[str]] = {"custom": symbols}
    elif args.group:
        groups = {args.group: ASSET_GROUPS[args.group]}
        symbols = ASSET_GROUPS[args.group]
    else:
        groups = ASSET_GROUPS
        symbols = ALL_SYMBOLS

    engine_url: str | None = None if args.csv_dir else args.engine_url
    csv_dir: str | None = args.csv_dir

    # --- Banner ---
    print(f"\n{BOLD}{CYAN}{_SEP_WIDE}{RESET}")
    print(f"{BOLD}{CYAN}  bracket_sweep.py — RETRAIN-I2: TP/SL Optimization{RESET}")
    print(f"{BOLD}{CYAN}{_SEP_WIDE}{RESET}")
    _info(f"Symbols:       {', '.join(symbols)}")
    _info(f"Groups:        {', '.join(groups.keys())}")
    _info(f"Bar source:    {'CSV: ' + csv_dir if csv_dir else 'Engine: ' + (engine_url or DEFAULT_ENGINE_URL)}")
    _info(f"Days back:     {args.days_back}")
    _info(f"Breakout type: {args.breakout_type}")
    _info(f"Grid size:     {len(PARAM_GRID)} combos")
    _info(f"Parallel jobs: {args.jobs}")
    _info(f"Output:        {args.output}")

    # --- Dry run ---
    if args.dry_run:
        _print_dry_run_plan(
            symbols=symbols,
            groups=groups,
            days_back=args.days_back,
            jobs=args.jobs,
            breakout_type=args.breakout_type,
            engine_url=engine_url,
            csv_dir=csv_dir,
        )
        return 0

    # --- Pre-fetch bars ---
    bars_map = prefetch_bars(
        symbols,
        engine_url=engine_url,
        csv_dir=csv_dir,
        days_back=args.days_back,
    )

    if not bars_map:
        _fail("No bar data could be loaded for any symbol — aborting.")
        return 1

    # Restrict to symbols that actually loaded
    available_symbols = list(bars_map.keys())
    _info(f"{len(available_symbols)}/{len(symbols)} symbols loaded successfully")

    # Rebuild groups to only include available symbols
    active_groups: dict[str, list[str]] = {g: [s for s in syms if s in bars_map] for g, syms in groups.items()}
    active_groups = {g: syms for g, syms in active_groups.items() if syms}

    if not active_groups:
        _fail("No groups have loadable symbols — aborting.")
        return 1

    # --- Run sweep ---
    sweep_results = run_sweep(
        symbols=available_symbols,
        bars_map=bars_map,
        breakout_type=args.breakout_type,
        jobs=args.jobs,
    )

    if not sweep_results:
        _fail("Sweep produced no results — aborting.")
        return 1

    # Diagnostics: how many evaluations had errors / no trades?
    n_errors = sum(1 for r in sweep_results if r.error)
    n_no_trades = sum(1 for r in sweep_results if r.n_trades == 0 and not r.error)
    n_ok = len(sweep_results) - n_errors - n_no_trades
    _dim(
        f"Results: {n_ok} with trades, {n_no_trades} no-trades, {n_errors} errors (out of {len(sweep_results):,} total)"
    )

    # --- Per-group aggregation ---
    _head("Aggregating results per group …")
    group_rankings: dict[str, list[dict[str, Any]]] = {}
    for group_name, group_symbols in active_groups.items():
        ranked = _aggregate_group(group_symbols, sweep_results)
        group_rankings[group_name] = ranked
        if ranked:
            best = ranked[0]
            _ok(
                f"{group_name}: best config sl={best['sl']}, tp1={best['tp1']}, "
                f"tp2={best['tp2']}, tp3={best['tp3']}  "
                f"→ expectancy={best['avg_expectancy']:.4f} "
                f"({best['total_trades']:,} trades)"
            )
        else:
            _warn(f"{group_name}: no ranked results (all symbols returned no trades?)")

    # --- Print summary table ---
    _print_summary(group_rankings, top_n=args.top_n, update_config=args.update_config)

    # --- Save JSON ---
    args_dict = {
        "engine_url": engine_url,
        "csv_dir": csv_dir,
        "days_back": args.days_back,
        "symbols": available_symbols,
        "groups": {g: syms for g, syms in active_groups.items()},
        "breakout_type": args.breakout_type,
        "jobs": args.jobs,
        "top_n": args.top_n,
    }
    save_results(args.output, sweep_results, group_rankings, args_dict)

    return 0


if __name__ == "__main__":
    sys.exit(main())
