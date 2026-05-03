"""
src/ml/optimize_labels.py — Label parameter search for PerAssetCNN training.

Standalone (200 trials, full diagnostics):
    python -m ml.optimize_labels
    python -m ml.optimize_labels --assets btc eth --trials 100

Importable API (called from train.py with --optimize-labels):
    from ml.optimize_labels import optimize_label_params
    params = optimize_label_params(asset_key, df, n_trials=50)

What this does
--------------
1. Data verification   — gaps, OHLCV sanity, staleness, cache provenance
2. Train/val split     — chronological 80/20; Optuna sees only train split
3. Regime detection    — HMM (3 states) or ATR-percentile fallback
4. Label generation    — generate_labels_breakout with candidate params
5. Empirical check     — walk-forward spot-verification that labels are correct
6. Scoring             — expectancy * balance * regime-consistency - frequency penalty
7. Result caching      — writes models/label_params_{asset}.json; warm-started on reuse
                         Cache is invalidated when the TTL expires OR a regime shift
                         is detected (via _regime_fingerprint), whichever comes first.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import optuna
import pandas as pd
from dotenv import load_dotenv

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent  # project root
_SRC = Path(__file__).resolve().parent.parent  # src/
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

load_dotenv(_ROOT / ".env")

from ml.kline_cache import KlineCache
from ml.labeler import fetch_klines, generate_labels_breakout

# ── Optional HMM ─────────────────────────────────────────────────────────────
try:
    from hmmlearn.hmm import GaussianHMM

    _HMM_AVAILABLE = True
except ImportError:
    _HMM_AVAILABLE = False

optuna.logging.set_verbosity(optuna.logging.WARNING)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("optimize_labels")

# ── Asset map ─────────────────────────────────────────────────────────────────
SYMBOLS: dict[str, str] = {
    "btc": "XBTUSDTM",
    "eth": "ETHUSDTM",
    "sol": "SOLUSDTM",
    "doge": "DOGEUSDTM",
    "pepe": "PEPEUSDTM",
    "avax": "AVAXUSDTM",
    "sui": "SUIUSDTM",
    "wif": "WIFUSDTM",
    "fart": "FARTCOINUSDTM",
    "gold": "XAUTUSDTM",
}

DEFAULT_ASSETS = list(SYMBOLS.keys())

# ── Param cache TTL ──────────────────────────────────────────────────────────
# Shortened from 7 to 3 days so that volatile assets (meme coins) don't hold
# stale params for too long.  The regime fingerprint (below) provides an
# additional early-invalidation signal independent of wall-clock age.
_CACHE_TTL_DAYS = 3
_MODELS_DIR = _ROOT / "models"

# ── Search bounds ─────────────────────────────────────────────────────────────
SEARCH_SPACE = {
    "consolidation_atr_mult": (3.5, 8.0),
    "consolidation_bars": (15, 30),
    "tp_atr_mult": (1.5, 3.0),
    "sl_atr_mult": (0.5, 1.5),
    "max_breakout_wait": (20, 60),
    "max_hold_bars": (60, 180),
}

# ═══════════════════════════════════════════════════════════════════════════
# 1.  DATA VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class DataReport:
    symbol: str
    n_bars: int
    from_cache: bool
    gap_count: int
    max_gap_min: float
    stale_min: float  # minutes since last bar
    ohlcv_errors: int
    ok: bool
    warnings: list[str] = field(default_factory=list)

    def print(self) -> None:
        tag = "✓" if self.ok else "✗"
        src = "cache" if self.from_cache else "exchange"
        print(
            f"  [{tag}] {self.symbol:<16} {self.n_bars:>6} bars  "
            f"src={src}  gaps={self.gap_count}  "
            f"max_gap={self.max_gap_min:.0f}m  "
            f"stale={self.stale_min:.0f}m  "
            f"ohlcv_errors={self.ohlcv_errors}"
        )
        for w in self.warnings:
            print(f"       ⚠  {w}")


def verify_data_quality(
    df: pd.DataFrame, symbol: str, from_cache: bool = True, timeframe_min: int = 1
) -> DataReport:
    """
    Validate a klines DataFrame:
      - timestamp monotonicity and gap detection
      - OHLCV sanity (high >= low, positive prices, etc.)
      - Staleness relative to now
    """
    report = DataReport(
        symbol=symbol,
        n_bars=len(df),
        from_cache=from_cache,
        gap_count=0,
        max_gap_min=0.0,
        stale_min=0.0,
        ohlcv_errors=0,
        ok=True,
    )

    if df.empty or len(df) < 500:
        report.ok = False
        report.warnings.append(f"Too few bars: {len(df)}")
        return report

    # Timestamp gaps ──────────────────────────────────────────────────────
    if "timestamp" in df.columns:
        ts = df["timestamp"].astype(np.int64).values
        diffs_min = np.diff(ts) / 60_000.0  # ms → minutes
        expected = float(timeframe_min)
        gaps = diffs_min[diffs_min > expected * 3]  # 3× expected = gap
        report.gap_count = int(len(gaps))
        report.max_gap_min = float(gaps.max()) if len(gaps) else 0.0
        report.stale_min = (time.time() * 1000 - float(ts[-1])) / 60_000.0

        if report.gap_count > 50:
            report.warnings.append(f"{report.gap_count} timestamp gaps > {expected * 3:.0f}m")
        if report.stale_min > 120:
            report.warnings.append(f"Data stale by {report.stale_min:.0f} minutes")
            report.ok = False

    # OHLCV sanity ────────────────────────────────────────────────────────
    errs = 0
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            v = df[col].astype(float)
            errs += int((v <= 0).sum())

    if "high" in df.columns and "low" in df.columns:
        hi = df["high"].astype(float)
        lo = df["low"].astype(float)
        errs += int((hi < lo).sum())

    if "open" in df.columns and "high" in df.columns and "close" in df.columns:
        op = df["open"].astype(float)
        hi = df["high"].astype(float)
        cl = df["close"].astype(float)
        errs += int((hi < op).sum() + (hi < cl).sum())

    report.ohlcv_errors = errs
    if errs > 10:
        report.warnings.append(f"{errs} OHLCV sanity errors (negative/inverted prices)")
        report.ok = False

    return report


# ═══════════════════════════════════════════════════════════════════════════
# 2.  REGIME DETECTION
# ═══════════════════════════════════════════════════════════════════════════


def _regime_fingerprint(df: pd.DataFrame) -> str:
    """
    Coarse volatility fingerprint of the most recent 7 days of data.

    Bucketed into 5 levels (0 = very calm … 4 = extremely volatile) so that
    small daily fluctuations don't bust the cache, but a real regime shift
    (e.g. going from low-volatility chop to a meme-coin spike) forces
    re-optimisation even within the TTL window.

    The fingerprint is stored alongside cached label params and re-computed on
    every cache-load attempt.  A mismatch invalidates the cache immediately,
    regardless of age.
    """
    cl = df["close"].astype(np.float64).values
    hi = df["high"].astype(np.float64).values
    lo = df["low"].astype(np.float64).values
    prev_cl = np.roll(cl, 1)
    prev_cl[0] = cl[0]
    tr = np.maximum(hi - lo, np.maximum(np.abs(hi - prev_cl), np.abs(lo - prev_cl)))
    atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values
    # Look back ~7 days of 1-minute bars (10 080 bars); fewer is fine
    tail = min(10_080, len(atr))
    recent_atr_pct = atr[-tail:] / (cl[-tail:] + 1e-10)
    median_atr_pct = float(np.median(recent_atr_pct))
    # Five buckets — adjust thresholds if you add non-crypto assets
    thresholds = [0.002, 0.004, 0.008, 0.015]
    level = sum(median_atr_pct > t for t in thresholds)
    return str(level)


def detect_regimes(df: pd.DataFrame, n_states: int = 3) -> np.ndarray:
    """
    Return a regime label array of shape (len(df),) with values 0..n_states-1.

    Tries GaussianHMM first; falls back to ATR-percentile bucketing if
    hmmlearn is not installed or fitting fails.

    Regime features: log_return, atr_pct, volume_ratio — all rolling-normalised
    so the HMM is not confused by asset-specific price levels.
    """
    cl = df["close"].astype(np.float64).values
    hi = df["high"].astype(np.float64).values
    lo = df["low"].astype(np.float64).values
    vo = df["volume"].astype(np.float64).values

    n = len(cl)
    log_ret = np.zeros(n)
    log_ret[1:] = np.log(cl[1:] / (cl[:-1] + 1e-10))

    # ATR (EWM-14)
    prev_cl = np.roll(cl, 1)
    prev_cl[0] = cl[0]
    tr = np.maximum(hi - lo, np.maximum(np.abs(hi - prev_cl), np.abs(lo - prev_cl)))
    atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values
    atr_pct = atr / (cl + 1e-10)

    # Volume ratio (20-bar mean)
    vol_mean = pd.Series(vo).rolling(20, min_periods=1).mean().values
    vol_ratio = vo / (vol_mean + 1e-10)

    # Clip and stack features
    X = np.column_stack(
        [
            np.clip(log_ret, -0.05, 0.05),
            np.clip(atr_pct, 0.0, 0.05),
            np.clip(vol_ratio, 0.0, 5.0),
        ]
    )
    X = np.nan_to_num(X, nan=0.0)

    # ── HMM path ─────────────────────────────────────────────────────────
    if _HMM_AVAILABLE:
        try:
            model = GaussianHMM(
                n_components=n_states,
                covariance_type="diag",
                n_iter=100,
                random_state=42,
            )
            model.fit(X)
            return model.predict(X).astype(np.int32)
        except Exception as exc:
            logger.debug("HMM fitting failed (%s) — using ATR fallback", exc)

    # ── ATR-percentile fallback ────────────────────────────────────────
    pctiles = np.percentile(atr_pct[atr_pct > 0], [33, 67])
    regimes = np.zeros(n, dtype=np.int32)
    regimes[atr_pct > pctiles[0]] = 1
    regimes[atr_pct > pctiles[1]] = 2
    return regimes


# ═══════════════════════════════════════════════════════════════════════════
# 3.  EMPIRICAL LABEL VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class LabelVerification:
    n_checked: int
    long_correct_pct: float  # % of LONG labels where price actually hit TP
    short_correct_pct: float
    loss_correct_pct: float  # % of LOSS labels where price actually hit SL
    overall_accuracy: float


def verify_labels_empirical(
    df: pd.DataFrame,
    labels: np.ndarray,
    tp_atr_mult: float,
    sl_atr_mult: float,
    n_sample: int = 300,
    rng_seed: int = 0,
) -> LabelVerification:
    """
    Spot-check that label assignments are correct by walking forward from
    a random sample of labelled bars and verifying the bracket outcome.

    This catches bugs where labels were generated with different params
    than what's stored, or where the labeler has an off-by-one issue.
    """
    cl = df["close"].astype(np.float64).values
    hi = df["high"].astype(np.float64).values
    lo = df["low"].astype(np.float64).values
    n = len(cl)

    # ATR for bracket sizing
    prev_cl = np.roll(cl, 1)
    prev_cl[0] = cl[0]
    tr = np.maximum(hi - lo, np.maximum(np.abs(hi - prev_cl), np.abs(lo - prev_cl)))
    atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values

    rng = np.random.default_rng(rng_seed)

    def _check(class_val: int, max_hold: int = 120) -> float:
        idxs = np.where(labels == class_val)[0]
        if len(idxs) == 0:
            return float("nan")
        sample = rng.choice(idxs, size=min(n_sample, len(idxs)), replace=False)
        correct = 0
        for i in sample:
            if i + max_hold >= n:
                continue
            entry = cl[i]
            atr_val = atr[i]
            if atr_val <= 0 or entry <= 0:
                continue
            tp = entry + tp_atr_mult * atr_val if class_val == 1 else entry - tp_atr_mult * atr_val
            sl = entry - sl_atr_mult * atr_val if class_val == 1 else entry + sl_atr_mult * atr_val

            outcome = "timeout"
            for k in range(i + 1, min(i + max_hold, n)):
                if class_val == 1:  # LONG
                    if hi[k] >= tp:
                        outcome = "tp"
                        break
                    if lo[k] <= sl:
                        outcome = "sl"
                        break
                elif class_val == 2:  # SHORT
                    if lo[k] <= tp:
                        outcome = "tp"
                        break
                    if hi[k] >= sl:
                        outcome = "sl"
                        break
                else:  # LOSS (3)
                    if hi[k] >= sl and class_val != 1:
                        outcome = "sl"
                        break
                    if lo[k] <= sl and class_val == 1:
                        outcome = "sl"
                        break

            if class_val in (1, 2) and outcome == "tp":
                correct += 1
            elif class_val == 3 and outcome == "sl":
                correct += 1

        denom = min(n_sample, len(idxs))
        return correct / denom if denom > 0 else float("nan")

    long_acc = _check(1)
    short_acc = _check(2)
    loss_acc = _check(3)

    valid = [x for x in [long_acc, short_acc, loss_acc] if not np.isnan(x)]
    overall = float(np.mean(valid)) if valid else 0.0

    return LabelVerification(
        n_checked=n_sample,
        long_correct_pct=long_acc if not np.isnan(long_acc) else 0.0,
        short_correct_pct=short_acc if not np.isnan(short_acc) else 0.0,
        loss_correct_pct=loss_acc if not np.isnan(loss_acc) else 0.0,
        overall_accuracy=overall,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4.  SCORING
# ═══════════════════════════════════════════════════════════════════════════


def label_quality_score(
    labels: np.ndarray,
    tp_atr: float,
    sl_atr: float,
    regimes: np.ndarray | None = None,
) -> float:
    """
    Composite score combining:
      expectancy  — E[pnl] per trade in ATR units
      balance     — long/short symmetry (penalises one-directional models)
      regime_consistency — penalises params that only work in one regime
      frequency_penalty  — penalises too-frequent signals (noisy gate)
    """
    n = len(labels)
    n_long = int((labels == 1).sum())
    n_short = int((labels == 2).sum())
    n_loss = int((labels == 3).sum())
    n_triggered = n_long + n_short + n_loss

    min_triggered = max(50, int(n * 0.005))  # 0.5% of total labels, but at least 50
    if n_triggered < min_triggered:
        return -1.0

    if n_long < 20 or n_short < 20:  # at least 20 long/short labels each
        return -1.0

    win_rate = (n_long + n_short) / n_triggered
    expectancy = win_rate * tp_atr - (1 - win_rate) * sl_atr

    if expectancy <= 0:
        return expectancy - 1.0  # still informative for Optuna

    balance = min(n_long, n_short) / max(max(n_long, n_short), 1)
    directional_pct = (n_long + n_short) / n
    freq_penalty = max(0.0, directional_pct - 0.10) * 5.0

    # Regime consistency ──────────────────────────────────────────────────
    regime_penalty = 0.0
    if regimes is not None:
        regime_win_rates = []
        for r in np.unique(regimes):
            mask = regimes == r
            r_n_long = int((labels[mask] == 1).sum())
            r_n_short = int((labels[mask] == 2).sum())
            r_n_loss = int((labels[mask] == 3).sum())
            r_triggered = r_n_long + r_n_short + r_n_loss
            if r_triggered >= 30:
                regime_win_rates.append((r_n_long + r_n_short) / r_triggered)
        if len(regime_win_rates) >= 2:
            # Penalty proportional to variance across regime win rates
            regime_penalty = float(np.std(regime_win_rates)) * 2.0

    return expectancy * balance - freq_penalty - regime_penalty


# ═══════════════════════════════════════════════════════════════════════════
# 5.  OPTUNA OBJECTIVE
# ═══════════════════════════════════════════════════════════════════════════


def objective(
    trial: optuna.Trial,
    df_train: pd.DataFrame,
    regimes: np.ndarray | None,
) -> float:
    consolidation_atr_mult = trial.suggest_float(
        "consolidation_atr_mult", *SEARCH_SPACE["consolidation_atr_mult"]
    )
    consolidation_bars = trial.suggest_int(
        "consolidation_bars", *SEARCH_SPACE["consolidation_bars"]
    )
    tp_atr_mult = trial.suggest_float("tp_atr_mult", *SEARCH_SPACE["tp_atr_mult"])
    sl_atr_mult = trial.suggest_float("sl_atr_mult", *SEARCH_SPACE["sl_atr_mult"])
    max_breakout_wait = trial.suggest_int("max_breakout_wait", *SEARCH_SPACE["max_breakout_wait"])
    max_hold_bars = trial.suggest_int("max_hold_bars", *SEARCH_SPACE["max_hold_bars"])

    if tp_atr_mult / sl_atr_mult < 1.2:
        return -1.0

    labels = generate_labels_breakout(
        df_train,
        consolidation_bars=consolidation_bars,
        consolidation_atr_mult=consolidation_atr_mult,
        max_breakout_wait=max_breakout_wait,
        tp_atr_mult=tp_atr_mult,
        sl_atr_mult=sl_atr_mult,
        max_hold_bars=max_hold_bars,
    )

    return label_quality_score(labels, tp_atr_mult, sl_atr_mult, regimes)


# ═══════════════════════════════════════════════════════════════════════════
# 6.  PUBLIC API — importable by train.py
# ═══════════════════════════════════════════════════════════════════════════


def optimize_label_params(
    asset_key: str,
    df: pd.DataFrame,
    n_trials: int = 50,
    val_split: float = 0.20,
    models_dir: Path = _MODELS_DIR,
    force: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Run Optuna label-param search on the training split of ``df``.

    Returns a dict compatible with generate_labels_breakout(**params).
    Results are cached to {models_dir}/label_params_{asset_key}.json and
    reused when BOTH of the following hold (unless force=True):
      - The cache file is less than _CACHE_TTL_DAYS old.
      - The regime fingerprint of the current data matches the cached one.
    A regime shift (e.g. meme coin moving from chop to spike) will invalidate
    the cache immediately regardless of age.

    Parameters
    ----------
    asset_key  : Short asset key, e.g. "btc".
    df         : Full OHLCV DataFrame (will be split internally).
    n_trials   : Optuna trials.  Use 50 for training-loop calls, 200 for standalone.
    val_split  : Fraction of df held out for post-optimisation validation.
    models_dir : Where to cache param JSON files.
    force      : If True, ignore cached params and re-optimise.
    verbose    : If True, print per-trial progress.
    """
    cache_path = models_dir / f"label_params_{asset_key.lower()}.json"

    # ── Load cached params if fresh and regime-stable ────────────────────
    if not force and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            age_days = (time.time() - cached.get("optimized_at_ts", 0)) / 86_400
            cached_fp = cached.get("regime_fingerprint", "")
            current_fp = _regime_fingerprint(df)
            if age_days < _CACHE_TTL_DAYS and cached_fp == current_fp:
                logger.info(
                    "[%s] Using cached label params (%.1f days old, regime=%s): %s",
                    asset_key.upper(),
                    age_days,
                    current_fp,
                    cache_path.name,
                )
                return cached["params"]
            if cached_fp != current_fp:
                logger.info(
                    "[%s] Cache invalidated — regime shift detected (%s → %s)",
                    asset_key.upper(),
                    cached_fp,
                    current_fp,
                )
            # If fingerprints match but TTL expired, fall through to re-optimise.
        except Exception:
            pass

    # ── Chronological train/val split ────────────────────────────────────
    split = int(len(df) * (1 - val_split))
    df_train = df.iloc[:split].reset_index(drop=True)
    df_val = df.iloc[split:].reset_index(drop=True)

    logger.info(
        "[%s] Label optimisation  train=%d bars  val=%d bars  trials=%d",
        asset_key.upper(),
        len(df_train),
        len(df_val),
        n_trials,
    )

    # ── Regime detection on training split ──────────────────────────────
    try:
        regimes_train = detect_regimes(df_train)
        n_regimes = len(np.unique(regimes_train))
        logger.info(
            "[%s] Regime detection: %d states (%s)",
            asset_key.upper(),
            n_regimes,
            "HMM" if _HMM_AVAILABLE else "ATR-pctile fallback",
        )
    except Exception as exc:
        logger.warning("[%s] Regime detection failed: %s — skipping", asset_key.upper(), exc)
        regimes_train = None

    # ── Optuna study ─────────────────────────────────────────────────────
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    if not verbose:
        optuna.logging.set_verbosity(optuna.logging.WARNING)

    study.optimize(
        lambda t: objective(t, df_train, regimes_train),
        n_trials=n_trials,
        show_progress_bar=verbose,
    )

    best = study.best_params
    train_score = study.best_value

    # ── Validate best params on held-out val split ────────────────────────
    val_labels = generate_labels_breakout(
        df_val,
        consolidation_bars=best["consolidation_bars"],
        consolidation_atr_mult=best["consolidation_atr_mult"],
        max_breakout_wait=best["max_breakout_wait"],
        tp_atr_mult=best["tp_atr_mult"],
        sl_atr_mult=best["sl_atr_mult"],
        max_hold_bars=best["max_hold_bars"],
    )

    regimes_val = None
    if regimes_train is not None:
        try:
            regimes_val = detect_regimes(df_val)
        except Exception:
            pass

    val_score = label_quality_score(
        val_labels,
        best["tp_atr_mult"],
        best["sl_atr_mult"],
        regimes_val,
    )

    # ── Empirical label verification on val split ─────────────────────────
    verification = verify_labels_empirical(
        df_val,
        val_labels,
        tp_atr_mult=best["tp_atr_mult"],
        sl_atr_mult=best["sl_atr_mult"],
        n_sample=200,
    )

    # ── Distribution summary ──────────────────────────────────────────────
    val_n = len(val_labels)
    val_n_long = int((val_labels == 1).sum())
    val_n_short = int((val_labels == 2).sum())
    val_n_loss = int((val_labels == 3).sum())
    val_n_flat = int((val_labels == 0).sum())

    logger.info(
        "[%s] Opt result  train_score=%.4f  val_score=%.4f  "
        "val_dist: flat=%.1f%% long=%.1f%% short=%.1f%% loss=%.1f%%",
        asset_key.upper(),
        train_score,
        val_score,
        val_n_flat / val_n * 100,
        val_n_long / val_n * 100,
        val_n_short / val_n * 100,
        val_n_loss / val_n * 100,
    )
    logger.info(
        "[%s] Empirical label accuracy  long=%.1f%%  short=%.1f%%  loss=%.1f%%",
        asset_key.upper(),
        verification.long_correct_pct * 100,
        verification.short_correct_pct * 100,
        verification.loss_correct_pct * 100,
    )

    # Warn if empirical accuracy is low (possible labeler bug or param mismatch)
    if verification.overall_accuracy < 0.50:
        logger.warning(
            "[%s] ⚠  Low empirical label accuracy %.1f%% — "
            "check labeler logic or tighten param bounds",
            asset_key.upper(),
            verification.overall_accuracy * 100,
        )

    # ── Cache result ──────────────────────────────────────────────────────
    models_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "asset": asset_key,
        "params": best,
        "train_score": round(train_score, 6),
        "val_score": round(val_score, 6),
        "val_distribution": {
            "flat": round(val_n_flat / val_n * 100, 2),
            "long": round(val_n_long / val_n * 100, 2),
            "short": round(val_n_short / val_n * 100, 2),
            "loss": round(val_n_loss / val_n * 100, 2),
        },
        "empirical_accuracy": {
            "long": round(verification.long_correct_pct, 4),
            "short": round(verification.short_correct_pct, 4),
            "loss": round(verification.loss_correct_pct, 4),
            "overall": round(verification.overall_accuracy, 4),
        },
        "regime_method": "hmm" if _HMM_AVAILABLE else "atr_pctile",
        "regime_fingerprint": _regime_fingerprint(df),  # invalidates cache on regime shift
        "n_trials": n_trials,
        "optimized_at_ts": time.time(),
    }
    cache_path.write_text(json.dumps(result, indent=2, default=str))
    logger.info("[%s] Cached label params → %s", asset_key.upper(), cache_path)

    return best


# ═══════════════════════════════════════════════════════════════════════════
# 7.  STANDALONE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════


def _print_summary(results: list[dict]) -> None:
    print(f"\n{'━' * 72}")
    print(f"  LABEL OPTIMISATION SUMMARY")
    print(f"{'━' * 72}")
    header = f"  {'Asset':<12} {'ConsolATR':>10} {'CBars':>6} {'TP':>6} {'SL':>6} {'Wait':>5} {'Hold':>5} {'TrScore':>8} {'ValScore':>8}"
    print(header)
    print(
        f"  {'─' * 12} {'─' * 10} {'─' * 6} {'─' * 6} {'─' * 6} {'─' * 5} {'─' * 5} {'─' * 8} {'─' * 8}"
    )
    for r in results:
        p = r["params"]
        print(
            f"  {r['asset'].upper():<12} "
            f"{p['consolidation_atr_mult']:>10.2f} "
            f"{p['consolidation_bars']:>6d} "
            f"{p['tp_atr_mult']:>6.2f} "
            f"{p['sl_atr_mult']:>6.2f} "
            f"{p['max_breakout_wait']:>5d} "
            f"{p['max_hold_bars']:>5d} "
            f"{r['train_score']:>8.4f} "
            f"{r['val_score']:>8.4f}"
        )
    print()

    # Print as a Python dict ready to paste into train.py
    print("  # ── Paste into train.py ASSET_LABEL_PARAMS ──")
    print("  ASSET_LABEL_PARAMS = {")
    for r in results:
        p = r["params"]
        print(f'    "{r["asset"]}": dict(')
        for k, v in p.items():
            fmtv = f"{v:.4f}" if isinstance(v, float) else str(v)
            print(f"        {k}={fmtv},")
        print("    ),")
    print("  }")


def main() -> None:
    import argparse

    import ccxt

    parser = argparse.ArgumentParser(description="Label parameter optimisation")
    parser.add_argument(
        "--assets", nargs="+", default=DEFAULT_ASSETS, help="Asset keys to optimise (default: all)"
    )
    parser.add_argument(
        "--trials", type=int, default=200, help="Optuna trials per asset (default: 200)"
    )
    parser.add_argument("--bars", type=int, default=100_000, help="Klines to fetch per asset")
    parser.add_argument("--force", action="store_true", help="Ignore cached params and re-optimise")
    parser.add_argument(
        "--no-cache", action="store_true", dest="no_cache", help="Disable Redis kline cache"
    )
    args = parser.parse_args()

    # ── Redis connection ─────────────────────────────────────────────────
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_password = os.environ.get("REDIS_PASSWORD") or None

    if args.no_cache:
        cache = KlineCache()
    else:
        cache = KlineCache.connect(redis_url, password=redis_password)

    # ── Exchange ─────────────────────────────────────────────────────────
    exchange = ccxt.kucoinfutures({"enableRateLimit": True, "rateLimit": 200})
    try:
        exchange.load_markets()
        logger.info("Exchange connected — %d markets", len(exchange.markets))
    except Exception as exc:
        logger.warning("load_markets failed: %s — continuing", exc)

    results = []
    for asset in args.assets:
        symbol = SYMBOLS.get(asset.lower())
        if symbol is None:
            logger.warning("Unknown asset '%s' — skipping (valid: %s)", asset, list(SYMBOLS))
            continue

        print(f"\n{'━' * 50}")
        print(f"  Optimising label params for {asset.upper()} ({symbol})")
        print(f"{'━' * 50}")

        # ── Fetch data ────────────────────────────────────────────────────
        t0 = time.time()
        df = fetch_klines(exchange, symbol, limit=args.bars, cache=cache)
        if df.empty or len(df) < 5_000:
            logger.error("[%s] Insufficient data (%d bars) — skipping", asset.upper(), len(df))
            continue
        logger.info("[%s] Fetched %d bars in %.1fs", asset.upper(), len(df), time.time() - t0)

        # ── Data quality verification ─────────────────────────────────────
        report = verify_data_quality(df, symbol, from_cache=cache.enabled)
        report.print()
        if not report.ok:
            logger.warning("[%s] Data quality check failed — skipping", asset.upper())
            continue

        # ── Optimise ──────────────────────────────────────────────────────
        best_params = optimize_label_params(
            asset_key=asset.lower(),
            df=df,
            n_trials=args.trials,
            models_dir=_MODELS_DIR,
            force=args.force,
            verbose=True,
        )

        # Load full result for summary (written by optimize_label_params)
        cache_path = _MODELS_DIR / f"label_params_{asset.lower()}.json"
        try:
            full_result = json.loads(cache_path.read_text())
            results.append(full_result)
        except Exception:
            results.append(
                {"asset": asset, "params": best_params, "train_score": 0.0, "val_score": 0.0}
            )

        # Print per-asset param block
        print(f"\n=== {asset.upper()} best params ===")
        for k, v in best_params.items():
            fmtv = f"{v:.6f}" if isinstance(v, float) else str(v)
            print(f"  {k:<26} {fmtv}")

    if results:
        _print_summary(results)


if __name__ == "__main__":
    main()
