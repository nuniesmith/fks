"""
Tests for the DOM (Depth of Market) API
========================================
Covers:
  - _build_mock_snapshot(): structure, bid/ask ordering, totals, imbalance,
    levels parameter, edge-case sizes (levels=1, levels=50)
  - _build_snapshot(): mock routing, crypto symbol pass-through
  - dom_snapshot endpoint (GET /api/dom/snapshot)
  - dom_config endpoint (GET /api/dom/config)
  - NaN / edge-case guard clauses
  - Crypto symbol routing: "BTC" maps to "KRAKEN:XBTUSD"
"""

import os

# Must be set before any project imports so Redis connections are skipped.
os.environ.setdefault("DISABLE_REDIS", "1")

import math
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.services.data.api.dom import (
    _CRYPTO_DOM_SYMBOLS,
    _DEFAULT_LEVELS,
    _DEFAULT_SYMBOL,
    _TICK_SIZES,
    _build_mock_snapshot,
    _build_snapshot,
    router,
    sse_router,
)

# ---------------------------------------------------------------------------
# Shared test client fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    """TestClient wired up with both the REST router and the SSE router."""
    app = FastAPI()
    app.include_router(router)
    app.include_router(sse_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_finite(v: object) -> bool:
    """Return True if *v* is a real, finite number (not NaN / Inf / None)."""
    try:
        f = float(v)  # type: ignore[arg-type]
        return math.isfinite(f)
    except (TypeError, ValueError):
        return False


# ===========================================================================
# Tests for _build_mock_snapshot
# ===========================================================================


class TestBuildMockSnapshot:
    """Unit tests for _build_mock_snapshot() — no network / Redis required."""

    def test_returns_dict(self):
        result = _build_mock_snapshot("MES")
        assert isinstance(result, dict)

    def test_symbol_preserved(self):
        result = _build_mock_snapshot("MGC")
        assert result["symbol"] == "MGC"

    def test_required_keys_present(self):
        result = _build_mock_snapshot("MES")
        required = {
            "symbol",
            "bids",
            "asks",
            "last",
            "spread",
            "bid_total",
            "ask_total",
            "imbalance_ratio",
            "levels",
            "timestamp",
            "source",
        }
        assert required <= result.keys(), f"Missing keys: {required - result.keys()}"

    def test_source_is_mock(self):
        result = _build_mock_snapshot("MES")
        assert result["source"] == "mock"

    # ------------------------------------------------------------------
    # Bid / Ask structure
    # ------------------------------------------------------------------

    def test_bids_is_list(self):
        result = _build_mock_snapshot("MES")
        assert isinstance(result["bids"], list)

    def test_asks_is_list(self):
        result = _build_mock_snapshot("MES")
        assert isinstance(result["asks"], list)

    def test_bids_count_matches_levels(self):
        result = _build_mock_snapshot("MES", levels=10)
        assert len(result["bids"]) == 10

    def test_asks_count_matches_levels(self):
        result = _build_mock_snapshot("MES", levels=10)
        assert len(result["asks"]) == 10

    def test_bid_level_keys(self):
        result = _build_mock_snapshot("MES")
        for lvl in result["bids"]:
            assert "price" in lvl
            assert "size" in lvl
            assert "cumulative_size" in lvl

    def test_ask_level_keys(self):
        result = _build_mock_snapshot("MES")
        for lvl in result["asks"]:
            assert "price" in lvl
            assert "size" in lvl
            assert "cumulative_size" in lvl

    def test_bids_descending_price(self):
        """Bids should be ordered best (highest) first."""
        result = _build_mock_snapshot("MES", levels=10)
        prices = [b["price"] for b in result["bids"]]
        assert prices == sorted(prices, reverse=True), f"Bids not descending: {prices}"

    def test_asks_ascending_price(self):
        """Asks should be ordered best (lowest) first."""
        result = _build_mock_snapshot("MES", levels=10)
        prices = [a["price"] for a in result["asks"]]
        assert prices == sorted(prices), f"Asks not ascending: {prices}"

    def test_best_bid_below_best_ask(self):
        """The spread must always be positive."""
        result = _build_mock_snapshot("MES", levels=5)
        assert result["bids"][0]["price"] < result["asks"][0]["price"]

    # ------------------------------------------------------------------
    # Sizes and totals
    # ------------------------------------------------------------------

    def test_bid_sizes_positive(self):
        result = _build_mock_snapshot("MES")
        assert all(b["size"] > 0 for b in result["bids"])

    def test_ask_sizes_positive(self):
        result = _build_mock_snapshot("MES")
        assert all(a["size"] > 0 for a in result["asks"])

    def test_bid_total_equals_sum_of_bid_sizes(self):
        result = _build_mock_snapshot("MES")
        assert result["bid_total"] == sum(b["size"] for b in result["bids"])

    def test_ask_total_equals_sum_of_ask_sizes(self):
        result = _build_mock_snapshot("MES")
        assert result["ask_total"] == sum(a["size"] for a in result["asks"])

    def test_bid_cumulative_monotone_increasing(self):
        result = _build_mock_snapshot("MES", levels=10)
        cumsizes = [b["cumulative_size"] for b in result["bids"]]
        assert cumsizes == sorted(cumsizes), f"Bid cumulative sizes not monotone: {cumsizes}"

    def test_ask_cumulative_monotone_increasing(self):
        result = _build_mock_snapshot("MES", levels=10)
        cumsizes = [a["cumulative_size"] for a in result["asks"]]
        assert cumsizes == sorted(cumsizes), f"Ask cumulative sizes not monotone: {cumsizes}"

    def test_imbalance_ratio_is_finite(self):
        result = _build_mock_snapshot("MES")
        assert _is_finite(result["imbalance_ratio"])

    def test_imbalance_ratio_positive(self):
        result = _build_mock_snapshot("MES")
        assert result["imbalance_ratio"] > 0

    # ------------------------------------------------------------------
    # Spread
    # ------------------------------------------------------------------

    def test_spread_is_positive(self):
        result = _build_mock_snapshot("MES")
        assert result["spread"] > 0

    def test_spread_matches_best_prices(self):
        """spread == best_ask - best_bid (within floating-point tolerance)."""
        result = _build_mock_snapshot("MES")
        expected = result["asks"][0]["price"] - result["bids"][0]["price"]
        assert abs(result["spread"] - expected) < 1e-6

    # ------------------------------------------------------------------
    # last price
    # ------------------------------------------------------------------

    def test_last_is_finite(self):
        result = _build_mock_snapshot("MES")
        assert _is_finite(result["last"])

    def test_last_between_bid_and_ask(self):
        result = _build_mock_snapshot("MES")
        best_bid = result["bids"][0]["price"]
        best_ask = result["asks"][0]["price"]
        assert best_bid <= result["last"] <= best_ask

    # ------------------------------------------------------------------
    # levels parameter
    # ------------------------------------------------------------------

    def test_levels_stored_in_result(self):
        result = _build_mock_snapshot("MES", levels=7)
        assert result["levels"] == 7

    def test_levels_1(self):
        """Minimum valid levels."""
        result = _build_mock_snapshot("MES", levels=1)
        assert len(result["bids"]) == 1
        assert len(result["asks"]) == 1

    def test_levels_50(self):
        """Maximum valid levels as accepted by the endpoint."""
        result = _build_mock_snapshot("MES", levels=50)
        assert len(result["bids"]) == 50
        assert len(result["asks"]) == 50

    # ------------------------------------------------------------------
    # Various symbols
    # ------------------------------------------------------------------

    def test_mgc_snapshot(self):
        result = _build_mock_snapshot("MGC")
        assert result["symbol"] == "MGC"
        assert result["bids"][0]["price"] > 0

    def test_mnq_snapshot(self):
        result = _build_mock_snapshot("MNQ")
        assert result["symbol"] == "MNQ"

    def test_unknown_symbol_uses_fallback_price(self):
        """An unrecognised symbol should still return a valid snapshot."""
        result = _build_mock_snapshot("FAKE")
        assert result["symbol"] == "FAKE"
        assert len(result["bids"]) > 0
        assert len(result["asks"]) > 0
        assert _is_finite(result["last"])

    # ------------------------------------------------------------------
    # Timestamp
    # ------------------------------------------------------------------

    def test_timestamp_is_recent(self):
        import time

        result = _build_mock_snapshot("MES")
        assert abs(result["timestamp"] - time.time()) < 5


# ===========================================================================
# Tests for _build_snapshot (source routing)
# ===========================================================================


class TestBuildSnapshot:
    """Test _build_snapshot() with source routing patched."""

    def _mock_source(self, source: str):
        """Return a patch context that forces the given source label."""
        return patch(
            "lib.services.data.api.dom.should_use_source",
            return_value=source,
        )

    def test_mock_source_returns_mock_snapshot(self):
        with self._mock_source("mock"):
            result = _build_snapshot("MES")
        assert result["source"] == "mock"

    def test_mock_source_skips_live_lookup(self):
        with self._mock_source("mock"), patch("lib.services.data.api.dom._build_live_snapshot") as live:
            _build_snapshot("MES")
            live.assert_not_called()

    def test_futures_symbol_uses_mock_when_no_live_data(self):
        """Futures symbols have no Kraken ticker → always use mock."""
        with self._mock_source("kraken"):
            result = _build_snapshot("MES")
        assert result["source"] == "mock"

    def test_crypto_symbol_btc_tried_via_kraken(self):
        """BTC should map to KRAKEN:XBTUSD and attempt a live snapshot."""
        fake_live = {"symbol": "BTC", "source": "kraken_live", "bids": [], "asks": []}
        with (
            self._mock_source("kraken"),
            patch(
                "lib.services.data.api.dom._build_live_snapshot",
                return_value=fake_live,
            ) as live,
        ):
            result = _build_snapshot("BTC")
            live.assert_called_once_with("BTC", "KRAKEN:XBTUSD", levels=_DEFAULT_LEVELS)
            assert result["source"] == "kraken_live"

    def test_crypto_symbol_falls_back_to_mock_when_no_live_data(self):
        """If live snapshot returns None, fall back to mock."""
        with (
            self._mock_source("kraken"),
            patch(
                "lib.services.data.api.dom._build_live_snapshot",
                return_value=None,
            ),
        ):
            result = _build_snapshot("BTC")
        assert result["source"] == "mock"

    def test_btc_internal_ticker_mapping(self):
        """Verify the BTC → KRAKEN:XBTUSD mapping in the module constant."""
        assert _CRYPTO_DOM_SYMBOLS.get("BTC") == "KRAKEN:XBTUSD"

    def test_eth_internal_ticker_mapping(self):
        assert _CRYPTO_DOM_SYMBOLS.get("ETH") == "KRAKEN:ETHUSD"

    def test_sol_internal_ticker_mapping(self):
        assert _CRYPTO_DOM_SYMBOLS.get("SOL") == "KRAKEN:SOLUSD"

    def test_levels_forwarded_to_mock(self):
        with (
            self._mock_source("mock"),
            patch(
                "lib.services.data.api.dom._build_mock_snapshot",
                wraps=_build_mock_snapshot,
            ) as mock_fn,
        ):
            _build_snapshot("MES", levels=7)
            mock_fn.assert_called_once_with("MES", levels=7)


# ===========================================================================
# Tests for GET /api/dom/snapshot
# ===========================================================================


class TestDomSnapshotEndpoint:
    """Integration tests for the /api/dom/snapshot REST endpoint."""

    def test_returns_200(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot")
        assert resp.status_code == 200

    def test_default_symbol_is_mes(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot")
        data = resp.json()
        assert data["symbol"] == _DEFAULT_SYMBOL

    def test_symbol_query_param(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot?symbol=MGC")
        data = resp.json()
        assert data["symbol"] == "MGC"

    def test_levels_query_param(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot?symbol=MES&levels=5")
        data = resp.json()
        assert len(data["bids"]) == 5
        assert len(data["asks"]) == 5

    def test_default_levels(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot")
        data = resp.json()
        assert len(data["bids"]) == _DEFAULT_LEVELS
        assert len(data["asks"]) == _DEFAULT_LEVELS

    def test_response_has_bids_and_asks(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot")
        data = resp.json()
        assert "bids" in data
        assert "asks" in data

    def test_response_has_spread(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot")
        data = resp.json()
        assert "spread" in data
        assert _is_finite(data["spread"])

    def test_response_has_bid_total_and_ask_total(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot")
        data = resp.json()
        assert "bid_total" in data
        assert "ask_total" in data
        assert data["bid_total"] > 0
        assert data["ask_total"] > 0

    def test_response_has_imbalance_ratio(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot")
        data = resp.json()
        assert "imbalance_ratio" in data
        assert _is_finite(data["imbalance_ratio"])

    def test_response_has_last(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot")
        data = resp.json()
        assert "last" in data
        assert _is_finite(data["last"])

    def test_response_has_source(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot")
        data = resp.json()
        assert "source" in data

    def test_levels_minimum_1(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot?levels=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["bids"]) == 1
        assert len(data["asks"]) == 1

    def test_levels_maximum_50(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot?levels=50")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["bids"]) == 50
        assert len(data["asks"]) == 50

    def test_levels_below_minimum_rejected(self, client: TestClient):
        """levels=0 should fail validation (ge=1)."""
        resp = client.get("/api/dom/snapshot?levels=0")
        assert resp.status_code == 422

    def test_levels_above_maximum_rejected(self, client: TestClient):
        """levels=51 should fail validation (le=50)."""
        resp = client.get("/api/dom/snapshot?levels=51")
        assert resp.status_code == 422

    def test_mnq_snapshot(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot?symbol=MNQ")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "MNQ"

    def test_content_type_json(self, client: TestClient):
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot")
        assert "application/json" in resp.headers.get("content-type", "")


# ===========================================================================
# Tests for GET /api/dom/config
# ===========================================================================


class TestDomConfigEndpoint:
    """Integration tests for the /api/dom/config endpoint."""

    def test_returns_200(self, client: TestClient):
        resp = client.get("/api/dom/config")
        assert resp.status_code == 200

    def test_has_default_symbol(self, client: TestClient):
        data = client.get("/api/dom/config").json()
        assert "default_symbol" in data
        assert data["default_symbol"] == _DEFAULT_SYMBOL

    def test_has_default_levels(self, client: TestClient):
        data = client.get("/api/dom/config").json()
        assert "default_levels" in data
        assert data["default_levels"] == _DEFAULT_LEVELS

    def test_has_available_symbols(self, client: TestClient):
        data = client.get("/api/dom/config").json()
        assert "available_symbols" in data
        assert isinstance(data["available_symbols"], list)
        assert len(data["available_symbols"]) > 0

    def test_available_symbols_includes_futures(self, client: TestClient):
        data = client.get("/api/dom/config").json()
        symbols = data["available_symbols"]
        for sym in ("MES", "MNQ", "MGC"):
            assert sym in symbols, f"{sym!r} missing from available_symbols"

    def test_has_tick_sizes(self, client: TestClient):
        data = client.get("/api/dom/config").json()
        assert "tick_sizes" in data
        assert isinstance(data["tick_sizes"], dict)

    def test_tick_sizes_include_known_futures(self, client: TestClient):
        data = client.get("/api/dom/config").json()
        tick_sizes = data["tick_sizes"]
        assert "MES" in tick_sizes
        assert tick_sizes["MES"] == pytest.approx(_TICK_SIZES["MES"])

    def test_has_color_scheme(self, client: TestClient):
        data = client.get("/api/dom/config").json()
        assert "color_scheme" in data
        cs = data["color_scheme"]
        assert "bid_text" in cs
        assert "ask_text" in cs

    def test_has_update_interval_ms(self, client: TestClient):
        data = client.get("/api/dom/config").json()
        assert "update_interval_ms" in data
        assert isinstance(data["update_interval_ms"], int)
        assert data["update_interval_ms"] > 0

    def test_has_max_levels(self, client: TestClient):
        data = client.get("/api/dom/config").json()
        assert "max_levels" in data
        assert data["max_levels"] >= _DEFAULT_LEVELS

    def test_has_show_cumulative(self, client: TestClient):
        data = client.get("/api/dom/config").json()
        assert "show_cumulative" in data
        assert isinstance(data["show_cumulative"], bool)

    def test_has_crypto_symbols(self, client: TestClient):
        data = client.get("/api/dom/config").json()
        assert "crypto_symbols" in data
        assert isinstance(data["crypto_symbols"], dict)

    def test_crypto_symbols_include_btc(self, client: TestClient):
        data = client.get("/api/dom/config").json()
        assert "BTC" in data["crypto_symbols"]
        assert data["crypto_symbols"]["BTC"] == "KRAKEN:XBTUSD"

    def test_content_type_json(self, client: TestClient):
        resp = client.get("/api/dom/config")
        assert "application/json" in resp.headers.get("content-type", "")


# ===========================================================================
# Edge-case / NaN guard tests
# ===========================================================================


class TestEdgeCases:
    """Guard-clause tests for unusual inputs and values."""

    def test_empty_symbol_string_still_returns_snapshot(self):
        """An empty symbol falls through to mock with unknown defaults."""
        result = _build_mock_snapshot("", levels=5)
        assert isinstance(result, dict)
        assert "bids" in result
        assert len(result["bids"]) == 5

    def test_imbalance_ratio_never_nan(self):
        """bid_total / ask_total must not produce NaN even with small sizes."""
        result = _build_mock_snapshot("MES", levels=1)
        assert not math.isnan(result["imbalance_ratio"])

    def test_all_bid_prices_finite(self):
        result = _build_mock_snapshot("MES", levels=20)
        for b in result["bids"]:
            assert _is_finite(b["price"]), f"Non-finite bid price: {b['price']}"

    def test_all_ask_prices_finite(self):
        result = _build_mock_snapshot("MES", levels=20)
        for a in result["asks"]:
            assert _is_finite(a["price"]), f"Non-finite ask price: {a['price']}"

    def test_levels_1_spread_still_positive(self):
        result = _build_mock_snapshot("MES", levels=1)
        assert result["spread"] > 0

    def test_levels_50_totals_match_sum(self):
        result = _build_mock_snapshot("MNQ", levels=50)
        assert result["bid_total"] == sum(b["size"] for b in result["bids"])
        assert result["ask_total"] == sum(a["size"] for a in result["asks"])

    def test_snapshot_serialisable_to_json(self):
        """The snapshot must be JSON-serialisable without errors."""
        import json

        result = _build_mock_snapshot("MES", levels=10)
        serialised = json.dumps(result)
        reparsed = json.loads(serialised)
        assert reparsed["symbol"] == "MES"

    def test_snapshot_via_endpoint_with_unknown_symbol(self, client: TestClient):
        """Unknown symbol should still return 200 (mock fallback)."""
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot?symbol=UNKNWN")
        assert resp.status_code == 200

    def test_crypto_symbol_via_endpoint_uses_mock_when_redis_down(self, client: TestClient):
        """BTC should return a valid mock snapshot when Redis is unavailable."""
        with patch("lib.services.data.api.dom.should_use_source", return_value="mock"):
            resp = client.get("/api/dom/snapshot?symbol=BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert "bids" in data
        assert "asks" in data


# ===========================================================================
# Crypto routing
# ===========================================================================


class TestCryptoSymbolRouting:
    """Verify that crypto shorthand symbols resolve to the correct tickers."""

    def test_btc_maps_to_kraken_xbtusd(self):
        assert _CRYPTO_DOM_SYMBOLS["BTC"] == "KRAKEN:XBTUSD"

    def test_eth_maps_to_kraken_ethusd(self):
        assert _CRYPTO_DOM_SYMBOLS["ETH"] == "KRAKEN:ETHUSD"

    def test_sol_maps_to_kraken_solusd(self):
        assert _CRYPTO_DOM_SYMBOLS["SOL"] == "KRAKEN:SOLUSD"

    def test_internal_ticker_resolves_to_itself(self):
        assert _CRYPTO_DOM_SYMBOLS["KRAKEN:XBTUSD"] == "KRAKEN:XBTUSD"

    def test_build_snapshot_btc_live_path(self):
        """_build_snapshot with 'kraken' source calls _build_live_snapshot for BTC."""
        fake_live_result = {
            "symbol": "BTC",
            "source": "kraken_live",
            "bids": [{"price": 65000.0, "size": 1, "cumulative_size": 1}],
            "asks": [{"price": 65000.1, "size": 1, "cumulative_size": 1}],
            "bid_total": 1,
            "ask_total": 1,
            "imbalance_ratio": 1.0,
            "last": 65000.0,
            "spread": 0.1,
            "levels": 1,
            "timestamp": 0.0,
        }
        with (
            patch(
                "lib.services.data.api.dom.should_use_source",
                return_value="kraken",
            ),
            patch(
                "lib.services.data.api.dom._build_live_snapshot",
                return_value=fake_live_result,
            ) as live,
        ):
            result = _build_snapshot("BTC", levels=1)

        live.assert_called_once_with("BTC", "KRAKEN:XBTUSD", levels=1)
        assert result["source"] == "kraken_live"

    def test_build_snapshot_eth_live_path(self):
        """ETH should try KRAKEN:ETHUSD."""
        with (
            patch(
                "lib.services.data.api.dom.should_use_source",
                return_value="kraken",
            ),
            patch(
                "lib.services.data.api.dom._build_live_snapshot",
                return_value=None,
            ) as live,
        ):
            _build_snapshot("ETH")

        live.assert_called_once_with("ETH", "KRAKEN:ETHUSD", levels=_DEFAULT_LEVELS)

    def test_build_snapshot_mes_is_not_crypto(self):
        """MES has no crypto mapping — _build_live_snapshot should not be called."""
        with (
            patch(
                "lib.services.data.api.dom.should_use_source",
                return_value="kraken",
            ),
            patch(
                "lib.services.data.api.dom._build_live_snapshot",
            ) as live,
        ):
            result = _build_snapshot("MES")

        live.assert_not_called()
        assert result["source"] == "mock"
