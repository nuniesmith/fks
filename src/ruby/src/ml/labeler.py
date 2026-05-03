"""
ml/labeler.py — Training label generation from historical OHLCV klines.

Strategy
--------
For every bar in a historical klines DataFrame we:

1. Compute the same entry signal the live bot uses:
       EMA fast > EMA slow  +  AO > 0   →  long candidate
       EMA fast < EMA slow  +  AO < 0   →  short candidate
       otherwise                         →  flat (no signal)

2. When a candidate signal exists, walk forward bar-by-bar from that
   point and check which occurs first:
       • TP hit  (price moves tp_pct in the signal direction)  → win
       • SL hit  (price moves sl_pct against the signal)       → loss
       • Timeout (neither hit within max_bars)                 → flat

3. Assign a 3-class label:
       0  flat   — no signal, or signal timed out without outcome
       1  long   — long signal that hit TP before SL
       2  short  — short signal that hit TP before SL

The resulting labels are intentionally conservative:
   • Signals that lost (hit SL first) are labelled flat=0 so the CNN
     learns to avoid those patterns, not to trade them short.
   • Signals that timed out are also labelled flat=0.

This gives a class distribution that is typically 70–85 % flat and
5–15 % each for long/short.  Use class_weight in the loss function
or WeightedRandomSampler in the DataLoader to compensate.

Usage
-----
    import ccxt
    import pandas as pd
    from ml.labeler import fetch_klines, generate_labels

    exchange = ccxt.kucoinfutures({"enableRateLimit": True})
    df = fetch_klines(exchange, "XBTUSDTM", timeframe="1m", limit=10_000)
    labels = generate_labels(df, tp_pct=0.004, sl_pct=0.0035, max_bars=60)
    # labels.shape == (len(df),)  dtype int64  values in {0, 1, 2}
"""

from __future__ import annotations

import logging
import math
import time as _time
from typing import Any

import numpy as np
import pandas as pd
from tqdm import tqdm

logger = logging.getLogger(__name__)

# ── Label constants ───────────────────────────────────────────────────────────

LABEL_FLAT: int = 0
LABEL_LONG: int = 1
LABEL_SHORT: int = 2
LABEL_LOSS: int = 3

# ── Defaults (should match futures.yaml strategy section) ────────────────────

DEFAULT_FAST_EMA: int = 8
DEFAULT_SLOW_EMA: int = 21
DEFAULT_AO_FAST: int = 5
DEFAULT_AO_SLOW: int = 34
DEFAULT_TP_PCT: float = 0.004
DEFAULT_SL_PCT: float = 0.0035
DEFAULT_MAX_BARS: int = 60  # bars to look forward before labelling as timeout

# ── Breakout-based labeling defaults ─────────────────────────────────────────
#
# Tuned for 1-minute crypto futures (KuCoin).  Empirical range/ATR ratios on
# 20-bar windows:  BTC med=6.8, ETH med=6.1, DOGE med=7.0, PEPE med=6.2.
# The old 2.5× threshold filtered 100% of bars — zero consolidations found.
# 5.5× lets ~25-40% of bars qualify, yielding ~1-3% long/short labels.

DEFAULT_CONSOLIDATION_BARS: int = 20  # bars in the consolidation lookback
DEFAULT_CONSOLIDATION_ATR_MULT: float = 5.5  # max range/ATR ratio to qualify as consolidation
DEFAULT_MAX_BREAKOUT_WAIT: int = 40  # bars to scan forward for a breakout
DEFAULT_TP_ATR_MULT: float = 1.5  # TP = entry ± tp_atr_mult × ATR
DEFAULT_SL_ATR_MULT: float = 1.0  # SL = entry ∓ sl_atr_mult × ATR  (1.5:1 R:R)
DEFAULT_MAX_HOLD_BARS: int = 90  # bars to walk forward from breakout entry
DEFAULT_ATR_PERIOD: int = 14  # ATR smoothing period


# ── Internal helpers ─────────────────────────────────────────────────────────


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _ao(high: pd.Series, low: pd.Series, fast: int, slow: int) -> pd.Series:
    median = (high + low) / 2.0
    return median.rolling(fast).mean() - median.rolling(slow).mean()


def _atr_arr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> np.ndarray:
    """Return an EWM-smoothed ATR array aligned with df rows.

    True Range = max(H-L, |H-Cprev|, |L-Cprev|)
    ATR = EWM(TR, span=period, adjust=False)
    """
    hi = high.astype(np.float64)
    lo = low.astype(np.float64)
    cl = close.astype(np.float64)

    prev_cl = cl.shift(1).fillna(cl)
    tr = pd.concat(
        [hi - lo, (hi - prev_cl).abs(), (lo - prev_cl).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()
    return atr.to_numpy(dtype=np.float64)


def _breakout_label_outcomes(
    close_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    atr_arr: np.ndarray,
    consolidation_bars: int,
    consolidation_atr_mult: float,
    max_breakout_wait: int,
    tp_atr_mult: float,
    sl_atr_mult: float,
    max_hold_bars: int,
) -> np.ndarray:
    """Walk-forward breakout labeler — pure NumPy, no EMA/AO signals.

    For each bar ``i``:
      1. Measure the rolling high/low over the last ``consolidation_bars`` bars.
      2. If (range_high - range_low) / ATR > ``consolidation_atr_mult`` → not a
         consolidation → label = FLAT.
      3. Scan forward up to ``max_breakout_wait`` bars for a *close* beyond the range.
      4. If no breakout → FLAT.
      5. From the breakout bar, size an ATR bracket and walk forward up to
         ``max_hold_bars`` bars:
           • high[k] >= tp_price          → outcome = LONG/SHORT (win)
           • low[k]  <= sl_price (LONG)   → outcome = LOSS (loss)
           • timeout                       → FLAT
      6. Assign the outcome label to bar ``i`` (the consolidation end bar).
    """
    n = len(close_arr)
    labels = np.zeros(n, dtype=np.int64)

    # Pre-compute rolling high/low arrays using a simple sliding window
    roll_high = np.empty(n, dtype=np.float64)
    roll_low = np.empty(n, dtype=np.float64)
    for i in range(n):
        start = max(0, i - consolidation_bars + 1)
        roll_high[i] = np.max(high_arr[start : i + 1])
        roll_low[i] = np.min(low_arr[start : i + 1])

    # Min bar index where we have a full consolidation window + warmup
    warmup = consolidation_bars + 14  # 14 for ATR warmup
    # Max bar index where we still have room to look forward
    max_i = n - max_breakout_wait - max_hold_bars - 1

    for i in range(warmup, max(warmup, max_i)):
        atr_i = atr_arr[i]
        if atr_i <= 0:
            continue

        range_h = roll_high[i]
        range_l = roll_low[i]
        if range_h <= range_l:
            continue

        # Consolidation gate: range must be tight relative to ATR
        if (range_h - range_l) / atr_i > consolidation_atr_mult:
            continue  # trending/wide → skip

        # Scan forward for breakout
        direction: int = LABEL_FLAT
        breakout_idx: int = -1
        entry_price: float = 0.0

        scan_end = min(i + max_breakout_wait + 1, n)
        for j in range(i + 1, scan_end):
            if close_arr[j] > range_h:
                direction = LABEL_LONG
                entry_price = range_h  # enter at the range boundary
                breakout_idx = j
                break
            elif close_arr[j] < range_l:
                direction = LABEL_SHORT
                entry_price = range_l
                breakout_idx = j
                break

        if direction == LABEL_FLAT or breakout_idx < 0:
            continue  # no breakout within wait window → flat

        # ATR at breakout bar for bracket sizing
        atr_j = atr_arr[breakout_idx]
        if atr_j <= 0:
            atr_j = atr_i  # fallback

        if direction == LABEL_LONG:
            tp_price = entry_price + tp_atr_mult * atr_j
            sl_price = entry_price - sl_atr_mult * atr_j
        else:  # SHORT
            tp_price = entry_price - tp_atr_mult * atr_j
            sl_price = entry_price + sl_atr_mult * atr_j

        # Walk forward from breakout bar to determine outcome
        outcome = LABEL_FLAT  # default: timeout → flat (no outcome, don't punish)
        walk_end = min(breakout_idx + max_hold_bars + 1, n)
        for k in range(breakout_idx + 1, walk_end):
            if direction == LABEL_LONG:
                if high_arr[k] >= tp_price:
                    outcome = LABEL_LONG  # TP hit → win
                    break
                if low_arr[k] <= sl_price:
                    outcome = LABEL_LOSS  # SL hit → explicit loss
                    break
            else:  # SHORT
                if low_arr[k] <= tp_price:
                    outcome = LABEL_SHORT  # TP hit → win
                    break
                if high_arr[k] >= sl_price:
                    outcome = LABEL_LOSS  # SL hit → explicit loss
                    break

        labels[i] = outcome

    return labels


def _compute_signals(
    df: pd.DataFrame,
    fast_period: int,
    slow_period: int,
    ao_fast: int,
    ao_slow: int,
) -> pd.Series:
    """Return a Series of raw signal strings: 'long', 'short', or 'flat'."""
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    fast_ema = _ema(close, fast_period)
    slow_ema = _ema(close, slow_period)
    ao = _ao(high, low, ao_fast, ao_slow)

    signals = pd.Series("flat", index=df.index, dtype=str)

    long_mask = (fast_ema > slow_ema) & (ao > 0)
    short_mask = (fast_ema < slow_ema) & (ao < 0)

    signals[long_mask] = "long"
    signals[short_mask] = "short"

    # Require warmup bars to be fully computed before trusting signals
    warmup = max(slow_period, ao_slow) + 5
    signals.iloc[:warmup] = "flat"

    return signals


def _label_outcomes(
    close_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    signals: np.ndarray,
    tp_pct: float,
    sl_pct: float,
    max_bars: int,
) -> np.ndarray:
    """Walk forward through every bar and assign TP/SL labels.

    Parameters
    ----------
    close_arr, high_arr, low_arr : np.ndarray of float64
    signals : np.ndarray of int  (0=flat, 1=long, 2=short)
    tp_pct  : fraction price must move in signal direction to count as TP
    sl_pct  : fraction price must move against signal to count as SL
    max_bars: maximum bars to look forward before declaring a timeout

    Returns
    -------
    labels : np.ndarray of int64, same length as inputs
    """
    n = len(close_arr)
    labels = np.zeros(n, dtype=np.int64)

    for i in range(n):
        sig = signals[i]
        if sig == LABEL_FLAT:
            continue  # no signal → flat

        entry_price = close_arr[i]
        if entry_price <= 0:
            continue

        tp_price = (
            entry_price * (1.0 + tp_pct) if sig == LABEL_LONG else entry_price * (1.0 - tp_pct)
        )
        sl_price = (
            entry_price * (1.0 - sl_pct) if sig == LABEL_LONG else entry_price * (1.0 + sl_pct)
        )

        outcome = LABEL_LOSS  # default: timeout

        end = min(i + max_bars, n)
        for j in range(i + 1, end):
            bar_high = high_arr[j]
            bar_low = low_arr[j]

            if sig == LABEL_LONG:
                if bar_high >= tp_price:
                    outcome = LABEL_LONG
                    break
                if bar_low <= sl_price:
                    outcome = LABEL_LOSS  # lost — label as loss, not short
                    break
            else:  # LABEL_SHORT
                if bar_low <= tp_price:
                    outcome = LABEL_SHORT
                    break
                if bar_high >= sl_price:
                    outcome = LABEL_LOSS  # lost — label as loss
                    break

        labels[i] = outcome

    return labels


# ── Public API ───────────────────────────────────────────────────────────────

# Avoid a hard import at module level — KlineCache is optional
# and only available when the training stack is installed.
try:
    from ml.kline_cache import KlineCache as _KlineCache
except ImportError:  # pragma: no cover
    _KlineCache = None  # type: ignore[assignment,misc]


# KuCoin Futures hard-caps fetch_ohlcv at 200 candles per request regardless
# of the ``limit`` parameter passed to ccxt.
_KUCOIN_PAGE_SIZE = 200

# Milliseconds per timeframe string — used to compute the starting timestamp.
_TF_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
}

# Retry / probe settings for fetch_klines
_MAX_PAGE_RETRIES: int = 3  # attempts per page before giving up on that page
_RETRY_BASE_DELAY: float = 4.0  # seconds; multiplied by attempt index → 4, 8, 12 s
_PROBE_LIMIT: int = 5  # bars fetched by the symbol probe (no 'since')


def fetch_klines(
    exchange: Any,
    symbol: str,
    timeframe: str = "1m",
    limit: int = 10_000,
    cache: Any | None = None,
    min_bars: int = 5_000,
) -> pd.DataFrame:
    """Fetch historical OHLCV klines from KuCoin Futures via ccxt.

    Returns a DataFrame with lowercase columns:
        timestamp, open, high, low, close, volume

    Parameters
    ----------
    exchange : ccxt.kucoinfutures instance (sync, not async)
    symbol   : KuCoin symbol e.g. "XBTUSDTM"
    timeframe: ccxt timeframe string e.g. "1m", "5m", "15m"
    limit    : total number of bars to collect; the function paginates
               forward in 200-bar pages (KuCoin's hard per-request cap).
    cache    : optional KlineCache instance.  When provided:
               • the full assembled dataset is checked first — a hit skips
                 all API calls entirely;
               • each individual 200-bar page is read from / written to
                 the page cache so crashed runs can resume cheaply.
    min_bars : minimum bars to accept as a usable partial dataset.  If the
               exchange has fewer bars than ``limit`` but at least ``min_bars``
               worth of history (e.g. a recently-listed symbol), the partial
               dataset is returned and training proceeds on the available
               history.  Set to ``limit`` to require the full history or
               nothing.  Default 5 000 (~3.5 days of 1m bars).

    How it works
    ------------
    **Symbol probe**
        Before the main pagination loop the function fetches the
        ``_PROBE_LIMIT`` most-recent bars *without* a ``since`` parameter.
        This serves two purposes:

        (a) Confirms the symbol is live on this exchange — if the probe
            fails after ``_MAX_PAGE_RETRIES`` attempts the function returns
            an empty DataFrame immediately rather than spending minutes
            making useless paginated requests.

        (b) Anchors ``since`` to the actual newest available bar timestamp
            rather than wall-clock ``now``.  KuCoin silently returns ``[]``
            for requests whose ``since`` pre-dates the listing date of the
            symbol.  Without the probe, newly-listed assets (WIF, FARTCOIN)
            hit this condition on page 0 and the old code broke out of the
            loop with 0 bars.

    **Per-page retry with exponential back-off**
        Each page is attempted up to ``_MAX_PAGE_RETRIES`` times.  Between
        attempts the function sleeps ``_RETRY_BASE_DELAY × attempt`` seconds
        (4 s, 8 s, 12 s).  A single empty page (data gap inside the history
        window) is tolerated by advancing the cursor one page forward.  Two
        consecutive empty pages signal the end of available history and stop
        the loop.  Previously any empty response caused an immediate ``break``
        — a single transient rate-limit blip could abort the entire fetch.

    **Partial-data acceptance**
        If the exchange has less than ``limit`` bars of history but at least
        ``min_bars``, the available data is returned with a warning.  This
        allows assets like AVAX (42 641 bars vs 60 000 target) to train on
        their actual available history rather than being silently dropped.

    **Last-resort fallback**
        If the forward pass returns nothing despite a successful probe, the
        function fetches the most-recent ``_KUCOIN_PAGE_SIZE`` bars directly
        (no ``since``) as a final safety net before giving up.
    """
    _EMPTY = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    logger.info(
        "Fetching %d %s klines for %s  (min_bars=%d)...",
        limit,
        timeframe,
        symbol,
        min_bars,
    )

    tf_ms = _TF_MS.get(timeframe, 60_000)
    now_ms = int(_time.time() * 1000)

    # ── Level 1: full-dataset cache ───────────────────────────────────────────
    # A hit means we already fetched and assembled this exact dataset today —
    # skip all API calls and return immediately.
    if cache is not None:
        cached_rows = cache.get_dataset(symbol, timeframe, limit)
        if cached_rows is not None:
            df_cached = pd.DataFrame(
                cached_rows,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            logger.info(
                "[cache] Served %d bars for %s from Redis (skipped exchange)",
                len(df_cached),
                symbol,
            )
            return df_cached

    # ── Symbol probe ──────────────────────────────────────────────────────────
    # Fetch the _PROBE_LIMIT most-recent bars (no 'since') to confirm the
    # symbol is live and to anchor 'since' to the real newest timestamp.
    probe_newest_ts: int | None = None
    for attempt in range(_MAX_PAGE_RETRIES):
        try:
            probe_bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=_PROBE_LIMIT)
        except Exception as exc:
            logger.warning(
                "[probe] %s  attempt %d/%d  error: %s",
                symbol,
                attempt + 1,
                _MAX_PAGE_RETRIES,
                exc,
            )
            probe_bars = []

        if probe_bars:
            probe_newest_ts = int(probe_bars[-1][0])
            logger.info(
                "[probe] %s is live — newest bar: %s",
                symbol,
                pd.to_datetime(probe_newest_ts, unit="ms"),
            )
            break

        if attempt < _MAX_PAGE_RETRIES - 1:
            delay = _RETRY_BASE_DELAY * (attempt + 1)
            logger.warning(
                "[probe] %s  attempt %d/%d  empty — retrying in %.0fs...",
                symbol,
                attempt + 1,
                _MAX_PAGE_RETRIES,
                delay,
            )
            _time.sleep(delay)

    if probe_newest_ts is None:
        logger.error(
            "Symbol %s returned no data on %d probe attempts. "
            "Verify the symbol is listed on KuCoin Futures (check ASSET_SYMBOLS in train.py).",
            symbol,
            _MAX_PAGE_RETRIES,
        )
        return _EMPTY

    # Anchor 'since' to the actual newest available bar, not wall-clock now.
    # This prevents 'since' from landing before the listing date.
    ceiling_ms: int = min(probe_newest_ts, now_ms)
    since: int = ceiling_ms - (limit + 50) * tf_ms

    # ── Level 2: paginated fetch with page-level cache ─────────────────────────
    all_ohlcv: list[list] = []
    max_pages = (limit // _KUCOIN_PAGE_SIZE) + 20  # safety ceiling
    expected_pages = math.ceil(limit / _KUCOIN_PAGE_SIZE)
    pages_from_cache = 0
    pages_from_api = 0
    consecutive_empty = 0

    bar = tqdm(
        total=expected_pages,
        desc=f"  Fetching {symbol}",
        unit="pg",
        bar_format="{desc} {bar} {n_fmt}/{total_fmt} pages [{elapsed}<{remaining}]  {postfix}",
    )

    for _page in range(max_pages):
        # ── Page cache check ──────────────────────────────────────────────────
        if cache is not None:
            cached_page = cache.get_page(symbol, timeframe, since)
            if cached_page is not None:
                all_ohlcv.extend(cached_page)
                last_ts = int(cached_page[-1][0])
                pages_from_cache += 1
                consecutive_empty = 0
                bar.set_postfix_str(f"cache={pages_from_cache} api={pages_from_api}")
                bar.update(1)
                if last_ts >= ceiling_ms - tf_ms or len(all_ohlcv) >= limit:
                    break
                since = last_ts + 1
                continue  # skip the exchange call for this page

        # ── Live exchange fetch with per-page retry ───────────────────────────
        ohlcv: list = []
        for attempt in range(_MAX_PAGE_RETRIES):
            try:
                ohlcv = exchange.fetch_ohlcv(
                    symbol,
                    timeframe=timeframe,
                    since=since,
                    limit=_KUCOIN_PAGE_SIZE,
                )
            except Exception as exc:
                logger.warning(
                    "fetch_ohlcv error page %d attempt %d/%d %s: %s",
                    _page,
                    attempt + 1,
                    _MAX_PAGE_RETRIES,
                    symbol,
                    exc,
                )
                ohlcv = []

            if ohlcv:
                break  # got data — no need to retry this page

            if attempt < _MAX_PAGE_RETRIES - 1:
                delay = _RETRY_BASE_DELAY * (attempt + 1)
                logger.debug(
                    "Empty page %d for %s attempt %d/%d — waiting %.0fs...",
                    _page,
                    symbol,
                    attempt + 1,
                    _MAX_PAGE_RETRIES,
                    delay,
                )
                _time.sleep(delay)

        if not ohlcv:
            consecutive_empty += 1
            if consecutive_empty >= 2:
                # Two consecutive empty pages → no more history at this cursor position
                logger.info(
                    "Stopping %s fetch at page %d — %d consecutive empty pages.",
                    symbol,
                    _page,
                    consecutive_empty,
                )
                break
            # Single gap: skip forward one page width and continue
            since += _KUCOIN_PAGE_SIZE * tf_ms
            bar.update(1)
            continue

        consecutive_empty = 0  # reset on any successful page

        # Store page in cache before extending so a partial run is recoverable
        if cache is not None:
            cache.set_page(symbol, timeframe, since, ohlcv)

        all_ohlcv.extend(ohlcv)
        pages_from_api += 1

        last_ts = int(ohlcv[-1][0])
        bar.set_postfix_str(f"cache={pages_from_cache} api={pages_from_api}")
        bar.update(1)

        # Stop when the newest bar is at or beyond the ceiling
        if last_ts >= ceiling_ms - tf_ms:
            break

        # Advance cursor to the bar immediately after the last one returned
        since = last_ts + 1

        if len(all_ohlcv) >= limit:
            break

    bar.close()

    if pages_from_cache or pages_from_api:
        logger.debug(
            "[cache] %s — pages from cache=%d  from API=%d",
            symbol,
            pages_from_cache,
            pages_from_api,
        )

    # ── Last-resort fallback ──────────────────────────────────────────────────
    # If the forward pass yielded nothing despite a successful probe, fetch the
    # most-recent page directly (no 'since') as a final safety net.
    if not all_ohlcv:
        logger.warning(
            "Forward pass returned 0 bars for %s — falling back to most-recent %d bars fetch.",
            symbol,
            _KUCOIN_PAGE_SIZE,
        )
        try:
            fallback = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                limit=min(_KUCOIN_PAGE_SIZE, limit),
            )
            if fallback:
                all_ohlcv.extend(fallback)
                logger.info("Fallback fetch returned %d bars for %s.", len(all_ohlcv), symbol)
        except Exception as exc:
            logger.warning("Fallback fetch also failed for %s: %s", symbol, exc)

    if not all_ohlcv:
        logger.error("0 bars for %s after all fetch attempts — skipping.", symbol)
        return _EMPTY

    df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)

    # Keep only the most-recent ``limit`` bars
    if len(df) > limit:
        df = df.tail(limit).reset_index(drop=True)

    # ── Partial-data check ────────────────────────────────────────────────────
    if len(df) < min_bars:
        logger.error(
            "Insufficient data for %s: got %d bars, need at least %d (target %d). "
            "The symbol may have limited history on KuCoin Futures. "
            "Try --bars %d to request a shorter window.",
            symbol,
            len(df),
            min_bars,
            limit,
            max(5_000, int(len(df) * 0.85)),
        )
        return _EMPTY

    if len(df) < limit:
        logger.warning(
            "Partial data for %s: got %d/%d bars (%.1f%%) — "
            "training will proceed with the available history.",
            symbol,
            len(df),
            limit,
            len(df) / limit * 100,
        )

    logger.info(
        "Fetched %d bars for %s  [%s → %s]",
        len(df),
        symbol,
        pd.to_datetime(df["timestamp"].iloc[0], unit="ms"),
        pd.to_datetime(df["timestamp"].iloc[-1], unit="ms"),
    )

    # ── Level 1 write-back: cache the fully assembled dataset ─────────────────
    if cache is not None and not df.empty:
        cache.set_dataset(symbol, timeframe, limit, df.values.tolist())

    return df


def generate_labels(
    df: pd.DataFrame,
    tp_pct: float = DEFAULT_TP_PCT,
    sl_pct: float = DEFAULT_SL_PCT,
    max_bars: int = DEFAULT_MAX_BARS,
    fast_period: int = DEFAULT_FAST_EMA,
    slow_period: int = DEFAULT_SLOW_EMA,
    ao_fast: int = DEFAULT_AO_FAST,
    ao_slow: int = DEFAULT_AO_SLOW,
) -> np.ndarray:
    """Generate 3-class training labels for a klines DataFrame.

    .. deprecated::
        Use ``generate_labels_breakout()`` instead.  This function gates labels on
        EMA/AO conditions that are also present in the feature vector, creating
        label/feature leakage that causes trivially perfect validation accuracy.

    Parameters
    ----------
    df        : DataFrame with columns open, high, low, close, volume
    tp_pct    : Take-profit fraction (e.g. 0.004 = 0.4 %)
    sl_pct    : Stop-loss fraction   (e.g. 0.0035 = 0.35 %)
    max_bars  : Bars to look forward before labelling a signal as timeout/flat
    fast_period, slow_period : EMA periods matching the live bot config
    ao_fast, ao_slow         : Awesome Oscillator SMA periods

    Returns
    -------
    labels : np.ndarray of int64, shape (len(df),)
              values in {0=flat, 1=long, 2=short}
    """
    if df.empty or len(df) < max(slow_period, ao_slow) + max_bars + 10:
        logger.warning(
            "DataFrame too short to generate labels (%d rows, need ~%d)",
            len(df),
            max(slow_period, ao_slow) + max_bars + 10,
        )
        return np.zeros(len(df), dtype=np.int64)

    # Compute entry signals using the same logic as the live bot
    sig_str = _compute_signals(df, fast_period, slow_period, ao_fast, ao_slow)

    # Convert string signals to int
    sig_int = np.where(
        sig_str == "long", LABEL_LONG, np.where(sig_str == "short", LABEL_SHORT, LABEL_FLAT)
    ).astype(np.int64)

    close_arr = df["close"].astype(np.float64).to_numpy()
    high_arr = df["high"].astype(np.float64).to_numpy()
    low_arr = df["low"].astype(np.float64).to_numpy()

    labels = _label_outcomes(
        close_arr,
        high_arr,
        low_arr,
        sig_int,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        max_bars=max_bars,
    )

    n_long = int((labels == LABEL_LONG).sum())
    n_short = int((labels == LABEL_SHORT).sum())
    n_flat = int((labels == LABEL_FLAT).sum())
    total = len(labels)

    logger.info(
        "Labels: flat=%d (%.1f%%)  long=%d (%.1f%%)  short=%d (%.1f%%)",
        n_flat,
        n_flat / total * 100,
        n_long,
        n_long / total * 100,
        n_short,
        n_short / total * 100,
    )

    return labels


def generate_labels_breakout(
    df: pd.DataFrame,
    consolidation_bars: int = DEFAULT_CONSOLIDATION_BARS,
    consolidation_atr_mult: float = DEFAULT_CONSOLIDATION_ATR_MULT,
    max_breakout_wait: int = DEFAULT_MAX_BREAKOUT_WAIT,
    tp_atr_mult: float = DEFAULT_TP_ATR_MULT,
    sl_atr_mult: float = DEFAULT_SL_ATR_MULT,
    max_hold_bars: int = DEFAULT_MAX_HOLD_BARS,
    atr_period: int = DEFAULT_ATR_PERIOD,
) -> np.ndarray:
    """Generate 3-class training labels using a consolidation-breakout framework.

    This replaces the EMA/AO signal-based ``generate_labels()`` function.
    The key improvement is that labels are derived from *price structure*
    (a tight consolidation range followed by a breakout with a walk-forward
    bracket outcome), while features describe the candle action *inside*
    the consolidation — completely decoupled from the label-gating logic.

    Algorithm
    ---------
    For each bar ``i`` (the consolidation end candidate):
      1. Measure rolling high/low over ``consolidation_bars`` bars.
      2. If the range is too wide relative to ATR → skip (label = flat).
      3. Scan up to ``max_breakout_wait`` bars ahead for a *close* that
         exits the range.  No breakout → label = flat.
      4. From the breakout bar, place an ATR-sized bracket and walk
         forward up to ``max_hold_bars`` bars.
         - TP hit → LONG (1) or SHORT (2)
         - SL hit or timeout → FLAT (0)
      5. Assign the outcome to bar ``i`` (not the breakout bar).

    Parameters
    ----------
    df                     : OHLCV DataFrame (open, high, low, close, volume)
    consolidation_bars     : Lookback bars to measure range tightness (default 20)
    consolidation_atr_mult : Max (range / ATR) to qualify as consolidation (default 5.5)
    max_breakout_wait      : Bars to scan forward for breakout (default 40)
    tp_atr_mult            : TP = entry ± tp_atr_mult × ATR (default 1.5)
    sl_atr_mult            : SL = entry ∓ sl_atr_mult × ATR (default 1.0)
    max_hold_bars          : Bars to walk forward after entry (default 90)
    atr_period             : ATR EWM smoothing period (default 14)

    Returns
    -------
    np.ndarray of int64, shape (len(df),)  — values in {0=flat, 1=long, 2=short}
    """
    min_required = consolidation_bars + atr_period + max_breakout_wait + max_hold_bars + 10
    if df.empty or len(df) < min_required:
        logger.warning(
            "DataFrame too short for breakout labels (%d rows, need ~%d)",
            len(df),
            min_required,
        )
        return np.zeros(len(df), dtype=np.int64)

    close_arr = df["close"].astype(np.float64).to_numpy()
    high_arr = df["high"].astype(np.float64).to_numpy()
    low_arr = df["low"].astype(np.float64).to_numpy()

    atr_values = _atr_arr(df["high"], df["low"], df["close"], period=atr_period)

    labels = _breakout_label_outcomes(
        close_arr=close_arr,
        high_arr=high_arr,
        low_arr=low_arr,
        atr_arr=atr_values,
        consolidation_bars=consolidation_bars,
        consolidation_atr_mult=consolidation_atr_mult,
        max_breakout_wait=max_breakout_wait,
        tp_atr_mult=tp_atr_mult,
        sl_atr_mult=sl_atr_mult,
        max_hold_bars=max_hold_bars,
    )

    n_long = int((labels == LABEL_LONG).sum())
    n_short = int((labels == LABEL_SHORT).sum())
    n_flat = int((labels == LABEL_FLAT).sum())
    n_loss = int((labels == LABEL_LOSS).sum())
    total = len(labels)

    logger.info(
        "Breakout labels: flat=%d (%.1f%%)  long=%d (%.1f%%)  short=%d (%.1f%%)  loss=%d (%.1f%%)",
        n_flat,
        n_flat / total * 100,
        n_long,
        n_long / total * 100,
        n_short,
        n_short / total * 100,
        n_loss,
        n_loss / total * 100,
    )

    return labels


def label_summary(labels: np.ndarray) -> dict[str, Any]:
    total = len(labels)
    if total == 0:
        return {"total": 0, "flat": 0, "long": 0, "short": 0, "loss": 0}

    n_flat = int((labels == LABEL_FLAT).sum())
    n_long = int((labels == LABEL_LONG).sum())
    n_short = int((labels == LABEL_SHORT).sum())
    n_loss = int((labels == LABEL_LOSS).sum())

    return {
        "total": total,
        "flat": n_flat,
        "long": n_long,
        "short": n_short,
        "loss": n_loss,
        "flat_pct": round(n_flat / total * 100, 1),
        "long_pct": round(n_long / total * 100, 1),
        "short_pct": round(n_short / total * 100, 1),
        "loss_pct": round(n_loss / total * 100, 1),
    }


def class_weights(labels: np.ndarray, max_weight: float = 50.0) -> list[float]:
    counts = np.array(
        [max(int((labels == c).sum()), 1) for c in (LABEL_FLAT, LABEL_LONG, LABEL_SHORT, LABEL_LOSS)],
        dtype=np.float64,
    )
    total = counts.sum()
    minority_pct = counts[1:].min() / total

    # Was 0.01/20.0 — too narrow; ETH at 2% was slipping through to 50× weights
    dynamic_cap = 10.0 if minority_pct < 0.05 else min(max_weight, 25.0)

    weights = total / (len(counts) * counts)
    weights = weights / weights.min()
    weights = np.clip(weights, 0.0, dynamic_cap)
    return weights.tolist()
