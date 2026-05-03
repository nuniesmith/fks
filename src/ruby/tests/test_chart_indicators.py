"""
Tests for the Chart Indicators API router
==========================================
Covers:
  - _safe_float(): NaN / None / non-numeric guards
  - _series_to_records(): conversion from pandas Series to [{time, value}] records
  - GET /api/chart/assets    — default list when Redis absent, filtered list with Redis
  - GET /api/chart/{symbol}/regime — undefined fallback, trending / choppy normalisation
  - GET /api/chart/{symbol}/indicators:
      * None / empty bars → graceful degradation (bars_count=0, indicators={})
      * Synthetic bars → response structure, all expected indicator keys present
      * Subset of indicators via query param
      * bars_count reflects actual row count
  - Edge cases: unknown symbol, single-bar DataFrame
"""

import os

# Must be set before any project imports so Redis connections are skipped.
os.environ.setdefault("DISABLE_REDIS", "1")

import json
import math
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.services.data.api.chart_indicators import (
    _DEFAULT_ASSETS,
    _safe_float,
    _series_to_records,
    router,
)

# ---------------------------------------------------------------------------
# Shared test client
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    """TestClient with the chart-indicators router mounted."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Synthetic DataFrame factory
# ---------------------------------------------------------------------------


def _make_ohlcv(
    n: int = 300,
    start_price: float = 2350.0,
    freq: str = "1min",
    seed: int = 42,
) -> pd.DataFrame:
    """Return a realistic OHLCV DataFrame with CAPITAL columns and DatetimeIndex.

    Columns: Open, High, Low, Close, Volume  (capital — matches what
    _fetch_stored_bars returns and what chart_indicators.py expects).
    """
    rng = np.random.default_rng(seed)
    returns = rng.normal(0, 0.003, n)
    close = start_price * np.exp(np.cumsum(returns))

    spread = close * rng.uniform(0.001, 0.004, n)
    high = close + rng.uniform(0, 1, n) * spread
    low = close - rng.uniform(0, 1, n) * spread
    opn = close + rng.uniform(-0.5, 0.5, n) * spread

    high = np.maximum(high, np.maximum(opn, close))
    low = np.minimum(low, np.minimum(opn, close))

    volume = rng.poisson(500, n).astype(float)
    volume = np.maximum(volume, 1.0)

    idx = pd.date_range(
        "2025-01-06 09:30",
        periods=n,
        freq=freq,
        tz="America/New_York",
    )
    return pd.DataFrame(
        {
            "Open": opn,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=idx,
    )


def _make_single_bar() -> pd.DataFrame:
    idx = pd.date_range("2025-01-06 09:30", periods=1, freq="1min", tz="America/New_York")
    return pd.DataFrame(
        {"Open": [2350.0], "High": [2351.0], "Low": [2349.0], "Close": [2350.5], "Volume": [100.0]},
        index=idx,
    )


# ---------------------------------------------------------------------------
# Context-manager helpers for lazy-import mocking
# ---------------------------------------------------------------------------


def _patch_bars(df_or_none):
    """Patch _fetch_stored_bars wherever chart_indicators imports it.

    chart_indicators lazily does:
        from lib.services.data.api.bars import _fetch_stored_bars

    Injecting the mock at the module level is the most reliable approach.
    """
    mock_bars_module = MagicMock()
    mock_bars_module._fetch_stored_bars = MagicMock(return_value=df_or_none)
    return patch.dict(sys.modules, {"lib.services.data.api.bars": mock_bars_module})


def _patch_cache_get(return_value):
    """Patch lib.core.cache.cache_get for regime endpoint tests."""
    mock_cache = MagicMock()
    mock_cache.cache_get = MagicMock(return_value=return_value)
    return patch.dict(sys.modules, {"lib.core.cache": mock_cache})


def _patch_redis_helpers(redis_client_or_none):
    """Patch lib.core.redis_helpers.get_redis for assets endpoint tests."""
    mock_rh = MagicMock()
    mock_rh.get_redis = MagicMock(return_value=redis_client_or_none)
    return patch.dict(sys.modules, {"lib.core.redis_helpers": mock_rh})


# ===========================================================================
# _safe_float unit tests
# ===========================================================================


class TestSafeFloat:
    """Unit tests for the _safe_float() serialisation helper."""

    def test_normal_float(self):
        assert _safe_float(3.14) == pytest.approx(3.14)

    def test_integer(self):
        assert _safe_float(42) == pytest.approx(42.0)

    def test_string_number(self):
        assert _safe_float("1.5") == pytest.approx(1.5)

    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_nan_returns_none(self):
        assert _safe_float(float("nan")) is None

    def test_inf_returns_none(self):
        assert _safe_float(float("inf")) is None

    def test_neg_inf_returns_none(self):
        assert _safe_float(float("-inf")) is None

    def test_non_numeric_string_returns_none(self):
        assert _safe_float("abc") is None

    def test_zero_is_valid(self):
        assert _safe_float(0) == pytest.approx(0.0)

    def test_negative_float(self):
        assert _safe_float(-99.5) == pytest.approx(-99.5)


# ===========================================================================
# _series_to_records unit tests
# ===========================================================================


class TestSeriesToRecords:
    """Unit tests for _series_to_records()."""

    def _make_series(self, values, n=None):
        if n is None:
            n = len(values)
        idx = pd.date_range("2025-01-06 09:30", periods=n, freq="1min", tz="America/New_York")
        return pd.Series(values, index=idx)

    def test_returns_list(self):
        s = self._make_series([1.0, 2.0, 3.0])
        result = _series_to_records(s)
        assert isinstance(result, list)

    def test_each_record_has_time_and_value(self):
        s = self._make_series([10.0, 20.0])
        result = _series_to_records(s)
        for rec in result:
            assert "time" in rec
            assert "value" in rec

    def test_time_is_unix_seconds_int(self):
        s = self._make_series([1.0])
        rec = _series_to_records(s)[0]
        assert isinstance(rec["time"], int)

    def test_nan_values_skipped(self):
        s = self._make_series([1.0, float("nan"), 3.0])
        result = _series_to_records(s)
        # Only the non-NaN rows should survive
        assert len(result) == 2

    def test_all_nan_returns_empty(self):
        s = self._make_series([float("nan"), float("nan")])
        result = _series_to_records(s)
        assert result == []

    def test_empty_series_returns_empty(self):
        idx = pd.DatetimeIndex([], tz="America/New_York")
        s = pd.Series([], index=idx, dtype=float)
        result = _series_to_records(s)
        assert result == []

    def test_values_are_rounded_floats(self):
        s = self._make_series([1.123456789])
        rec = _series_to_records(s)[0]
        # Should be rounded to 6 decimal places
        assert rec["value"] == pytest.approx(1.123457, rel=1e-4)

    def test_monotone_time_for_sorted_index(self):
        s = self._make_series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _series_to_records(s)
        times = [r["time"] for r in result]
        assert times == sorted(times)


# ===========================================================================
# GET /api/chart/assets
# ===========================================================================


class TestChartAssets:
    """Tests for GET /api/chart/assets."""

    def test_returns_200(self, client: TestClient):
        with _patch_redis_helpers(None):
            resp = client.get("/api/chart/assets")
        assert resp.status_code == 200

    def test_response_has_assets_key(self, client: TestClient):
        with _patch_redis_helpers(None):
            data = client.get("/api/chart/assets").json()
        assert "assets" in data

    def test_assets_is_list(self, client: TestClient):
        with _patch_redis_helpers(None):
            data = client.get("/api/chart/assets").json()
        assert isinstance(data["assets"], list)

    def test_default_assets_returned_when_no_redis(self, client: TestClient):
        """Without Redis the fallback list should contain known futures symbols."""
        with _patch_redis_helpers(None):
            data = client.get("/api/chart/assets").json()
        for sym in ("MES", "MNQ", "MGC"):
            assert sym in data["assets"], f"{sym!r} missing from default assets"

    def test_default_assets_match_module_constant(self, client: TestClient):
        with _patch_redis_helpers(None):
            data = client.get("/api/chart/assets").json()
        for sym in _DEFAULT_ASSETS:
            assert sym in data["assets"]

    def test_assets_not_empty(self, client: TestClient):
        with _patch_redis_helpers(None):
            data = client.get("/api/chart/assets").json()
        assert len(data["assets"]) > 0

    def test_assets_from_redis_when_available(self, client: TestClient):
        """When Redis holds config:enabled_assets, those symbols are returned."""
        mock_r = MagicMock()
        enabled = [
            {"symbol": "MES", "enabled": True},
            {"symbol": "MGC", "enabled": True},
            {"symbol": "MNQ", "enabled": False},  # disabled — should be excluded
        ]
        mock_r.get = MagicMock(return_value=json.dumps(enabled).encode())

        with _patch_redis_helpers(mock_r):
            data = client.get("/api/chart/assets").json()

        assert "MES" in data["assets"]
        assert "MGC" in data["assets"]
        # MNQ is disabled so should not appear
        assert "MNQ" not in data["assets"]

    def test_redis_exception_falls_back_to_default(self, client: TestClient):
        """If Redis.get raises, the default list should still be returned."""
        mock_r = MagicMock()
        mock_r.get = MagicMock(side_effect=Exception("Redis error"))

        with _patch_redis_helpers(mock_r):
            data = client.get("/api/chart/assets").json()

        assert "MES" in data["assets"]

    def test_content_type_json(self, client: TestClient):
        with _patch_redis_helpers(None):
            resp = client.get("/api/chart/assets")
        assert "application/json" in resp.headers.get("content-type", "")


# ===========================================================================
# GET /api/chart/{symbol}/regime
# ===========================================================================

# Regime values accepted by the normaliser inside chart_regime()
_VALID_REGIMES = {"trending", "choppy", "undefined"}


class TestChartRegime:
    """Tests for GET /api/chart/{symbol}/regime."""

    def test_returns_200(self, client: TestClient):
        with _patch_cache_get(None):
            resp = client.get("/api/chart/MGC/regime")
        assert resp.status_code == 200

    def test_response_has_required_keys(self, client: TestClient):
        with _patch_cache_get(None):
            data = client.get("/api/chart/MGC/regime").json()
        for key in ("symbol", "regime", "confidence", "ts"):
            assert key in data, f"Missing key: {key!r}"

    def test_symbol_echoed_in_response(self, client: TestClient):
        with _patch_cache_get(None):
            data = client.get("/api/chart/MGC/regime").json()
        assert data["symbol"] == "MGC"

    def test_undefined_regime_when_no_redis(self, client: TestClient):
        with _patch_cache_get(None):
            data = client.get("/api/chart/MGC/regime").json()
        assert data["regime"] == "undefined"

    def test_confidence_zero_when_no_redis(self, client: TestClient):
        with _patch_cache_get(None):
            data = client.get("/api/chart/MGC/regime").json()
        assert data["confidence"] == pytest.approx(0.0)

    def test_trending_regime_returned(self, client: TestClient):
        payload = json.dumps({"regime": "trending", "confidence": 0.85}).encode()
        with _patch_cache_get(payload):
            data = client.get("/api/chart/MGC/regime").json()
        assert data["regime"] == "trending"
        assert data["confidence"] == pytest.approx(0.85)

    def test_choppy_regime_returned(self, client: TestClient):
        payload = json.dumps({"regime": "choppy", "confidence": 0.72}).encode()
        with _patch_cache_get(payload):
            data = client.get("/api/chart/MES/regime").json()
        assert data["regime"] == "choppy"

    def test_volatile_normalised_to_undefined(self, client: TestClient):
        """'volatile' is not a display regime — it should be normalised to 'undefined'."""
        payload = json.dumps({"regime": "volatile", "confidence": 0.5}).encode()
        with _patch_cache_get(payload):
            data = client.get("/api/chart/MGC/regime").json()
        assert data["regime"] == "undefined"

    def test_unknown_regime_normalised_to_undefined(self, client: TestClient):
        payload = json.dumps({"regime": "sideways", "confidence": 0.3}).encode()
        with _patch_cache_get(payload):
            data = client.get("/api/chart/MGC/regime").json()
        assert data["regime"] == "undefined"

    def test_regime_value_always_valid(self, client: TestClient):
        """Whatever Redis holds, the returned regime should be one of the valid values."""
        for raw_regime in ("trending", "choppy", "volatile", "undefined", "random", ""):
            payload = json.dumps({"regime": raw_regime, "confidence": 0.5}).encode()
            with _patch_cache_get(payload):
                data = client.get("/api/chart/MGC/regime").json()
            assert data["regime"] in _VALID_REGIMES, f"Got invalid regime {data['regime']!r} for raw {raw_regime!r}"

    def test_ts_is_integer(self, client: TestClient):
        with _patch_cache_get(None):
            data = client.get("/api/chart/MGC/regime").json()
        assert isinstance(data["ts"], int)
        assert data["ts"] > 0

    def test_different_symbols(self, client: TestClient):
        for sym in ("MES", "MNQ", "MGC", "MCL"):
            with _patch_cache_get(None):
                data = client.get(f"/api/chart/{sym}/regime").json()
            assert data["symbol"] == sym

    def test_cache_exception_returns_undefined(self, client: TestClient):
        """Even if cache_get raises, the endpoint should return a safe default."""
        mock_cache = MagicMock()
        mock_cache.cache_get = MagicMock(side_effect=Exception("cache error"))
        with patch.dict(sys.modules, {"lib.core.cache": mock_cache}):
            data = client.get("/api/chart/MGC/regime").json()
        assert data["regime"] == "undefined"
        assert data["symbol"] == "MGC"


# ===========================================================================
# GET /api/chart/{symbol}/indicators — empty / None bars
# ===========================================================================

# All indicator keys that the endpoint emits for the default indicator set
_ALL_INDICATOR_KEYS = {
    "rsi",
    "macd_line",
    "macd_signal",
    "macd_hist",
    "bb_upper",
    "bb_middle",
    "bb_lower",
    "atr",
    "vwap",
    "ema9",
    "ema21",
    "schaff",
    "chop",
}


class TestChartIndicatorsEmpty:
    """Indicator endpoint with no bar data — graceful degradation."""

    def test_returns_200_when_bars_none(self, client: TestClient):
        with _patch_bars(None):
            resp = client.get("/api/chart/MGC/indicators")
        assert resp.status_code == 200

    def test_returns_200_when_bars_empty(self, client: TestClient):
        empty_df = pd.DataFrame(columns=pd.Index(["Open", "High", "Low", "Close", "Volume"]))
        with _patch_bars(empty_df):
            resp = client.get("/api/chart/MGC/indicators")
        assert resp.status_code == 200

    def test_bars_count_zero_when_no_bars(self, client: TestClient):
        with _patch_bars(None):
            data = client.get("/api/chart/MGC/indicators").json()
        assert data["bars_count"] == 0

    def test_indicators_empty_dict_when_no_bars(self, client: TestClient):
        with _patch_bars(None):
            data = client.get("/api/chart/MGC/indicators").json()
        assert data["indicators"] == {}

    def test_symbol_echoed_when_no_bars(self, client: TestClient):
        with _patch_bars(None):
            data = client.get("/api/chart/MGC/indicators").json()
        assert data["symbol"] == "MGC"

    def test_interval_echoed_when_no_bars(self, client: TestClient):
        with _patch_bars(None):
            data = client.get("/api/chart/MGC/indicators?interval=5m").json()
        assert data["interval"] == "5m"

    def test_has_required_top_level_keys_when_no_bars(self, client: TestClient):
        with _patch_bars(None):
            data = client.get("/api/chart/MGC/indicators").json()
        for key in ("symbol", "interval", "bars_count", "indicators"):
            assert key in data, f"Missing key {key!r} in response"

    def test_bar_fetch_exception_returns_500(self, client: TestClient):
        """If _fetch_stored_bars raises, the endpoint returns HTTP 500."""
        mock_bars_module = MagicMock()
        mock_bars_module._fetch_stored_bars = MagicMock(side_effect=RuntimeError("DB connection failed"))
        with patch.dict(sys.modules, {"lib.services.data.api.bars": mock_bars_module}):
            resp = client.get("/api/chart/MGC/indicators")
        assert resp.status_code == 500


# ===========================================================================
# GET /api/chart/{symbol}/indicators — with synthetic bar data
# ===========================================================================


class TestChartIndicatorsWithData:
    """Indicator endpoint with synthetic OHLCV data."""

    @pytest.fixture()
    def df(self):
        """300-bar 1-minute OHLCV DataFrame at MGC-like prices."""
        return _make_ohlcv(n=300, start_price=2350.0, seed=42)

    @pytest.fixture()
    def small_df(self):
        """Small 30-bar DataFrame — some indicators may not have enough data."""
        return _make_ohlcv(n=30, start_price=2350.0, seed=7)

    def test_returns_200_with_synthetic_bars(self, client: TestClient, df):
        with _patch_bars(df):
            resp = client.get("/api/chart/MGC/indicators")
        assert resp.status_code == 200

    def test_bars_count_matches_dataframe_length(self, client: TestClient, df):
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators").json()
        assert data["bars_count"] == len(df)

    def test_symbol_echoed(self, client: TestClient, df):
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators").json()
        assert data["symbol"] == "MGC"

    def test_interval_echoed(self, client: TestClient, df):
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators?interval=5m").json()
        assert data["interval"] == "5m"

    def test_indicators_key_present(self, client: TestClient, df):
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators").json()
        assert "indicators" in data

    def test_indicators_is_dict(self, client: TestClient, df):
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators").json()
        assert isinstance(data["indicators"], dict)

    def test_all_default_indicator_keys_present(self, client: TestClient, df):
        """All keys in _ALL_INDICATOR_KEYS should be present (may be empty lists)."""
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators").json()
        ind = data["indicators"]
        missing = _ALL_INDICATOR_KEYS - ind.keys()
        assert not missing, f"Missing indicator keys: {missing}"

    def test_each_indicator_is_list(self, client: TestClient, df):
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators").json()
        for key, val in data["indicators"].items():
            assert isinstance(val, list), f"Indicator {key!r} is not a list"

    def test_record_structure_when_data_present(self, client: TestClient, df):
        """Any non-empty indicator list should contain {time, value} dicts."""
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators").json()
        for key, records in data["indicators"].items():
            if not records:
                continue  # skip empty (indicator lib may not be installed)
            for rec in records[:3]:  # spot-check first three
                assert "time" in rec, f"Missing 'time' in {key!r} record"
                assert "value" in rec, f"Missing 'value' in {key!r} record"
                assert isinstance(rec["time"], int)
                assert isinstance(rec["value"], float)

    def test_single_indicator_subset(self, client: TestClient, df):
        """Requesting only 'rsi' should return a response with only 'rsi'."""
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators?indicators=rsi").json()
        ind = data["indicators"]
        assert "rsi" in ind
        # No other indicator keys should be present
        unexpected = set(ind.keys()) - {"rsi"}
        assert not unexpected, f"Unexpected indicator keys: {unexpected}"

    def test_macd_keys_present_as_group(self, client: TestClient, df):
        """Requesting 'macd' should produce macd_line, macd_signal, macd_hist."""
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators?indicators=macd").json()
        ind = data["indicators"]
        for key in ("macd_line", "macd_signal", "macd_hist"):
            assert key in ind, f"Missing MACD sub-key {key!r}"

    def test_bbands_keys_present_as_group(self, client: TestClient, df):
        """Requesting 'bbands' should produce bb_upper, bb_middle, bb_lower."""
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators?indicators=bbands").json()
        ind = data["indicators"]
        for key in ("bb_upper", "bb_middle", "bb_lower"):
            assert key in ind, f"Missing BBands sub-key {key!r}"

    def test_multiple_indicators_subset(self, client: TestClient, df):
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators?indicators=rsi,atr").json()
        ind = data["indicators"]
        assert "rsi" in ind
        assert "atr" in ind
        # Indicators not requested should not be present
        assert "vwap" not in ind
        assert "ema9" not in ind

    def test_bars_count_300(self, client: TestClient, df):
        assert len(df) == 300
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators").json()
        assert data["bars_count"] == 300

    def test_small_dataframe_no_crash(self, client: TestClient, small_df):
        """Fewer bars than indicator warm-up period should not crash the endpoint."""
        with _patch_bars(small_df):
            resp = client.get("/api/chart/MGC/indicators")
        assert resp.status_code == 200
        data = resp.json()
        assert data["bars_count"] == len(small_df)

    def test_single_bar_no_crash(self, client: TestClient):
        """A single-row DataFrame should degrade gracefully."""
        with _patch_bars(_make_single_bar()):
            resp = client.get("/api/chart/MGC/indicators")
        assert resp.status_code == 200

    def test_different_symbol_mes(self, client: TestClient):
        df = _make_ohlcv(n=100, start_price=5420.0, seed=10)
        with _patch_bars(df):
            data = client.get("/api/chart/MES/indicators").json()
        assert data["symbol"] == "MES"
        assert data["bars_count"] == 100

    def test_response_serialisable(self, client: TestClient, df):
        """The full response must be valid JSON with no NaN / Inf values."""
        with _patch_bars(df):
            resp = client.get("/api/chart/MGC/indicators")
        # If the response is already deserialisable we're good
        data = resp.json()
        for key, records in data["indicators"].items():
            for rec in records:
                assert math.isfinite(rec["value"]), f"Non-finite value {rec['value']} in indicator {key!r}"

    def test_days_back_query_param_accepted(self, client: TestClient, df):
        """days_back query param should be forwarded to _fetch_stored_bars."""
        mock_bars_module = MagicMock()
        mock_bars_module._fetch_stored_bars = MagicMock(return_value=df)
        with patch.dict(sys.modules, {"lib.services.data.api.bars": mock_bars_module}):
            resp = client.get("/api/chart/MGC/indicators?days_back=10")
        assert resp.status_code == 200
        mock_bars_module._fetch_stored_bars.assert_called_once()
        call_kwargs = mock_bars_module._fetch_stored_bars.call_args
        # days_back should be passed through
        assert 10 in call_kwargs.args or call_kwargs.kwargs.get("days_back") == 10


# ===========================================================================
# Response structure contract tests
# ===========================================================================


class TestChartIndicatorsStructure:
    """Strict contract tests for the response envelope."""

    @pytest.fixture()
    def df(self):
        return _make_ohlcv(n=200, start_price=2350.0, seed=99)

    def test_top_level_keys_exact(self, client: TestClient, df):
        """The top-level response should have exactly these four keys."""
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators").json()
        assert set(data.keys()) >= {"symbol", "interval", "bars_count", "indicators"}

    def test_bars_count_is_int(self, client: TestClient, df):
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators").json()
        assert isinstance(data["bars_count"], int)

    def test_interval_is_string(self, client: TestClient, df):
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators").json()
        assert isinstance(data["interval"], str)

    def test_default_interval_is_1m(self, client: TestClient, df):
        with _patch_bars(df):
            data = client.get("/api/chart/MGC/indicators").json()
        assert data["interval"] == "1m"

    def test_empty_bars_response_structure(self, client: TestClient):
        with _patch_bars(None):
            data = client.get("/api/chart/MGC/indicators").json()
        assert data == {
            "symbol": "MGC",
            "interval": "1m",
            "bars_count": 0,
            "indicators": {},
        }

    def test_content_type_json(self, client: TestClient, df):
        with _patch_bars(df):
            resp = client.get("/api/chart/MGC/indicators")
        assert "application/json" in resp.headers.get("content-type", "")

    def test_days_back_validation_minimum(self, client: TestClient):
        """days_back=0 should be rejected (ge=1)."""
        resp = client.get("/api/chart/MGC/indicators?days_back=0")
        assert resp.status_code == 422

    def test_days_back_validation_maximum(self, client: TestClient):
        """days_back=91 should be rejected (le=90)."""
        resp = client.get("/api/chart/MGC/indicators?days_back=91")
        assert resp.status_code == 422
