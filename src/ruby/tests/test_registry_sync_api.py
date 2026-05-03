"""
Tests for Registry Sync API endpoints.

Covers all routes in ``lib.services.data.api.registry_sync``:

    GET  /api/registry/sync             → JSON array of assets (Janus-compatible)
    GET  /api/registry/sync/v1          → versioned envelope with metadata
    POST /api/registry/annotations      → accept annotations from Janus
    GET  /api/registry/annotations      → list all stored annotations
    GET  /api/registry/annotations/{symbol} → get annotation for one symbol
    GET  /api/registry/services         → list Python-side services
"""

from __future__ import annotations

import json
import os

# Ensure Redis is disabled before any project imports.
os.environ.setdefault("DISABLE_REDIS", "1")

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.services.data.api.registry_sync import (
    _ANNOTATION_PREFIX,
    _compute_price_precision,
    _python_asset_class_to_janus,
    router,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build_app(*, redis=None, asset_registry=None) -> FastAPI:
    """Create a minimal FastAPI app with the registry sync router mounted."""
    app = FastAPI()
    app.include_router(router)

    # Wire up app.state so the endpoints can access shared objects
    app.state.redis = redis
    app.state.asset_registry = asset_registry
    return app


class FakeRedis:
    """In-memory Redis-like store for testing annotation endpoints.

    Supports ``setex``, ``get``, ``scan``, and key-prefix matching.
    """

    def __init__(self):
        self._store: dict[str, bytes] = {}

    def setex(self, key: str, ttl: int, value: str | bytes) -> None:
        self._store[key] = value.encode() if isinstance(value, str) else value

    def get(self, key: str) -> bytes | None:
        return self._store.get(key)

    def scan(self, cursor: int = 0, match: str = "*", count: int = 200):
        """Emulate a single-pass SCAN — returns (0, matching_keys)."""
        prefix = match.replace("*", "")
        keys = [k for k in self._store if k.startswith(prefix)]
        return (0, keys)


@pytest.fixture()
def fake_redis():
    return FakeRedis()


def _patch_core_registry(monkeypatch, *, items=None):
    """Patch the core in-memory ASSET_REGISTRY so sync endpoints don't load real assets.

    When *items* is ``None`` the registry is empty.  Otherwise pass a dict
    of ``{name: mock_asset}`` entries.
    """
    import lib.core.asset_registry as _ar

    monkeypatch.setattr(_ar, "ASSET_REGISTRY", items or {})


@pytest.fixture()
def client_no_redis(monkeypatch):
    """TestClient with no Redis and no registries — exercises empty paths."""
    # Patch the core asset registry import to avoid real imports
    monkeypatch.setattr(
        "lib.services.data.api.registry_sync._get_redis",
        lambda request=None: None,
    )
    _patch_core_registry(monkeypatch)

    app = _build_app(redis=None, asset_registry=None)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def client_with_redis(fake_redis, monkeypatch):
    """TestClient wired to a FakeRedis for annotation endpoints."""
    monkeypatch.setattr(
        "lib.services.data.api.registry_sync._get_redis",
        lambda request=None: fake_redis,
    )
    _patch_core_registry(monkeypatch)

    app = _build_app(redis=fake_redis, asset_registry=None)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def client_with_factory_registry(monkeypatch):
    """TestClient wired with a mock DataFactory asset registry."""
    monkeypatch.setattr(
        "lib.services.data.api.registry_sync._get_redis",
        lambda request=None: None,
    )
    _patch_core_registry(monkeypatch)

    # Mock a factory registry that returns one asset
    mock_registry = MagicMock()
    mock_asset = MagicMock()
    mock_asset.symbol = "BTC/USD"
    mock_asset.name = "Bitcoin"
    mock_asset.asset_class.value = "crypto"
    mock_asset.enabled = True
    mock_asset.exchange = "kraken"
    mock_asset.tick_size = 0.01
    mock_asset.provider_symbol_map = {"kraken": "XXBTZUSD"}
    mock_asset.created_at = None
    mock_asset.updated_at = None

    async def _all_assets():
        return [mock_asset]

    mock_registry.all_assets = _all_assets

    app = _build_app(redis=None, asset_registry=mock_registry)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# Pure helper tests
# ===========================================================================


class TestPythonAssetClassToJanus:
    """Test the asset class mapping helper."""

    def test_metals_maps_to_commodity(self):
        assert _python_asset_class_to_janus("metals") == "Commodity"

    def test_energy_maps_to_commodity(self):
        assert _python_asset_class_to_janus("energy") == "Commodity"

    def test_equity_index_maps_to_futures(self):
        assert _python_asset_class_to_janus("equity_index") == "Futures"

    def test_fx_maps_to_forex(self):
        assert _python_asset_class_to_janus("fx") == "Forex"

    def test_crypto_maps_to_crypto(self):
        assert _python_asset_class_to_janus("crypto") == "Crypto"

    def test_stocks_maps_to_equity(self):
        assert _python_asset_class_to_janus("stocks") == "Equity"

    def test_unknown_maps_to_other(self):
        assert _python_asset_class_to_janus("unknown_class") == "Other"

    def test_case_insensitive(self):
        assert _python_asset_class_to_janus("CRYPTO") == "Crypto"
        assert _python_asset_class_to_janus("Metals") == "Commodity"

    def test_futures_cme_maps_to_futures(self):
        assert _python_asset_class_to_janus("futures_cme") == "Futures"

    def test_etf_maps_to_equity(self):
        assert _python_asset_class_to_janus("etf") == "Equity"

    def test_index_maps_to_index(self):
        assert _python_asset_class_to_janus("index") == "Index"

    def test_commodity_maps_to_commodity(self):
        assert _python_asset_class_to_janus("commodity") == "Commodity"

    def test_forex_maps_to_forex(self):
        assert _python_asset_class_to_janus("forex") == "Forex"


class TestComputePricePrecision:
    """Test the tick-size → precision helper."""

    def test_tick_001(self):
        assert _compute_price_precision(0.01) == 2

    def test_tick_025(self):
        assert _compute_price_precision(0.25) == 2

    def test_tick_1(self):
        assert _compute_price_precision(1.0) == 0

    def test_tick_0001(self):
        assert _compute_price_precision(0.001) == 3

    def test_tick_00001(self):
        assert _compute_price_precision(0.0001) == 4

    def test_tick_5(self):
        assert _compute_price_precision(5.0) == 0

    def test_tick_01(self):
        assert _compute_price_precision(0.1) == 1


# ===========================================================================
# GET /api/registry/sync
# ===========================================================================


class TestSyncAssets:
    """GET /api/registry/sync — returns the full asset catalog."""

    def test_returns_200(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/sync")
        assert resp.status_code == 200

    def test_returns_json_array(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/sync")
        body = resp.json()
        assert isinstance(body, list)

    def test_empty_when_no_registries(self, client_no_redis):
        """With no core or factory registries, sync returns empty array."""
        resp = client_no_redis.get("/api/registry/sync")
        body = resp.json()
        assert body == []

    def test_content_type_is_json(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/sync")
        assert "application/json" in resp.headers.get("content-type", "")

    def test_sync_with_factory_registry(self, client_with_factory_registry):
        """When DataFactory registry has assets, they appear in the sync response."""
        resp = client_with_factory_registry.get("/api/registry/sync")
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) >= 1

    def test_sync_asset_has_required_fields(self, client_with_factory_registry):
        resp = client_with_factory_registry.get("/api/registry/sync")
        body = resp.json()
        assert len(body) >= 1
        asset = body[0]
        required_fields = [
            "id",
            "name",
            "symbol",
            "asset_type",
            "status",
            "trading_pairs",
            "price_precision",
            "quantity_precision",
            "tick_size",
            "lot_size",
            "maker_fee",
            "taker_fee",
            "exchanges",
            "metadata",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in asset, f"Missing field: {field}"

    def test_sync_asset_type_mapped_correctly(self, client_with_factory_registry):
        resp = client_with_factory_registry.get("/api/registry/sync")
        body = resp.json()
        asset = body[0]
        assert asset["asset_type"] == "Crypto"

    def test_sync_active_status_when_enabled(self, client_with_factory_registry):
        resp = client_with_factory_registry.get("/api/registry/sync")
        body = resp.json()
        asset = body[0]
        assert asset["status"] == "Active"

    def test_sync_asset_id_normalized(self, client_with_factory_registry):
        """Asset ID should be lowercase with slashes and spaces replaced."""
        resp = client_with_factory_registry.get("/api/registry/sync")
        body = resp.json()
        asset = body[0]
        # BTC/USD → btc-usd
        assert asset["id"] == "btc-usd"

    def test_sync_crypto_quantity_precision_8(self, client_with_factory_registry):
        resp = client_with_factory_registry.get("/api/registry/sync")
        body = resp.json()
        asset = body[0]
        assert asset["quantity_precision"] == 8


# ===========================================================================
# GET /api/registry/sync/v1
# ===========================================================================


class TestSyncAssetsV1:
    """GET /api/registry/sync/v1 — versioned envelope."""

    def test_returns_200(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/sync/v1")
        assert resp.status_code == 200

    def test_envelope_has_version(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/sync/v1")
        body = resp.json()
        assert "version" in body
        assert body["version"] == 1

    def test_envelope_has_generated_at(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/sync/v1")
        body = resp.json()
        assert "generated_at" in body
        assert isinstance(body["generated_at"], str)
        assert len(body["generated_at"]) > 0

    def test_envelope_has_asset_count(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/sync/v1")
        body = resp.json()
        assert "asset_count" in body
        assert isinstance(body["asset_count"], int)

    def test_envelope_has_assets_array(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/sync/v1")
        body = resp.json()
        assert "assets" in body
        assert isinstance(body["assets"], list)

    def test_asset_count_matches_array_length(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/sync/v1")
        body = resp.json()
        assert body["asset_count"] == len(body["assets"])

    def test_v1_with_factory_data(self, client_with_factory_registry):
        resp = client_with_factory_registry.get("/api/registry/sync/v1")
        body = resp.json()
        assert body["asset_count"] >= 1
        assert body["version"] == 1
        assert len(body["assets"]) == body["asset_count"]


# ===========================================================================
# POST /api/registry/annotations
# ===========================================================================


class TestReceiveAnnotations:
    """POST /api/registry/annotations — accept Janus annotations."""

    def test_valid_annotations_returns_200(self, client_with_redis):
        resp = client_with_redis.post(
            "/api/registry/annotations",
            json={
                "annotations": [
                    {
                        "symbol": "BTC",
                        "exchange": "kraken",
                        "health": "healthy",
                        "last_trade_at": "2025-01-01T00:00:00Z",
                    }
                ]
            },
        )
        assert resp.status_code == 200

    def test_valid_annotations_accepted_count(self, client_with_redis):
        resp = client_with_redis.post(
            "/api/registry/annotations",
            json={
                "annotations": [
                    {"symbol": "BTC", "health": "healthy"},
                    {"symbol": "ETH", "health": "healthy"},
                ]
            },
        )
        body = resp.json()
        assert body["accepted"] == 2

    def test_annotations_stored_in_redis(self, client_with_redis, fake_redis):
        client_with_redis.post(
            "/api/registry/annotations",
            json={"annotations": [{"symbol": "BTC", "health": "healthy"}]},
        )
        key = f"{_ANNOTATION_PREFIX}BTC"
        raw = fake_redis.get(key)
        assert raw is not None
        data = json.loads(raw)
        assert data["symbol"] == "BTC"

    def test_annotation_without_symbol_skipped(self, client_with_redis):
        resp = client_with_redis.post(
            "/api/registry/annotations",
            json={
                "annotations": [
                    {"health": "healthy"},  # missing symbol
                    {"symbol": "ETH", "health": "healthy"},
                ]
            },
        )
        body = resp.json()
        assert body["accepted"] == 1

    def test_invalid_json_returns_400(self, client_with_redis):
        resp = client_with_redis.post(
            "/api/registry/annotations",
            content=b"not json {{{",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_missing_annotations_key_returns_422(self, client_with_redis):
        resp = client_with_redis.post(
            "/api/registry/annotations",
            json={"data": []},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert "error" in body

    def test_annotations_not_list_returns_422(self, client_with_redis):
        resp = client_with_redis.post(
            "/api/registry/annotations",
            json={"annotations": "not a list"},
        )
        assert resp.status_code == 422

    def test_annotations_redis_unavailable_returns_503(self, client_no_redis):
        resp = client_no_redis.post(
            "/api/registry/annotations",
            json={"annotations": [{"symbol": "BTC"}]},
        )
        assert resp.status_code == 503

    def test_empty_annotations_list_returns_zero_accepted(self, client_with_redis):
        resp = client_with_redis.post(
            "/api/registry/annotations",
            json={"annotations": []},
        )
        body = resp.json()
        assert body["accepted"] == 0


# ===========================================================================
# Annotations roundtrip: POST then GET
# ===========================================================================


class TestAnnotationsRoundtrip:
    """POST annotations, then GET them back."""

    def test_post_then_get_all(self, client_with_redis):
        # POST two annotations
        client_with_redis.post(
            "/api/registry/annotations",
            json={
                "annotations": [
                    {"symbol": "BTC", "exchange": "kraken", "health": "healthy"},
                    {"symbol": "ETH", "exchange": "coinbase", "health": "degraded"},
                ]
            },
        )

        # GET all annotations
        resp = client_with_redis.get("/api/registry/annotations")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 2

        symbols = {a["symbol"] for a in body}
        assert "BTC" in symbols
        assert "ETH" in symbols

    def test_post_then_get_per_symbol(self, client_with_redis):
        # POST
        client_with_redis.post(
            "/api/registry/annotations",
            json={
                "annotations": [
                    {
                        "symbol": "BTC",
                        "exchange": "kraken",
                        "health": "healthy",
                        "exchange_symbol": "XXBTZUSD",
                    }
                ]
            },
        )

        # GET by symbol
        resp = client_with_redis.get("/api/registry/annotations/BTC")
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "BTC"
        assert body["exchange"] == "kraken"
        assert body["exchange_symbol"] == "XXBTZUSD"

    def test_overwrite_annotation(self, client_with_redis):
        """POSTing the same symbol twice overwrites the previous value."""
        client_with_redis.post(
            "/api/registry/annotations",
            json={"annotations": [{"symbol": "BTC", "health": "healthy"}]},
        )
        client_with_redis.post(
            "/api/registry/annotations",
            json={"annotations": [{"symbol": "BTC", "health": "degraded"}]},
        )

        resp = client_with_redis.get("/api/registry/annotations/BTC")
        body = resp.json()
        assert body["health"] == "degraded"


# ===========================================================================
# GET /api/registry/annotations
# ===========================================================================


class TestGetAnnotations:
    """GET /api/registry/annotations — list all stored annotations."""

    def test_returns_200(self, client_with_redis):
        resp = client_with_redis.get("/api/registry/annotations")
        assert resp.status_code == 200

    def test_returns_empty_list_when_no_annotations(self, client_with_redis):
        resp = client_with_redis.get("/api/registry/annotations")
        body = resp.json()
        assert body == []

    def test_returns_empty_list_when_redis_unavailable(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/annotations")
        body = resp.json()
        assert body == []
        assert resp.status_code == 200


# ===========================================================================
# GET /api/registry/annotations/{symbol}
# ===========================================================================


class TestGetSymbolAnnotations:
    """GET /api/registry/annotations/{symbol} — single symbol annotation."""

    def test_returns_404_when_not_found(self, client_with_redis):
        resp = client_with_redis.get("/api/registry/annotations/NONEXIST")
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body

    def test_returns_503_when_redis_unavailable(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/annotations/BTC")
        assert resp.status_code == 503

    def test_returns_annotation_when_exists(self, client_with_redis, fake_redis):
        # Seed directly into Redis
        ann = {"symbol": "SOL", "health": "healthy", "exchange": "binance"}
        fake_redis.setex(f"{_ANNOTATION_PREFIX}SOL", 600, json.dumps(ann))

        resp = client_with_redis.get("/api/registry/annotations/SOL")
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "SOL"
        assert body["health"] == "healthy"

    def test_corrupt_annotation_returns_500(self, client_with_redis, fake_redis):
        """If the stored data is not valid JSON, should return 500."""
        fake_redis.setex(f"{_ANNOTATION_PREFIX}BAD", 600, b"not json {{")

        resp = client_with_redis.get("/api/registry/annotations/BAD")
        assert resp.status_code == 500
        assert "error" in resp.json()


# ===========================================================================
# GET /api/registry/services
# ===========================================================================


class TestListPythonServices:
    """GET /api/registry/services — service discovery for Janus."""

    def test_returns_200(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/services")
        assert resp.status_code == 200

    def test_returns_list(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/services")
        body = resp.json()
        assert isinstance(body, list)

    def test_services_are_non_empty(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/services")
        body = resp.json()
        assert len(body) > 0

    def test_each_service_has_name(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/services")
        for svc in resp.json():
            assert "name" in svc
            assert isinstance(svc["name"], str)

    def test_each_service_has_type(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/services")
        for svc in resp.json():
            assert "type" in svc

    def test_each_service_has_host_and_port(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/services")
        for svc in resp.json():
            assert "host" in svc
            assert "port" in svc
            assert isinstance(svc["port"], int)

    def test_each_service_has_health(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/services")
        for svc in resp.json():
            assert "health" in svc

    def test_each_service_has_endpoints(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/services")
        for svc in resp.json():
            assert "endpoints" in svc
            assert isinstance(svc["endpoints"], list)

    def test_known_services_present(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/services")
        names = {svc["name"] for svc in resp.json()}
        assert "data" in names
        assert "engine" in names
        assert "web" in names

    def test_data_service_has_endpoints(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/services")
        data_svc = next(s for s in resp.json() if s["name"] == "data")
        assert len(data_svc["endpoints"]) > 0

    def test_content_type_is_json(self, client_no_redis):
        resp = client_no_redis.get("/api/registry/services")
        assert "application/json" in resp.headers.get("content-type", "")
