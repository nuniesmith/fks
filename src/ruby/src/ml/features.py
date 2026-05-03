"""
ml/features.py — Feature extraction for the futures CNN.

Produces a (n_features, window_size) float32 tensor from a candle
DataFrame plus live market state.  Every feature is normalised to a
roughly [-1, 1] or [0, 1] range so the CNN receives consistent input
regardless of the asset's price level.

Feature vector (20 channels, one value per candle bar)
-------------------------------------------------------
 0  log_return        log(close_t / close_{t-1})
 1  norm_close        z-score of close over the window
 2  norm_atr          ATR-14 / close  (volatility relative to price)
 3  volume_ratio      volume / 20-bar rolling mean volume
 4  rsi               RSI-14 / 100  → [0, 1]
 5  range_tightness   rolling(max_H - min_L, 20) / (ATR + ε) / 5.0, clipped [0, 1]
                       → small = tight consolidation, large = trending/wide range
 6  close_vs_range    (close - rolling_min_L_20) / (rolling_max_H_20 - rolling_min_L_20 + ε)
                       → [0, 1]: 0 = bottom of 20-bar range, 1 = top of range
 7  book_imbalance    bid_vol / (bid_vol + ask_vol)  — scalar broadcast to window
 8  wave_ratio        WaveState.wave_ratio normalised to [-1, 1]
 9  vol_percentile    ATR percentile [0, 1]
10  body_ratio        |close - open| / (high - low + ε)
11  upper_wick        (high - max(open, close)) / (high - low + ε)
12  lower_wick        (min(open, close) - low) / (high - low + ε)
13  candle_dir        +1 bullish, -1 bearish, 0 doji  (sign of close - open)
14  hurst_exponent    R/S rescaled-range Hurst exponent [0, 1]
                       → <0.4 mean-reverting, ≈0.5 random walk, >0.6 trending
15  atr_trend         ATR expanding(1.0) vs contracting(0.0) over last 10 bars
                       → recent-half mean TR / older-half mean TR, normalised [0, 1]
16  volume_trend      linear regression slope of last 5 volume bars [0, 1]
                       → rising volume >0.5, flat ≈0.5, falling <0.5
17  norm_velocity     3-bar momentum / rolling_std → clipped/scaled to [-1, 1]
                       → detects momentum exhaustion before price reversal
18  price_acceleration  change of velocity (2nd derivative) → [-1, 1]
                       → signals trend deceleration / acceleration
19  market_phase      structural phase: 0.0 ACCUMULATION, 0.33 UPTREND,
                       0.67 DOWNTREND, 1.00 DISTRIBUTION

Channels removed (vs previous 15-channel version)
--------------------------------------------------
  ao_norm       — Awesome Oscillator / close: derived from EMA crossovers used in
                  label generation → label/feature leakage.
  fast_ema_dist — (close - fast_ema) / close: directly used in label generation
                  → label/feature leakage.
  slow_ema_dist — (close - slow_ema) / close: directly used in label generation
                  → label/feature leakage.

Usage
-----
    from ml.features import extract_features

    tensor = extract_features(
        candles=candles,           # pd.DataFrame with OHLCV columns
        imbalance=imbalance,       # float from order book
        vol_pct=vol_pct,           # float [0, 1] from compute_vol_pct()
        wave_ratio=wave_state.wave_ratio,
        window=60,
    )
    # tensor.shape == (20, 60)  — ready for CNN input
"""

from __future__ import annotations

import numpy as np
import pandas as pd

N_FEATURES = 20
DEFAULT_WINDOW = 60

# Consolidation / breakout-context window (bars)
_CONSOL_BARS = 20

# Indicator periods
_RSI_PERIOD = 14
_ATR_PERIOD = 14
_AO_FAST = 5
_AO_SLOW = 34

# Kept for backward compatibility (no longer used internally)
_DEFAULT_FAST = 8
_DEFAULT_SLOW = 21


# ---------------------------------------------------------------------------
# Internal helpers — all operate on numpy arrays for speed
# ---------------------------------------------------------------------------


def _ema_np(arr: np.ndarray, span: int) -> np.ndarray:
    """Exponential moving average using pandas ewm (matches bot formula)."""
    s = pd.Series(arr)
    return s.ewm(span=span, adjust=False).mean().to_numpy(dtype=np.float32)


def _rsi(close: np.ndarray, period: int = _RSI_PERIOD) -> np.ndarray:
    """Wilder-smoothed RSI, returns array in [0, 100]."""
    if len(close) < period + 1:
        return np.full(len(close), 50.0, dtype=np.float32)

    delta = np.diff(close.astype(np.float64))
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)

    # Seed with simple average for first period
    avg_gain = np.zeros(len(delta), dtype=np.float64)
    avg_loss = np.zeros(len(delta), dtype=np.float64)
    avg_gain[period - 1] = gain[:period].mean()
    avg_loss[period - 1] = loss[:period].mean()

    alpha = 1.0 / period
    for i in range(period, len(delta)):
        avg_gain[i] = avg_gain[i - 1] * (1 - alpha) + gain[i] * alpha
        avg_loss[i] = avg_loss[i - 1] * (1 - alpha) + loss[i] * alpha

    rs = np.where(avg_loss == 0, 100.0, avg_gain / (avg_loss + 1e-10))
    rsi = 100.0 - 100.0 / (1.0 + rs)

    # Prepend neutral (50) for the first bar where diff is undefined
    rsi_full = np.full(len(close), 50.0, dtype=np.float32)
    rsi_full[1:] = rsi.astype(np.float32)
    return rsi_full


def _atr(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = _ATR_PERIOD
) -> np.ndarray:
    """ATR using EWM smoothing (matches bot helpers.py)."""
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]

    tr = np.maximum(
        high - low,
        np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
    )
    return _ema_np(tr, period)


def _ao(
    high: np.ndarray, low: np.ndarray, fast: int = _AO_FAST, slow: int = _AO_SLOW
) -> np.ndarray:
    """Awesome Oscillator: SMA(median, fast) - SMA(median, slow).

    Kept as a module-level helper for any external callers; no longer used
    inside extract_features() as of the 14-channel feature set.
    """
    median = (high + low) / 2.0
    s = pd.Series(median)
    ao_fast = s.rolling(fast).mean().to_numpy(dtype=np.float32)
    ao_slow = s.rolling(slow).mean().to_numpy(dtype=np.float32)
    result = ao_fast - ao_slow
    result = np.nan_to_num(result, nan=0.0)
    return result


def _rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    s = pd.Series(arr)
    return s.rolling(window, min_periods=1).mean().to_numpy(dtype=np.float32)


def _rolling_std(arr: np.ndarray, window: int) -> np.ndarray:
    s = pd.Series(arr)
    return s.rolling(window, min_periods=2).std().fillna(1.0).to_numpy(dtype=np.float32)


def _rolling_max(arr: np.ndarray, window: int) -> np.ndarray:
    s = pd.Series(arr)
    return s.rolling(window, min_periods=1).max().to_numpy(dtype=np.float32)


def _rolling_min(arr: np.ndarray, window: int) -> np.ndarray:
    s = pd.Series(arr)
    return s.rolling(window, min_periods=1).min().to_numpy(dtype=np.float32)


def _hurst_exponent(close: np.ndarray, max_lag: int = 20) -> np.ndarray:
    """Compute a rolling Hurst exponent for every bar using the R/S method.

    Returns an array of shape (n,) with values in [0, 1].
    Falls back to 0.5 (random walk) when there is not enough data.

    H < 0.5 → mean-reverting / choppy
    H ≈ 0.5 → random walk
    H > 0.5 → trending / persistent
    """
    n = len(close)
    result = np.full(n, 0.5, dtype=np.float32)

    min_bars = max_lag * 2 + 1
    for t in range(min_bars, n):
        prices = close[max(0, t - max_lag * 2) : t + 1]
        lags = range(2, max_lag + 1)
        log_lags: list[float] = []
        log_rs: list[float] = []
        for lag in lags:
            chunks = len(prices) // lag
            if chunks < 1:
                continue
            rs_values: list[float] = []
            for i in range(chunks):
                chunk = prices[i * lag : (i + 1) * lag]
                if len(chunk) < 2:
                    continue
                rets = np.diff(chunk.astype(np.float64))
                if len(rets) < 2:
                    continue
                mean_r = rets.mean()
                devs = np.cumsum(rets - mean_r)
                r = devs.max() - devs.min()
                s = rets.std(ddof=1)
                if s > 1e-12:
                    rs_values.append(r / s)
            if rs_values:
                log_lags.append(np.log(float(lag)))
                log_rs.append(np.log(np.mean(rs_values)))
        if len(log_lags) >= 3:
            try:
                coeffs = np.polyfit(log_lags, log_rs, 1)
                h = float(coeffs[0])
                result[t] = float(np.clip(h, 0.0, 1.0))
            except Exception:
                pass

    return result


def _atr_trend(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, lookback: int = 10
) -> np.ndarray:
    """Compare recent-half vs older-half mean TR to classify ATR expanding/contracting.

    Returns array in [0, 1]: 1.0 = expanding, 0.5 = flat, 0.0 = contracting.
    Defaults to 0.5 when there is not enough data.
    """
    n = len(close)
    result = np.full(n, 0.5, dtype=np.float32)
    if n < lookback + 1:
        return result

    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(
        high - low,
        np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
    )

    half = lookback // 2
    for t in range(lookback, n):
        window_tr = tr[t - lookback + 1 : t + 1]
        older_mean = float(window_tr[:half].mean())
        recent_mean = float(window_tr[half:].mean())
        if older_mean > 1e-12:
            ratio = recent_mean / older_mean
            # Map ratio: 0.5→0.0, 1.0→0.5, 1.5→1.0
            normalised = float(np.clip((ratio - 0.5) / 1.0, 0.0, 1.0))
            result[t] = normalised

    return result


def _volume_trend(volume: np.ndarray, lookback: int = 5) -> np.ndarray:
    """Linear-regression slope of volume over the last `lookback` bars, normalised [0, 1].

    Rising volume → >0.5, flat → ≈0.5, falling → <0.5.
    """
    n = len(volume)
    result = np.full(n, 0.5, dtype=np.float32)
    if n < lookback:
        return result

    x = np.arange(lookback, dtype=np.float64)
    x_mean = x.mean()
    x_denom = float(((x - x_mean) ** 2).sum())
    if x_denom < 1e-12:
        return result

    for t in range(lookback - 1, n):
        vol_window = volume[t - lookback + 1 : t + 1].astype(np.float64)
        vol_mean = vol_window.mean()
        if vol_mean < 1e-10:
            continue
        numerator = float(((x - x_mean) * (vol_window - vol_mean)).sum())
        slope = numerator / x_denom
        slope_pct = slope / vol_mean
        # Map [-0.3, +0.3] → [0.0, 1.0]
        normalised = float(np.clip((slope_pct + 0.3) / 0.6, 0.0, 1.0))
        result[t] = normalised

    return result


def _normalized_velocity(
    close: np.ndarray, momentum_bars: int = 3, norm_window: int = 100
) -> np.ndarray:
    """3-bar momentum normalized by rolling stdev, clipped and scaled to [-1, 1]."""
    n = len(close)
    result = np.zeros(n, dtype=np.float32)

    # Raw velocity: (close[i] - close[i-momentum_bars]) / (close[i-momentum_bars] + 1e-10)
    for i in range(momentum_bars, n):
        result[i] = (close[i] - close[i - momentum_bars]) / (close[i - momentum_bars] + 1e-10)

    # Rolling stdev for normalization
    vel_std = _rolling_std(result, norm_window)
    normalized = result / (vel_std + 1e-10)

    # Clip to [-3, 3] then scale to [-1, 1]
    return np.clip(normalized / 3.0, -1.0, 1.0).astype(np.float32)


def _price_acceleration(
    close: np.ndarray, momentum_bars: int = 3, norm_window: int = 100
) -> np.ndarray:
    """Change of velocity (second derivative), normalized and scaled to [-1, 1]."""
    n = len(close)
    velocity = np.zeros(n, dtype=np.float32)

    for i in range(momentum_bars, n):
        velocity[i] = (close[i] - close[i - momentum_bars]) / (close[i - momentum_bars] + 1e-10)

    # Acceleration = change in velocity over momentum_bars
    acceleration = np.zeros(n, dtype=np.float32)
    for i in range(momentum_bars * 2, n):
        acceleration[i] = velocity[i] - velocity[i - momentum_bars]

    # Normalize by rolling stdev of velocity
    vel_std = _rolling_std(velocity, norm_window)
    normalized = acceleration / (vel_std + 1e-10)

    # Clip to [-3, 3] then scale to [-1, 1]
    return np.clip(normalized / 3.0, -1.0, 1.0).astype(np.float32)


def _market_phase(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    ao_fast: int = 5,
    ao_slow: int = 34,
    lookback: int = 20,
) -> np.ndarray:
    """Encode market phase as a float feature in [0, 1].

    Uses Awesome Oscillator direction + price position relative to recent range:
      0.00 = ACCUMULATION (range-bound, neutral AO)
      0.33 = UPTREND (rising AO, price near highs)
      0.67 = DOWNTREND (falling AO, price near lows)
      1.00 = DISTRIBUTION (range-bound after uptrend, AO divergence)
    """
    n = len(close)
    result = np.full(n, 0.0, dtype=np.float32)

    # Compute AO
    ao = _ao(high, low, ao_fast, ao_slow)

    # Price position within recent range [0, 1]
    roll_high = _rolling_max(high, lookback)
    roll_low = _rolling_min(low, lookback)
    range_span = roll_high - roll_low + 1e-10
    price_pos = (close - roll_low) / range_span  # 0 = at lows, 1 = at highs

    # AO slope (change over last 3 bars)
    ao_slope = np.zeros(n, dtype=np.float32)
    for i in range(3, n):
        ao_slope[i] = ao[i] - ao[i - 3]

    # Range tightness for detecting accumulation/distribution
    atr = _atr(high, low, close)
    range_ratio = (roll_high - roll_low) / (atr + 1e-10)
    is_tight = range_ratio < 4.0  # tight range = consolidation

    for i in range(ao_slow + lookback, n):
        pp = float(price_pos[i])
        slope = float(ao_slope[i])
        tight = bool(is_tight[i])

        if tight and abs(slope) < float(np.abs(ao[max(0, i - lookback) : i + 1]).mean()) * 0.3:
            # Range-bound with weak AO momentum
            if pp > 0.6:
                result[i] = 1.0  # DISTRIBUTION (high price, tight range)
            else:
                result[i] = 0.0  # ACCUMULATION (low price, tight range)
        elif slope > 0 and pp > 0.5:
            result[i] = 0.33  # UPTREND
        elif slope < 0 and pp < 0.5:
            result[i] = 0.67  # DOWNTREND
        elif slope > 0 and pp < 0.5:
            result[i] = 0.0  # Accumulation with rising AO
        elif slope < 0 and pp > 0.5:
            result[i] = 1.0  # Distribution with falling AO
        else:
            result[i] = 0.0  # Default to accumulation

    return result


# ---------------------------------------------------------------------------
# Shared feature computation — single source of truth for all 20 channels
# ---------------------------------------------------------------------------


def _compute_channels(
    op: np.ndarray,
    hi: np.ndarray,
    lo: np.ndarray,
    cl: np.ndarray,
    vo: np.ndarray,
    imbalance: float,
    wave_ratio: float,
    vol_pct: float,
    window: int,
    training: bool = False,
) -> np.ndarray:
    """Compute all N_FEATURES channels over the given OHLCV arrays.

    Parameters
    ----------
    op, hi, lo, cl, vo : np.ndarray
        OHLCV arrays, all same length.
    imbalance : float
        Order-book bid/ask volume ratio.
    wave_ratio : float
        WaveState.wave_ratio value.
    vol_pct : float
        Volatility percentile [0, 1].
    window : int
        Window size for rolling stats.
    training : bool
        If True, channels 7-9 use random perturbation instead of constant
        broadcast.  This simulates realistic inference-time distributions
        during training so the CNN learns useful filters for these channels.

    Returns
    -------
    np.ndarray of shape (N_FEATURES, n) float32
    """
    n = len(cl)

    # ── Compute all indicators ────────────────────────────────────────────

    # 0  log_return
    log_ret = np.zeros(n, dtype=np.float32)
    log_ret[1:] = np.log(cl[1:] / (cl[:-1] + 1e-10)).astype(np.float32)

    # 1  norm_close  (z-score over rolling window)
    cl_mean = _rolling_mean(cl, window)
    cl_std = _rolling_std(cl, window)
    norm_close = (cl - cl_mean) / (cl_std + 1e-8)

    # 2  norm_atr
    atr = _atr(hi, lo, cl, _ATR_PERIOD)
    norm_atr = atr / (cl + 1e-10)

    # 3  volume_ratio
    vol_mean = _rolling_mean(vo, 20)
    volume_ratio = vo / (vol_mean + 1e-10)

    # 4  rsi  [0, 1]
    rsi = _rsi(cl, _RSI_PERIOD) / 100.0

    # 5  range_tightness — breakout-context: how compressed is the 20-bar range
    #    relative to ATR?  Small value → tight consolidation; large → trending/wide.
    #    Normalised by 5.0 (expected random-walk 20-bar range ≈ 4.5 ATR), clipped [0, 1].
    roll_high_20 = _rolling_max(hi, _CONSOL_BARS)
    roll_low_20 = _rolling_min(lo, _CONSOL_BARS)

    range_raw = (roll_high_20 - roll_low_20) / (atr + 1e-10)
    range_tightness = np.clip(range_raw / 5.0, 0.0, 1.0).astype(np.float32)

    # 6  close_vs_range — where does close sit within the 20-bar high/low range?
    #    0 = at the bottom, 1 = at the top.
    range_span = roll_high_20 - roll_low_20
    close_vs_range = (cl - roll_low_20) / (range_span + 1e-10)
    close_vs_range = np.clip(close_vs_range, 0.0, 1.0).astype(np.float32)

    # 7-9  book_imbalance, wave_ratio, vol_percentile
    #    These channels depend on live orderbook/wave/vol state which is
    #    unavailable in historical training data.
    if training:
        # During training, historical orderbook/wave/vol data isn't available.
        # Instead of broadcasting a constant (which teaches the CNN nothing),
        # generate realistic random walks so the CNN learns useful filters
        # for these channels at inference time.

        # Channel 7: book_imbalance — random walk around 0.5, bounded [0.05, 0.95]
        noise = np.cumsum(np.random.normal(0, 0.02, n))
        book_imbalance = np.clip(0.5 + noise, 0.05, 0.95).astype(np.float32)

        # Channel 8: wave_ratio — random walk around 0.0, bounded [-1, 1]
        noise = np.cumsum(np.random.normal(0, 0.03, n))
        wave_ratio_arr = np.clip(noise, -1.0, 1.0).astype(np.float32)

        # Channel 9: vol_percentile — random walk around 0.5, bounded [0.05, 0.95]
        noise = np.cumsum(np.random.normal(0, 0.02, n))
        vol_pct_arr = np.clip(0.5 + noise, 0.05, 0.95).astype(np.float32)
    else:
        # Live inference: use actual values, broadcast to window
        imb_01 = np.clip(imbalance / (imbalance + 1.0), 0.0, 1.0)
        book_imbalance = np.full(n, imb_01, dtype=np.float32)

        wr_norm = float(np.clip(wave_ratio, -3.0, 3.0)) / 3.0
        wave_ratio_arr = np.full(n, wr_norm, dtype=np.float32)

        vol_pct_arr = np.full(n, float(vol_pct), dtype=np.float32)

    # 10-12  candle shape features
    rng = hi - lo + 1e-10
    body_ratio = np.abs(cl - op) / rng
    upper_wick = (hi - np.maximum(op, cl)) / rng
    lower_wick = (np.minimum(op, cl) - lo) / rng

    # 13  candle direction
    candle_dir = np.sign(cl - op).astype(np.float32)

    # 14  hurst_exponent [0, 1] — R/S rescaled range
    hurst = _hurst_exponent(cl, max_lag=20)

    # 15  atr_trend [0, 1] — expanding vs contracting volatility
    atr_trend = _atr_trend(hi, lo, cl, lookback=10)

    # 16  volume_trend [0, 1] — 5-bar linear regression slope of volume
    vol_trend = _volume_trend(vo, lookback=5)

    # 17  normalized_velocity [-1, 1] — 3-bar momentum, stdev-normalized
    norm_velocity = _normalized_velocity(cl)

    # 18  price_acceleration [-1, 1] — change of velocity (2nd derivative)
    price_accel = _price_acceleration(cl)

    # 19  market_phase [0, 1] — structural market phase encoding
    market_ph = _market_phase(hi, lo, cl)

    # ── Stack into (N_FEATURES, n) ────────────────────────────────────────

    features_full = np.stack(
        [
            log_ret,  #  0
            norm_close,  #  1
            norm_atr,  #  2
            volume_ratio,  #  3
            rsi,  #  4
            range_tightness,  #  5
            close_vs_range,  #  6
            book_imbalance,  #  7
            wave_ratio_arr,  #  8
            vol_pct_arr,  #  9
            body_ratio,  # 10
            upper_wick,  # 11
            lower_wick,  # 12
            candle_dir,  # 13
            hurst,  # 14
            atr_trend,  # 15
            vol_trend,  # 16
            norm_velocity,  # 17
            price_accel,  # 18
            market_ph,  # 19
        ],
        axis=0,
    )  # shape: (N_FEATURES, n)

    # Clip outliers to keep input bounded
    features_full = np.clip(features_full, -3.0, 3.0)
    features_full = np.nan_to_num(features_full, nan=0.0, posinf=0.0, neginf=0.0)

    return features_full.astype(np.float32)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_features(
    candles: pd.DataFrame,
    imbalance: float = 1.0,
    vol_pct: float = 0.5,
    wave_ratio: float = 0.0,
    # deprecated params — kept for backward compat, ignored
    fast_ema: float | None = None,
    slow_ema: float | None = None,
    fast_period: int = _DEFAULT_FAST,
    slow_period: int = _DEFAULT_SLOW,
    window: int = DEFAULT_WINDOW,
) -> np.ndarray | None:
    """Extract a (N_FEATURES, window) float32 feature array from candle data.

    Parameters
    ----------
    candles:
        DataFrame produced by ``build_candles()``.  Must have columns
        ``open``, ``high``, ``low``, ``close``, ``volume``.
        Needs at least ``window + max(_CONSOL_BARS, _RSI_PERIOD, _ATR_PERIOD) + 5``
        rows for full indicator warmup; if fewer rows are available the
        function returns ``None``.
    imbalance:
        Current order-book bid/ask volume ratio (bid_vol / ask_vol).
        Converted to [0, 1] range internally.
    vol_pct:
        Volatility percentile [0, 1] from ``compute_vol_pct()``.
    wave_ratio:
        ``WaveState.wave_ratio`` value (typically 0-3, clipped then normalised).
    fast_ema, slow_ema:
        **Deprecated** — accepted for backward compatibility but ignored.
        Previously used for EMA-distance channels that caused label/feature
        leakage; those channels have been removed.
    fast_period, slow_period:
        **Deprecated** — accepted for backward compatibility but ignored.
        Previously used to compute EMA-distance channels.
    window:
        Number of bars to include in the output tensor (time dimension).

    Returns
    -------
    np.ndarray of shape (N_FEATURES, window) or None if there is not
    enough data to compute all indicators.
    """
    min_rows = window + max(_CONSOL_BARS, _RSI_PERIOD, _ATR_PERIOD) + 5
    if candles is None or len(candles) < min_rows:
        return None

    # Work on the tail we actually need (extra warmup + window)
    warmup = max(_CONSOL_BARS, _RSI_PERIOD, _ATR_PERIOD) + 5
    tail = candles.tail(window + warmup).copy()

    try:
        op = tail["open"].astype(np.float32).to_numpy()
        hi = tail["high"].astype(np.float32).to_numpy()
        lo = tail["low"].astype(np.float32).to_numpy()
        cl = tail["close"].astype(np.float32).to_numpy()
        vo = tail["volume"].astype(np.float32).to_numpy()
    except KeyError:
        return None

    features_full = _compute_channels(
        op,
        hi,
        lo,
        cl,
        vo,
        imbalance=imbalance,
        wave_ratio=wave_ratio,
        vol_pct=vol_pct,
        window=window,
        training=False,  # live inference always uses real values
    )

    # Take the last `window` columns (most recent bars)
    out = features_full[:, -window:].astype(np.float32)

    if out.shape != (N_FEATURES, window):
        return None

    # Replace any remaining NaN/Inf with 0
    out = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)

    return out


def precompute_all_features(
    candles: pd.DataFrame,
    imbalance: float = 1.0,
    vol_pct: float = 0.5,
    wave_ratio: float = 0.0,
    window: int = DEFAULT_WINDOW,
    training: bool = False,
) -> np.ndarray | None:
    """Precompute all feature channels over an entire DataFrame.

    Unlike ``extract_features`` which slices a single window, this function
    computes indicators over every bar and returns the full-length array.
    This allows ``AssetDataset`` to precompute once in ``__init__`` and
    then cheaply slice windows in ``__getitem__``.

    Parameters
    ----------
    candles : pd.DataFrame
        Full OHLCV DataFrame with columns: open, high, low, close, volume.
    imbalance : float
        Order-book bid/ask ratio (broadcast as constant).
    vol_pct : float
        Volatility percentile [0, 1] (broadcast as constant).
    wave_ratio : float
        Wave ratio (broadcast as constant).
    window : int
        Window size, used only for norm_close rolling stats.
    training : bool
        If True, channels 7-9 (book_imbalance, wave_ratio, vol_percentile)
        use random-walk perturbation instead of constant broadcast.  This
        fixes the train/inference distribution mismatch: during training
        these values are always constant (0.5, 0.0, 0.5) because historical
        orderbook/wave/vol data is unavailable, but at inference they vary
        with real market state.  Random walks teach the CNN to use these
        channels rather than ignore them.

    Returns
    -------
    np.ndarray of shape (N_FEATURES, len(candles)) float32, or None.
    """
    min_rows = max(_CONSOL_BARS, _RSI_PERIOD, _ATR_PERIOD) + 5
    if candles is None or len(candles) < min_rows:
        return None

    try:
        op = candles["open"].astype(np.float32).to_numpy()
        hi = candles["high"].astype(np.float32).to_numpy()
        lo = candles["low"].astype(np.float32).to_numpy()
        cl = candles["close"].astype(np.float32).to_numpy()
        vo = candles["volume"].astype(np.float32).to_numpy()
    except KeyError:
        return None

    return _compute_channels(
        op,
        hi,
        lo,
        cl,
        vo,
        imbalance=imbalance,
        wave_ratio=wave_ratio,
        vol_pct=vol_pct,
        window=window,
        training=training,
    )


def feature_names() -> list[str]:
    """Return the ordered list of feature channel names."""
    return [
        "log_return",  #  0
        "norm_close",  #  1
        "norm_atr",  #  2
        "volume_ratio",  #  3
        "rsi",  #  4
        "range_tightness",  #  5
        "close_vs_range",  #  6
        "book_imbalance",  #  7
        "wave_ratio",  #  8
        "vol_percentile",  #  9
        "body_ratio",  # 10
        "upper_wick",  # 11
        "lower_wick",  # 12
        "candle_dir",  # 13
        "hurst_exponent",  # 14
        "atr_trend",  # 15
        "volume_trend",  # 16
        "norm_velocity",  # 17
        "price_acceleration",  # 18
        "market_phase",  # 19
    ]
