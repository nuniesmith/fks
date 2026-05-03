"""
Breakout CNN — Feature engineering helper functions.

All ``get_*`` helpers that compute individual tabular features for the CNN
live here.  They are used by both the dataset (training) and the inference
pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from analysis.ml.breakout_constants import (
    _BREAKOUT_TYPE_CATEGORY,
    ASSET_CLASS_ORDINALS,
    ASSET_VOLATILITY_CLASS,
    BREAKOUT_TYPE_ORDINALS,
)
from core.logging_config import get_logger

if TYPE_CHECKING:
    import pandas as pd

logger = get_logger("analysis.breakout_cnn")


# ---------------------------------------------------------------------------
# Asset class / volatility helpers
# ---------------------------------------------------------------------------


def get_asset_class_id(ticker: str) -> float:
    """Return the asset class ordinal / 4 for *ticker*, matching asset class normalisation.

    Classes:
        0.00 — equity index (MES, MNQ, M2K, MYM)
        0.25 — FX          (6E, 6B, 6J, 6A, 6C, 6S)
        0.50 — metals/energy (MGC, SIL, MHG, MCL, MNG)
        0.75 — treasuries/ags (ZN, ZB, ZC, ZS, ZW)
        1.00 — crypto      (MBT, MET, BTC, ETH, …)

    Falls back to 0.0 (equity index) for unknown tickers.
    """
    return ASSET_CLASS_ORDINALS.get(str(ticker).upper().strip(), 0.0)


def get_asset_volatility_class(ticker: str) -> float:
    """Return the legacy volatility class [0.0/0.5/1.0] for *ticker*.

    Kept for backward compatibility.  New code should use get_asset_class_id().
    """
    return ASSET_VOLATILITY_CLASS.get(str(ticker).upper().strip(), 0.5)


# ---------------------------------------------------------------------------
# Breakout type helpers
# ---------------------------------------------------------------------------


def get_breakout_type_ordinal(breakout_type: str) -> float:
    """Return the normalised ordinal [0, 1] for a BreakoutType string.

    Accepts both upper-case ("ORB", "PDR") and lower-case / mixed variants.
    Falls back to 0.0 (ORB) for unknown types.
    """
    return BREAKOUT_TYPE_ORDINALS.get(str(breakout_type).upper().strip(), 0.0)


def get_breakout_type_category(breakout_type: str) -> float:
    """Return the breakout type category for the CNN tabular vector.

    Categories decompose breakout_type_ord into a coarser grouping that
    captures *how* the range is formed:
      - time-based (0.0):    ORB, Asian, IB — fixed time window
      - range-based (0.5):   PDR, Weekly, Monthly, VA, Inside, Gap, Pivot, Fib
      - squeeze-based (1.0): Consolidation, BollingerSqueeze

    This helps the CNN learn that squeeze breakouts share characteristics
    (explosive expansion) regardless of the specific detection algorithm,
    while time-based breakouts share session-dependency characteristics.

    Args:
        breakout_type: Short name (``"ORB"``, ``"PDR"``, ``"CONS"``, …)
                       or canonical name (``"PrevDay"``, ``"Consolidation"``, …).

    Returns:
        Float in {0.0, 0.5, 1.0}.  Falls back to 0.5 (range-based) for
        unknown types.
    """
    upper = str(breakout_type).upper().strip()
    if upper in _BREAKOUT_TYPE_CATEGORY:
        return _BREAKOUT_TYPE_CATEGORY[upper]
    # Try canonical name → short name mapping
    _CANONICAL_TO_SHORT = {
        "PREVDAY": "PDR",
        "INITIALBALANCE": "IB",
        "CONSOLIDATION": "CONS",
        "BOLLINGERSQUEEZE": "BBSQUEEZE",
        "VALUEAREA": "VA",
        "INSIDEDAY": "INSIDE",
        "GAPREJECTION": "GAP",
        "PIVOTPOINTS": "PIVOT",
        "FIBONACCI": "FIB",
    }
    short = _CANONICAL_TO_SHORT.get(upper, upper)
    return _BREAKOUT_TYPE_CATEGORY.get(short, 0.5)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def get_session_overlap_flag(
    session_key: str | None = None,
    *,
    bar_hour_et: int | None = None,
) -> float:
    """Return 1.0 if the bar is in the London+NY overlap window, else 0.0.

    The London-NY overlap (roughly 08:00–12:00 ET / 13:00–17:00 UTC) is the
    highest-volume window of the trading day.  Breakouts during this window
    have significantly higher follow-through rates because of the liquidity
    depth from both European and American institutional flow.

    This sub-feature enriches ``session_ordinal`` by explicitly flagging the
    overlap, which the model can use as a multiplicative signal quality boost.

    Detection logic (any of these → 1.0):
      - ``session_key == "london_ny"``
      - ``bar_hour_et`` is in [8, 9, 10, 11] (08:00–11:59 ET)

    Args:
        session_key: ORBSession.key (e.g. ``"london_ny"``).
        bar_hour_et: Hour of the bar in US/Eastern (0–23).

    Returns:
        1.0 if in the overlap window, 0.0 otherwise.
    """
    if session_key is not None and session_key.lower().strip() == "london_ny":
        return 1.0
    if bar_hour_et is not None and 8 <= bar_hour_et <= 11:
        return 1.0
    return 0.0


# ---------------------------------------------------------------------------
# ATR / Volume trend helpers  (v7.1 sub-feature decomposition)
# ---------------------------------------------------------------------------


def get_atr_trend(
    bars: pd.DataFrame | None = None,
    *,
    lookback: int = 10,
) -> float:
    """Return whether ATR is expanding (1.0) or contracting (0.0) over the last N bars.

    Computes the per-bar true range for the most recent ``lookback`` bars,
    then compares the mean of the second half to the first half.  If the
    recent half has higher average TR, ATR is expanding (→ 1.0); if lower,
    it's contracting (→ 0.0).  Equal → 0.5.

    This sub-feature enriches ``atr_pct`` (which is a point-in-time snapshot)
    by adding the *direction* of volatility change.  Expanding ATR into a
    breakout is bullish for continuation; contracting ATR suggests the move
    may be exhausting.

    Args:
        bars:     1-minute OHLCV DataFrame (needs at least ``lookback`` rows).
        lookback: Number of bars to measure the TR trend over (default 10).

    Returns:
        Float in [0.0, 1.0].  1.0 = expanding, 0.0 = contracting, 0.5 = flat.
        Falls back to 0.5 if insufficient data.
    """
    if bars is None or len(bars) < lookback + 1:
        return 0.5

    try:
        tail = bars.iloc[-(lookback + 1) :]
        highs = tail["High"].astype(float).values
        lows = tail["Low"].astype(float).values
        closes = tail["Close"].astype(float).values

        # Compute per-bar true range (skip first bar — no prior close)
        tr = np.empty(lookback)
        for i in range(lookback):
            j = i + 1  # offset into tail (skip row 0 which is the "prior close" anchor)
            tr[i] = max(
                highs[j] - lows[j],
                abs(highs[j] - closes[j - 1]),
                abs(lows[j] - closes[j - 1]),
            )

        half = lookback // 2
        first_half_mean = float(np.mean(tr[:half]))
        second_half_mean = float(np.mean(tr[half:]))

        if first_half_mean <= 0:
            return 0.5

        ratio = second_half_mean / first_half_mean
        # Map ratio to [0, 1]: ratio > 1 = expanding, ratio < 1 = contracting
        # Use a sigmoid-like clamp: ratio 0.5 → 0.0, ratio 1.0 → 0.5, ratio 1.5 → 1.0
        normalised = max(0.0, min(1.0, (ratio - 0.5) / 1.0))
        return normalised
    except Exception:
        return 0.5


def get_volume_trend(
    bars: pd.DataFrame | None = None,
    *,
    lookback: int = 5,
) -> float:
    """Return the normalised volume trend over the last N bars [0, 1].

    Computes a simple linear slope of volume over the last ``lookback`` bars,
    then normalises to [0, 1] where:
      - 0.0 = volume declining sharply
      - 0.5 = volume flat
      - 1.0 = volume rising sharply

    This sub-feature enriches ``volume_ratio`` (which is a single-bar snapshot)
    by adding the *trend* of volume leading into the breakout.  Rising volume
    into a breakout is bullish for continuation; declining volume suggests a
    false breakout / low-conviction move.

    Args:
        bars:     1-minute OHLCV DataFrame (needs at least ``lookback`` rows).
        lookback: Number of bars to measure the volume trend over (default 5).

    Returns:
        Float in [0.0, 1.0].  0.5 = flat, >0.5 = rising, <0.5 = falling.
        Falls back to 0.5 if insufficient data or no Volume column.
    """
    if bars is None or len(bars) < lookback:
        return 0.5

    try:
        if "Volume" not in bars.columns:
            return 0.5

        vol = bars["Volume"].astype(float).values[-lookback:]

        # Skip if all zero (no volume data)
        if np.sum(vol) <= 0:  # type: ignore[call-overload]
            return 0.5

        # Simple linear regression slope: y = vol, x = 0..lookback-1
        x = np.arange(lookback, dtype=float)
        x_mean = x.mean()
        vol_mean = vol.mean()  # type: ignore[union-attr]

        if vol_mean <= 0:
            return 0.5

        numerator = float(np.sum((x - x_mean) * (vol - vol_mean)))
        denominator = float(np.sum((x - x_mean) ** 2))

        if denominator <= 0:
            return 0.5

        slope = numerator / denominator

        # Normalise slope relative to mean volume:
        # slope_pct = slope / vol_mean gives the fractional change per bar.
        # A slope_pct of +0.2 means volume is growing 20% per bar — very strong.
        # Map [-0.3, +0.3] → [0.0, 1.0] with clamp.
        slope_pct = slope / vol_mean
        normalised = max(0.0, min(1.0, (slope_pct + 0.3) / 0.6))
        return normalised
    except Exception:
        return 0.5


# ---------------------------------------------------------------------------
# v7 feature helpers — Daily Strategy layer
# ---------------------------------------------------------------------------


def get_daily_bias_direction(
    asset_name: str,
    bars_daily: pd.DataFrame | None = None,
    *,
    _bias_cache: dict[str, Any] | None = None,
) -> float:
    """Return normalised daily bias direction for the CNN tabular vector.

    Maps BiasDirection to [0, 1]:  SHORT → 0.0, NEUTRAL → 0.5, LONG → 1.0.
    Falls back to 0.5 (neutral) if the bias analyzer is unavailable or errors.

    Args:
        asset_name: Human-readable asset name (e.g. ``"Gold"``, ``"S&P"``).
        bars_daily: Daily OHLCV bars (≥10 rows preferred).
        _bias_cache: Optional pre-computed DailyBias dict keyed by asset name.
    """
    if _bias_cache is not None and asset_name in _bias_cache:
        bias = _bias_cache[asset_name]
        return getattr(bias, "direction_feature", 0.5)
    try:
        from trading.strategies.daily.bias_analyzer import compute_daily_bias

        if bars_daily is not None and not bars_daily.empty:
            bias = compute_daily_bias(asset_name, bars_daily)  # type: ignore[arg-type]
            return bias.direction_feature
    except Exception:
        pass
    return 0.5


def get_daily_bias_confidence(
    asset_name: str,
    bars_daily: pd.DataFrame | None = None,
    *,
    _bias_cache: dict[str, Any] | None = None,
) -> float:
    """Return daily bias confidence [0, 1] for the CNN tabular vector.

    Falls back to 0.0 if unavailable.
    """
    if _bias_cache is not None and asset_name in _bias_cache:
        bias = _bias_cache[asset_name]
        return getattr(bias, "confidence_feature", 0.0)
    try:
        from trading.strategies.daily.bias_analyzer import compute_daily_bias

        if bars_daily is not None and not bars_daily.empty:
            bias = compute_daily_bias(asset_name, bars_daily)  # type: ignore[arg-type]
            return bias.confidence_feature
    except Exception:
        pass
    return 0.0


def get_prior_day_pattern(
    asset_name: str,
    bars_daily: pd.DataFrame | None = None,
    *,
    _bias_cache: dict[str, Any] | None = None,
) -> float:
    """Return normalised prior-day candle pattern ordinal [0, 1].

    Uses the ordinal encoding from ``bias_analyzer.CANDLE_PATTERN_ORDINAL``:
        inside=0, doji=1, engulfing_bull=2, engulfing_bear=3, hammer=4,
        shooting_star=5, strong_close_up=6, strong_close_down=7,
        outside_day=8, neutral=9.
    Normalised as ordinal / 9.

    Falls back to 1.0 (neutral=9/9) if unavailable.
    """
    if _bias_cache is not None and asset_name in _bias_cache:
        bias = _bias_cache[asset_name]
        return getattr(bias, "candle_pattern_feature", 1.0)
    try:
        from trading.strategies.daily.bias_analyzer import compute_daily_bias

        if bars_daily is not None and not bars_daily.empty:
            bias = compute_daily_bias(asset_name, bars_daily)  # type: ignore[arg-type]
            return bias.candle_pattern_feature
    except Exception:
        pass
    return 1.0  # neutral pattern


def get_weekly_range_position(
    asset_name: str,
    bars_daily: pd.DataFrame | None = None,
    *,
    _bias_cache: dict[str, Any] | None = None,
) -> float:
    """Return where price sits within the prior week's H/L range [0, 1].

    0.0 = at weekly low, 1.0 = at weekly high.
    Falls back to 0.5 (midpoint) if unavailable.
    """
    if _bias_cache is not None and asset_name in _bias_cache:
        bias = _bias_cache[asset_name]
        return getattr(bias, "weekly_range_feature", 0.5)
    try:
        from trading.strategies.daily.bias_analyzer import compute_daily_bias

        if bars_daily is not None and not bars_daily.empty:
            bias = compute_daily_bias(asset_name, bars_daily)  # type: ignore[arg-type]
            return bias.weekly_range_feature
    except Exception:
        pass
    return 0.5


def get_monthly_trend_score(
    asset_name: str,
    bars_daily: pd.DataFrame | None = None,
    *,
    _bias_cache: dict[str, Any] | None = None,
) -> float:
    """Return normalised monthly trend score [0, 1].

    Raw score is the slope of the 20-day EMA on daily bars, in [-1, +1].
    Mapped to [0, 1] as (raw + 1) / 2.
    Falls back to 0.5 (flat) if unavailable.
    """
    if _bias_cache is not None and asset_name in _bias_cache:
        bias = _bias_cache[asset_name]
        return getattr(bias, "monthly_trend_feature", 0.5)
    try:
        from trading.strategies.daily.bias_analyzer import compute_daily_bias

        if bars_daily is not None and not bars_daily.empty:
            bias = compute_daily_bias(asset_name, bars_daily)  # type: ignore[arg-type]
            return bias.monthly_trend_feature
    except Exception:
        pass
    return 0.5


def get_crypto_momentum_score(
    ticker: str,
    bars_1m: pd.DataFrame | None = None,
) -> float:
    """Return normalised crypto momentum score [0, 1] for the CNN.

    Raw score from ``crypto_momentum.CryptoMomentumSignal.to_tabular_feature()``
    is in [-1, +1].  Mapped to [0, 1] as (raw + 1) / 2.

    For non-crypto assets, this captures whether crypto momentum is leading
    the broader risk-on/risk-off move.  Returns 0.5 (neutral) if unavailable.
    """
    try:
        from analysis.crypto_momentum import compute_crypto_momentum

        signal = compute_crypto_momentum(ticker)
        if signal is not None:
            raw = signal.to_tabular_feature()  # [-1, +1]
            return max(0.0, min(1.0, (raw + 1.0) / 2.0))
    except Exception:
        pass
    return 0.5
