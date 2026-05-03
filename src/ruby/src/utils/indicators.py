"""
utils/indicators.py
====================
Pure, stateless indicator functions extracted from main.py.

All functions take DataFrames / scalars and return computed values.
No I/O, no async, no exchange calls — safe to call from any context
including Optuna trial closures and unit tests.
"""

from __future__ import annotations

from collections import deque

import pandas as pd

# ═══════════════════════════════════════════════════════════════════
# Candle construction
# ═══════════════════════════════════════════════════════════════════


def build_candles(trades_deque: deque | list, min_ticks: int = 60) -> pd.DataFrame:
    """Build 5-second OHLCV candles from a tick stream.

    Args:
        trades_deque: Iterable of dicts with keys: timestamp (ms), price, qty.
        min_ticks:    Minimum number of ticks required; returns empty DF otherwise.

    Returns:
        DataFrame with columns: open, high, low, close, volume, hl2.
        Empty DataFrame when there are not enough ticks.
    """
    if len(trades_deque) < min_ticks:
        return pd.DataFrame()

    df = pd.DataFrame(list(trades_deque))
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)

    ohlc = df["price"].resample("5s").ohlc()
    ohlc["high"] = df["price"].resample("5s").max()
    ohlc["low"] = df["price"].resample("5s").min()
    ohlc["volume"] = df["qty"].resample("5s").sum()
    ohlc["hl2"] = (ohlc["high"] + ohlc["low"]) / 2
    ohlc["open"] = df["price"].resample("5s").first()
    return ohlc.dropna()


# ═══════════════════════════════════════════════════════════════════
# Formatting helpers
# ═══════════════════════════════════════════════════════════════════


def fmt_price(value: float) -> str:
    """Format a price with enough decimal places for sub-penny assets."""
    if abs(value) < 0.01:
        return f"{value:.8f}"
    if abs(value) < 1.0:
        return f"{value:.6f}"
    return f"{value:.4f}"


# ═══════════════════════════════════════════════════════════════════
# Core indicators
# ═══════════════════════════════════════════════════════════════════


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range using Wilder's EMA smoothing.

    Args:
        df:     OHLCV DataFrame with columns high, low, close.
        period: ATR period (default 14).

    Returns:
        Series of ATR values, same index as *df*.
    """
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def compute_ao(df: pd.DataFrame, fast: int = 5, slow: int = 34) -> float:
    """Awesome Oscillator: SMA(hl2, fast) - SMA(hl2, slow).

    Returns:
        Scalar float — value of the last bar. 0.0 when not enough data.
    """
    if len(df) < slow:
        return 0.0
    ao = df["hl2"].rolling(fast).mean() - df["hl2"].rolling(slow).mean()
    return float(ao.iloc[-1])


def compute_vol_pct(
    df: pd.DataFrame,
    atr_period: int = 14,
    lookback: int = 200,
) -> float:
    """Volatility percentile in [0.0, 1.0].

    0.0 = historically calm; 1.0 = historically extreme.

    Implementation notes:
      - Warmup guard: requires (atr_period + lookback) bars.  Returns 0.5
        (neutral) while warming up.
      - Flat / illiquid guard: when ATR spread < 1% of its range the asset
        is effectively range-less.  Returns 0.25 (low-vol conservative) so
        sizing and TP logic remain cautious.
      - Uses interpolated rank (percentileofscore kind='mean') to break ties
        gracefully, clamped to [0.05, 0.95].

    Args:
        df:         OHLCV DataFrame.
        atr_period: ATR smoothing period.
        lookback:   Number of ATR bars used for the percentile window.

    Returns:
        Float in [0.05, 0.95] (or 0.5 during warmup).
    """
    warmup = atr_period + lookback
    if len(df) < warmup:
        return 0.5

    atr = compute_atr(df, atr_period).dropna()
    recent = atr.values[-lookback:]
    cur = float(atr.iloc[-1])

    atr_min, atr_max = float(recent.min()), float(recent.max())
    if atr_max < 1e-12 or (atr_max - atr_min) / atr_max < 0.01:
        return 0.25

    n = len(recent)
    strict_below = float((recent < cur).sum())
    at_or_below = float((recent <= cur).sum())
    pct = (strict_below + at_or_below) / (2.0 * n)

    return max(0.05, min(0.95, pct))


def compute_regime(
    df: pd.DataFrame,
    sma_period: int = 200,
    slope_lookback: int = 20,
    slope_threshold: float = 1.0,
    vol_volatile: float = 1.5,
    vol_ranging: float = 0.8,
) -> tuple[str, float]:
    """Classify the current market regime.

    Returns one of: TRENDING_UP, TRENDING_DOWN, VOLATILE, RANGING, NEUTRAL.

    Args:
        df:              OHLCV DataFrame with column 'close'.
        sma_period:      Period for the trend SMA.
        slope_lookback:  Bars over which to measure SMA slope.
        slope_threshold: Normalised slope magnitude that defines a trend.
        vol_volatile:    Normalised vol ratio above which → VOLATILE.
        vol_ranging:     Normalised vol ratio below which → RANGING.

    Returns:
        Tuple of (regime_string, diagnostic_value).
        Returns ("NEUTRAL", 0.0) when there is insufficient history.
    """
    min_bars = sma_period + slope_lookback
    if len(df) < min_bars:
        return "NEUTRAL", 0.0

    ma = df["close"].rolling(sma_period).mean()
    avg_chg = ma.diff().abs().rolling(100).mean()
    slope = (ma - ma.shift(slope_lookback)) / (avg_chg * slope_lookback + 1e-10)
    slope_n = float(slope.iloc[-1])

    ret_s = df["close"].pct_change().rolling(100).std()
    ret_sma = ret_s.rolling(50).mean()
    vol_n = float(ret_s.iloc[-1] / (ret_sma.iloc[-1] + 1e-10))

    if slope_n > slope_threshold:
        return "TRENDING_UP", slope_n
    if slope_n < -slope_threshold:
        return "TRENDING_DOWN", slope_n
    if vol_n > vol_volatile:
        return "VOLATILE", vol_n
    if vol_n < vol_ranging:
        return "RANGING", vol_n
    return "NEUTRAL", vol_n


# ═══════════════════════════════════════════════════════════════════
# Wave analysis
# ═══════════════════════════════════════════════════════════════════


def update_wave_state(
    df: pd.DataFrame,
    ws: WaveState,  # noqa: F821  (imported by callers from utils.state)
    ema_period: int = 20,
    rma_alpha: float = 0.1,
) -> WaveState:  # noqa: F821
    """Update the WaveState with the latest candles.

    Wave speed = cumulative (c_rma - o_rma) within each EMA-cross wave.
    Bear→Bull cross → record trough → bear_waves.
    Bull→Bear cross → record peak  → bull_waves.
    wave_ratio = bull_avg / |bear_avg|

    Stacking gate:
        wave_ratio > 1.0 → bull momentum harder → safe to add longs.
        wave_ratio < 1.0 → bear momentum harder → safe to add shorts.

    Args:
        df:         OHLCV DataFrame (≥ 40 bars recommended).
        ws:         Mutable WaveState instance (modified in-place and returned).
        ema_period: Period for the reference EMA.
        rma_alpha:  Smoothing factor for the RMA (smaller = slower).

    Returns:
        The same WaveState instance, updated.
    """
    if len(df) < 40:
        return ws

    ema = df["close"].ewm(span=ema_period, adjust=False).mean()
    c_rma = df["close"].ewm(alpha=rma_alpha, adjust=False).mean()
    o_rma = df["open"].ewm(alpha=rma_alpha, adjust=False).mean()
    speed_series = c_rma - o_rma

    above_now = bool(df["close"].iloc[-1] > ema.iloc[-1])
    above_prev = bool(df["close"].iloc[-2] > ema.iloc[-2])
    just_crossed = above_now != above_prev

    if just_crossed:
        lookback = min(50, len(speed_series) - 1)
        wave_speeds = speed_series.iloc[-lookback:].values
        if above_now:
            ws.bear_waves.append(float(wave_speeds.min()))
        else:
            ws.bull_waves.append(float(wave_speeds.max()))

    bull_list = list(ws.bull_waves)
    bear_list = list(ws.bear_waves)
    bull_avg = sum(bull_list) / len(bull_list) if bull_list else 0.0001
    bear_avg = abs(sum(bear_list) / len(bear_list)) if bear_list else 0.0001

    ws.wave_ratio = bull_avg / bear_avg if bear_avg > 0 else 1.0
    ws.bias = "Bullish" if bull_avg > bear_avg else "Bearish"

    cur_speed = float(speed_series.iloc[-1])
    ws.rma_speed = cur_speed
    if cur_speed >= 0:
        ws.cur_ratio = cur_speed / bull_avg if bull_avg > 0 else 1.0
    else:
        ws.cur_ratio = -(abs(cur_speed) / bear_avg) if bear_avg > 0 else -1.0

    ws.wr_history.append(ws.wave_ratio)
    ws.mom_history.append(abs(ws.cur_ratio))
    wr_arr = list(ws.wr_history)
    mom_arr = list(ws.mom_history)
    ws.wr_pct = sum(v < ws.wave_ratio for v in wr_arr) / max(len(wr_arr), 1)
    ws.mom_pct = sum(v < abs(ws.cur_ratio) for v in mom_arr) / max(len(mom_arr), 1)

    ws.last_above = above_now
    return ws


# ═══════════════════════════════════════════════════════════════════
# Quality score
# ═══════════════════════════════════════════════════════════════════


def compute_quality(
    df: pd.DataFrame,
    ao: float,
    vol_pct: float,
    fast_ema: float,
    slow_ema: float,
    imbalance: float,
    regime: str,
    quality_cfg=None,
) -> float:
    """
    Quality Score 0–100, adapted for 24/7 crypto futures.

    1. AO confirms EMA direction          → 20 pts
    2. Close on correct side of fast EMA  → 15 pts
    3. Book imbalance confirms direction  → 20 pts  (replaces VWAP)
    4. Volume above vol-adjusted average  → 25 pts
    5. Regime aligns with direction       → 20 pts  (replaces ORB)
       (partial credit in RANGING/NEUTRAL → 10 pts)
    """
    if len(df) < 35:
        return 0.0

    close = float(df["close"].iloc[-1])
    volume = float(df["volume"].iloc[-1])
    vol_avg = float(df["volume"].rolling(20).mean().iloc[-1])
    bull_bias = fast_ema > slow_ema

    # Vol multiplier for volume comparison
    if quality_cfg is not None:
        vm_high = quality_cfg.vol_mult_high
        vm_mid = quality_cfg.vol_mult_mid
        vm_low = quality_cfg.vol_mult_low
        neutral_credit = quality_cfg.neutral_regime_credit
    else:
        vm_high, vm_mid, vm_low = 1.8, 1.2, 0.8
        neutral_credit = 10.0

    vol_mult = vm_high if vol_pct >= 0.6 else vm_mid if vol_pct >= 0.4 else vm_low

    score = 0.0
    score += 20.0 if (bull_bias and ao > 0) or (not bull_bias and ao < 0) else 0.0
    score += (
        15.0 if (bull_bias and close > fast_ema) or (not bull_bias and close < fast_ema) else 0.0
    )
    score += (
        20.0 if (bull_bias and imbalance >= 1.2) or (not bull_bias and imbalance <= 0.8) else 0.0
    )
    score += 25.0 if volume > vol_avg * vol_mult else 0.0

    if bull_bias and regime == "TRENDING_UP":
        score += 20.0
    elif not bull_bias and regime == "TRENDING_DOWN":
        score += 20.0
    elif regime in ("NEUTRAL", "RANGING"):
        score += float(neutral_credit)

    return min(score, 100.0)


# ═══════════════════════════════════════════════════════════════════
# Adaptive sizing helpers
# ═══════════════════════════════════════════════════════════════════


def adaptive_tp(
    vol_pct: float,
    regime: str,
    tp_pct_base: float,
    vol_cfg=None,
) -> float:
    """Scale TP_PCT_BASE by regime and volatility percentile.

    Regime multiplier guide:
        RANGING   → 0.7–1.0×  (collect small wins quickly)
        NEUTRAL   → 1.0–1.3×
        VOLATILE  → 1.2–1.7×  (give room so normal swings don't stop you out)
        TRENDING  → 1.4–2.0×  (ride the wave)

    Args:
        vol_pct:      Current volatility percentile [0, 1].
        regime:       Current regime string.
        tp_pct_base:  Base TP percentage before scaling.
        vol_cfg:      Optional config with tp_multipliers dict.

    Returns:
        Scaled TP percentage.
    """
    if vol_cfg is not None and vol_cfg.tp_multipliers:
        mults = vol_cfg.tp_multipliers
        if regime in ("TRENDING_UP", "TRENDING_DOWN") and "trending" in mults:
            m = mults["trending"]
            mult = m.base + vol_pct * m.vol_scale
        elif regime == "VOLATILE" and "volatile" in mults:
            m = mults["volatile"]
            mult = m.base + vol_pct * m.vol_scale
        elif regime == "RANGING" and "ranging" in mults:
            m = mults["ranging"]
            mult = m.base + vol_pct * m.vol_scale
        elif "neutral" in mults:
            m = mults["neutral"]
            mult = m.base + vol_pct * m.vol_scale
        else:
            mult = 1.0 + vol_pct * 0.3
    else:
        if regime in ("TRENDING_UP", "TRENDING_DOWN"):
            mult = 1.4 + vol_pct * 0.6
        elif regime == "VOLATILE":
            mult = 1.2 + vol_pct * 0.5
        elif regime == "RANGING":
            mult = 0.7 + vol_pct * 0.3
        else:
            mult = 1.0 + vol_pct * 0.3

    return tp_pct_base * mult


def adaptive_add_threshold(vol_pct: float, base: float) -> float:
    """Price retrace fraction required before we add another position.

    Higher volatility → wider threshold (0.20%–0.40% typical).

    Args:
        vol_pct: Current volatility percentile [0, 1].
        base:    Base threshold percentage.

    Returns:
        Scaled threshold.
    """
    return base * (1.0 + vol_pct)


# ═══════════════════════════════════════════════════════════════════
# Entry gates
# ═══════════════════════════════════════════════════════════════════


def wave_gate_ok(ws: WaveState, direction: str, gate: float) -> bool:  # noqa: F821
    """Return True when wave momentum favours an additional stack entry.

    Mirrors the Pine Script waveOK_L / waveOK_S gates.

    Args:
        ws:        Current WaveState.
        direction: "buy" or "sell".
        gate:      Minimum wr_pct threshold (e.g. 0.55).

    Returns:
        True → allow the add; False → skip.
    """
    if direction == "buy":
        return ws.wr_pct >= gate and ws.cur_ratio > 0
    return ws.wr_pct <= (1.0 - gate) and ws.cur_ratio < 0


def regime_stack_ok(regime: str, direction: str) -> bool:
    """Return True when the regime allows a stack add in *direction*.

    Blocks counter-trend adds only; first entries are allowed in any regime.

    Args:
        regime:    Current regime string.
        direction: "buy" or "sell".

    Returns:
        False when adding would be counter-trend (e.g. buying in TRENDING_DOWN).
    """
    if direction == "buy" and regime == "TRENDING_DOWN":
        return False
    if direction == "sell" and regime == "TRENDING_UP":
        return False
    return True
