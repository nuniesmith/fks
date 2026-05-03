"""
Breakout Filters — Quality-over-Quantity Gate for Crypto Futures
================================================================
Adapted from ruby/lib/analysis/breakout_filters.py.

CME-specific filters (session windows, lunch dead-zone, pre-market range)
have been removed — they don't apply to 24/7 crypto markets.

What's kept and adapted:
  1. NR7 (Narrow Range 7)   — Toby Crabel: compressed range → coiled energy
  2. VWAP Confluence        — price must be on the correct side of VWAP
  3. EMA Trend Bias         — higher-timeframe EMA slope must agree with signal
  4. Volume Confirmation    — breakout bar volume above average
  5. ATR Expansion          — ATR must be expanding (not compressing) at entry

Design:
  - Pure functions, no Redis, no side-effects, fully testable.
  - Each filter returns a FilterVerdict(passed, reason, score_boost).
  - apply_all_filters() orchestrates them with configurable enable/disable.
  - Hard filters can reject; soft filters only boost the quality score.
  - gate_mode="all"      → every hard filter must pass
  - gate_mode="majority" → >50% of hard filters must pass

Usage:
    from analysis.breakout_filters import apply_all_filters, FilterVerdict

    result = apply_all_filters(
        candles=df,        # pd.DataFrame with OHLCV (lowercase columns)
        direction="buy",   # "buy" | "sell"
        trigger_price=price,
    )
    if result.passed:
        # place order
        quality_boost = result.quality_boost  # add to quality score
    else:
        logger.debug("Filtered: %s", result.summary)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger("breakout_filters")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class FilterVerdict:
    """Result of a single filter check."""

    name: str
    passed: bool
    reason: str = ""
    score_boost: float = 0.0  # quality-score adjustment; soft filters only boost

    def __str__(self) -> str:
        status = "✅" if self.passed else "❌"
        return f"{status} {self.name}: {self.reason}"


@dataclass
class BreakoutFilterResult:
    """Composite result from running all breakout filters."""

    passed: bool = False
    verdicts: list[FilterVerdict] = field(default_factory=list)
    filters_passed: int = 0
    filters_total: int = 0
    quality_boost: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "filters_passed": self.filters_passed,
            "filters_total": self.filters_total,
            "quality_boost": round(self.quality_boost, 3),
            "summary": self.summary,
            "verdicts": [
                {
                    "name": v.name,
                    "passed": v.passed,
                    "reason": v.reason,
                    "score_boost": v.score_boost,
                }
                for v in self.verdicts
            ],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_col(df: pd.DataFrame, name: str) -> np.ndarray:
    """Return column as float64 numpy array; accepts lower or upper case."""
    if name in df.columns:
        return df[name].astype(np.float64).to_numpy()
    cap = name[0].upper() + name[1:]
    if cap in df.columns:
        return df[cap].astype(np.float64).to_numpy()
    raise KeyError(f"Column '{name}' not found in DataFrame (tried '{name}' and '{cap}')")


def _ema_np(arr: np.ndarray, span: int) -> np.ndarray:
    """EWM EMA matching the bot's formula."""
    alpha = 2.0 / (span + 1)
    out = np.empty_like(arr, dtype=np.float64)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = out[i - 1] * (1 - alpha) + arr[i] * alpha
    return out


# ---------------------------------------------------------------------------
# 1. NR7 — Narrow Range 7  (SOFT filter — never rejects, only boosts)
# ---------------------------------------------------------------------------
# Toby Crabel (1990): when the current bar's high-low range is the narrowest
# of the last 7 bars, subsequent breakouts have significantly higher
# follow-through.  A compressed range implies coiled energy.


def check_nr7(
    candles: pd.DataFrame | None,
    lookback: int = 7,
    boost: float = 0.15,
) -> FilterVerdict:
    """Check whether the most recent bar is an NR7 (Narrow Range 7).

    NR7 is a SOFT filter: it never rejects a signal; it only boosts the
    quality score when the condition is met.

    Parameters
    ----------
    candles:
        OHLCV DataFrame.  Needs at least ``lookback`` rows.
    lookback:
        Number of bars to compare (default 7, per Crabel's original research).
    boost:
        Quality-score boost to apply when NR7 is detected.

    Returns
    -------
    FilterVerdict with passed=True always.
    score_boost > 0 only when the NR7 condition holds.
    """
    name = "NR7"

    if candles is None or candles.empty or len(candles) < lookback:
        return FilterVerdict(
            name=name,
            passed=True,
            reason=f"Insufficient data ({len(candles) if candles is not None else 0} bars, need {lookback}) — skipped",
        )

    try:
        hi = _get_col(candles, "high")[-lookback:]
        lo = _get_col(candles, "low")[-lookback:]
    except KeyError as exc:
        return FilterVerdict(name=name, passed=True, reason=f"Missing columns: {exc}")

    daily_ranges = hi - lo

    if np.all(daily_ranges <= 0):
        return FilterVerdict(name=name, passed=True, reason="All zero-range bars — NR7 skipped")

    today_range = daily_ranges[-1]
    is_nr7 = today_range <= np.min(daily_ranges)

    if is_nr7:
        return FilterVerdict(
            name=name,
            passed=True,
            reason=f"NR7 active — current range {today_range:.6f} is narrowest of {lookback} bars",
            score_boost=boost,
        )

    rank = int(np.sum(daily_ranges < today_range)) + 1
    return FilterVerdict(
        name=name,
        passed=True,
        reason=f"Not NR7 — ranks #{rank}/{lookback} (range={today_range:.6f})",
    )


# ---------------------------------------------------------------------------
# 2. VWAP Confluence  (HARD filter)
# ---------------------------------------------------------------------------
# For crypto 24/7: use a rolling VWAP over a configurable lookback (default
# 200 bars) rather than a session-resetting VWAP.
# LONG signals should be above VWAP; SHORT signals below.


def compute_rolling_vwap(candles: pd.DataFrame, lookback: int = 200) -> float | None:
    """Compute a rolling VWAP over the last ``lookback`` bars.

    VWAP = Σ(typical_price × volume) / Σ(volume)
    typical_price = (high + low + close) / 3

    Returns the current VWAP value, or None if insufficient data.
    """
    if candles is None or candles.empty or len(candles) < 2:
        return None

    try:
        hi = _get_col(candles, "high")
        lo = _get_col(candles, "low")
        cl = _get_col(candles, "close")
        vo = _get_col(candles, "volume")
    except KeyError:
        return None

    # Use last lookback bars
    n = min(lookback, len(cl))
    hi = hi[-n:]
    lo = lo[-n:]
    cl = cl[-n:]
    vo = vo[-n:]

    tp = (hi + lo + cl) / 3.0
    cum_vol = np.sum(vo)
    if cum_vol <= 0:
        return None

    return float(np.sum(tp * vo) / cum_vol)


def check_vwap_confluence(
    candles: pd.DataFrame | None,
    direction: str,
    trigger_price: float,
    vwap: float | None = None,
    vwap_lookback: int = 200,
) -> FilterVerdict:
    """Check that the trigger price is on the correct side of VWAP.

    LONG:  trigger_price >= VWAP  (buying above value → strength)
    SHORT: trigger_price <= VWAP  (selling below value → weakness)

    Parameters
    ----------
    candles:
        OHLCV DataFrame used to compute rolling VWAP if ``vwap`` is None.
    direction:
        "buy" | "sell" (or "long" | "short", case-insensitive).
    trigger_price:
        Current price at the point of signal.
    vwap:
        Pre-computed VWAP.  If None, computed from candles.
    vwap_lookback:
        Rolling window for VWAP computation.
    """
    name = "VWAP Confluence"
    is_long = direction.lower() in ("buy", "long")

    if vwap is None and candles is not None:
        vwap = compute_rolling_vwap(candles, lookback=vwap_lookback)

    if vwap is None or vwap <= 0:
        return FilterVerdict(name=name, passed=True, reason="VWAP unavailable — skipped")

    dist_pct = (trigger_price - vwap) / vwap * 100

    if is_long:
        if trigger_price >= vwap:
            return FilterVerdict(
                name=name,
                passed=True,
                reason=f"LONG above VWAP {vwap:.6f} by {dist_pct:+.3f}%",
                score_boost=0.05 if dist_pct > 0.1 else 0.0,
            )
        return FilterVerdict(
            name=name,
            passed=False,
            reason=f"LONG trigger {trigger_price:.6f} below VWAP {vwap:.6f} by {abs(dist_pct):.3f}%",
        )
    else:
        if trigger_price <= vwap:
            return FilterVerdict(
                name=name,
                passed=True,
                reason=f"SHORT below VWAP {vwap:.6f} by {abs(dist_pct):.3f}%",
                score_boost=0.05 if dist_pct < -0.1 else 0.0,
            )
        return FilterVerdict(
            name=name,
            passed=False,
            reason=f"SHORT trigger {trigger_price:.6f} above VWAP {vwap:.6f} by {dist_pct:.3f}%",
        )


# ---------------------------------------------------------------------------
# 3. EMA Trend Bias  (HARD filter)
# ---------------------------------------------------------------------------
# The signal direction must agree with the slope of a longer-period EMA
# computed on the same candle data.  Rejects counter-trend entries.


def check_ema_trend_bias(
    candles: pd.DataFrame | None,
    direction: str,
    ema_period: int = 50,
    slope_bars: int = 3,
    min_slope_pct: float = 0.0,
) -> FilterVerdict:
    """Check that the EMA slope agrees with the signal direction.

    Parameters
    ----------
    candles:
        OHLCV DataFrame.  Needs at least ``ema_period + slope_bars + 1`` bars.
    direction:
        "buy" | "sell" (or "long" | "short").
    ema_period:
        EMA period.  Default 50 (about 50 minutes on 1m, good intermediate trend).
    slope_bars:
        Number of bars over which to measure the EMA slope (default 3).
    min_slope_pct:
        Minimum absolute EMA slope as a fraction of price to count as directional.
        0.0 = any positive slope counts for LONG.
    """
    name = "EMA Trend Bias"
    is_long = direction.lower() in ("buy", "long")

    if candles is None or candles.empty:
        return FilterVerdict(name=name, passed=True, reason="No candles — skipped")

    min_required = ema_period + slope_bars + 1
    if len(candles) < min_required:
        return FilterVerdict(
            name=name,
            passed=True,
            reason=f"Only {len(candles)} bars (need {min_required}) — skipped",
        )

    try:
        cl = _get_col(candles, "close")
    except KeyError as exc:
        return FilterVerdict(name=name, passed=True, reason=f"Missing column: {exc}")

    ema = _ema_np(cl, ema_period)
    ema_now = ema[-1]
    ema_prev = ema[-(slope_bars + 1)]

    if ema_prev <= 0:
        return FilterVerdict(name=name, passed=True, reason="EMA is zero — skipped")

    slope_pct = (ema_now - ema_prev) / ema_prev

    if slope_pct > min_slope_pct:
        slope_dir = "UP"
    elif slope_pct < -min_slope_pct:
        slope_dir = "DOWN"
    else:
        slope_dir = "FLAT"

    if is_long:
        if slope_dir == "DOWN":
            return FilterVerdict(
                name=name,
                passed=False,
                reason=f"BUY vs DOWN EMA({ema_period}) slope ({slope_pct:+.4%}) — counter-trend rejected",
            )
        return FilterVerdict(
            name=name,
            passed=True,
            reason=f"BUY agrees with {slope_dir} EMA({ema_period}) slope ({slope_pct:+.4%})",
            score_boost=0.05 if slope_dir == "UP" else 0.0,
        )
    else:
        if slope_dir == "UP":
            return FilterVerdict(
                name=name,
                passed=False,
                reason=f"SELL vs UP EMA({ema_period}) slope ({slope_pct:+.4%}) — counter-trend rejected",
            )
        return FilterVerdict(
            name=name,
            passed=True,
            reason=f"SELL agrees with {slope_dir} EMA({ema_period}) slope ({slope_pct:+.4%})",
            score_boost=0.05 if slope_dir == "DOWN" else 0.0,
        )


# ---------------------------------------------------------------------------
# 4. Volume Confirmation  (HARD filter)
# ---------------------------------------------------------------------------
# The breakout bar's volume should be above the recent rolling average.
# Low-volume breakouts have a high false-breakout rate.


def check_volume_confirmation(
    candles: pd.DataFrame | None,
    volume_mult: float = 1.2,
    avg_bars: int = 20,
) -> FilterVerdict:
    """Check that the current bar's volume is above the rolling average.

    Parameters
    ----------
    candles:
        OHLCV DataFrame.
    volume_mult:
        Required multiple of the average volume.  Default 1.2 (20% above avg).
    avg_bars:
        Lookback for rolling average (default 20 bars).
    """
    name = "Volume Confirmation"

    if candles is None or candles.empty or len(candles) < avg_bars + 1:
        return FilterVerdict(
            name=name,
            passed=True,
            reason=f"Insufficient data ({len(candles) if candles is not None else 0} bars) — skipped",
        )

    try:
        vo = _get_col(candles, "volume")
    except KeyError as exc:
        return FilterVerdict(name=name, passed=True, reason=f"Missing column: {exc}")

    current_vol = vo[-1]
    avg_vol = float(np.mean(vo[-avg_bars - 1 : -1]))  # exclude current bar from avg

    if avg_vol <= 0:
        return FilterVerdict(name=name, passed=True, reason="Zero average volume — skipped")

    ratio = current_vol / avg_vol

    if ratio >= volume_mult:
        return FilterVerdict(
            name=name,
            passed=True,
            reason=f"Volume {ratio:.2f}× avg (≥{volume_mult:.1f}× required)",
            score_boost=min(0.10, (ratio - volume_mult) * 0.05),
        )

    return FilterVerdict(
        name=name,
        passed=False,
        reason=f"Volume {ratio:.2f}× avg (need ≥{volume_mult:.1f}×) — low-volume breakout",
    )


# ---------------------------------------------------------------------------
# 5. ATR Expansion  (SOFT filter — boosts score, never rejects)
# ---------------------------------------------------------------------------
# An expanding ATR means the market is waking up, which is favourable for
# breakouts.  A contracting ATR suggests the market is going to sleep.
# This is a soft filter — low-ATR breakouts are still allowed but not boosted.


def check_atr_expansion(
    candles: pd.DataFrame | None,
    atr_period: int = 14,
    lookback_half: int = 5,
    boost: float = 0.10,
) -> FilterVerdict:
    """Check whether ATR is expanding (good for breakouts) or contracting.

    Compares the mean ATR of the most recent ``lookback_half`` bars against
    the prior ``lookback_half`` bars.  Expanding → score boost.

    This is a SOFT filter — always passes, only adjusts score_boost.
    """
    name = "ATR Expansion"
    lookback = lookback_half * 2

    if candles is None or candles.empty or len(candles) < lookback + atr_period + 1:
        return FilterVerdict(name=name, passed=True, reason="Insufficient data — skipped")

    try:
        hi = _get_col(candles, "high")
        lo = _get_col(candles, "low")
        cl = _get_col(candles, "close")
    except KeyError as exc:
        return FilterVerdict(name=name, passed=True, reason=f"Missing column: {exc}")

    prev_cl = np.roll(cl, 1)
    prev_cl[0] = cl[0]
    tr = np.maximum(hi - lo, np.maximum(np.abs(hi - prev_cl), np.abs(lo - prev_cl)))

    # Use last lookback bars of TR (after ATR warmup)
    recent_tr = tr[-(lookback):]
    older_half = float(np.mean(recent_tr[:lookback_half]))
    newer_half = float(np.mean(recent_tr[lookback_half:]))

    if older_half <= 1e-12:
        return FilterVerdict(name=name, passed=True, reason="ATR too small to measure — skipped")

    ratio = newer_half / older_half

    if ratio >= 1.05:  # expanding by >5%
        return FilterVerdict(
            name=name,
            passed=True,
            reason=f"ATR expanding — recent/older ratio={ratio:.2f}",
            score_boost=boost,
        )
    elif ratio <= 0.95:  # contracting by >5%
        return FilterVerdict(
            name=name,
            passed=True,
            reason=f"ATR contracting — recent/older ratio={ratio:.2f} (no boost)",
            score_boost=0.0,
        )
    else:
        return FilterVerdict(
            name=name,
            passed=True,
            reason=f"ATR flat — recent/older ratio={ratio:.2f}",
            score_boost=0.0,
        )


# ---------------------------------------------------------------------------
# Composite: apply_all_filters
# ---------------------------------------------------------------------------


def apply_all_filters(
    candles: pd.DataFrame | None,
    direction: str,
    trigger_price: float,
    vwap: float | None = None,
    # Per-filter enable/disable
    enable_nr7: bool = True,
    enable_vwap: bool = True,
    enable_ema_bias: bool = True,
    enable_volume: bool = True,
    enable_atr_expansion: bool = True,
    # Filter parameters
    nr7_lookback: int = 7,
    nr7_boost: float = 0.15,
    vwap_lookback: int = 200,
    ema_period: int = 50,
    ema_slope_bars: int = 3,
    volume_mult: float = 1.2,
    volume_avg_bars: int = 20,
    atr_lookback_half: int = 5,
    atr_boost: float = 0.10,
    # Gate mode
    gate_mode: str = "all",
) -> BreakoutFilterResult:
    """Run all enabled breakout quality filters and return a composite result.

    Filters are split into two categories:
      - **Hard filters** (VWAP, EMA trend bias, volume confirmation):
        these can reject a signal outright.
      - **Soft filters** (NR7, ATR expansion):
        these only adjust the quality score boost; they never reject.

    Parameters
    ----------
    candles:
        OHLCV DataFrame (lowercase columns: open, high, low, close, volume).
    direction:
        Signal direction: "buy" | "sell" (also accepts "long" | "short").
    trigger_price:
        Current price at the point of signal.
    vwap:
        Pre-computed VWAP.  If None, computed from candles (rolling).
    enable_*:
        Toggle individual filters on/off.
    gate_mode:
        "all"      → every hard filter must pass (conservative, fewer trades).
        "majority" → >50% of hard filters must pass (more permissive).

    Returns
    -------
    BreakoutFilterResult with .passed, .quality_boost, .summary, .verdicts.
    """
    verdicts: list[FilterVerdict] = []

    # ── Soft filters (always pass, only boost) ────────────────────────────

    if enable_nr7:
        verdicts.append(check_nr7(candles, lookback=nr7_lookback, boost=nr7_boost))

    if enable_atr_expansion:
        verdicts.append(
            check_atr_expansion(candles, lookback_half=atr_lookback_half, boost=atr_boost)
        )

    # ── Hard filters (can reject) ─────────────────────────────────────────

    if enable_vwap:
        verdicts.append(
            check_vwap_confluence(
                candles=candles,
                direction=direction,
                trigger_price=trigger_price,
                vwap=vwap,
                vwap_lookback=vwap_lookback,
            )
        )

    if enable_ema_bias:
        verdicts.append(
            check_ema_trend_bias(
                candles=candles,
                direction=direction,
                ema_period=ema_period,
                slope_bars=ema_slope_bars,
            )
        )

    if enable_volume:
        verdicts.append(
            check_volume_confirmation(
                candles=candles,
                volume_mult=volume_mult,
                avg_bars=volume_avg_bars,
            )
        )

    # ── Compose result ────────────────────────────────────────────────────

    soft_names = {"NR7", "ATR Expansion"}
    hard_verdicts = [v for v in verdicts if v.name not in soft_names]

    total_boost = sum(v.score_boost for v in verdicts)
    filters_passed = sum(1 for v in verdicts if v.passed)

    if gate_mode == "majority":
        overall_passed = (
            len([v for v in hard_verdicts if v.passed]) >= (len(hard_verdicts) / 2.0)
            if hard_verdicts
            else True
        )
    else:  # "all"
        overall_passed = all(v.passed for v in hard_verdicts) if hard_verdicts else True

    failed_names = [v.name for v in verdicts if not v.passed]
    if overall_passed:
        summary = f"PASS ({filters_passed}/{len(verdicts)} filters OK, boost={total_boost:+.2f})"
    else:
        summary = (
            f"REJECT — failed: {', '.join(failed_names)} ({filters_passed}/{len(verdicts)} OK)"
        )

    logger.debug("Breakout filter [%s]: %s", direction.upper(), summary)

    return BreakoutFilterResult(
        passed=overall_passed,
        verdicts=verdicts,
        filters_passed=filters_passed,
        filters_total=len(verdicts),
        quality_boost=total_boost,
        summary=summary,
    )
