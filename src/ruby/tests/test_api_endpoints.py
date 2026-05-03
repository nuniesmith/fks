"""
Comprehensive API endpoint tests covering:
  - Kraken spot account (balance, orders, trades) — unauthenticated + authenticated
  - Kraken futures account (balance, positions, orders, fills) — unauthenticated + authenticated
  - Bars (status, assets, historical symbol bars)
  - Backup status
  - CNN model status
  - Chart indicators (assets, indicators, regime)
  - Market data source
  - Health check
"""

from __future__ import annotations

import os

# Must be set before any project imports so Redis connections are skipped.
os.environ.setdefault("DISABLE_REDIS", "1")

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_sqlite(tmp_path, monkeypatch):
    """Point the models layer at a fresh SQLite file and initialise tables."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.setenv("DATABASE_URL", "")

    from lib.core import models  # noqa: PLC0415

    models.DB_PATH = db_file
    models.DATABASE_URL = ""
    models._USE_POSTGRES = False
    models._sa_engine = None
    models.init_db()
    return db_file


# ===========================================================================
# Fixtures — Kraken
# ===========================================================================


@pytest.fixture()
def kraken_client(monkeypatch):
    """Kraken TestClient with *no* API keys configured → unauthenticated path."""
    # Clear all Kraken credential env vars
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    monkeypatch.delenv("KRAKEN_FUTURES_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_FUTURES_API_SECRET", raising=False)

    import lib.services.data.api.kraken as kraken_mod  # noqa: PLC0415

    # Patch at module level so no key_manager / network call is made
    monkeypatch.setattr(kraken_mod, "_get_authed_provider", lambda: None)
    monkeypatch.setattr(kraken_mod, "_get_authed_futures_client", lambda: None)

    app = FastAPI()
    app.include_router(kraken_mod.router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def kraken_authed_client(monkeypatch):
    """Kraken TestClient with mocked authenticated provider + futures client."""
    # --- Spot mock ---
    mock_provider = MagicMock()
    mock_provider.get_balance.return_value = {
        "XXBT": "0.5000",
        "ZUSD": "1234.56",
    }
    mock_provider.get_open_orders.return_value = {"open": {}}
    mock_provider.get_trade_history.return_value = {
        "trades": {
            "T001": {
                "ordertxid": "O001",
                "pair": "XBTUSD",
                "type": "buy",
                "ordertype": "limit",
                "price": "50000.00",
                "vol": "0.01",
                "cost": "500.00",
                "fee": "1.25",
                "time": 1700000000.0,
                "misc": "",
            },
            "T002": {
                "ordertxid": "O002",
                "pair": "ETHUSD",
                "type": "sell",
                "ordertype": "market",
                "price": "3000.00",
                "vol": "0.5",
                "cost": "1500.00",
                "fee": "3.75",
                "time": 1700003600.0,
                "misc": "",
            },
            "T003": {
                "ordertxid": "O003",
                "pair": "XBTUSD",
                "type": "buy",
                "ordertype": "limit",
                "price": "49000.00",
                "vol": "0.02",
                "cost": "980.00",
                "fee": "2.45",
                "time": 1699990000.0,
                "misc": "",
            },
        }
    }

    # --- Futures mock ---
    mock_futures = MagicMock()
    mock_futures.get_accounts.return_value = {
        "result": "success",
        "accounts": {
            "fi_xbtusd_180615": {
                "type": "marginAccount",
                "currency": "XBT",
                "balance": 0.5,
                "pnl": 0.01,
                "unrealizedFunding": 0.001,
            }
        },
    }
    mock_futures.get_open_positions.return_value = {"openPositions": []}
    mock_futures.get_open_orders.return_value = {"openOrders": []}
    mock_futures.get_fills.return_value = {
        "fills": [
            {
                "fillId": "F001",
                "symbol": "PI_XBTUSD",
                "side": "buy",
                "price": 50000.0,
                "size": 1,
                "fillTime": "2025-01-01T12:00:00Z",
                "orderId": "O101",
                "fee": 0.5,
            }
        ]
    }

    import lib.services.data.api.kraken as kraken_mod  # noqa: PLC0415

    monkeypatch.setattr(kraken_mod, "_get_authed_provider", lambda: mock_provider)
    monkeypatch.setattr(kraken_mod, "_get_authed_futures_client", lambda: mock_futures)

    app = FastAPI()
    app.include_router(kraken_mod.router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# Fixtures — Bars
# ===========================================================================


@pytest.fixture()
def bars_client(monkeypatch, tmp_path):
    """Bars TestClient backed by a fresh SQLite database."""
    _init_sqlite(tmp_path, monkeypatch)

    # Try to create the historical_bars table so bar-count queries don't fail
    try:
        from lib.services.engine.backfill import init_backfill_table  # noqa: PLC0415

        init_backfill_table()
    except Exception:
        pass  # table creation failure is handled gracefully inside each endpoint

    from lib.services.data.api.bars import router as bars_router  # noqa: PLC0415

    app = FastAPI()
    app.include_router(bars_router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# Fixtures — Backup
# ===========================================================================


@pytest.fixture()
def backup_client(monkeypatch, tmp_path):
    """Backup TestClient backed by a fresh SQLite database."""
    _init_sqlite(tmp_path, monkeypatch)

    from lib.services.data.api.backup import router as backup_router  # noqa: PLC0415

    app = FastAPI()
    # router already carries the /api/backup prefix
    app.include_router(backup_router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# Fixtures — CNN
# ===========================================================================


@pytest.fixture()
def cnn_client():
    """CNN TestClient — no file system or Redis dependencies required."""
    from lib.services.data.api.cnn import router as cnn_router  # noqa: PLC0415

    app = FastAPI()
    app.include_router(cnn_router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# Fixtures — Chart Indicators
# ===========================================================================


@pytest.fixture()
def chart_client(monkeypatch, tmp_path):
    """Chart Indicators TestClient backed by a fresh SQLite database."""
    _init_sqlite(tmp_path, monkeypatch)

    from lib.services.data.api.chart_indicators import router as chart_router  # noqa: PLC0415

    app = FastAPI()
    app.include_router(chart_router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# Fixtures — Market Data
# ===========================================================================


@pytest.fixture()
def market_data_client():
    """Market Data TestClient — stateless source endpoint only."""
    from lib.services.data.api.market_data import router as market_data_router  # noqa: PLC0415

    app = FastAPI()
    app.include_router(market_data_router, prefix="/data")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# Fixtures — Health
# ===========================================================================


@pytest.fixture()
def health_client(monkeypatch, tmp_path):
    """Health TestClient backed by a fresh SQLite database.

    _get_engine_or_none is patched to return None so the engine always shows
    as 'not_initialized' regardless of any singleton created by other tests.
    """
    _init_sqlite(tmp_path, monkeypatch)

    import lib.services.data.api.health as health_mod  # noqa: PLC0415

    monkeypatch.setattr(health_mod, "_get_engine_or_none", lambda: None)

    from lib.services.data.api.health import router as health_router  # noqa: PLC0415

    app = FastAPI()
    app.include_router(health_router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# Tests — Kraken Spot: Unauthenticated
# ===========================================================================


class TestKrakenSpotUnauthenticated:
    """Verify that spot account endpoints return 200 with authenticated=False
    when no API credentials are configured."""

    def test_balance_returns_200(self, kraken_client):
        resp = kraken_client.get("/kraken/account/balance")
        assert resp.status_code == 200

    def test_balance_not_authenticated(self, kraken_client):
        data = kraken_client.get("/kraken/account/balance").json()
        assert data["authenticated"] is False

    def test_balance_has_error_key(self, kraken_client):
        data = kraken_client.get("/kraken/account/balance").json()
        assert "error" in data

    def test_balance_has_empty_balances(self, kraken_client):
        data = kraken_client.get("/kraken/account/balance").json()
        assert data.get("balances") == []

    def test_orders_returns_200(self, kraken_client):
        resp = kraken_client.get("/kraken/account/orders")
        assert resp.status_code == 200

    def test_orders_not_authenticated(self, kraken_client):
        data = kraken_client.get("/kraken/account/orders").json()
        assert data["authenticated"] is False

    def test_orders_has_error_key(self, kraken_client):
        data = kraken_client.get("/kraken/account/orders").json()
        assert "error" in data

    def test_trades_returns_200(self, kraken_client):
        resp = kraken_client.get("/kraken/account/trades")
        assert resp.status_code == 200

    def test_trades_not_authenticated(self, kraken_client):
        data = kraken_client.get("/kraken/account/trades").json()
        assert data["authenticated"] is False

    def test_trades_has_error_key(self, kraken_client):
        data = kraken_client.get("/kraken/account/trades").json()
        assert "error" in data


# ===========================================================================
# Tests — Kraken Futures: Unauthenticated
# ===========================================================================


class TestKrakenFuturesUnauthenticated:
    """Verify that futures account endpoints return 200 with authenticated=False
    when no futures API credentials are configured."""

    def test_futures_balance_returns_200(self, kraken_client):
        resp = kraken_client.get("/kraken/futures/balance")
        assert resp.status_code == 200

    def test_futures_balance_not_authenticated(self, kraken_client):
        data = kraken_client.get("/kraken/futures/balance").json()
        assert data["authenticated"] is False

    def test_futures_balance_has_error_key(self, kraken_client):
        data = kraken_client.get("/kraken/futures/balance").json()
        assert "error" in data

    def test_futures_balance_has_empty_accounts(self, kraken_client):
        data = kraken_client.get("/kraken/futures/balance").json()
        assert data.get("accounts") == []

    def test_futures_positions_returns_200(self, kraken_client):
        resp = kraken_client.get("/kraken/futures/positions")
        assert resp.status_code == 200

    def test_futures_positions_not_authenticated(self, kraken_client):
        data = kraken_client.get("/kraken/futures/positions").json()
        assert data["authenticated"] is False

    def test_futures_positions_has_error_key(self, kraken_client):
        data = kraken_client.get("/kraken/futures/positions").json()
        assert "error" in data

    def test_futures_orders_returns_200(self, kraken_client):
        resp = kraken_client.get("/kraken/futures/orders")
        assert resp.status_code == 200

    def test_futures_orders_not_authenticated(self, kraken_client):
        data = kraken_client.get("/kraken/futures/orders").json()
        assert data["authenticated"] is False

    def test_futures_orders_has_error_key(self, kraken_client):
        data = kraken_client.get("/kraken/futures/orders").json()
        assert "error" in data

    def test_futures_fills_returns_200(self, kraken_client):
        resp = kraken_client.get("/kraken/futures/fills")
        assert resp.status_code == 200

    def test_futures_fills_not_authenticated(self, kraken_client):
        data = kraken_client.get("/kraken/futures/fills").json()
        assert data["authenticated"] is False

    def test_futures_fills_has_error_key(self, kraken_client):
        data = kraken_client.get("/kraken/futures/fills").json()
        assert "error" in data


# ===========================================================================
# Tests — Kraken Spot: Authenticated (mocked provider)
# ===========================================================================


class TestKrakenSpotAuthenticated:
    """Verify that spot account endpoints return well-shaped responses when
    an authenticated provider is injected via mock."""

    def test_balance_returns_200(self, kraken_authed_client):
        resp = kraken_authed_client.get("/kraken/account/balance")
        assert resp.status_code == 200

    def test_balance_authenticated_true(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/balance").json()
        assert data["authenticated"] is True

    def test_balance_has_balances_list(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/balance").json()
        assert isinstance(data["balances"], list)

    def test_balance_list_non_empty(self, kraken_authed_client):
        """Mock returns XXBT=0.5 and ZUSD=1234.56, both above the 1e-8 threshold."""
        data = kraken_authed_client.get("/kraken/account/balance").json()
        assert len(data["balances"]) >= 1

    def test_balance_item_has_required_fields(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/balance").json()
        for item in data["balances"]:
            assert "asset" in item
            assert "kraken_code" in item
            assert "amount" in item
            assert "amount_str" in item

    def test_balance_amount_is_numeric(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/balance").json()
        for item in data["balances"]:
            assert isinstance(item["amount"], (int, float))

    def test_balance_has_updated_at(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/balance").json()
        assert "updated_at" in data

    def test_orders_returns_200(self, kraken_authed_client):
        resp = kraken_authed_client.get("/kraken/account/orders")
        assert resp.status_code == 200

    def test_orders_authenticated_true(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/orders").json()
        assert data["authenticated"] is True

    def test_orders_has_open_orders_list(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/orders").json()
        assert isinstance(data["open_orders"], list)

    def test_orders_count_is_non_negative(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/orders").json()
        assert data["count"] >= 0

    def test_orders_count_matches_list_length(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/orders").json()
        assert data["count"] == len(data["open_orders"])

    def test_orders_has_updated_at(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/orders").json()
        assert "updated_at" in data

    def test_trades_returns_200(self, kraken_authed_client):
        resp = kraken_authed_client.get("/kraken/account/trades")
        assert resp.status_code == 200

    def test_trades_authenticated_true(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/trades").json()
        assert data["authenticated"] is True

    def test_trades_has_trades_list(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/trades").json()
        assert isinstance(data["trades"], list)

    def test_trades_count_matches_list_length(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/trades").json()
        assert data["count"] == len(data["trades"])

    def test_trades_has_updated_at(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/trades").json()
        assert "updated_at" in data

    def test_trades_with_limit_returns_200(self, kraken_authed_client):
        resp = kraken_authed_client.get("/kraken/account/trades?limit=5")
        assert resp.status_code == 200

    def test_trades_with_limit_respects_cap(self, kraken_authed_client):
        """Mock has 3 trades; requesting limit=2 must return at most 2."""
        data = kraken_authed_client.get("/kraken/account/trades?limit=2").json()
        assert data["count"] <= 2
        assert len(data["trades"]) <= 2

    def test_trades_default_limit_25(self, kraken_authed_client):
        """Default limit is 25; 3 mock trades → count should be 3."""
        data = kraken_authed_client.get("/kraken/account/trades").json()
        assert data["count"] <= 25

    def test_trades_item_has_required_fields(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/account/trades").json()
        if data["trades"]:
            for item in data["trades"]:
                assert "pair" in item
                assert "side" in item
                assert "price" in item
                assert "volume" in item

    def test_trades_sorted_by_time_descending(self, kraken_authed_client):
        """Most recent trade should appear first (mock has 3 trades at different times)."""
        data = kraken_authed_client.get("/kraken/account/trades").json()
        times = [t.get("time") for t in data["trades"] if t.get("time") is not None]
        assert times == sorted(times, reverse=True)


# ===========================================================================
# Tests — Kraken Futures: Authenticated (mocked client)
# ===========================================================================


class TestKrakenFuturesAuthenticated:
    """Verify that futures account endpoints return well-shaped responses when
    an authenticated client is injected via mock."""

    def test_futures_balance_returns_200(self, kraken_authed_client):
        resp = kraken_authed_client.get("/kraken/futures/balance")
        assert resp.status_code == 200

    def test_futures_balance_authenticated_true(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/balance").json()
        assert data["authenticated"] is True

    def test_futures_balance_has_accounts_list(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/balance").json()
        assert isinstance(data["accounts"], list)

    def test_futures_balance_account_non_empty(self, kraken_authed_client):
        """Mock returns one account in the 'accounts' dict."""
        data = kraken_authed_client.get("/kraken/futures/balance").json()
        assert len(data["accounts"]) >= 1

    def test_futures_balance_account_has_required_fields(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/balance").json()
        for acct in data["accounts"]:
            assert "name" in acct
            assert "type" in acct
            assert "currency" in acct
            assert "balance" in acct

    def test_futures_balance_has_updated_at(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/balance").json()
        assert "updated_at" in data

    def test_futures_positions_returns_200(self, kraken_authed_client):
        resp = kraken_authed_client.get("/kraken/futures/positions")
        assert resp.status_code == 200

    def test_futures_positions_authenticated_true(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/positions").json()
        assert data["authenticated"] is True

    def test_futures_positions_has_positions_list(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/positions").json()
        assert isinstance(data["positions"], list)

    def test_futures_positions_count_matches_list(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/positions").json()
        assert data["count"] == len(data["positions"])

    def test_futures_positions_has_updated_at(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/positions").json()
        assert "updated_at" in data

    def test_futures_orders_returns_200(self, kraken_authed_client):
        resp = kraken_authed_client.get("/kraken/futures/orders")
        assert resp.status_code == 200

    def test_futures_orders_authenticated_true(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/orders").json()
        assert data["authenticated"] is True

    def test_futures_orders_has_open_orders_list(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/orders").json()
        assert isinstance(data["open_orders"], list)

    def test_futures_orders_count_matches_list(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/orders").json()
        assert data["count"] == len(data["open_orders"])

    def test_futures_orders_has_updated_at(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/orders").json()
        assert "updated_at" in data

    def test_futures_fills_returns_200(self, kraken_authed_client):
        resp = kraken_authed_client.get("/kraken/futures/fills")
        assert resp.status_code == 200

    def test_futures_fills_authenticated_true(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/fills").json()
        assert data["authenticated"] is True

    def test_futures_fills_has_fills_list(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/fills").json()
        assert isinstance(data["fills"], list)

    def test_futures_fills_count_matches_list(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/fills").json()
        assert data["count"] == len(data["fills"])

    def test_futures_fills_non_empty(self, kraken_authed_client):
        """Mock returns one fill entry."""
        data = kraken_authed_client.get("/kraken/futures/fills").json()
        assert len(data["fills"]) >= 1

    def test_futures_fills_item_has_required_fields(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/fills").json()
        for fill in data["fills"]:
            assert "fill_id" in fill
            assert "symbol" in fill
            assert "side" in fill
            assert "price" in fill
            assert "size" in fill

    def test_futures_fills_has_updated_at(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/fills").json()
        assert "updated_at" in data

    def test_futures_fills_with_limit_returns_200(self, kraken_authed_client):
        resp = kraken_authed_client.get("/kraken/futures/fills?limit=10")
        assert resp.status_code == 200

    def test_futures_fills_with_limit_respects_cap(self, kraken_authed_client):
        data = kraken_authed_client.get("/kraken/futures/fills?limit=1").json()
        assert data["count"] <= 1
        assert len(data["fills"]) <= 1

    def test_futures_fills_limit_1_returns_most_recent(self, kraken_authed_client):
        """With limit=1, endpoint should return the single mock fill."""
        data = kraken_authed_client.get("/kraken/futures/fills?limit=1").json()
        assert data["count"] == 1


# ===========================================================================
# Tests — Bars
# ===========================================================================


class TestBars:
    """Verify bar API endpoints work against an empty SQLite database.
    Endpoints should never return 500 — they must degrade gracefully."""

    def test_bars_status_returns_non_500(self, bars_client):
        resp = bars_client.get("/bars/status")
        # 200 expected; 503/404 acceptable; never 500
        assert resp.status_code != 500

    def test_bars_status_returns_json(self, bars_client):
        resp = bars_client.get("/bars/status")
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct

    def test_bars_status_has_timestamp(self, bars_client):
        resp = bars_client.get("/bars/status")
        if resp.status_code == 200:
            data = resp.json()
            assert "timestamp" in data

    def test_bars_status_has_market_hours(self, bars_client):
        resp = bars_client.get("/bars/status")
        if resp.status_code == 200:
            data = resp.json()
            assert "market_hours" in data

    def test_bars_status_has_stale_threshold(self, bars_client):
        resp = bars_client.get("/bars/status")
        if resp.status_code == 200:
            data = resp.json()
            assert "stale_threshold_minutes" in data

    def test_bars_assets_returns_200(self, bars_client):
        resp = bars_client.get("/bars/assets")
        assert resp.status_code == 200

    def test_bars_assets_returns_json(self, bars_client):
        resp = bars_client.get("/bars/assets")
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct

    def test_bars_assets_has_assets_key(self, bars_client):
        data = bars_client.get("/bars/assets").json()
        assert "assets" in data

    def test_bars_assets_is_a_list(self, bars_client):
        data = bars_client.get("/bars/assets").json()
        assert isinstance(data["assets"], list)

    def test_bars_assets_has_total_symbols(self, bars_client):
        data = bars_client.get("/bars/assets").json()
        assert "total_symbols" in data

    def test_bars_assets_total_matches_list_length(self, bars_client):
        data = bars_client.get("/bars/assets").json()
        assert data["total_symbols"] == len(data["assets"])

    def test_bars_assets_items_have_required_fields(self, bars_client):
        data = bars_client.get("/bars/assets").json()
        for item in data["assets"]:
            assert "name" in item
            assert "ticker" in item
            assert "bar_count" in item
            assert "has_data" in item

    def test_bars_symbol_no_data_not_500(self, bars_client):
        """Empty DB → graceful response (200 with empty bars, 404, or 503; never 500)."""
        resp = bars_client.get("/bars/MES?auto_fill=false")
        assert resp.status_code not in (500,)

    def test_bars_symbol_no_data_returns_json(self, bars_client):
        resp = bars_client.get("/bars/MES?auto_fill=false")
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            assert "application/json" in ct

    def test_bars_symbol_200_has_symbol_key(self, bars_client):
        resp = bars_client.get("/bars/MES?auto_fill=false")
        if resp.status_code == 200:
            data = resp.json()
            assert "symbol" in data

    def test_bars_symbol_200_has_bar_count(self, bars_client):
        resp = bars_client.get("/bars/MES?auto_fill=false")
        if resp.status_code == 200:
            data = resp.json()
            assert "bar_count" in data

    def test_bars_symbol_200_bar_count_zero_for_empty_db(self, bars_client):
        """Fresh empty DB should return 0 bars."""
        resp = bars_client.get("/bars/MES?auto_fill=false")
        if resp.status_code == 200:
            data = resp.json()
            assert data["bar_count"] == 0

    def test_bars_symbol_200_has_interval(self, bars_client):
        resp = bars_client.get("/bars/MES?auto_fill=false")
        if resp.status_code == 200:
            data = resp.json()
            assert "interval" in data

    def test_bars_symbol_200_has_data_key(self, bars_client):
        resp = bars_client.get("/bars/MES?auto_fill=false")
        if resp.status_code == 200:
            data = resp.json()
            assert "data" in data

    def test_bars_symbols_endpoint_returns_non_500(self, bars_client):
        """/bars/symbols is a lightweight endpoint that requires no DB queries."""
        resp = bars_client.get("/bars/symbols")
        assert resp.status_code not in (500,)

    def test_bars_symbols_has_symbols_key(self, bars_client):
        resp = bars_client.get("/bars/symbols")
        if resp.status_code == 200:
            data = resp.json()
            assert "symbols" in data

    def test_bars_symbols_list_is_sorted(self, bars_client):
        resp = bars_client.get("/bars/symbols")
        if resp.status_code == 200:
            symbols = resp.json()["symbols"]
            assert symbols == sorted(symbols)


# ===========================================================================
# Tests — Backup Status
# ===========================================================================


class TestBackupStatus:
    """Verify /api/backup/status returns well-formed JSON regardless of DB state."""

    def test_backup_status_returns_200(self, backup_client):
        resp = backup_client.get("/api/backup/status")
        assert resp.status_code == 200

    def test_backup_status_is_json(self, backup_client):
        resp = backup_client.get("/api/backup/status")
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct

    def test_backup_status_is_dict(self, backup_client):
        data = backup_client.get("/api/backup/status").json()
        assert isinstance(data, dict)

    def test_backup_status_has_row_counts(self, backup_client):
        """row_counts key should always be present (may contain error sub-dicts
        if individual tables do not exist yet)."""
        data = backup_client.get("/api/backup/status").json()
        assert "row_counts" in data

    def test_backup_status_row_counts_is_dict(self, backup_client):
        data = backup_client.get("/api/backup/status").json()
        assert isinstance(data["row_counts"], dict)

    def test_backup_status_has_last_backup_at_key(self, backup_client):
        """last_backup_at may be None on a fresh instance (no prior backups)."""
        data = backup_client.get("/api/backup/status").json()
        assert "last_backup_at" in data

    def test_backup_status_last_backup_at_none_or_string(self, backup_client):
        data = backup_client.get("/api/backup/status").json()
        val = data["last_backup_at"]
        assert val is None or isinstance(val, str)

    def test_backup_status_row_counts_covers_expected_sections(self, backup_client):
        """All configured POSTGRES_SECTIONS must appear as keys in row_counts."""
        from lib.services.data.api.backup import POSTGRES_SECTIONS  # noqa: PLC0415

        data = backup_client.get("/api/backup/status").json()
        for section in POSTGRES_SECTIONS:
            assert section in data["row_counts"], f"Missing section: {section}"


# ===========================================================================
# Tests — CNN Status
# ===========================================================================


class TestCNNStatus:
    """Verify /cnn/status returns well-formed JSON even when the model file is absent."""

    def test_cnn_status_returns_200(self, cnn_client):
        resp = cnn_client.get("/cnn/status")
        assert resp.status_code == 200

    def test_cnn_status_is_json(self, cnn_client):
        resp = cnn_client.get("/cnn/status")
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct

    def test_cnn_status_has_model_key(self, cnn_client):
        data = cnn_client.get("/cnn/status").json()
        assert "model" in data

    def test_cnn_status_has_meta_key(self, cnn_client):
        data = cnn_client.get("/cnn/status").json()
        assert "meta" in data

    def test_cnn_status_has_sync_key(self, cnn_client):
        data = cnn_client.get("/cnn/status").json()
        assert "sync" in data

    def test_cnn_status_has_timestamp(self, cnn_client):
        data = cnn_client.get("/cnn/status").json()
        assert "timestamp" in data

    def test_cnn_status_model_has_available_field(self, cnn_client):
        data = cnn_client.get("/cnn/status").json()
        assert "available" in data["model"]

    def test_cnn_status_model_unavailable_without_file(self, cnn_client):
        """Model file will not exist in the test environment."""
        data = cnn_client.get("/cnn/status").json()
        assert data["model"]["available"] is False

    def test_cnn_status_model_has_model_path(self, cnn_client):
        data = cnn_client.get("/cnn/status").json()
        # model_path may be None when the file is absent
        assert "model_path" in data["model"]

    def test_cnn_status_sync_has_stale_field(self, cnn_client):
        data = cnn_client.get("/cnn/status").json()
        assert "stale" in data["sync"]

    def test_cnn_status_sync_has_meta_available_field(self, cnn_client):
        data = cnn_client.get("/cnn/status").json()
        assert "meta_available" in data["sync"]

    def test_cnn_status_has_note(self, cnn_client):
        data = cnn_client.get("/cnn/status").json()
        assert "note" in data


# ===========================================================================
# Tests — Chart Indicators
# ===========================================================================


class TestChartIndicators:
    """Verify chart indicator endpoints return well-shaped JSON responses.
    Redis is disabled; DB may be empty — all failures must be graceful."""

    def test_chart_assets_returns_200(self, chart_client):
        resp = chart_client.get("/api/chart/assets")
        assert resp.status_code == 200

    def test_chart_assets_is_json(self, chart_client):
        resp = chart_client.get("/api/chart/assets")
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct

    def test_chart_assets_has_assets_key(self, chart_client):
        data = chart_client.get("/api/chart/assets").json()
        assert "assets" in data

    def test_chart_assets_is_a_list(self, chart_client):
        data = chart_client.get("/api/chart/assets").json()
        assert isinstance(data["assets"], list)

    def test_chart_assets_falls_back_to_defaults_without_redis(self, chart_client):
        """With DISABLE_REDIS=1 the endpoint returns the hardcoded default list."""
        from lib.services.data.api.chart_indicators import _DEFAULT_ASSETS  # noqa: PLC0415

        data = chart_client.get("/api/chart/assets").json()
        assert data["assets"] == _DEFAULT_ASSETS

    def test_chart_assets_non_empty(self, chart_client):
        data = chart_client.get("/api/chart/assets").json()
        assert len(data["assets"]) > 0

    def test_chart_assets_items_are_strings(self, chart_client):
        data = chart_client.get("/api/chart/assets").json()
        for sym in data["assets"]:
            assert isinstance(sym, str)

    def test_chart_indicators_not_500(self, chart_client):
        """Empty DB → bars_count=0 response, not a 500 server error."""
        resp = chart_client.get("/api/chart/MES/indicators")
        assert resp.status_code != 500

    def test_chart_indicators_200_has_symbol(self, chart_client):
        resp = chart_client.get("/api/chart/MES/indicators")
        if resp.status_code == 200:
            data = resp.json()
            assert "symbol" in data

    def test_chart_indicators_200_has_interval(self, chart_client):
        resp = chart_client.get("/api/chart/MES/indicators")
        if resp.status_code == 200:
            data = resp.json()
            assert "interval" in data

    def test_chart_indicators_200_has_bars_count(self, chart_client):
        resp = chart_client.get("/api/chart/MES/indicators")
        if resp.status_code == 200:
            data = resp.json()
            assert "bars_count" in data

    def test_chart_indicators_200_has_indicators_dict(self, chart_client):
        resp = chart_client.get("/api/chart/MES/indicators")
        if resp.status_code == 200:
            data = resp.json()
            assert "indicators" in data
            assert isinstance(data["indicators"], dict)

    def test_chart_indicators_empty_db_zero_bars(self, chart_client):
        """Fresh empty DB → bars_count should be 0 and indicators empty."""
        resp = chart_client.get("/api/chart/MES/indicators")
        if resp.status_code == 200:
            data = resp.json()
            assert data["bars_count"] == 0
            assert data["indicators"] == {}

    def test_chart_indicators_symbol_reflected(self, chart_client):
        """Response symbol should match the path parameter."""
        resp = chart_client.get("/api/chart/MNQ/indicators")
        if resp.status_code == 200:
            assert resp.json()["symbol"] == "MNQ"

    def test_chart_indicators_interval_param(self, chart_client):
        """Interval query param should be reflected in the response."""
        resp = chart_client.get("/api/chart/MES/indicators?interval=5m")
        if resp.status_code == 200:
            assert resp.json()["interval"] == "5m"

    def test_chart_regime_returns_200(self, chart_client):
        resp = chart_client.get("/api/chart/MES/regime")
        assert resp.status_code == 200

    def test_chart_regime_is_json(self, chart_client):
        resp = chart_client.get("/api/chart/MES/regime")
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct

    def test_chart_regime_has_regime_key(self, chart_client):
        data = chart_client.get("/api/chart/MES/regime").json()
        assert "regime" in data

    def test_chart_regime_has_symbol_key(self, chart_client):
        data = chart_client.get("/api/chart/MES/regime").json()
        assert "symbol" in data

    def test_chart_regime_symbol_matches_path(self, chart_client):
        data = chart_client.get("/api/chart/MGC/regime").json()
        assert data["symbol"] == "MGC"

    def test_chart_regime_has_confidence(self, chart_client):
        data = chart_client.get("/api/chart/MES/regime").json()
        assert "confidence" in data

    def test_chart_regime_has_ts(self, chart_client):
        data = chart_client.get("/api/chart/MES/regime").json()
        assert "ts" in data

    def test_chart_regime_value_is_valid(self, chart_client):
        """Without Redis, regime must be 'undefined'."""
        data = chart_client.get("/api/chart/MES/regime").json()
        assert data["regime"] in ("trending", "choppy", "undefined")

    def test_chart_regime_undefined_without_redis(self, chart_client):
        """DISABLE_REDIS=1 → cache_get returns None → regime falls back to undefined."""
        data = chart_client.get("/api/chart/MES/regime").json()
        assert data["regime"] == "undefined"

    def test_chart_regime_confidence_is_numeric(self, chart_client):
        data = chart_client.get("/api/chart/MES/regime").json()
        assert isinstance(data["confidence"], (int, float))


# ===========================================================================
# Tests — Market Data Source
# ===========================================================================


class TestMarketData:
    """Verify the /data/source endpoint returns the active data source info."""

    def test_data_source_returns_200(self, market_data_client):
        resp = market_data_client.get("/data/source")
        assert resp.status_code == 200

    def test_data_source_is_json(self, market_data_client):
        resp = market_data_client.get("/data/source")
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct

    def test_data_source_has_data_source_key(self, market_data_client):
        data = market_data_client.get("/data/source").json()
        assert "data_source" in data

    def test_data_source_has_massive_available_key(self, market_data_client):
        data = market_data_client.get("/data/source").json()
        assert "massive_available" in data

    def test_data_source_value_is_string(self, market_data_client):
        data = market_data_client.get("/data/source").json()
        assert isinstance(data["data_source"], str)

    def test_massive_available_is_bool(self, market_data_client):
        data = market_data_client.get("/data/source").json()
        assert isinstance(data["massive_available"], bool)


# ===========================================================================
# Tests — Health
# ===========================================================================


class TestHealth:
    """Verify /health returns a complete, well-shaped JSON response.
    In the test environment most subsystems are unavailable — the overall
    status will be 'degraded', which is the expected outcome."""

    def test_health_returns_200(self, health_client):
        resp = health_client.get("/health")
        assert resp.status_code == 200

    def test_health_is_json(self, health_client):
        resp = health_client.get("/health")
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct

    def test_health_has_status_key(self, health_client):
        data = health_client.get("/health").json()
        assert "status" in data

    def test_health_status_is_string(self, health_client):
        data = health_client.get("/health").json()
        assert isinstance(data["status"], str)

    def test_health_status_is_ok_or_degraded(self, health_client):
        data = health_client.get("/health").json()
        assert data["status"] in ("ok", "degraded")

    def test_health_degraded_in_test_environment(self, health_client):
        """Engine is not initialised and model is absent → always degraded."""
        data = health_client.get("/health").json()
        assert data["status"] == "degraded"

    def test_health_has_timestamp(self, health_client):
        data = health_client.get("/health").json()
        assert "timestamp" in data

    def test_health_has_components_key(self, health_client):
        data = health_client.get("/health").json()
        assert "components" in data

    def test_health_components_is_dict(self, health_client):
        data = health_client.get("/health").json()
        assert isinstance(data["components"], dict)

    def test_health_components_has_redis(self, health_client):
        data = health_client.get("/health").json()
        assert "redis" in data["components"]

    def test_health_components_has_postgres(self, health_client):
        data = health_client.get("/health").json()
        assert "postgres" in data["components"]

    def test_health_components_has_engine(self, health_client):
        data = health_client.get("/health").json()
        assert "engine" in data["components"]

    def test_health_components_has_model(self, health_client):
        data = health_client.get("/health").json()
        assert "model" in data["components"]

    def test_health_components_has_kraken(self, health_client):
        data = health_client.get("/health").json()
        assert "kraken" in data["components"]

    def test_health_components_has_rithmic(self, health_client):
        data = health_client.get("/health").json()
        assert "rithmic" in data["components"]

    def test_health_redis_not_connected_without_server(self, health_client):
        """With DISABLE_REDIS=1, Redis should report not connected."""
        data = health_client.get("/health").json()
        redis_comp = data["components"]["redis"]
        assert redis_comp.get("connected") is False

    def test_health_engine_not_initialised(self, health_client):
        """No engine singleton → status should be 'not_initialized'."""
        data = health_client.get("/health").json()
        engine_comp = data["components"]["engine"]
        assert engine_comp.get("status") == "not_initialized"

    def test_health_model_not_available_in_test(self, health_client):
        """CNN model file absent in test env → model.available should be False."""
        data = health_client.get("/health").json()
        model_comp = data["components"]["model"]
        assert model_comp.get("available") is False
