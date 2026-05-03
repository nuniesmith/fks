"""Pipeline edge-case tests — TESTS-B.

Covers:
  1a. Indicator computation with NaN / missing / short data
  1b. Bar aggregation with gaps (empty result, time gaps, duplicate timestamps)
  1c. Timezone / DST transition edge cases
  1d. Redis connection loss — SSE cache helpers return None gracefully
  1e. JSON serialisation with NaN / Inf values (SafeJSONResponse / _sanitize)
"""

import os

os.environ.setdefault("DISABLE_REDIS", "1")

import json
import math
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_lower_ohlcv(
    n: int = 100,
    start_price: float = 100.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Return a realistic lowercase-column OHLCV DataFrame.

    The indicator classes (RSI, MACD, BollingerBands, ATR) use lowercase
    column names by default (``close``, ``high``, ``low``).  The conftest
    fixtures use UPPERCASE — this helper produces the right shape without
    depending on fixture column renaming.
    """
    rng = np.random.default_rng(seed)
    returns = rng.normal(0, 0.005, n)
    close = start_price * np.exp(np.cumsum(returns))

    spread = close * rng.uniform(0.001, 0.004, n)
    high = close + rng.uniform(0, 1, n) * spread
    low = close - rng.uniform(0, 1, n) * spread
    opn = close + rng.uniform(-0.3, 0.3, n) * spread

    high = np.maximum(high, np.maximum(opn, close))
    low = np.minimum(low, np.minimum(opn, close))

    volume = rng.poisson(1_000, n).astype(float)
    idx = pd.date_range("2025-01-06 09:30", periods=n, freq="1min", tz="America/New_York")
    return pd.DataFrame(
        {"open": opn, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def _lower(df: pd.DataFrame) -> pd.DataFrame:
    """Rename OHLCV columns to lowercase (for conftest fixtures → indicators)."""
    return df.rename(columns=str.lower)


def _bar_df(timestamps: list, close_values: list) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame with an explicit UTC DatetimeIndex.

    Used for bar-gap tests where we need precise control over timestamps.
    """
    n = len(timestamps)
    return pd.DataFrame(
        {
            "Open": [100.0] * n,
            "High": [101.0] * n,
            "Low": [99.0] * n,
            "Close": list(close_values),
            "Volume": [1_000] * n,
        },
        index=pd.DatetimeIndex(timestamps),
    )


# ===========================================================================
# 1a. Indicator computation with NaN / missing data
# ===========================================================================


class TestRSIEdgeCases:
    """RSI indicator — NaN / zero-volume / short / inf edge cases."""

    def setup_method(self):
        from lib.indicators.momentum.rsi import RSI

        self.rsi14 = RSI(params={"period": 14, "column": "close"})

    # ── NaN in close ────────────────────────────────────────────────────────

    def test_nan_in_close_does_not_raise(self):
        """RSI must return a DataFrame even when some close values are NaN."""
        df = _make_lower_ohlcv(100)
        df.loc[df.index[10:15], "close"] = np.nan
        result = self.rsi14.calculate(df)
        assert isinstance(result, pd.DataFrame)

    def test_nan_in_close_preserves_row_count(self):
        """Output row count must equal input row count regardless of NaN."""
        df = _make_lower_ohlcv(100)
        df.loc[df.index[20:25], "close"] = np.nan
        result = self.rsi14.calculate(df)
        assert len(result) == len(df)

    def test_nan_propagates_to_output_at_nan_position(self):
        """A NaN close forces NaN in RSI at and near that row."""
        df = _make_lower_ohlcv(50)
        df.loc[df.index[30], "close"] = np.nan
        result = self.rsi14.calculate(df)
        col = result.columns[0]
        # The row itself must be NaN
        assert math.isnan(result[col].iloc[30])

    # ── All-zero volume ──────────────────────────────────────────────────────

    def test_all_zeros_volume_no_crash(self):
        """RSI is computed from close only — all-zero Volume should be ignored."""
        df = _make_lower_ohlcv(50)
        df["volume"] = 0.0
        result = self.rsi14.calculate(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(df)

    # ── Fewer bars than period (conftest tiny_df fixture) ───────────────────

    def test_fewer_bars_than_period_all_nan(self, tiny_df):
        """5-bar DataFrame < period=14 must produce an all-NaN RSI column."""
        df = _lower(tiny_df)
        result = self.rsi14.calculate(df)
        col = result.columns[0]
        assert result[col].isna().all(), f"Expected all-NaN RSI when len(df)=5 < period=14; got {result[col].tolist()}"

    # ── inf replaced by NaN ─────────────────────────────────────────────────

    def test_inf_replaced_by_nan_no_crash(self):
        """RSI handles close series that had inf values sanitised to NaN."""
        df = _make_lower_ohlcv(50)
        df.loc[df.index[5], "close"] = np.inf
        df["close"] = df["close"].replace([np.inf, -np.inf], np.nan)
        result = self.rsi14.calculate(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(df)

    # ── Normal data sanity ──────────────────────────────────────────────────

    def test_output_in_valid_range_for_clean_data(self, ohlcv_df):
        """RSI values for clean 500-bar data must lie in [0, 100]."""
        df = _lower(ohlcv_df)
        result = self.rsi14.calculate(df)
        col = result.columns[0]
        valid = result[col].dropna()
        assert len(valid) > 0, "Expected some non-NaN RSI values"
        assert (valid >= 0).all() and (valid <= 100).all(), (
            f"RSI out of [0, 100] range: min={valid.min():.2f}, max={valid.max():.2f}"
        )


class TestMACDEdgeCases:
    """MACD indicator — NaN / short / zero-close edge cases."""

    def setup_method(self):
        from lib.indicators.trend.macd import MACD

        self.macd = MACD(params={"fast_period": 12, "slow_period": 26, "signal_period": 9, "column": "close"})

    def test_nan_in_close_does_not_raise(self):
        df = _make_lower_ohlcv(100)
        df.loc[df.index[30:33], "close"] = np.nan
        result = self.macd.calculate(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(df)

    def test_fewer_bars_than_slow_period_no_crash(self, tiny_df):
        """5 bars < slow_period=26; MACD must still return a DataFrame."""
        df = _lower(tiny_df)
        result = self.macd.calculate(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(df)

    def test_all_zeros_close_no_crash(self):
        """Constant close (all zeros) produces zero MACD — no crash."""
        df = _make_lower_ohlcv(50)
        df["close"] = 0.0
        result = self.macd.calculate(df)
        assert isinstance(result, pd.DataFrame)

    def test_output_columns_present(self, ohlcv_df):
        """MACD must always return line, signal, and histogram columns."""
        df = _lower(ohlcv_df)
        result = self.macd.calculate(df)
        assert "MACD_line" in result.columns
        assert "MACD_signal" in result.columns
        assert "MACD_histogram" in result.columns

    def test_inf_replaced_by_nan_no_crash(self):
        df = _make_lower_ohlcv(50)
        df.loc[df.index[10], "close"] = np.inf
        df["close"] = df["close"].replace([np.inf, -np.inf], np.nan)
        result = self.macd.calculate(df)
        assert isinstance(result, pd.DataFrame)


class TestBollingerBandsEdgeCases:
    """BollingerBands indicator — NaN / short / zero / inf edge cases."""

    def setup_method(self):
        from lib.indicators.trend.volatility.bollinger import BollingerBands

        self.bb = BollingerBands(params={"period": 20, "std_dev": 2, "column": "close"})

    def test_nan_in_close_does_not_raise(self):
        df = _make_lower_ohlcv(100)
        df.loc[df.index[5:8], "close"] = np.nan
        result = self.bb.calculate(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(df)

    def test_fewer_bars_than_period_middle_all_nan(self, tiny_df):
        """5 bars < period=20; rolling produces all-NaN middle band."""
        df = _lower(tiny_df)
        result = self.bb.calculate(df)
        middle_col = next(c for c in result.columns if "middle" in c)
        assert result[middle_col].isna().all(), "Expected all-NaN middle band when len(df)=5 < period=20"

    def test_all_zeros_close_no_crash(self):
        """Zero close makes std=0 and collapses bandwidth — must not crash."""
        df = _make_lower_ohlcv(50)
        df["close"] = 0.0
        result = self.bb.calculate(df)
        assert isinstance(result, pd.DataFrame)

    def test_inf_replaced_by_nan_no_crash(self):
        df = _make_lower_ohlcv(50)
        df.loc[df.index[10], "close"] = np.inf
        df["close"] = df["close"].replace([np.inf, -np.inf], np.nan)
        result = self.bb.calculate(df)
        assert isinstance(result, pd.DataFrame)

    def test_upper_band_above_lower_band_for_clean_data(self, ohlcv_df):
        """For clean data, upper band must always exceed lower band."""
        df = _lower(ohlcv_df)
        result = self.bb.calculate(df)
        upper_col = next(c for c in result.columns if "upper" in c)
        lower_col = next(c for c in result.columns if "lower" in c)
        valid = result[[upper_col, lower_col]].dropna()
        assert (valid[upper_col] >= valid[lower_col]).all()


class TestATREdgeCases:
    """ATR (AverageTrueRange) indicator — NaN / short / inf edge cases.

    Note: the class in the codebase is named ``ATR`` (not ``AverageTrueRange``),
    but is documented under the full name in indicator metadata.
    """

    def setup_method(self):
        # The module exposes the class as ``ATR``
        from lib.indicators.trend.volatility.atr import ATR

        self.atr = ATR(params={"period": 14, "method": "sma"})

    def test_nan_in_close_does_not_raise(self):
        df = _make_lower_ohlcv(100)
        df.loc[df.index[10:12], "close"] = np.nan
        result = self.atr.calculate(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(df)

    def test_fewer_bars_than_period_atr_all_nan(self, tiny_df):
        """5 bars < period=14; rolling ATR must be all NaN."""
        df = _lower(tiny_df)
        result = self.atr.calculate(df)
        atr_col = next(c for c in result.columns if c.endswith("_14") and "norm" not in c)
        assert result[atr_col].isna().all(), "Expected all-NaN ATR when len(df)=5 < period=14"

    def test_all_zeros_volume_no_crash(self):
        """ATR does not use Volume — all-zero Volume must not crash."""
        df = _make_lower_ohlcv(50)
        df["volume"] = 0.0
        result = self.atr.calculate(df)
        assert isinstance(result, pd.DataFrame)

    def test_inf_in_close_replaced_by_nan_no_crash(self):
        df = _make_lower_ohlcv(50)
        df.loc[df.index[5], "close"] = np.inf
        df["close"] = df["close"].replace([np.inf, -np.inf], np.nan)
        result = self.atr.calculate(df)
        assert isinstance(result, pd.DataFrame)

    def test_atr_non_negative_for_clean_data(self, ohlcv_df):
        """ATR should be non-negative for valid OHLCV bars."""
        df = _lower(ohlcv_df)
        result = self.atr.calculate(df)
        atr_col = next(c for c in result.columns if c.endswith("_14") and "norm" not in c)
        valid = result[atr_col].dropna()
        assert len(valid) > 0, "Expected some non-NaN ATR values"
        assert (valid >= 0).all(), f"Negative ATR detected: min={valid.min():.6f}"

    def test_ema_method_no_crash(self):
        """ATR with method='ema' must also handle NaN without crashing."""
        from lib.indicators.trend.volatility.atr import ATR

        atr_ema = ATR(params={"period": 14, "method": "ema"})
        df = _make_lower_ohlcv(100)
        df.loc[df.index[20], "close"] = np.nan
        result = atr_ema.calculate(df)
        assert isinstance(result, pd.DataFrame)


# ===========================================================================
# 1b. Bar aggregation with gaps
# ===========================================================================


class TestComputeGapWindows:
    """_compute_gap_windows() — empty, gapped, duplicate, weekend, maintenance."""

    # Convenience: the function path to patch
    _FETCH_PATH = "lib.services.data.api.bars._fetch_stored_bars"

    def _call(self, df: pd.DataFrame) -> list:
        from lib.services.data.api.bars import _compute_gap_windows

        with patch(self._FETCH_PATH, return_value=df):
            return _compute_gap_windows("MES")

    # ── Empty / degenerate inputs ────────────────────────────────────────────

    def test_empty_dataframe_returns_no_gaps(self):
        """_compute_gap_windows with an empty DB result returns []."""
        result = self._call(pd.DataFrame())
        assert result == []

    def test_single_bar_returns_no_gaps(self):
        """A single-row DataFrame has no consecutive pair to compare."""
        ts = pd.Timestamp("2025-01-06 14:00", tz="UTC")
        df = _bar_df([ts], [100.5])
        result = self._call(df)
        assert result == []

    # ── No gaps ─────────────────────────────────────────────────────────────

    def test_consecutive_bars_no_gaps_detected(self):
        """Bars exactly 1 minute apart (≤ 5 min threshold) produce no gaps."""
        idx = pd.date_range("2025-01-06 14:00", periods=10, freq="1min", tz="UTC")
        df = _bar_df(list(idx), [100.0 + i * 0.1 for i in range(10)])
        result = self._call(df)
        assert result == [], f"Expected no gaps for consecutive 1-min bars, got: {result}"

    def test_five_minute_gap_not_reported(self):
        """A 5-minute gap is exactly at the threshold — not reported (> 5 required)."""
        ts1 = pd.Timestamp("2025-01-06 14:00", tz="UTC")
        ts2 = pd.Timestamp("2025-01-06 14:05", tz="UTC")
        df = _bar_df([ts1, ts2], [100.0, 100.5])
        result = self._call(df)
        assert result == []

    # ── Gaps present ─────────────────────────────────────────────────────────

    def test_thirty_minute_gap_detected(self):
        """A 30-minute intraday gap (not weekend, not maintenance) must be reported."""
        ts1 = pd.Timestamp("2025-01-06 14:00", tz="UTC")  # 09:00 ET
        ts2 = pd.Timestamp("2025-01-06 14:30", tz="UTC")  # 09:30 ET
        df = _bar_df([ts1, ts2], [100.0, 100.5])
        result = self._call(df)
        assert len(result) == 1, f"Expected 1 gap, got: {result}"
        assert result[0]["missing_minutes"] == 30

    def test_gap_result_has_required_keys(self):
        """Each gap entry must contain start, end, and missing_minutes."""
        ts1 = pd.Timestamp("2025-01-06 14:00", tz="UTC")
        ts2 = pd.Timestamp("2025-01-06 14:45", tz="UTC")
        df = _bar_df([ts1, ts2], [100.0, 101.0])
        result = self._call(df)
        assert len(result) == 1
        gap = result[0]
        assert "start" in gap
        assert "end" in gap
        assert "missing_minutes" in gap

    def test_multiple_gaps_all_detected(self):
        """Two independent gaps in the same dataset must both be reported.

        Layout:
          t1 (14:00) ──30 min gap──> t2 (14:30)
          t2 (14:30) ── 1 min ──────> t3 (14:31)   ← no gap (consecutive)
          t3 (14:31) ──44 min gap──> t4 (15:15)
        Expected: 2 gaps with missing_minutes 30 and 44.
        """
        t1 = pd.Timestamp("2025-01-06 14:00", tz="UTC")
        t2 = pd.Timestamp("2025-01-06 14:30", tz="UTC")  # +30 min gap
        t3 = pd.Timestamp("2025-01-06 14:31", tz="UTC")  # +1 min (consecutive)
        t4 = pd.Timestamp("2025-01-06 15:15", tz="UTC")  # +44 min gap
        df = _bar_df([t1, t2, t3, t4], [100.0, 100.5, 101.0, 101.5])
        result = self._call(df)
        assert len(result) == 2, f"Expected exactly 2 gaps, got {len(result)}: {result}"
        minutes = sorted(g["missing_minutes"] for g in result)
        assert minutes == [30, 44]

    # ── Duplicate timestamps ─────────────────────────────────────────────────

    def test_duplicate_timestamps_not_reported_as_gaps(self):
        """Two bars at the same timestamp have diff=0 min — no gap reported."""
        ts = pd.Timestamp("2025-01-06 14:00", tz="UTC")
        df = _bar_df([ts, ts], [100.0, 100.0])
        result = self._call(df)
        assert result == [], f"Duplicate timestamps must not be reported as gaps: {result}"

    # ── Weekend gap excluded ─────────────────────────────────────────────────

    def test_weekend_gap_excluded(self):
        """A Friday→Monday gap (> 2880 min on weekday=4) must be skipped."""
        # 2025-01-03 is a Friday; 2025-01-06 is Monday
        ts_fri = pd.Timestamp("2025-01-03 22:00", tz="UTC")  # ~17:00 ET Friday
        ts_mon = pd.Timestamp("2025-01-06 23:00", tz="UTC")  # ~18:00 ET Monday
        df = _bar_df([ts_fri, ts_mon], [100.0, 101.0])
        result = self._call(df)
        assert result == [], f"Weekend gap must be excluded, got: {result}"

    # ── Daily maintenance break excluded ────────────────────────────────────

    def test_maintenance_break_excluded(self):
        """A ~60-min gap starting at 17:00 ET (CME daily break) must be skipped."""
        # 22:00 UTC = 17:00 ET (start of maintenance break)
        ts1 = pd.Timestamp("2025-01-06 22:00", tz="UTC")
        ts2 = pd.Timestamp("2025-01-06 23:00", tz="UTC")  # 60-min gap from 17:00 ET
        df = _bar_df([ts1, ts2], [100.0, 100.5])
        result = self._call(df)
        assert result == [], f"Maintenance break must not be reported as a gap: {result}"


# ===========================================================================
# 1c. Timezone edge cases (DST transitions)
# ===========================================================================


class TestTimezoneEdgeCases:
    """DST transition timestamps — pandas conversions must be stable."""

    # ── Spring forward 2025-03-09 (clocks jump from 01:59 EST → 03:00 EDT) ──

    def test_spring_forward_utc_timestamps_are_continuous(self):
        """UTC timestamps around spring-forward are continuous — no gap in unix seconds.

        UTC 06:59 = 01:59 AM EST (last moment before spring-forward)
        UTC 07:00 = 03:00 AM EDT (first moment after spring-forward)
        The gap in ET is 1 hour, but UTC unix seconds increment normally.
        """
        ts_before = pd.Timestamp("2025-03-09 06:59", tz="UTC")
        ts_after = pd.Timestamp("2025-03-09 07:00", tz="UTC")
        diff_seconds = ts_after.timestamp() - ts_before.timestamp()
        assert diff_seconds == 60.0, (
            f"UTC timestamps before/after spring-forward must differ by 60 s, got {diff_seconds}"
        )

    def test_spring_forward_et_skips_2am(self):
        """After spring-forward, UTC 07:00 maps to 03:00 AM EDT (2 AM ET is skipped)."""
        ts_utc = pd.Timestamp("2025-03-09 07:00", tz="UTC")
        ts_et = ts_utc.tz_convert("America/New_York")
        assert ts_et.hour == 3, f"Expected 03:00 AM ET after spring-forward, got {ts_et.hour}:00"
        assert ts_et.utcoffset().total_seconds() == -4 * 3600, "After spring-forward, ET offset must be -04:00 (EDT)"

    def test_spring_forward_unix_seconds_round_trip(self):
        """pd.Timestamp unix-seconds round-trip must be lossless at spring-forward boundary."""
        ts_utc = pd.Timestamp("2025-03-09 07:00", tz="UTC")
        unix = ts_utc.timestamp()
        recovered = pd.Timestamp(unix, unit="s", tz="UTC")
        assert recovered == ts_utc, f"Round-trip failed: {ts_utc} → {unix} → {recovered}"

    # ── Fall back 2025-11-02 (clocks repeat 01:00–01:59 AM, offset -05:00) ──

    def test_fall_back_same_et_time_maps_to_different_utc(self):
        """During fall-back, two UTC times map to the same local clock reading.

        UTC 05:00 = 01:00 AM EDT (before fall-back, offset -04:00)
        UTC 06:00 = 01:00 AM EST (after fall-back,  offset -05:00)
        Both show '01:00 AM' on a wall clock but have distinct unix seconds.
        """
        utc_edt = pd.Timestamp("2025-11-02 05:00", tz="UTC")
        utc_est = pd.Timestamp("2025-11-02 06:00", tz="UTC")

        et_edt = utc_edt.tz_convert("America/New_York")
        et_est = utc_est.tz_convert("America/New_York")

        # Both should read 01:00 on the wall clock
        assert et_edt.hour == 1 and et_edt.minute == 0, f"Unexpected ET time: {et_edt}"
        assert et_est.hour == 1 and et_est.minute == 0, f"Unexpected ET time: {et_est}"

        # But they have different unix seconds
        assert utc_edt.timestamp() != utc_est.timestamp(), (
            "The two UTC timestamps at the fall-back boundary must have different unix seconds"
        )
        diff = utc_est.timestamp() - utc_edt.timestamp()
        assert diff == pytest.approx(3600.0), f"The two timestamps should be exactly 3600 s apart, got {diff}"

    def test_fall_back_edt_offset_is_minus_four(self):
        """The first 01:00 AM (EDT, before fall-back) must carry offset -04:00."""
        utc_edt = pd.Timestamp("2025-11-02 05:00", tz="UTC")
        et = utc_edt.tz_convert("America/New_York")
        offset_hours = et.utcoffset().total_seconds() / 3600
        assert offset_hours == pytest.approx(-4.0), f"Expected -04:00 (EDT) before fall-back, got {offset_hours:+.1f}h"

    def test_fall_back_est_offset_is_minus_five(self):
        """The second 01:00 AM (EST, after fall-back) must carry offset -05:00."""
        utc_est = pd.Timestamp("2025-11-02 06:00", tz="UTC")
        et = utc_est.tz_convert("America/New_York")
        offset_hours = et.utcoffset().total_seconds() / 3600
        assert offset_hours == pytest.approx(-5.0), f"Expected -05:00 (EST) after fall-back, got {offset_hours:+.1f}h"

    def test_fall_back_unix_seconds_round_trip_both_occurrences(self):
        """Unix-second round-trips must be lossless for both fall-back timestamps."""
        for utc_str in ("2025-11-02 05:00", "2025-11-02 06:00"):
            ts = pd.Timestamp(utc_str, tz="UTC")
            recovered = pd.Timestamp(ts.timestamp(), unit="s", tz="UTC")
            assert recovered == ts, f"Round-trip failed for {utc_str}: {ts.timestamp()} → {recovered}"

    # ── UTC is always unambiguous ────────────────────────────────────────────

    def test_utc_based_bar_index_is_unambiguous(self):
        """A DatetimeIndex built in UTC has no ambiguous / nonexistent times."""
        idx = pd.date_range("2025-11-02 04:00", periods=4, freq="1h", tz="UTC")
        assert len(idx) == 4
        assert idx.tz is not None
        # All UTC offsets must be 0
        for ts in idx:
            assert ts.utcoffset().total_seconds() == 0

    def test_bar_index_tz_convert_stable_around_dst(self):
        """Converting a UTC bar index to ET preserves the number of timestamps."""
        idx_utc = pd.date_range("2025-03-09 05:00", periods=6, freq="1h", tz="UTC")
        idx_et = idx_utc.tz_convert("America/New_York")
        assert len(idx_et) == len(idx_utc), "tz_convert must not lose timestamps at DST boundary"


# ===========================================================================
# 1d. Redis connection loss — SSE cache helpers return None gracefully
# ===========================================================================


class TestRedisCacheGracefulDegradation:
    """Verify that SSE cache helpers return None when Redis is unavailable.

    DISABLE_REDIS=1 is set at the top of this file (and in conftest.py),
    so the in-memory cache is empty and no live Redis connection is attempted.
    The helpers must never raise — they must silently return None.
    """

    def _import_sse_functions(self):
        """Lazily import SSE helper functions to keep the test module importable
        even if optional SSE dependencies are absent.
        """
        from lib.services.data.api.sse import (
            _get_focus_from_cache,
            _get_posint_from_cache,
            _get_risk_from_cache,
        )

        return _get_focus_from_cache, _get_posint_from_cache, _get_risk_from_cache

    def test_get_risk_from_cache_returns_none_no_redis(self):
        """_get_risk_from_cache() must return None when Redis is unavailable."""
        _, _, _get_risk_from_cache = self._import_sse_functions()
        # Ensure cache_get returns None (empty in-memory cache)
        with patch("lib.core.cache.cache_get", return_value=None):
            result = _get_risk_from_cache()
        assert result is None, f"Expected None, got {result!r}"

    def test_get_focus_from_cache_returns_none_no_redis(self):
        """_get_focus_from_cache() must return None when Redis is unavailable."""
        _get_focus_from_cache, _, _ = self._import_sse_functions()
        with patch("lib.core.cache.cache_get", return_value=None):
            result = _get_focus_from_cache()
        assert result is None, f"Expected None, got {result!r}"

    def test_get_posint_from_cache_returns_none_no_redis(self):
        """_get_posint_from_cache() must return None when Redis client is None."""
        _, _get_posint_from_cache, _ = self._import_sse_functions()
        # Patch _get_redis to explicitly return None (simulates unavailable Redis)
        with patch("lib.services.data.api.sse._get_redis", return_value=None):
            result = _get_posint_from_cache()
        assert result is None, f"Expected None, got {result!r}"

    def test_get_risk_from_cache_does_not_raise_on_exception(self):
        """_get_risk_from_cache() must swallow all exceptions and return None."""
        _, _, _get_risk_from_cache = self._import_sse_functions()

        def _exploding_cache_get(key):
            raise RuntimeError("Simulated Redis timeout")

        with patch("lib.core.cache.cache_get", side_effect=_exploding_cache_get):
            result = _get_risk_from_cache()
        assert result is None

    def test_get_focus_from_cache_does_not_raise_on_exception(self):
        """_get_focus_from_cache() must swallow all exceptions and return None."""
        _get_focus_from_cache, _, _ = self._import_sse_functions()

        def _exploding_cache_get(key):
            raise ConnectionError("Simulated Redis connection refused")

        with patch("lib.core.cache.cache_get", side_effect=_exploding_cache_get):
            result = _get_focus_from_cache()
        assert result is None

    def test_get_posint_from_cache_does_not_raise_on_exception(self):
        """_get_posint_from_cache() must swallow all exceptions and return None."""
        _, _get_posint_from_cache, _ = self._import_sse_functions()

        def _exploding_redis():
            raise ConnectionError("Simulated Redis connection refused")

        with patch("lib.services.data.api.sse._get_redis", side_effect=_exploding_redis):
            result = _get_posint_from_cache()
        assert result is None

    def test_all_three_cache_helpers_return_none_simultaneously(self):
        """All three helpers return None under a shared Redis-unavailable scenario."""
        _get_focus_from_cache, _get_posint_from_cache, _get_risk_from_cache = self._import_sse_functions()
        with (
            patch("lib.core.cache.cache_get", return_value=None),
            patch("lib.services.data.api.sse._get_redis", return_value=None),
        ):
            assert _get_risk_from_cache() is None
            assert _get_focus_from_cache() is None
            assert _get_posint_from_cache() is None


# ===========================================================================
# 1e. JSON serialisation with NaN / Inf
# ===========================================================================


class TestSanitizeFunction:
    """Unit tests for the module-level _sanitize() helper in data/main.py.

    _sanitize() recursively replaces non-finite floats with None so that
    downstream JSON serialisation (which rejects NaN / Inf) never crashes.
    """

    @pytest.fixture(autouse=True, scope="class")
    def _import_sanitize(self):
        """Import _sanitize once per class — slow because data/main.py is heavy."""
        from lib.services.data.main import _sanitize

        type(self)._sanitize = staticmethod(_sanitize)

    # ── Scalar inputs ────────────────────────────────────────────────────────

    def test_nan_becomes_none(self):
        assert self._sanitize(float("nan")) is None

    def test_pos_inf_becomes_none(self):
        assert self._sanitize(float("inf")) is None

    def test_neg_inf_becomes_none(self):
        assert self._sanitize(float("-inf")) is None

    def test_finite_float_unchanged(self):
        assert self._sanitize(3.14) == pytest.approx(3.14)

    def test_zero_unchanged(self):
        assert self._sanitize(0.0) == pytest.approx(0.0)

    def test_negative_float_unchanged(self):
        assert self._sanitize(-99.5) == pytest.approx(-99.5)

    def test_integer_unchanged(self):
        result = self._sanitize(42)
        assert result == 42

    def test_string_unchanged(self):
        assert self._sanitize("hello") == "hello"

    def test_none_unchanged(self):
        assert self._sanitize(None) is None

    def test_bool_unchanged(self):
        assert self._sanitize(True) is True

    # ── Nested containers ────────────────────────────────────────────────────

    def test_dict_nan_values_sanitised(self):
        raw = {"a": float("nan"), "b": 1.5, "c": float("inf")}
        result = self._sanitize(raw)
        assert result == {"a": None, "b": 1.5, "c": None}

    def test_list_nan_values_sanitised(self):
        raw = [float("nan"), 1.0, float("-inf"), 2.5]
        result = self._sanitize(raw)
        assert result == [None, 1.0, None, 2.5]

    def test_tuple_treated_as_list(self):
        raw = (float("nan"), 42)
        result = self._sanitize(raw)
        assert result == [None, 42]

    def test_nested_dict_sanitised_recursively(self):
        raw = {"outer": {"inner": float("nan"), "val": 1.0}, "top": float("inf")}
        result = self._sanitize(raw)
        assert result["outer"]["inner"] is None
        assert result["outer"]["val"] == pytest.approx(1.0)
        assert result["top"] is None

    def test_nested_list_sanitised_recursively(self):
        raw = [{"sharpe": float("nan"), "win_rate": 0.6}, {"sharpe": 1.2, "win_rate": float("inf")}]
        result = self._sanitize(raw)
        assert result[0]["sharpe"] is None
        assert result[0]["win_rate"] == pytest.approx(0.6)
        assert result[1]["sharpe"] == pytest.approx(1.2)
        assert result[1]["win_rate"] is None

    def test_deeply_nested_sanitised(self):
        raw = {"level1": {"level2": {"level3": float("nan")}}}
        result = self._sanitize(raw)
        assert result["level1"]["level2"]["level3"] is None


class TestSafeJSONResponse:
    """SafeJSONResponse renders NaN / Inf floats as JSON null (not crash)."""

    _cls: type

    @pytest.fixture(autouse=True, scope="class")
    def _import_response(self):
        from lib.services.data.main import SafeJSONResponse

        type(self)._cls = SafeJSONResponse

    def _render(self, content) -> dict:
        resp = self._cls(content=content)
        body = resp.body
        return json.loads(body)

    def test_nan_float_renders_as_null(self):
        result = self._render({"value": float("nan")})
        assert result["value"] is None

    def test_pos_inf_renders_as_null(self):
        result = self._render({"value": float("inf")})
        assert result["value"] is None

    def test_neg_inf_renders_as_null(self):
        result = self._render({"value": float("-inf")})
        assert result["value"] is None

    def test_finite_float_renders_correctly(self):
        result = self._render({"value": 3.14})
        assert result["value"] == pytest.approx(3.14)

    def test_nested_nan_renders_as_null(self):
        result = self._render({"metrics": {"sharpe": float("nan"), "win_rate": 0.65}})
        assert result["metrics"]["sharpe"] is None
        assert result["metrics"]["win_rate"] == pytest.approx(0.65)

    def test_list_with_nan_renders_correctly(self):
        result = self._render([1.0, float("nan"), 2.0, float("inf")])
        assert result == [1.0, None, 2.0, None]

    def test_valid_json_output_is_parseable(self):
        """Output of SafeJSONResponse must always be valid JSON (never raises)."""
        content = {
            "sharpe": float("nan"),
            "max_drawdown": float("-inf"),
            "win_rate": 0.6,
            "trades": [{"pnl": float("inf")}, {"pnl": -50.0}],
        }
        resp = self._cls(content=content)
        parsed = json.loads(resp.body)
        assert parsed["sharpe"] is None
        assert parsed["max_drawdown"] is None
        assert parsed["win_rate"] == pytest.approx(0.6)
        assert parsed["trades"][0]["pnl"] is None
        assert parsed["trades"][1]["pnl"] == pytest.approx(-50.0)

    def test_empty_dict_renders_as_empty_object(self):
        result = self._render({})
        assert result == {}

    def test_none_value_renders_as_null(self):
        result = self._render({"key": None})
        assert result["key"] is None
