"""
utils/optimizer.py
===================
Optuna-based EMA parameter optimizer.

Extracted from main.py so it can be:
  - Called from AssetWorker._maybe_optimize() (unchanged)
  - Triggered from the web task runner for manual / scheduled runs
  - Unit-tested independently

All functions are synchronous and CPU-bound — they are always dispatched
to a thread pool by the caller.  A module-level ThreadPoolExecutor is
provided for convenience but callers may supply their own executor.

Fee model
---------
``fee_per_trade`` should be the *one-way* cost for a single fill:

    taker-only (use_post_only_entries=false):
        fee_per_trade = taker_pct + slippage_pct          (e.g. 0.0007)

    maker entry / taker exit (use_post_only_entries=true):
        fee_per_trade = (maker_pct + taker_pct) / 2 + slippage_pct  (e.g. 0.0005)

The round-trip cost varies by transition type:
    0 ↔ ±1  (open or close)  →  1 × fee_per_trade
    +1 ↔ −1 (flip)           →  2 × fee_per_trade  (close + reopen)

The task runner (services/task_runner.py) is responsible for computing
the correct fee_per_trade before calling these functions.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import NamedTuple

import optuna
import pandas as pd

from utils.indicators import build_candles

# Suppress Optuna's verbose per-trial logging; summary is logged by callers.
optuna.logging.set_verbosity(optuna.logging.WARNING)

# Shared thread pool for blocking Optuna work across all workers.
# max_workers=2 keeps CPU pressure low enough not to starve the event loop.
OPTUNA_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="optuna")

# Minimum candle rows required before running optimisation.
_MIN_CANDLES_SIMPLE = 100
_MIN_CANDLES_PIPELINE = 150


# ═══════════════════════════════════════════════════════════════════
# Internal strategy kernel
# ═══════════════════════════════════════════════════════════════════


class _PrecomputedBase(NamedTuple):
    """Columns that are invariant across trials, computed once per run."""

    close: pd.Series
    returns: pd.Series  # close.pct_change()
    ao: pd.Series  # SMA(hl2, ao_fast) − SMA(hl2, ao_slow)


def _precompute(df: pd.DataFrame, ao_fast: int, ao_slow: int) -> _PrecomputedBase:
    """Compute trial-invariant columns once so trials work on cheap arrays.

    Args:
        df:      OHLCV candles DataFrame with a ``hl2`` column.
        ao_fast: Awesome Oscillator fast period.
        ao_slow: Awesome Oscillator slow period.

    Returns:
        _PrecomputedBase namedtuple.

    Raises:
        KeyError: if ``df`` is missing required columns (``close`` or ``hl2``).
    """
    if "hl2" not in df.columns:
        raise KeyError(
            "'hl2' column missing from candles DataFrame. "
            "Ensure build_candles() computes hl2 = (high + low) / 2."
        )
    ao = df["hl2"].rolling(ao_fast).mean() - df["hl2"].rolling(ao_slow).mean()
    return _PrecomputedBase(
        close=df["close"],
        returns=df["close"].pct_change(),
        ao=ao,
    )


def _run_strategy(
    base: _PrecomputedBase,
    fast: int,
    slow: int,
    fee_per_trade: float,
) -> float:
    """Evaluate EMA crossover + AO filter and return net P&L after fees.

    This is the single canonical implementation shared by the Optuna objective
    and hold-out validation, so changing the logic here affects both paths.

    Fee accounting (per transition):
        open / close  (0 ↔ ±1):  1 × fee_per_trade
        flip          (+1 ↔ −1):  2 × fee_per_trade  (close old + open new)

    Args:
        base:          Pre-computed trial-invariant arrays.
        fast:          Fast EMA period (trial-sampled).
        slow:          Slow EMA period (trial-sampled).
        fee_per_trade: One-way cost per fill (taker or blended maker/taker).

    Returns:
        Net P&L float.  Returns ``-999.0`` if all signals are flat / zero to
        prevent Optuna from treating no-trade solutions as valid optima.
    """
    close = base.close

    fast_ema = close.ewm(span=fast, adjust=False).mean()
    slow_ema = close.ewm(span=slow, adjust=False).mean()

    signal = pd.Series(0, index=close.index, dtype=int)
    signal[fast_ema > slow_ema] = 1
    signal[fast_ema < slow_ema] = -1

    # AO gate — zero out signals where AO disagrees with EMA bias
    ao_disagrees = ((signal == 1) & (base.ao <= 0)) | ((signal == -1) & (base.ao >= 0))
    signal[ao_disagrees] = 0

    if signal.abs().sum() == 0:
        return -999.0

    # P&L: previous bar's signal × this bar's return
    pnl = (signal.shift(1) * base.returns).sum()

    # --- Accurate fee accounting -----------------------------------------
    prev_sig = signal.shift(1).fillna(0).astype(int)
    curr_sig = signal.astype(int)

    # Flip: long↔short — costs 2 fills (close + open in the other direction)
    flips = ((prev_sig == 1) & (curr_sig == -1)) | ((prev_sig == -1) & (curr_sig == 1))
    # Simple open or close — costs 1 fill
    opens_closes = (~flips) & (prev_sig != curr_sig)

    fee_cost = (int(flips.sum()) * 2 + int(opens_closes.sum())) * fee_per_trade
    # ---------------------------------------------------------------------

    net = float(pnl) - fee_cost
    return net if net != 0.0 else -999.0


# ═══════════════════════════════════════════════════════════════════
# Objective factory
# ═══════════════════════════════════════════════════════════════════


def make_objective(
    df_base: pd.DataFrame,
    ao_fast: int,
    ao_slow: int,
    search_space: dict,
    fee_per_trade: float = 0.0005,
):
    """Return a closure suitable for ``study.optimize``.

    Design notes:
      - Expensive trial-invariant columns (returns, AO) are pre-computed ONCE
        and captured by the closure.  Each of the N trials only computes the
        two EMA series — removing the per-trial DataFrame.copy() that
        previously made 70 full-frame copies per optimisation run.
      - Fee model distinguishes open/close (1 fill) from flips (2 fills) so
        the objective accurately reflects actual trading costs.
      - Only fast/slow EMA periods are sampled.  Other params were removed
        because they had no causal effect in the vectorised backtest.

    Args:
        df_base:       Pre-built OHLCV candles DataFrame (with ``hl2`` col).
        ao_fast:       Fast period for the Awesome Oscillator filter.
        ao_slow:       Slow period for the Awesome Oscillator filter.
        search_space:  Dict with keys "fast" and "slow", each a dict with
                       "min" and "max" bounds.
        fee_per_trade: One-way cost per fill — see module docstring for how
                       to derive this from futures.yaml fee config.

    Returns:
        Callable ``(optuna.Trial) → float``.

    Raises:
        KeyError: if ``df_base`` is missing ``hl2``.
    """
    # Pre-compute once; closure captures the NamedTuple (no DataFrame copies).
    base = _precompute(df_base, ao_fast, ao_slow)
    ss = search_space

    def objective(trial: optuna.Trial) -> float:
        fast_range = ss.get("fast", {})
        slow_range = ss.get("slow", {})

        fast = trial.suggest_int(
            "fast",
            int(fast_range.get("min", 5)),
            int(fast_range.get("max", 15)),
        )
        slow = trial.suggest_int(
            "slow",
            int(slow_range.get("min", 18)),
            int(slow_range.get("max", 35)),
        )

        return _run_strategy(base, fast, slow, fee_per_trade)

    return objective


# ═══════════════════════════════════════════════════════════════════
# Blocking runner (called from thread pool)
# ═══════════════════════════════════════════════════════════════════


def run_optuna_sync(
    trades_snapshot: list,
    min_ticks: int,
    ao_fast: int,
    ao_slow: int,
    search_space: dict,
    n_trials: int,
    timeout_sec: int,
    fee_per_trade: float = 0.0005,
) -> dict | None:
    """Blocking Optuna run — call via a thread pool from async code.

    Receives a pre-copied list snapshot instead of the live deque,
    eliminating the race condition with the async WS tick appender.

    Builds candles ONCE and pre-computes trial-invariant columns before
    launching Optuna, so each of the N trials only computes two EMA series.

    Args:
        trades_snapshot: Plain list copy of the worker's tick deque.
        min_ticks:       Minimum ticks for build_candles(); skips if too few.
        ao_fast:         Awesome Oscillator fast period.
        ao_slow:         Awesome Oscillator slow period.
        search_space:    Dict with "fast" and "slow" bound dicts.
        n_trials:        Number of Optuna trials to run.
        timeout_sec:     Hard timeout for the optimisation run.
        fee_per_trade:   One-way cost per fill (see module docstring).

    Returns:
        Dict of best params ``{"fast": int, "slow": int}``, or ``None`` when
        there are not enough candles or all trials failed.
    """
    df_base = build_candles(trades_snapshot, min_ticks)
    if len(df_base) < _MIN_CANDLES_SIMPLE:
        return None

    objective = make_objective(df_base, ao_fast, ao_slow, search_space, fee_per_trade)
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, timeout=timeout_sec)

    # Guard: best_params raises ValueError if no trials completed successfully.
    completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if not completed:
        return None

    return study.best_params


# ═══════════════════════════════════════════════════════════════════
# Full-pipeline optimiser (used by the web task runner)
# ═══════════════════════════════════════════════════════════════════


def run_full_pipeline_sync(
    trades_snapshot: list,
    min_ticks: int,
    ao_fast: int,
    ao_slow: int,
    search_space: dict,
    n_trials: int,
    timeout_sec: int,
    fee_per_trade: float = 0.0005,
    n_startup_trials: int = 10,
    sampler: str = "tpe",
    min_holdout_pnl: float | None = None,
) -> dict:
    """Extended optimisation pipeline with train/hold-out split and diagnostics.

    Runs the same objective as run_optuna_sync() and additionally:
      - Performs an 80/20 train/hold-out split
      - Validates best params on the hold-out slice using the same strategy
        kernel as the objective (no silent drift)
      - Optionally rejects params if hold-out P&L falls below
        ``min_holdout_pnl`` (overfit guard)
      - Returns full diagnostics: best value, completed trials, param
        importance, and the hold-out result

    Args:
        trades_snapshot:  Plain list copy of tick deque.
        min_ticks:        Minimum ticks required.
        ao_fast:          AO fast period.
        ao_slow:          AO slow period.
        search_space:     Param bounds dict.
        n_trials:         Max trials.
        timeout_sec:      Hard time limit.
        fee_per_trade:    One-way cost per fill (see module docstring).
        n_startup_trials: Random exploration trials before TPE kicks in.
        sampler:          "tpe" (default) or "random".
        min_holdout_pnl:  If set, params are flagged as overfit when
                          hold-out P&L < this value.  The result dict will
                          include ``"overfit": True`` so callers can decide
                          whether to apply the params.  Pass
                          ``-fee_per_trade * 2`` to use a fee-aware floor.

    Returns:
        Dict with keys: best_params, best_value, n_trials_completed,
        hold_out_pnl, overfit (bool), diagnostics.
        Returns ``{"error": reason}`` when there is insufficient data or all
        trials failed.
    """
    df_base = build_candles(trades_snapshot, min_ticks)
    if len(df_base) < _MIN_CANDLES_PIPELINE:
        return {"error": f"Insufficient candles: {len(df_base)} < {_MIN_CANDLES_PIPELINE}"}

    # Split: first 80% for optimisation, last 20% for hold-out validation.
    split_idx = int(len(df_base) * 0.8)
    df_train = df_base.iloc[:split_idx].reset_index(drop=True)
    df_holdout = df_base.iloc[split_idx:].reset_index(drop=True)

    if len(df_train) < _MIN_CANDLES_SIMPLE:
        return {"error": "Training split too small after 80/20 split"}

    # Choose sampler.
    if sampler == "random":
        _sampler = optuna.samplers.RandomSampler()
    else:
        _sampler = optuna.samplers.TPESampler(n_startup_trials=n_startup_trials)

    objective = make_objective(df_train, ao_fast, ao_slow, search_space, fee_per_trade)
    study = optuna.create_study(direction="maximize", sampler=_sampler)
    study.optimize(objective, n_trials=n_trials, timeout=timeout_sec)

    completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if not completed:
        return {"error": "All Optuna trials failed — check candle data and hl2 column"}

    best = study.best_params
    best_value = study.best_value
    n_completed = len(completed)

    # Hold-out validation — uses the same _run_strategy kernel, so logic
    # stays in sync with the objective automatically.
    holdout_base = _precompute(df_holdout, ao_fast, ao_slow)
    hold_out_pnl = _run_strategy(
        holdout_base,
        fast=int(best.get("fast", 8)),
        slow=int(best.get("slow", 21)),
        fee_per_trade=fee_per_trade,
    )

    # Overfit guard: flag if hold-out PnL falls below caller-supplied floor.
    overfit = False
    if min_holdout_pnl is not None and hold_out_pnl < min_holdout_pnl:
        overfit = True

    # Param importance (graceful fallback — requires ≥ 2 completed trials).
    importance: dict[str, float] = {}
    try:
        if n_completed >= 2:
            importance = optuna.importance.get_param_importances(study)
    except Exception:
        pass

    return {
        "best_params": best,
        "best_value": round(best_value, 6),
        "n_trials_completed": n_completed,
        "hold_out_pnl": round(float(hold_out_pnl), 6),
        "overfit": overfit,
        "diagnostics": {
            "train_bars": len(df_train),
            "holdout_bars": len(df_holdout),
            "param_importance": importance,
            "sampler": sampler,
            "fee_per_trade": fee_per_trade,
        },
    }
