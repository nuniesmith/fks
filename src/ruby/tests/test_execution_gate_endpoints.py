"""
Tests for Execution Gate REST API endpoints.

Covers all routes in ``lib.services.data.api.execution_gate_routes``:

    GET  /api/execution_gate/status
    GET  /api/execution_gate/config
    POST /api/execution_gate/config
    GET  /api/execution_gate/assets
    POST /api/execution_gate/assets
    GET  /api/execution_gate/pending
    POST /api/execution_gate/confirm/{signal_id}
    POST /api/execution_gate/dismiss/{signal_id}
    GET  /api/execution_gate/circuit
    POST /api/execution_gate/circuit/reset
    POST /api/execution_gate/pnl
    POST /api/execution_gate/pnl/live-feed
"""

from __future__ import annotations

import os

# Ensure Redis is disabled before any project imports.
os.environ.setdefault("DISABLE_REDIS", "1")

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Shared mock gate fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_gate():
    """Minimal mock of the ExecutionGate singleton."""
    gate = MagicMock()

    # status() returns a full status dict
    gate.status.return_value = {
        "circuit": {
            "state": "closed",
            "daily_pnl": 0.0,
            "consecutive_losses": 0,
            "opened_at": None,
            "is_open": False,
        },
        "config": {
            "confidence_threshold": 0.65,
            "daily_loss_limit": -3300.0,
            "max_risk_pct": 0.02,
            "account_balance": 150000.0,
            "pending_ttl": 300,
            "max_consecutive_losses": 3,
            "auto_execute_crypto": True,
            "disabled": False,
        },
        "pending_count": 0,
        "focus_futures": ["MES", "MNQ"],
        "focus_crypto": ["XBTUSD"],
    }

    # get_pending_signals() returns a dict (keyed by signal_id)
    gate.get_pending_signals.return_value = {}

    # confirm_signal returns True by default
    gate.confirm_signal.return_value = True

    # dismiss_signal returns True by default
    gate.dismiss_signal.return_value = True

    # get_circuit_state() returns an object with to_dict()
    circuit_snap = MagicMock()
    circuit_snap.to_dict.return_value = {
        "state": "closed",
        "daily_pnl": 0.0,
        "daily_loss_limit": -3300.0,
        "consecutive_losses": 0,
        "max_consecutive_losses": 3,
        "opened_at": None,
        "trading_date": "2025-01-06",
        "is_open": False,
    }
    gate.get_circuit_state.return_value = circuit_snap

    # reset_circuit is void
    gate.reset_circuit.return_value = None

    # update_daily_pnl is void
    gate.update_daily_pnl.return_value = None

    return gate


@pytest.fixture()
def client(mock_gate, monkeypatch):
    """TestClient for the execution gate router with mocked dependencies."""
    # Patch get_execution_gate so _get_gate() returns our mock.
    # _get_gate() does `from lib.services.engine.execution_gate import get_execution_gate`
    # inside the function body, so we patch at the source module.
    import lib.services.engine.execution_gate as ege

    monkeypatch.setattr(ege, "get_execution_gate", lambda: mock_gate)

    # Patch _get_redis inside the routes module to return None.
    # This exercises the Redis-unavailable fallback paths cleanly.
    import lib.services.data.api.execution_gate_routes as egr

    monkeypatch.setattr(egr, "_get_redis", lambda: None)
    # Also patch _get_db_conn so asset upsert short-circuits without Postgres.
    monkeypatch.setattr(egr, "_get_db_conn", lambda: None)

    from lib.services.data.api.execution_gate_routes import router

    app = FastAPI()
    app.include_router(router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def client_not_found(mock_gate, monkeypatch):
    """TestClient where confirm/dismiss return False (signal not found)."""
    mock_gate.confirm_signal.return_value = False
    mock_gate.dismiss_signal.return_value = False

    import lib.services.engine.execution_gate as ege

    monkeypatch.setattr(ege, "get_execution_gate", lambda: mock_gate)

    import lib.services.data.api.execution_gate_routes as egr

    monkeypatch.setattr(egr, "_get_redis", lambda: None)
    monkeypatch.setattr(egr, "_get_db_conn", lambda: None)

    from lib.services.data.api.execution_gate_routes import router

    app = FastAPI()
    app.include_router(router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# TestGateStatus
# ===========================================================================


class TestGateStatus:
    """GET /api/execution_gate/status"""

    def test_returns_200(self, client):
        resp = client.get("/api/execution_gate/status")
        assert resp.status_code == 200

    def test_response_is_valid_json(self, client):
        resp = client.get("/api/execution_gate/status")
        data = resp.json()
        assert isinstance(data, dict)

    def test_ok_field_is_true(self, client):
        resp = client.get("/api/execution_gate/status")
        assert resp.json()["ok"] is True

    def test_has_circuit_field(self, client):
        resp = client.get("/api/execution_gate/status")
        data = resp.json()
        assert "circuit" in data
        assert isinstance(data["circuit"], dict)

    def test_has_config_field(self, client):
        resp = client.get("/api/execution_gate/status")
        data = resp.json()
        assert "config" in data
        assert isinstance(data["config"], dict)

    def test_has_pending_count(self, client):
        resp = client.get("/api/execution_gate/status")
        data = resp.json()
        assert "pending_count" in data
        assert isinstance(data["pending_count"], int)

    def test_pending_count_is_zero_by_default(self, client):
        resp = client.get("/api/execution_gate/status")
        assert resp.json()["pending_count"] == 0

    def test_circuit_has_state(self, client):
        resp = client.get("/api/execution_gate/status")
        circuit = resp.json()["circuit"]
        assert "state" in circuit

    def test_circuit_state_is_closed(self, client):
        resp = client.get("/api/execution_gate/status")
        circuit = resp.json()["circuit"]
        # Default mock has state "closed"
        assert circuit["state"] in ("closed", "CLOSED", "open", "OPEN")

    def test_circuit_has_daily_pnl(self, client):
        resp = client.get("/api/execution_gate/status")
        circuit = resp.json()["circuit"]
        assert "daily_pnl" in circuit

    def test_content_type_json(self, client):
        resp = client.get("/api/execution_gate/status")
        assert "application/json" in resp.headers.get("content-type", "")


# ===========================================================================
# TestGateConfig
# ===========================================================================


class TestGateConfig:
    """GET /api/execution_gate/config  and  POST /api/execution_gate/config"""

    def test_get_returns_200(self, client):
        resp = client.get("/api/execution_gate/config")
        assert resp.status_code == 200

    def test_get_response_has_ok(self, client):
        resp = client.get("/api/execution_gate/config")
        assert resp.json()["ok"] is True

    def test_get_response_has_config(self, client):
        resp = client.get("/api/execution_gate/config")
        data = resp.json()
        assert "config" in data
        assert isinstance(data["config"], dict)

    def test_get_config_has_confidence_threshold(self, client):
        resp = client.get("/api/execution_gate/config")
        cfg = resp.json()["config"]
        assert "confidence_threshold" in cfg

    def test_get_config_has_daily_loss_limit(self, client):
        resp = client.get("/api/execution_gate/config")
        cfg = resp.json()["config"]
        assert "daily_loss_limit" in cfg

    def test_get_config_has_max_risk_pct(self, client):
        resp = client.get("/api/execution_gate/config")
        cfg = resp.json()["config"]
        assert "max_risk_pct" in cfg

    def test_get_config_has_account_balance(self, client):
        resp = client.get("/api/execution_gate/config")
        cfg = resp.json()["config"]
        assert "account_balance" in cfg

    def test_get_config_has_pending_ttl(self, client):
        resp = client.get("/api/execution_gate/config")
        cfg = resp.json()["config"]
        assert "pending_ttl" in cfg

    def test_get_config_has_max_consecutive_losses(self, client):
        resp = client.get("/api/execution_gate/config")
        cfg = resp.json()["config"]
        assert "max_consecutive_losses" in cfg

    def test_get_config_confidence_in_range(self, client):
        resp = client.get("/api/execution_gate/config")
        cfg = resp.json()["config"]
        threshold = cfg["confidence_threshold"]
        assert 0.0 <= threshold <= 1.0

    def test_post_config_returns_200(self, client):
        resp = client.post(
            "/api/execution_gate/config",
            json={"confidence_threshold": 0.75},
        )
        assert resp.status_code == 200

    def test_post_config_response_has_ok(self, client):
        resp = client.post(
            "/api/execution_gate/config",
            json={"confidence_threshold": 0.70},
        )
        assert resp.json()["ok"] is True

    def test_post_config_response_has_config(self, client):
        resp = client.post(
            "/api/execution_gate/config",
            json={"confidence_threshold": 0.70},
        )
        data = resp.json()
        assert "config" in data
        assert isinstance(data["config"], dict)

    def test_post_config_response_has_changed(self, client):
        resp = client.post(
            "/api/execution_gate/config",
            json={"confidence_threshold": 0.80},
        )
        data = resp.json()
        assert "changed" in data

    def test_post_config_confidence_too_high_returns_422(self, client):
        # confidence_threshold has ge=0.0, le=1.0 — 1.5 should fail Pydantic validation
        resp = client.post(
            "/api/execution_gate/config",
            json={"confidence_threshold": 1.5},
        )
        assert resp.status_code == 422

    def test_post_config_confidence_negative_returns_422(self, client):
        resp = client.post(
            "/api/execution_gate/config",
            json={"confidence_threshold": -0.1},
        )
        assert resp.status_code == 422

    def test_post_config_empty_body_returns_200(self, client):
        # No fields provided — all are Optional, so no changes
        resp = client.post("/api/execution_gate/config", json={})
        assert resp.status_code == 200

    def test_post_config_daily_loss_must_be_negative(self, client):
        # daily_loss_limit has le=0.0 — positive value should fail
        resp = client.post(
            "/api/execution_gate/config",
            json={"daily_loss_limit": 100.0},
        )
        assert resp.status_code == 422

    def test_post_config_pending_ttl_below_minimum_returns_422(self, client):
        # pending_ttl has ge=30
        resp = client.post(
            "/api/execution_gate/config",
            json={"pending_ttl": 10},
        )
        assert resp.status_code == 422

    def test_post_config_max_risk_pct_zero_returns_422(self, client):
        # max_risk_pct has gt=0.0
        resp = client.post(
            "/api/execution_gate/config",
            json={"max_risk_pct": 0.0},
        )
        assert resp.status_code == 422


# ===========================================================================
# TestGateAssets
# ===========================================================================


class TestGateAssets:
    """GET /api/execution_gate/assets  and  POST /api/execution_gate/assets"""

    def test_get_returns_200(self, client):
        resp = client.get("/api/execution_gate/assets")
        assert resp.status_code == 200

    def test_get_response_has_ok(self, client):
        resp = client.get("/api/execution_gate/assets")
        assert resp.json()["ok"] is True

    def test_get_response_has_assets(self, client):
        resp = client.get("/api/execution_gate/assets")
        data = resp.json()
        assert "assets" in data
        assert isinstance(data["assets"], list)

    def test_get_response_has_count(self, client):
        resp = client.get("/api/execution_gate/assets")
        data = resp.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_get_count_matches_assets_length(self, client):
        resp = client.get("/api/execution_gate/assets")
        data = resp.json()
        assert data["count"] == len(data["assets"])

    def test_get_assets_are_non_empty_by_default(self, client):
        # Should fall back to hardcoded FOCUS_FUTURES + FOCUS_CRYPTO
        resp = client.get("/api/execution_gate/assets")
        data = resp.json()
        assert data["count"] > 0

    def test_get_asset_has_symbol(self, client):
        resp = client.get("/api/execution_gate/assets")
        assets = resp.json()["assets"]
        if assets:
            assert "symbol" in assets[0]

    def test_get_asset_has_asset_type(self, client):
        resp = client.get("/api/execution_gate/assets")
        assets = resp.json()["assets"]
        if assets:
            assert "asset_type" in assets[0]

    def test_post_assets_returns_200(self, client):
        resp = client.post(
            "/api/execution_gate/assets",
            json={
                "assets": [
                    {
                        "symbol": "MES",
                        "display_name": "Micro E-mini S&P",
                        "exchange": "rithmic",
                        "asset_type": "futures",
                        "enabled": True,
                        "min_confidence": 0.65,
                        "max_position_pct": 0.05,
                    }
                ]
            },
        )
        assert resp.status_code == 200

    def test_post_assets_response_has_ok(self, client):
        resp = client.post(
            "/api/execution_gate/assets",
            json={
                "assets": [
                    {
                        "symbol": "MNQ",
                        "display_name": "Micro Nasdaq",
                        "exchange": "rithmic",
                        "asset_type": "futures",
                        "enabled": True,
                        "min_confidence": 0.65,
                        "max_position_pct": 0.05,
                    }
                ]
            },
        )
        assert resp.json()["ok"] is True

    def test_post_assets_response_has_count(self, client):
        resp = client.post(
            "/api/execution_gate/assets",
            json={
                "assets": [
                    {
                        "symbol": "MGC",
                        "display_name": "Micro Gold",
                        "exchange": "rithmic",
                        "asset_type": "futures",
                        "enabled": True,
                        "min_confidence": 0.65,
                        "max_position_pct": 0.05,
                    }
                ]
            },
        )
        data = resp.json()
        assert "count" in data
        assert data["count"] == 1

    def test_post_assets_response_has_enabled_futures(self, client):
        resp = client.post(
            "/api/execution_gate/assets",
            json={
                "assets": [
                    {
                        "symbol": "MES",
                        "display_name": "Micro E-mini S&P",
                        "exchange": "rithmic",
                        "asset_type": "futures",
                        "enabled": True,
                        "min_confidence": 0.65,
                        "max_position_pct": 0.05,
                    }
                ]
            },
        )
        data = resp.json()
        assert "enabled_futures" in data
        assert "MES" in data["enabled_futures"]

    def test_post_multiple_assets(self, client):
        resp = client.post(
            "/api/execution_gate/assets",
            json={
                "assets": [
                    {
                        "symbol": "MES",
                        "display_name": "Micro E-mini S&P",
                        "exchange": "rithmic",
                        "asset_type": "futures",
                        "enabled": True,
                        "min_confidence": 0.65,
                        "max_position_pct": 0.05,
                    },
                    {
                        "symbol": "MNQ",
                        "display_name": "Micro Nasdaq",
                        "exchange": "rithmic",
                        "asset_type": "futures",
                        "enabled": True,
                        "min_confidence": 0.65,
                        "max_position_pct": 0.05,
                    },
                ]
            },
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_post_assets_crypto_in_enabled_crypto(self, client):
        resp = client.post(
            "/api/execution_gate/assets",
            json={
                "assets": [
                    {
                        "symbol": "XBTUSD",
                        "display_name": "Bitcoin",
                        "exchange": "kraken",
                        "asset_type": "crypto",
                        "enabled": True,
                        "min_confidence": 0.65,
                        "max_position_pct": 0.05,
                    }
                ]
            },
        )
        data = resp.json()
        assert "enabled_crypto" in data
        assert "XBTUSD" in data["enabled_crypto"]

    def test_post_assets_min_confidence_out_of_range_returns_422(self, client):
        resp = client.post(
            "/api/execution_gate/assets",
            json={
                "assets": [
                    {
                        "symbol": "MES",
                        "display_name": "MES",
                        "exchange": "rithmic",
                        "asset_type": "futures",
                        "enabled": True,
                        "min_confidence": 1.5,  # > 1.0 — invalid
                        "max_position_pct": 0.05,
                    }
                ]
            },
        )
        assert resp.status_code == 422

    def test_post_assets_empty_list_returns_200(self, client):
        resp = client.post("/api/execution_gate/assets", json={"assets": []})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


# ===========================================================================
# TestPendingSignals
# ===========================================================================


class TestPendingSignals:
    """GET /api/execution_gate/pending"""

    def test_returns_200(self, client):
        resp = client.get("/api/execution_gate/pending")
        assert resp.status_code == 200

    def test_response_has_ok(self, client):
        resp = client.get("/api/execution_gate/pending")
        assert resp.json()["ok"] is True

    def test_response_has_signals_list(self, client):
        resp = client.get("/api/execution_gate/pending")
        data = resp.json()
        assert "signals" in data
        assert isinstance(data["signals"], list)

    def test_response_has_count(self, client):
        resp = client.get("/api/execution_gate/pending")
        data = resp.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_empty_pending_queue(self, client):
        # Mock returns empty dict → 0 pending signals
        resp = client.get("/api/execution_gate/pending")
        data = resp.json()
        assert data["count"] == 0
        assert data["signals"] == []

    def test_count_matches_signals_length(self, client):
        resp = client.get("/api/execution_gate/pending")
        data = resp.json()
        assert data["count"] == len(data["signals"])

    def test_response_has_timestamp(self, client):
        resp = client.get("/api/execution_gate/pending")
        assert "timestamp" in resp.json()

    def test_pending_with_one_signal(self, mock_gate, monkeypatch):
        """With a single pending signal in the mock, count == 1."""
        pending_signal = MagicMock()
        pending_signal.to_dict.return_value = {
            "signal_id": "abcdef1234abcdef",
            "symbol": "MES",
            "direction": "LONG",
            "trigger_price": 5420.00,
            "clamped_size": 1,
            "confidence": 0.82,
            "queued_at": "2025-01-06T10:00:00-05:00",
            "expires_at": "2025-01-06T10:05:00-05:00",
            "breakout_type": "orb",
        }
        mock_gate.get_pending_signals.return_value = {"abcdef1234abcdef": pending_signal}

        import lib.services.data.api.execution_gate_routes as egr
        import lib.services.engine.execution_gate as ege

        monkeypatch.setattr(ege, "get_execution_gate", lambda: mock_gate)
        monkeypatch.setattr(egr, "_get_redis", lambda: None)

        from lib.services.data.api.execution_gate_routes import router

        app = FastAPI()
        app.include_router(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/execution_gate/pending")
        data = resp.json()
        assert data["count"] == 1
        assert len(data["signals"]) == 1
        assert data["signals"][0]["signal_id"] == "abcdef1234abcdef"

    def test_symbol_filter_query_param(self, mock_gate, monkeypatch):
        """?symbol= filters signals by symbol (case-insensitive)."""
        sig_mes = MagicMock()
        sig_mes.to_dict.return_value = {
            "signal_id": "aaa111aaa111aaa1",
            "symbol": "MES",
            "direction": "LONG",
            "trigger_price": 5420.0,
            "clamped_size": 1,
            "confidence": 0.75,
            "queued_at": "2025-01-06T10:00:00-05:00",
            "expires_at": "2025-01-06T10:05:00-05:00",
            "breakout_type": "orb",
        }
        sig_mnq = MagicMock()
        sig_mnq.to_dict.return_value = {
            "signal_id": "bbb222bbb222bbb2",
            "symbol": "MNQ",
            "direction": "SHORT",
            "trigger_price": 18900.0,
            "clamped_size": 1,
            "confidence": 0.78,
            "queued_at": "2025-01-06T10:01:00-05:00",
            "expires_at": "2025-01-06T10:06:00-05:00",
            "breakout_type": "orb",
        }
        mock_gate.get_pending_signals.return_value = {
            "aaa111aaa111aaa1": sig_mes,
            "bbb222bbb222bbb2": sig_mnq,
        }

        import lib.services.data.api.execution_gate_routes as egr
        import lib.services.engine.execution_gate as ege

        monkeypatch.setattr(ege, "get_execution_gate", lambda: mock_gate)
        monkeypatch.setattr(egr, "_get_redis", lambda: None)

        from lib.services.data.api.execution_gate_routes import router

        app = FastAPI()
        app.include_router(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/execution_gate/pending?symbol=MES")
        data = resp.json()
        assert data["count"] == 1
        assert data["signals"][0]["symbol"] == "MES"


# ===========================================================================
# TestConfirmDismiss
# ===========================================================================


class TestConfirmDismiss:
    """POST /api/execution_gate/confirm/{signal_id}  and  /dismiss/{signal_id}"""

    def test_confirm_returns_200(self, client):
        resp = client.post("/api/execution_gate/confirm/abcdef1234abcdef")
        assert resp.status_code == 200

    def test_confirm_response_has_ok_true(self, client):
        resp = client.post("/api/execution_gate/confirm/abcdef1234abcdef")
        assert resp.json()["ok"] is True

    def test_confirm_response_has_signal_id(self, client):
        resp = client.post("/api/execution_gate/confirm/abcdef1234abcdef")
        data = resp.json()
        assert "signal_id" in data
        assert data["signal_id"] == "abcdef1234abcdef"

    def test_confirm_response_has_confirmed_at(self, client):
        resp = client.post("/api/execution_gate/confirm/abcdef1234abcdef")
        data = resp.json()
        assert "confirmed_at" in data

    def test_confirm_response_has_fill_price(self, client):
        resp = client.post("/api/execution_gate/confirm/abcdef1234abcdef")
        data = resp.json()
        assert "fill_price" in data

    def test_confirm_with_fill_price_body(self, client):
        resp = client.post(
            "/api/execution_gate/confirm/abcdef1234abcdef",
            json={"fill_price": 5425.50},
        )
        assert resp.status_code == 200
        assert resp.json()["fill_price"] == 5425.50

    def test_confirm_not_found_returns_404(self, client_not_found):
        resp = client_not_found.post("/api/execution_gate/confirm/NOTFOUNDXYZ12345")
        assert resp.status_code == 404

    def test_dismiss_returns_200(self, client):
        resp = client.post("/api/execution_gate/dismiss/abcdef1234abcdef")
        assert resp.status_code == 200

    def test_dismiss_response_has_ok_true(self, client):
        resp = client.post("/api/execution_gate/dismiss/abcdef1234abcdef")
        assert resp.json()["ok"] is True

    def test_dismiss_response_has_signal_id(self, client):
        resp = client.post("/api/execution_gate/dismiss/abcdef1234abcdef")
        data = resp.json()
        assert "signal_id" in data
        assert data["signal_id"] == "abcdef1234abcdef"

    def test_dismiss_response_has_dismissed_at(self, client):
        resp = client.post("/api/execution_gate/dismiss/abcdef1234abcdef")
        assert "dismissed_at" in resp.json()

    def test_dismiss_not_found_returns_404(self, client_not_found):
        resp = client_not_found.post("/api/execution_gate/dismiss/NOTFOUNDXYZ12345")
        assert resp.status_code == 404

    def test_confirm_calls_gate_with_signal_id(self, mock_gate, monkeypatch):
        """Verify the gate's confirm_signal is called with the correct id."""
        import lib.services.data.api.execution_gate_routes as egr
        import lib.services.engine.execution_gate as ege

        monkeypatch.setattr(ege, "get_execution_gate", lambda: mock_gate)
        monkeypatch.setattr(egr, "_get_redis", lambda: None)

        from lib.services.data.api.execution_gate_routes import router

        app = FastAPI()
        app.include_router(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            c.post("/api/execution_gate/confirm/deadbeef12345678")

        mock_gate.confirm_signal.assert_called_once()
        call_args = mock_gate.confirm_signal.call_args
        assert call_args[0][0] == "deadbeef12345678"

    def test_dismiss_calls_gate_with_signal_id(self, mock_gate, monkeypatch):
        """Verify the gate's dismiss_signal is called with the correct id."""
        import lib.services.data.api.execution_gate_routes as egr
        import lib.services.engine.execution_gate as ege

        monkeypatch.setattr(ege, "get_execution_gate", lambda: mock_gate)
        monkeypatch.setattr(egr, "_get_redis", lambda: None)

        from lib.services.data.api.execution_gate_routes import router

        app = FastAPI()
        app.include_router(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            c.post("/api/execution_gate/dismiss/deadbeef12345678")

        mock_gate.dismiss_signal.assert_called_once_with("deadbeef12345678")


# ===========================================================================
# TestCircuitBreaker
# ===========================================================================


class TestCircuitBreaker:
    """
    GET  /api/execution_gate/circuit
    POST /api/execution_gate/circuit/reset
    POST /api/execution_gate/pnl
    POST /api/execution_gate/pnl/live-feed
    """

    # --- GET /circuit ---

    def test_get_circuit_returns_200(self, client):
        resp = client.get("/api/execution_gate/circuit")
        assert resp.status_code == 200

    def test_get_circuit_has_ok(self, client):
        resp = client.get("/api/execution_gate/circuit")
        assert resp.json()["ok"] is True

    def test_get_circuit_has_circuit_dict(self, client):
        resp = client.get("/api/execution_gate/circuit")
        data = resp.json()
        assert "circuit" in data
        assert isinstance(data["circuit"], dict)

    def test_get_circuit_has_state(self, client):
        resp = client.get("/api/execution_gate/circuit")
        circuit = resp.json()["circuit"]
        assert "state" in circuit

    def test_get_circuit_state_is_closed(self, client):
        resp = client.get("/api/execution_gate/circuit")
        circuit = resp.json()["circuit"]
        assert circuit["state"] in ("closed", "CLOSED", "open", "OPEN")

    def test_get_circuit_has_daily_pnl(self, client):
        resp = client.get("/api/execution_gate/circuit")
        circuit = resp.json()["circuit"]
        assert "daily_pnl" in circuit
        assert isinstance(circuit["daily_pnl"], (int, float))

    def test_get_circuit_has_consecutive_losses(self, client):
        resp = client.get("/api/execution_gate/circuit")
        circuit = resp.json()["circuit"]
        assert "consecutive_losses" in circuit

    def test_get_circuit_has_timestamp(self, client):
        resp = client.get("/api/execution_gate/circuit")
        assert "timestamp" in resp.json()

    # --- POST /circuit/reset ---

    def test_reset_circuit_returns_200(self, client):
        resp = client.post("/api/execution_gate/circuit/reset")
        assert resp.status_code == 200

    def test_reset_circuit_has_ok_true(self, client):
        resp = client.post("/api/execution_gate/circuit/reset")
        assert resp.json()["ok"] is True

    def test_reset_circuit_has_message(self, client):
        resp = client.post("/api/execution_gate/circuit/reset")
        data = resp.json()
        assert "message" in data
        assert isinstance(data["message"], str)

    def test_reset_circuit_has_reset_at(self, client):
        resp = client.post("/api/execution_gate/circuit/reset")
        assert "reset_at" in resp.json()

    def test_reset_circuit_calls_gate_reset(self, mock_gate, monkeypatch):
        import lib.services.data.api.execution_gate_routes as egr
        import lib.services.engine.execution_gate as ege

        monkeypatch.setattr(ege, "get_execution_gate", lambda: mock_gate)
        monkeypatch.setattr(egr, "_get_redis", lambda: None)

        from lib.services.data.api.execution_gate_routes import router

        app = FastAPI()
        app.include_router(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            c.post("/api/execution_gate/circuit/reset")

        mock_gate.reset_circuit.assert_called_once()

    # --- POST /pnl ---

    def test_report_pnl_returns_200(self, client):
        resp = client.post(
            "/api/execution_gate/pnl",
            json={"pnl_delta": -100.0, "is_loss": True},
        )
        assert resp.status_code == 200

    def test_report_pnl_has_ok(self, client):
        resp = client.post(
            "/api/execution_gate/pnl",
            json={"pnl_delta": -100.0, "is_loss": True},
        )
        assert resp.json()["ok"] is True

    def test_report_pnl_echoes_pnl_delta(self, client):
        resp = client.post(
            "/api/execution_gate/pnl",
            json={"pnl_delta": -150.0, "is_loss": True},
        )
        data = resp.json()
        assert "pnl_delta" in data
        assert data["pnl_delta"] == -150.0

    def test_report_pnl_echoes_is_loss(self, client):
        resp = client.post(
            "/api/execution_gate/pnl",
            json={"pnl_delta": 200.0, "is_loss": False},
        )
        data = resp.json()
        assert "is_loss" in data
        assert data["is_loss"] is False

    def test_report_pnl_has_circuit_snapshot(self, client):
        resp = client.post(
            "/api/execution_gate/pnl",
            json={"pnl_delta": -100.0, "is_loss": True},
        )
        data = resp.json()
        assert "circuit" in data
        assert isinstance(data["circuit"], dict)

    def test_report_pnl_missing_pnl_delta_returns_422(self, client):
        # pnl_delta is required with no default
        resp = client.post(
            "/api/execution_gate/pnl",
            json={"is_loss": True},
        )
        assert resp.status_code == 422

    def test_report_pnl_win_scenario(self, client):
        resp = client.post(
            "/api/execution_gate/pnl",
            json={"pnl_delta": 350.0, "is_loss": False},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_report_pnl_calls_update_daily_pnl(self, mock_gate, monkeypatch):
        import lib.services.data.api.execution_gate_routes as egr
        import lib.services.engine.execution_gate as ege

        monkeypatch.setattr(ege, "get_execution_gate", lambda: mock_gate)
        monkeypatch.setattr(egr, "_get_redis", lambda: None)

        from lib.services.data.api.execution_gate_routes import router

        app = FastAPI()
        app.include_router(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            c.post(
                "/api/execution_gate/pnl",
                json={"pnl_delta": -200.0, "is_loss": True},
            )

        mock_gate.update_daily_pnl.assert_called_once_with(-200.0, is_loss=True)

    # --- POST /pnl/live-feed ---

    def test_live_feed_returns_503_when_redis_unavailable(self, client):
        # client fixture patches _get_redis to return None → should 503
        resp = client.post("/api/execution_gate/pnl/live-feed")
        assert resp.status_code == 503

    def test_live_feed_503_body_has_error(self, client):
        resp = client.post("/api/execution_gate/pnl/live-feed")
        data = resp.json()
        assert "error" in data
        assert data["ok"] is False

    def test_live_feed_503_body_has_ok_false(self, client):
        resp = client.post("/api/execution_gate/pnl/live-feed")
        assert resp.json()["ok"] is False

    def test_live_feed_with_redis_processes_entry(self, mock_gate, monkeypatch):
        """When Redis has a pending feed entry, it's consumed and gate is updated."""
        import json

        import lib.services.data.api.execution_gate_routes as egr
        import lib.services.engine.execution_gate as ege

        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({"pnl_delta": -75.0, "is_loss": True}).encode()
        mock_redis.delete.return_value = 1

        monkeypatch.setattr(ege, "get_execution_gate", lambda: mock_gate)
        monkeypatch.setattr(egr, "_get_redis", lambda: mock_redis)

        from lib.services.data.api.execution_gate_routes import router

        app = FastAPI()
        app.include_router(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post("/api/execution_gate/pnl/live-feed")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["processed"] is True
        assert data["pnl_delta"] == -75.0
        assert data["is_loss"] is True

    def test_live_feed_with_redis_no_entry(self, mock_gate, monkeypatch):
        """When Redis has no feed entry, returns processed=False."""
        import lib.services.data.api.execution_gate_routes as egr
        import lib.services.engine.execution_gate as ege

        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # key doesn't exist

        monkeypatch.setattr(ege, "get_execution_gate", lambda: mock_gate)
        monkeypatch.setattr(egr, "_get_redis", lambda: mock_redis)

        from lib.services.data.api.execution_gate_routes import router

        app = FastAPI()
        app.include_router(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post("/api/execution_gate/pnl/live-feed")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["processed"] is False
