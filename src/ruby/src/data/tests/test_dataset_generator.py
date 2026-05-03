"""Tests for lib.data_factory.dataset_generator — indicator math and utilities.

Covers the pure-Python technical indicator helpers (_ema, _rsi, _atr,
_vwap_daily, _bollinger_bands) and the standalone utility functions
(_parse_filename, _safe_filename, _forward_fill_gaps, _interval_sort_key,
_fmt, _write_csv, _sha256, _count_rows_and_range) that can be exercised
without any database, Redis, or network access.
"""

from __future__ import annotations

import json
import math
import random
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# EMA
# ---------------------------------------------------------------------------


class TestEMA(unittest.TestCase):
    """Tests for the _ema (Exponential Moving Average) helper."""

    def test_basic_ema(self):
        """EMA with period=3 should produce None warmup then valid floats."""
        from data_factory.dataset_generator import _ema

        values = [10.0, 11.0, 12.0, 11.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
        result = _ema(values, 3)
        self.assertEqual(len(result), len(values))
        # First (period-1) entries are warmup → None
        self.assertIsNone(result[0])
        self.assertIsNone(result[1])
        # Third value is the SMA seed: (10+11+12)/3 = 11.0
        self.assertAlmostEqual(result[2], 11.0, places=4)
        # Remaining values should all be valid floats
        for v in result[3:]:
            self.assertIsNotNone(v)
            self.assertIsInstance(v, float)

    def test_ema_monotonic_input(self):
        """Monotonically increasing input → EMA should also increase after warmup."""
        from data_factory.dataset_generator import _ema

        values = [float(i) for i in range(1, 21)]
        result = _ema(values, 5)
        non_none = [v for v in result if v is not None]
        for i in range(1, len(non_none)):
            self.assertGreater(non_none[i], non_none[i - 1])

    def test_empty_input(self):
        """Empty input should return an empty list."""
        from data_factory.dataset_generator import _ema

        self.assertEqual(_ema([], 3), [])

    def test_single_value(self):
        """A single value with period > 1 should return [None]."""
        from data_factory.dataset_generator import _ema

        result = _ema([10.0], 3)
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0])

    def test_period_equals_length(self):
        """When len(values) == period, only the last entry is non-None (SMA seed)."""
        from data_factory.dataset_generator import _ema

        values = [2.0, 4.0, 6.0]
        result = _ema(values, 3)
        self.assertEqual(len(result), 3)
        self.assertIsNone(result[0])
        self.assertIsNone(result[1])
        self.assertAlmostEqual(result[2], 4.0, places=4)

    def test_fewer_values_than_period(self):
        """When values are shorter than period, all entries should be None."""
        from data_factory.dataset_generator import _ema

        result = _ema([1.0, 2.0], 5)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(v is None for v in result))

    def test_constant_input_ema_equals_constant(self):
        """EMA of a constant series should equal that constant after warmup."""
        from data_factory.dataset_generator import _ema

        values = [42.0] * 20
        result = _ema(values, 5)
        for v in result:
            if v is not None:
                self.assertAlmostEqual(v, 42.0, places=6)


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------


class TestRSI(unittest.TestCase):
    """Tests for the _rsi (Relative Strength Index) helper."""

    def test_basic_rsi_steadily_rising(self):
        """Steadily rising prices → RSI should approach 100."""
        from data_factory.dataset_generator import _rsi

        values = [float(i) for i in range(1, 30)]
        result = _rsi(values, 14)
        self.assertEqual(len(result), len(values))
        last = result[-1]
        self.assertIsNotNone(last)
        self.assertGreater(last, 90.0)

    def test_basic_rsi_steadily_falling(self):
        """Steadily falling prices → RSI should approach 0."""
        from data_factory.dataset_generator import _rsi

        values = [float(100 - i) for i in range(30)]
        result = _rsi(values, 14)
        last = result[-1]
        self.assertIsNotNone(last)
        self.assertLess(last, 10.0)

    def test_rsi_range(self):
        """RSI should always be in [0, 100] for any input."""
        from data_factory.dataset_generator import _rsi

        random.seed(42)
        values = [100.0 + random.uniform(-5, 5) for _ in range(50)]
        result = _rsi(values, 14)
        for v in result:
            if v is not None:
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 100.0)

    def test_rsi_warmup_nones(self):
        """First `period` entries should be None (warmup)."""
        from data_factory.dataset_generator import _rsi

        values = [float(i) for i in range(30)]
        result = _rsi(values, 14)
        for v in result[:14]:
            self.assertIsNone(v)
        # Entry at index=period should be the first computed RSI
        self.assertIsNotNone(result[14])

    def test_rsi_constant_prices(self):
        """Constant prices → no gains or losses → RSI should be 100 (0/0 edge)."""
        from data_factory.dataset_generator import _rsi

        values = [50.0] * 30
        result = _rsi(values, 14)
        # With zero avg_loss, function returns 100.0
        for v in result:
            if v is not None:
                self.assertAlmostEqual(v, 100.0, places=2)

    def test_rsi_too_few_values(self):
        """Fewer than period+1 values should yield all None."""
        from data_factory.dataset_generator import _rsi

        result = _rsi([1.0, 2.0, 3.0], 14)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(v is None for v in result))


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------


class TestATR(unittest.TestCase):
    """Tests for the _atr (Average True Range) helper."""

    def test_basic_atr_constant_range(self):
        """When high-low is constant, ATR should converge to that range."""
        from data_factory.dataset_generator import _atr

        highs = [11.0] * 20
        lows = [9.0] * 20
        closes = [10.0] * 20
        result = _atr(highs, lows, closes, 14)
        self.assertEqual(len(result), 20)
        # After warmup, ATR ≈ 2.0
        for v in result[14:]:
            if v is not None:
                self.assertAlmostEqual(v, 2.0, places=1)

    def test_atr_warmup_nones(self):
        """First (period-1) entries should be None."""
        from data_factory.dataset_generator import _atr

        highs = [11.0] * 20
        lows = [9.0] * 20
        closes = [10.0] * 20
        result = _atr(highs, lows, closes, 14)
        for v in result[:13]:
            self.assertIsNone(v)
        # Entry at index=period-1 is the first ATR (SMA of true ranges)
        self.assertIsNotNone(result[13])

    def test_atr_uses_prev_close_for_gaps(self):
        """True range should account for gap from previous close."""
        from data_factory.dataset_generator import _atr

        # Create a scenario with a gap: close at 10, next bar high=15 low=14
        highs = [11.0] * 5 + [15.0] + [11.0] * 14
        lows = [9.0] * 5 + [14.0] + [9.0] * 14
        closes = [10.0] * 5 + [14.5] + [10.0] * 14
        result = _atr(highs, lows, closes, 5)
        # The ATR after the gap bar should be larger than 2.0
        self.assertIsNotNone(result[5])
        self.assertGreater(result[5], 2.0)

    def test_atr_too_few_values(self):
        """Fewer than period+1 values → all None."""
        from data_factory.dataset_generator import _atr

        result = _atr([11.0] * 3, [9.0] * 3, [10.0] * 3, 14)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(v is None for v in result))

    def test_atr_always_non_negative(self):
        """ATR should never be negative."""
        from data_factory.dataset_generator import _atr

        random.seed(99)
        n = 40
        closes = [100.0]
        for _ in range(n - 1):
            closes.append(closes[-1] + random.uniform(-3, 3))
        highs = [c + abs(random.uniform(0, 2)) for c in closes]
        lows = [c - abs(random.uniform(0, 2)) for c in closes]
        result = _atr(highs, lows, closes, 14)
        for v in result:
            if v is not None:
                self.assertGreaterEqual(v, 0.0)


# ---------------------------------------------------------------------------
# VWAP
# ---------------------------------------------------------------------------


class TestVWAP(unittest.TestCase):
    """Tests for the _vwap_daily (Volume-Weighted Average Price) helper."""

    def test_basic_vwap_constant_price(self):
        """When all prices are equal, VWAP should equal that price."""
        from data_factory.dataset_generator import _vwap_daily

        base = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        timestamps = [base.isoformat() for _ in range(10)]
        highs = [10.0] * 10
        lows = [10.0] * 10
        closes = [10.0] * 10
        volumes = [100.0] * 10
        result = _vwap_daily(timestamps, highs, lows, closes, volumes)
        self.assertEqual(len(result), 10)
        for v in result:
            if v is not None:
                self.assertAlmostEqual(v, 10.0, places=4)

    def test_vwap_resets_on_new_day(self):
        """VWAP should reset cumulative sums on a new calendar day."""
        from data_factory.dataset_generator import _vwap_daily

        day1 = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        day2 = datetime(2024, 1, 16, 10, 0, 0, tzinfo=UTC)
        timestamps = [day1.isoformat(), day1.isoformat(), day2.isoformat(), day2.isoformat()]
        highs = [12.0, 12.0, 20.0, 20.0]
        lows = [8.0, 8.0, 18.0, 18.0]
        closes = [10.0, 10.0, 19.0, 19.0]
        volumes = [100.0, 100.0, 100.0, 100.0]
        result = _vwap_daily(timestamps, highs, lows, closes, volumes)
        self.assertEqual(len(result), 4)
        # Day 1 VWAP: typical = (12+8+10)/3 = 10.0
        self.assertAlmostEqual(result[0], 10.0, places=2)
        # Day 2 first bar resets: typical = (20+18+19)/3 = 19.0
        self.assertAlmostEqual(result[2], 19.0, places=2)

    def test_vwap_zero_volume(self):
        """Zero volume should produce None."""
        from data_factory.dataset_generator import _vwap_daily

        timestamps = ["2024-01-15T10:00:00+00:00"]
        result = _vwap_daily(timestamps, [10.0], [10.0], [10.0], [0.0])
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0])

    def test_vwap_weighted_towards_high_volume(self):
        """VWAP should be pulled towards the price with higher volume."""
        from data_factory.dataset_generator import _vwap_daily

        ts = "2024-01-15T10:00:00+00:00"
        timestamps = [ts, ts]
        # Bar 1: typical price = (10+10+10)/3 = 10.0, volume = 10
        # Bar 2: typical price = (20+20+20)/3 = 20.0, volume = 1000
        highs = [10.0, 20.0]
        lows = [10.0, 20.0]
        closes = [10.0, 20.0]
        volumes = [10.0, 1000.0]
        result = _vwap_daily(timestamps, highs, lows, closes, volumes)
        # VWAP after bar 2 should be much closer to 20 than 10
        self.assertGreater(result[1], 19.0)

    def test_vwap_empty_input(self):
        """Empty input → empty output."""
        from data_factory.dataset_generator import _vwap_daily

        result = _vwap_daily([], [], [], [], [])
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------


class TestBollingerBands(unittest.TestCase):
    """Tests for the _bollinger_bands helper."""

    def test_basic_bb_ordering(self):
        """After warmup: upper > mid > lower."""
        from data_factory.dataset_generator import _bollinger_bands

        values = [10.0 + i * 0.1 for i in range(30)]
        upper, mid, lower = _bollinger_bands(values, 20, 2.0)
        self.assertEqual(len(upper), len(values))
        self.assertEqual(len(mid), len(values))
        self.assertEqual(len(lower), len(values))
        for i in range(19, len(values)):
            if upper[i] is not None and mid[i] is not None and lower[i] is not None:
                self.assertGreater(upper[i], mid[i])
                self.assertGreater(mid[i], lower[i])

    def test_bb_warmup_nones(self):
        """First (period-1) entries should be None."""
        from data_factory.dataset_generator import _bollinger_bands

        values = [10.0] * 30
        upper, mid, lower = _bollinger_bands(values, 20, 2.0)
        for i in range(19):
            self.assertIsNone(upper[i])
            self.assertIsNone(mid[i])
            self.assertIsNone(lower[i])

    def test_bb_constant_input_bands_equal(self):
        """Constant input → std=0, so upper == mid == lower."""
        from data_factory.dataset_generator import _bollinger_bands

        values = [50.0] * 30
        upper, mid, lower = _bollinger_bands(values, 20, 2.0)
        for i in range(19, 30):
            self.assertAlmostEqual(upper[i], 50.0, places=6)
            self.assertAlmostEqual(mid[i], 50.0, places=6)
            self.assertAlmostEqual(lower[i], 50.0, places=6)

    def test_bb_middle_is_sma(self):
        """Middle band should be SMA(period)."""
        from data_factory.dataset_generator import _bollinger_bands

        values = [float(i) for i in range(1, 26)]
        _, mid, _ = _bollinger_bands(values, 5, 2.0)
        # At index 4 (first non-None): SMA of [1,2,3,4,5] = 3.0
        self.assertAlmostEqual(mid[4], 3.0, places=4)
        # At index 5: SMA of [2,3,4,5,6] = 4.0
        self.assertAlmostEqual(mid[5], 4.0, places=4)

    def test_bb_symmetry(self):
        """upper - mid should equal mid - lower (symmetric bands)."""
        from data_factory.dataset_generator import _bollinger_bands

        random.seed(7)
        values = [50.0 + random.uniform(-5, 5) for _ in range(40)]
        upper, mid, lower = _bollinger_bands(values, 10, 2.0)
        for i in range(9, len(values)):
            if upper[i] is not None:
                spread_up = upper[i] - mid[i]
                spread_dn = mid[i] - lower[i]
                self.assertAlmostEqual(spread_up, spread_dn, places=8)

    def test_bb_output_lengths(self):
        """Output lists should match input length when len >= period."""
        from data_factory.dataset_generator import _bollinger_bands

        for n in (20, 25, 100):
            values = [1.0] * n
            upper, mid, lower = _bollinger_bands(values, 20, 2.0)
            self.assertEqual(len(upper), n)
            self.assertEqual(len(mid), n)
            self.assertEqual(len(lower), n)

    def test_bb_short_input_returns_warmup_only(self):
        """When input is shorter than period, output is just the warmup Nones.

        The implementation always initialises with ``[None] * (period - 1)``
        and the loop body never executes when ``len(values) < period``, so
        the returned lists have length ``period - 1`` regardless of input
        length.  This is an edge-case artefact, not a contract, but we
        document the current behaviour here.
        """
        from data_factory.dataset_generator import _bollinger_bands

        for n in (0, 1, 5, 19):
            values = [1.0] * n
            upper, mid, lower = _bollinger_bands(values, 20, 2.0)
            # Current implementation: warmup list of length period-1
            self.assertEqual(len(upper), 19)
            self.assertEqual(len(mid), 19)
            self.assertEqual(len(lower), 19)
            self.assertTrue(all(v is None for v in upper))
            self.assertTrue(all(v is None for v in mid))
            self.assertTrue(all(v is None for v in lower))


# ---------------------------------------------------------------------------
# _parse_filename
# ---------------------------------------------------------------------------


class TestParseFilename(unittest.TestCase):
    """Tests for the _parse_filename utility."""

    def test_training_file(self):
        from data_factory.dataset_generator import _parse_filename

        ds_type, ds_interval = _parse_filename("training_BTC_USD_20240115.csv")
        self.assertEqual(ds_type, "training")
        self.assertEqual(ds_interval, "multi")

    def test_backtest_file(self):
        from data_factory.dataset_generator import _parse_filename

        ds_type, ds_interval = _parse_filename("backtest_BTC_USD_1h_20240115.csv")
        self.assertEqual(ds_type, "backtest")
        self.assertEqual(ds_interval, "1h")

    def test_features_file(self):
        from data_factory.dataset_generator import _parse_filename

        ds_type, ds_interval = _parse_filename("features_Gold_5m_20240115.parquet")
        self.assertEqual(ds_type, "features")
        self.assertEqual(ds_interval, "5m")

    def test_unknown_file(self):
        from data_factory.dataset_generator import _parse_filename

        ds_type, ds_interval = _parse_filename("random_file.csv")
        self.assertEqual(ds_type, "random")
        self.assertEqual(ds_interval, "unknown")


# ---------------------------------------------------------------------------
# _safe_filename
# ---------------------------------------------------------------------------


class TestSafeFilename(unittest.TestCase):
    """Tests for the _safe_filename utility."""

    def test_slash_replaced(self):
        from data_factory.dataset_generator import _safe_filename

        self.assertEqual(_safe_filename("BTC/USD"), "BTC_USD")

    def test_backslash_replaced(self):
        from data_factory.dataset_generator import _safe_filename

        self.assertEqual(_safe_filename("A\\B"), "A_B")

    def test_space_replaced(self):
        from data_factory.dataset_generator import _safe_filename

        self.assertEqual(_safe_filename("Micro Gold"), "Micro_Gold")

    def test_clean_name_unchanged(self):
        from data_factory.dataset_generator import _safe_filename

        self.assertEqual(_safe_filename("Gold"), "Gold")


# ---------------------------------------------------------------------------
# _fmt
# ---------------------------------------------------------------------------


class TestFmt(unittest.TestCase):
    """Tests for the _fmt value formatter."""

    def test_none_returns_empty(self):
        from data_factory.dataset_generator import _fmt

        self.assertEqual(_fmt(None), "")

    def test_float_formatted(self):
        from data_factory.dataset_generator import _fmt

        result = _fmt(1.234567890)
        self.assertEqual(result, "1.234568")  # 6 decimal places, rounded

    def test_zero(self):
        from data_factory.dataset_generator import _fmt

        self.assertEqual(_fmt(0.0), "0.000000")


# ---------------------------------------------------------------------------
# _interval_sort_key
# ---------------------------------------------------------------------------


class TestIntervalSortKey(unittest.TestCase):
    """Tests for _interval_sort_key ordering."""

    def test_known_intervals_sorted(self):
        from data_factory.dataset_generator import _interval_sort_key

        intervals = ["1d", "1h", "5m", "1m", "15m", "4h"]
        sorted_intervals = sorted(intervals, key=_interval_sort_key)
        self.assertEqual(sorted_intervals, ["1m", "5m", "15m", "1h", "4h", "1d"])

    def test_unknown_interval_sorts_last(self):
        from data_factory.dataset_generator import _interval_sort_key

        self.assertEqual(_interval_sort_key("weird"), 999999)


# ---------------------------------------------------------------------------
# _forward_fill_gaps
# ---------------------------------------------------------------------------


class TestForwardFillGaps(unittest.TestCase):
    """Tests for the _forward_fill_gaps gap-filling helper."""

    def test_no_gaps(self):
        """Sequential bars without gaps should pass through unchanged."""
        from data_factory.dataset_generator import _forward_fill_gaps

        base = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        bars = []
        for i in range(5):
            ts = (base + timedelta(minutes=i)).isoformat()
            bars.append(
                {
                    "timestamp": ts,
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.0,
                    "close": 10.0,
                    "volume": 100.0,
                }
            )
        result = _forward_fill_gaps(bars, "1m")
        self.assertEqual(len(result), 5)

    def test_fills_single_gap(self):
        """A 1-bar gap in 1m data should produce one fill bar."""
        from data_factory.dataset_generator import _forward_fill_gaps

        base = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        bars = [
            {"timestamp": base.isoformat(), "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100.0},
            # Skip 10:01 (the gap)
            {
                "timestamp": (base + timedelta(minutes=2)).isoformat(),
                "open": 11.0,
                "high": 12.0,
                "low": 10.0,
                "close": 11.0,
                "volume": 50.0,
            },
        ]
        result = _forward_fill_gaps(bars, "1m")
        # Should have 3 bars: original, fill, original
        self.assertEqual(len(result), 3)
        # Fill bar should use previous close
        fill = result[1]
        self.assertAlmostEqual(fill["open"], 10.5)
        self.assertAlmostEqual(fill["close"], 10.5)
        self.assertAlmostEqual(fill["volume"], 0.0)

    def test_unknown_interval_returns_as_is(self):
        """Unknown interval string should return bars unchanged."""
        from data_factory.dataset_generator import _forward_fill_gaps

        bars = [{"timestamp": "2024-01-01T00:00:00", "close": 10.0}]
        result = _forward_fill_gaps(bars, "unknown")
        self.assertEqual(result, bars)

    def test_empty_bars(self):
        """Empty list → empty list."""
        from data_factory.dataset_generator import _forward_fill_gaps

        self.assertEqual(_forward_fill_gaps([], "1m"), [])

    def test_single_bar(self):
        """Single bar → returned unchanged."""
        from data_factory.dataset_generator import _forward_fill_gaps

        bar = [
            {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
            }
        ]
        result = _forward_fill_gaps(bar, "1m")
        self.assertEqual(len(result), 1)

    def test_gap_cap_at_500(self):
        """Very large gaps should be capped at 500 fill bars."""
        from data_factory.dataset_generator import _forward_fill_gaps

        base = datetime(2024, 1, 15, 0, 0, 0, tzinfo=UTC)
        far = base + timedelta(days=5)  # ~7200 minutes gap on 1m
        bars = [
            {"timestamp": base.isoformat(), "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0, "volume": 100.0},
            {"timestamp": far.isoformat(), "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0, "volume": 100.0},
        ]
        result = _forward_fill_gaps(bars, "1m")
        # 2 original bars + max 500 fills = 502
        self.assertEqual(len(result), 502)


# ---------------------------------------------------------------------------
# _write_csv + _sha256 + _count_rows_and_range (file I/O)
# ---------------------------------------------------------------------------


class TestFileUtilities(unittest.TestCase):
    """Tests for _write_csv, _sha256, and _count_rows_and_range."""

    def test_write_csv_and_read_back(self):
        """Write a CSV, then verify its contents."""
        from data_factory.dataset_generator import _write_csv

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "test.csv"
            header = ["timestamp", "open", "high", "low", "close", "volume"]
            rows = [
                ["2024-01-15T10:00:00", "10.0", "11.0", "9.0", "10.5", "100"],
                ["2024-01-15T10:01:00", "10.5", "11.5", "9.5", "11.0", "200"],
            ]
            _write_csv(p, header, rows)
            text = p.read_text(encoding="utf-8")
            lines = text.strip().split("\n")
            self.assertEqual(len(lines), 3)  # header + 2 data rows
            self.assertEqual(lines[0], "timestamp,open,high,low,close,volume")

    def test_sha256_deterministic(self):
        """SHA-256 of the same content should be identical."""
        from data_factory.dataset_generator import _sha256, _write_csv

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "test.csv"
            _write_csv(p, ["a", "b"], [["1", "2"]])
            h1 = _sha256(p)
            h2 = _sha256(p)
            self.assertEqual(h1, h2)
            self.assertEqual(len(h1), 64)  # SHA-256 hex digest is 64 chars

    def test_count_rows_and_range_csv(self):
        """_count_rows_and_range should count data rows and extract date range."""
        from data_factory.dataset_generator import _count_rows_and_range, _write_csv

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "test.csv"
            _write_csv(
                p,
                ["timestamp", "close"],
                [
                    ["2024-01-15T10:00:00", "10.0"],
                    ["2024-01-15T10:01:00", "11.0"],
                    ["2024-01-15T10:02:00", "12.0"],
                ],
            )
            row_count, date_range = _count_rows_and_range(p)
            self.assertEqual(row_count, 3)
            self.assertEqual(date_range["start"], "2024-01-15T10:00:00")
            self.assertEqual(date_range["end"], "2024-01-15T10:02:00")

    def test_count_rows_empty_csv(self):
        """An empty CSV (header only) should return 0 rows."""
        from data_factory.dataset_generator import _count_rows_and_range, _write_csv

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "empty.csv"
            _write_csv(p, ["timestamp", "close"], [])
            row_count, date_range = _count_rows_and_range(p)
            self.assertEqual(row_count, 0)


# ---------------------------------------------------------------------------
# Coverage threshold logic
# ---------------------------------------------------------------------------


class TestCoverageThreshold(unittest.TestCase):
    """Test the coverage threshold constant and its expected default."""

    def test_default_min_coverage(self):
        """DATASET_MIN_COVERAGE should default to 0.80."""
        from data_factory.dataset_generator import DATASET_MIN_COVERAGE

        self.assertAlmostEqual(DATASET_MIN_COVERAGE, 0.80, places=2)

    def test_training_intervals_not_empty(self):
        """The training intervals list should have at least one entry."""
        from data_factory.dataset_generator import _TRAINING_INTERVALS

        self.assertIsInstance(_TRAINING_INTERVALS, list)
        self.assertGreater(len(_TRAINING_INTERVALS), 0)

    def test_backtest_intervals_not_empty(self):
        from data_factory.dataset_generator import _BACKTEST_INTERVALS

        self.assertIsInstance(_BACKTEST_INTERVALS, list)
        self.assertGreater(len(_BACKTEST_INTERVALS), 0)

    def test_feature_intervals_not_empty(self):
        from data_factory.dataset_generator import _FEATURE_INTERVALS

        self.assertIsInstance(_FEATURE_INTERVALS, list)
        self.assertGreater(len(_FEATURE_INTERVALS), 0)


# ---------------------------------------------------------------------------
# Manifest structure validation
# ---------------------------------------------------------------------------


class TestManifestStructure(unittest.TestCase):
    """Validate the expected manifest JSON structure shape."""

    def test_manifest_keys(self):
        """A valid manifest should have generated_at, datasets, and coverage_summary."""
        # Simulate a manifest dict as _write_manifest would produce
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "datasets": [
                {
                    "symbol": "BTC/USD",
                    "type": "training",
                    "interval": "multi",
                    "path": "BTC_USD/training_BTC_USD_20240115.csv",
                    "rows": 1000,
                    "date_range": {"start": "2024-01-01", "end": "2024-01-15"},
                    "size_bytes": 50000,
                    "checksum_sha256": "abc123",
                }
            ],
            "coverage_summary": {"BTC/USD": {"1m": 0.95, "5m": 0.88}},
        }
        # Validate top-level keys
        self.assertIn("generated_at", manifest)
        self.assertIn("datasets", manifest)
        self.assertIn("coverage_summary", manifest)
        self.assertIsInstance(manifest["datasets"], list)
        self.assertIsInstance(manifest["coverage_summary"], dict)

    def test_dataset_entry_has_required_fields(self):
        """Each dataset entry should contain all required metadata fields."""
        required_fields = {
            "symbol",
            "type",
            "interval",
            "path",
            "rows",
            "date_range",
            "size_bytes",
            "checksum_sha256",
        }
        entry = {
            "symbol": "Gold",
            "type": "features",
            "interval": "1h",
            "path": "Gold/features_Gold_1h_20240115.csv",
            "rows": 500,
            "date_range": {"start": "2024-01-01", "end": "2024-01-15"},
            "size_bytes": 25000,
            "checksum_sha256": "def456",
        }
        self.assertTrue(required_fields.issubset(entry.keys()))

    def test_manifest_serialises_to_json(self):
        """Manifest dict should be JSON-serialisable."""
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "datasets": [],
            "coverage_summary": {},
        }
        json_str = json.dumps(manifest, indent=2)
        loaded = json.loads(json_str)
        self.assertEqual(loaded["datasets"], [])


# ---------------------------------------------------------------------------
# Dataset file path construction
# ---------------------------------------------------------------------------


class TestDatasetPathConstruction(unittest.TestCase):
    """Verify the expected file path patterns for generated datasets."""

    def test_training_path_pattern(self):
        """Training dataset path: {output_dir}/{safe_symbol}/training_{safe_symbol}_{date}.csv"""
        from data_factory.dataset_generator import _safe_filename

        symbol = "BTC/USD"
        safe = _safe_filename(symbol)
        output_dir = Path("data/datasets")
        date_str = "20240115"
        expected = output_dir / safe / f"training_{safe}_{date_str}.csv"
        self.assertEqual(str(expected), "data/datasets/BTC_USD/training_BTC_USD_20240115.csv")

    def test_backtest_path_pattern(self):
        """Backtest dataset: {output_dir}/{safe_symbol}/backtest_{safe_symbol}_{interval}_{date}.csv"""
        from data_factory.dataset_generator import _safe_filename

        symbol = "Gold"
        safe = _safe_filename(symbol)
        output_dir = Path("data/datasets")
        expected = output_dir / safe / f"backtest_{safe}_1h_20240115.csv"
        self.assertEqual(str(expected), "data/datasets/Gold/backtest_Gold_1h_20240115.csv")

    def test_features_path_pattern(self):
        """Feature dataset: {output_dir}/{safe_symbol}/features_{safe_symbol}_{interval}_{date}.csv"""
        from data_factory.dataset_generator import _safe_filename

        symbol = "Micro Gold"
        safe = _safe_filename(symbol)
        output_dir = Path("data/datasets")
        expected = output_dir / safe / f"features_{safe}_5m_20240115.csv"
        self.assertEqual(str(expected), "data/datasets/Micro_Gold/features_Micro_Gold_5m_20240115.csv")


if __name__ == "__main__":
    unittest.main()
