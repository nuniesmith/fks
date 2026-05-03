"""
Tests for Dataset API endpoints.

Covers the main routes in ``lib.data_factory.dataset_api``:

    GET  /api/datasets              → list all datasets (with optional filters)
    GET  /api/datasets/manifest     → full manifest
    GET  /api/datasets/status       → generation daemon status
    GET  /api/datasets/coverage     → coverage summary for all enabled assets
    POST /api/datasets/prune        → prune old dataset files
    POST /api/datasets/generate     → trigger manual dataset generation
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# Ensure Redis is disabled before any project imports.
os.environ.setdefault("DISABLE_REDIS", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.data_factory import dataset_api
from lib.data_factory.dataset_api import router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_MANIFEST: dict[str, Any] = {
    "generated_at": "2025-01-06T08:00:00+00:00",
    "datasets": [
        {
            "symbol": "MGC",
            "type": "training",
            "interval": "1m",
            "path": "/data/datasets/MGC_training_1m.parquet",
            "rows": 50000,
            "date_range": {"start": "2024-01-01", "end": "2025-01-05"},
            "size_bytes": 1024000,
            "checksum_sha256": "abc123",
        },
        {
            "symbol": "MES",
            "type": "backtest",
            "interval": "5m",
            "path": "/data/datasets/MES_backtest_5m.parquet",
            "rows": 12000,
            "date_range": {"start": "2024-06-01", "end": "2025-01-05"},
            "size_bytes": 512000,
            "checksum_sha256": "def456",
        },
        {
            "symbol": "MES",
            "type": "training",
            "interval": "1m",
            "path": "/data/datasets/MES_training_1m.parquet",
            "rows": 60000,
            "date_range": {"start": "2024-01-01", "end": "2025-01-05"},
            "size_bytes": 2048000,
            "checksum_sha256": "ghi789",
        },
    ],
    "coverage_summary": {
        "MGC": {"1m": 0.95, "5m": 0.92},
        "MES": {"1m": 0.98, "5m": 0.97},
    },
}


def _write_manifest(path: Path, data: dict[str, Any] | None = None) -> None:
    """Write a manifest.json file to disk."""
    payload = data if data is not None else SAMPLE_MANIFEST
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_app(
    *,
    manifest_path: Path | None = None,
    generator: Any = None,
    registry: Any = None,
    redis_client: Any = None,
) -> FastAPI:
    """Build a minimal FastAPI app with the dataset router and configure module state."""
    # Reset module-level references so tests are isolated
    dataset_api._dataset_generator = None
    dataset_api._registry = None
    dataset_api._redis = None
    dataset_api._MANIFEST_PATH = None

    if manifest_path is not None or generator is not None or registry is not None:
        dataset_api.configure(
            dataset_generator=generator,
            registry=registry,
            redis_client=redis_client,
            manifest_path=manifest_path or Path("/tmp/nonexistent_manifest.json"),
        )

    app = FastAPI()
    app.include_router(router)
    return app


def _mock_generator(
    *,
    state: dict[str, Any] | None = None,
    prune_return: int = 3,
    generate_return: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a mock DatasetGenerator."""
    gen = MagicMock()

    gen.get_state.return_value = state or {
        "last_run": "2025-01-06T07:00:00+00:00",
        "next_run": "2025-01-06T08:00:00+00:00",
        "in_progress": False,
        "current_symbol": None,
        "interval_secs": 3600,
        "output_dir": "/data/datasets",
        "min_coverage": 0.9,
    }

    gen.prune_old_datasets = AsyncMock(return_value=prune_return)

    gen.generate_for_symbol = AsyncMock(return_value=generate_return or {"status": "ok", "datasets_written": 2})
    gen.generate_all = AsyncMock(return_value=generate_return or {"status": "complete", "symbols_processed": 5})

    return gen


def _mock_registry(*, symbols: list[str] | None = None) -> MagicMock:
    """Build a mock asset registry."""
    reg = MagicMock()

    sym_list = symbols or ["MGC", "MES"]
    assets = []
    for sym in sym_list:
        asset = MagicMock()
        asset.symbol = sym
        assets.append(asset)

    reg.enabled_assets = AsyncMock(return_value=assets)

    def _get(symbol: str):
        for a in assets:
            if a.symbol == symbol:
                return a
        return None

    reg.get = AsyncMock(side_effect=_get)

    return reg


def _mock_redis(*, coverage_data: dict[str, dict[str, float]] | None = None) -> MagicMock:
    """Build a mock async Redis client."""
    r = AsyncMock()

    cov = coverage_data or {}

    async def _redis_get(key: str):
        # key format: ruby:coverage:{symbol}:{interval}
        parts = key.split(":")
        if len(parts) == 4 and parts[0] == "ruby" and parts[1] == "coverage":
            sym, iv = parts[2], parts[3]
            if sym in cov and iv in cov[sym]:
                return json.dumps({"pct": cov[sym][iv]}).encode()
        return None

    r.get = AsyncMock(side_effect=_redis_get)
    return r


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_manifest(tmp_path):
    """Create a temporary manifest.json with sample data."""
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path)
    return manifest_path


@pytest.fixture()
def tmp_empty_manifest(tmp_path):
    """Create a temporary manifest.json with no datasets."""
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, {"generated_at": "", "datasets": [], "coverage_summary": {}})
    return manifest_path


@pytest.fixture()
def client_no_manifest():
    """TestClient with no manifest configured — exercises fallback paths."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def client_empty(tmp_empty_manifest):
    """TestClient with an empty manifest."""
    app = _make_app(manifest_path=tmp_empty_manifest, generator=_mock_generator())
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def client_with_data(tmp_manifest):
    """TestClient with sample datasets in the manifest."""
    app = _make_app(
        manifest_path=tmp_manifest,
        generator=_mock_generator(),
        registry=_mock_registry(),
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def client_full(tmp_manifest):
    """TestClient with generator, registry, and mock Redis."""
    app = _make_app(
        manifest_path=tmp_manifest,
        generator=_mock_generator(),
        registry=_mock_registry(),
        redis_client=_mock_redis(coverage_data={"MGC": {"1m": 0.96}, "MES": {"5m": 0.99}}),
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# GET /api/datasets — list datasets
# ===========================================================================


class TestListDatasets:
    """GET /api/datasets"""

    def test_returns_200(self, client_with_data):
        resp = client_with_data.get("/api/datasets")
        assert resp.status_code == 200

    def test_response_has_count(self, client_with_data):
        resp = client_with_data.get("/api/datasets")
        body = resp.json()
        assert "count" in body
        assert isinstance(body["count"], int)

    def test_response_has_datasets(self, client_with_data):
        resp = client_with_data.get("/api/datasets")
        body = resp.json()
        assert "datasets" in body
        assert isinstance(body["datasets"], list)

    def test_response_has_generated_at(self, client_with_data):
        resp = client_with_data.get("/api/datasets")
        body = resp.json()
        assert "generated_at" in body

    def test_count_matches_datasets_length(self, client_with_data):
        resp = client_with_data.get("/api/datasets")
        body = resp.json()
        assert body["count"] == len(body["datasets"])

    def test_returns_all_datasets_unfiltered(self, client_with_data):
        resp = client_with_data.get("/api/datasets")
        body = resp.json()
        assert body["count"] == 3

    def test_content_type_is_json(self, client_with_data):
        resp = client_with_data.get("/api/datasets")
        assert "application/json" in resp.headers.get("content-type", "")

    def test_dataset_entry_has_symbol(self, client_with_data):
        resp = client_with_data.get("/api/datasets")
        for ds in resp.json()["datasets"]:
            assert "symbol" in ds

    def test_dataset_entry_has_type(self, client_with_data):
        resp = client_with_data.get("/api/datasets")
        for ds in resp.json()["datasets"]:
            assert "type" in ds

    def test_dataset_entry_has_interval(self, client_with_data):
        resp = client_with_data.get("/api/datasets")
        for ds in resp.json()["datasets"]:
            assert "interval" in ds

    def test_dataset_entry_has_rows(self, client_with_data):
        resp = client_with_data.get("/api/datasets")
        for ds in resp.json()["datasets"]:
            assert "rows" in ds


class TestListDatasetsEmpty:
    """GET /api/datasets — with no datasets in the manifest."""

    def test_returns_200(self, client_empty):
        resp = client_empty.get("/api/datasets")
        assert resp.status_code == 200

    def test_returns_empty_list(self, client_empty):
        resp = client_empty.get("/api/datasets")
        body = resp.json()
        assert body["datasets"] == []

    def test_count_is_zero(self, client_empty):
        resp = client_empty.get("/api/datasets")
        body = resp.json()
        assert body["count"] == 0

    def test_returns_200_when_no_manifest(self, client_no_manifest):
        resp = client_no_manifest.get("/api/datasets")
        assert resp.status_code == 200

    def test_empty_when_no_manifest(self, client_no_manifest):
        resp = client_no_manifest.get("/api/datasets")
        body = resp.json()
        assert body["count"] == 0
        assert body["datasets"] == []


class TestListDatasetsFiltered:
    """GET /api/datasets with query filters."""

    def test_filter_by_type_training(self, client_with_data):
        resp = client_with_data.get("/api/datasets", params={"type": "training"})
        body = resp.json()
        assert body["count"] == 2
        for ds in body["datasets"]:
            assert ds["type"] == "training"

    def test_filter_by_type_backtest(self, client_with_data):
        resp = client_with_data.get("/api/datasets", params={"type": "backtest"})
        body = resp.json()
        assert body["count"] == 1
        assert body["datasets"][0]["type"] == "backtest"

    def test_filter_by_interval(self, client_with_data):
        resp = client_with_data.get("/api/datasets", params={"interval": "5m"})
        body = resp.json()
        assert body["count"] == 1
        assert body["datasets"][0]["interval"] == "5m"

    def test_filter_by_type_and_interval(self, client_with_data):
        resp = client_with_data.get("/api/datasets", params={"type": "training", "interval": "1m"})
        body = resp.json()
        assert body["count"] == 2
        for ds in body["datasets"]:
            assert ds["type"] == "training"
            assert ds["interval"] == "1m"

    def test_filter_no_match_returns_empty(self, client_with_data):
        resp = client_with_data.get("/api/datasets", params={"type": "features"})
        body = resp.json()
        assert body["count"] == 0
        assert body["datasets"] == []


# ===========================================================================
# GET /api/datasets/manifest
# ===========================================================================


class TestGetManifest:
    """GET /api/datasets/manifest"""

    def test_returns_200(self, client_with_data):
        resp = client_with_data.get("/api/datasets/manifest")
        assert resp.status_code == 200

    def test_has_generated_at(self, client_with_data):
        resp = client_with_data.get("/api/datasets/manifest")
        body = resp.json()
        assert "generated_at" in body

    def test_has_datasets(self, client_with_data):
        resp = client_with_data.get("/api/datasets/manifest")
        body = resp.json()
        assert "datasets" in body
        assert isinstance(body["datasets"], list)

    def test_has_coverage_summary(self, client_with_data):
        resp = client_with_data.get("/api/datasets/manifest")
        body = resp.json()
        assert "coverage_summary" in body

    def test_empty_manifest(self, client_no_manifest):
        resp = client_no_manifest.get("/api/datasets/manifest")
        body = resp.json()
        assert body["generated_at"] == ""
        assert body["datasets"] == []


# ===========================================================================
# GET /api/datasets/status
# ===========================================================================


class TestGetStatus:
    """GET /api/datasets/status"""

    def test_returns_200(self, client_with_data):
        resp = client_with_data.get("/api/datasets/status")
        assert resp.status_code == 200

    def test_has_last_run(self, client_with_data):
        resp = client_with_data.get("/api/datasets/status")
        body = resp.json()
        assert "last_run" in body

    def test_has_next_run(self, client_with_data):
        resp = client_with_data.get("/api/datasets/status")
        body = resp.json()
        assert "next_run" in body

    def test_has_in_progress(self, client_with_data):
        resp = client_with_data.get("/api/datasets/status")
        body = resp.json()
        assert "in_progress" in body
        assert isinstance(body["in_progress"], bool)

    def test_has_interval_secs(self, client_with_data):
        resp = client_with_data.get("/api/datasets/status")
        body = resp.json()
        assert "interval_secs" in body

    def test_has_output_dir(self, client_with_data):
        resp = client_with_data.get("/api/datasets/status")
        body = resp.json()
        assert "output_dir" in body

    def test_has_min_coverage(self, client_with_data):
        resp = client_with_data.get("/api/datasets/status")
        body = resp.json()
        assert "min_coverage" in body

    def test_in_progress_false_by_default(self, client_with_data):
        resp = client_with_data.get("/api/datasets/status")
        body = resp.json()
        assert body["in_progress"] is False

    def test_status_without_generator_or_redis(self, client_no_manifest):
        """When no generator or Redis is available, returns sensible defaults."""
        resp = client_no_manifest.get("/api/datasets/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["last_run"] is None
        assert body["in_progress"] is False

    def test_status_content_type(self, client_with_data):
        resp = client_with_data.get("/api/datasets/status")
        assert "application/json" in resp.headers.get("content-type", "")


# ===========================================================================
# GET /api/datasets/coverage
# ===========================================================================


class TestGetCoverage:
    """GET /api/datasets/coverage"""

    def test_returns_200(self, client_with_data):
        resp = client_with_data.get("/api/datasets/coverage")
        assert resp.status_code == 200

    def test_has_coverage_summary(self, client_with_data):
        resp = client_with_data.get("/api/datasets/coverage")
        body = resp.json()
        assert "coverage_summary" in body

    def test_coverage_summary_is_dict(self, client_with_data):
        resp = client_with_data.get("/api/datasets/coverage")
        body = resp.json()
        assert isinstance(body["coverage_summary"], dict)

    def test_coverage_from_manifest(self, client_with_data):
        """When Redis is unavailable, coverage comes from the manifest."""
        resp = client_with_data.get("/api/datasets/coverage")
        body = resp.json()
        coverage = body["coverage_summary"]
        assert "MGC" in coverage
        assert "MES" in coverage

    def test_coverage_values_are_numeric(self, client_with_data):
        resp = client_with_data.get("/api/datasets/coverage")
        coverage = resp.json()["coverage_summary"]
        for symbol, intervals in coverage.items():
            for iv, pct in intervals.items():
                assert isinstance(pct, (int, float))

    def test_coverage_empty_when_no_manifest(self, client_no_manifest):
        resp = client_no_manifest.get("/api/datasets/coverage")
        body = resp.json()
        assert body["coverage_summary"] == {}

    def test_coverage_enriched_from_redis(self, client_full):
        """When Redis has live coverage data, it should be merged in."""
        resp = client_full.get("/api/datasets/coverage")
        body = resp.json()
        coverage = body["coverage_summary"]
        # The mock Redis has MGC:1m=0.96 and MES:5m=0.99
        # These should override or supplement the manifest values
        assert "MGC" in coverage
        assert "MES" in coverage


# ===========================================================================
# POST /api/datasets/prune
# ===========================================================================


class TestPruneDatasets:
    """POST /api/datasets/prune"""

    def test_returns_200(self, client_with_data):
        resp = client_with_data.post("/api/datasets/prune")
        assert resp.status_code == 200

    def test_response_has_pruned_count(self, client_with_data):
        resp = client_with_data.post("/api/datasets/prune")
        body = resp.json()
        assert "pruned" in body
        assert isinstance(body["pruned"], int)

    def test_default_keep_is_3(self, client_with_data):
        resp = client_with_data.post("/api/datasets/prune")
        assert resp.status_code == 200
        # The mock generator's prune returns 3
        assert resp.json()["pruned"] == 3

    def test_custom_keep_param(self, client_with_data):
        resp = client_with_data.post("/api/datasets/prune", params={"keep": 5})
        assert resp.status_code == 200

    def test_keep_below_minimum_returns_422(self, client_with_data):
        resp = client_with_data.post("/api/datasets/prune", params={"keep": 0})
        assert resp.status_code == 422

    def test_keep_above_maximum_returns_422(self, client_with_data):
        resp = client_with_data.post("/api/datasets/prune", params={"keep": 200})
        assert resp.status_code == 422

    def test_prune_calls_generator(self, tmp_manifest):
        gen = _mock_generator(prune_return=7)
        app = _make_app(manifest_path=tmp_manifest, generator=gen)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post("/api/datasets/prune", params={"keep": 2})
        assert resp.status_code == 200
        assert resp.json()["pruned"] == 7
        gen.prune_old_datasets.assert_called_once_with(keep_latest=2)

    def test_prune_returns_503_when_no_generator(self, client_no_manifest):
        resp = client_no_manifest.post("/api/datasets/prune")
        assert resp.status_code == 503

    def test_prune_returns_500_on_generator_error(self, tmp_manifest):
        gen = _mock_generator()
        gen.prune_old_datasets = AsyncMock(side_effect=RuntimeError("disk error"))
        app = _make_app(manifest_path=tmp_manifest, generator=gen)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post("/api/datasets/prune")
        assert resp.status_code == 500


# ===========================================================================
# POST /api/datasets/generate
# ===========================================================================


class TestTriggerGenerate:
    """POST /api/datasets/generate"""

    def test_generate_all_returns_200(self, client_with_data):
        resp = client_with_data.post("/api/datasets/generate", json={})
        assert resp.status_code == 200

    def test_generate_all_response_structure(self, client_with_data):
        resp = client_with_data.post("/api/datasets/generate", json={})
        body = resp.json()
        assert isinstance(body, dict)

    def test_generate_specific_symbol(self, tmp_manifest):
        gen = _mock_generator()
        reg = _mock_registry(symbols=["MGC", "MES"])
        app = _make_app(manifest_path=tmp_manifest, generator=gen, registry=reg)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post("/api/datasets/generate", json={"symbol": "MGC"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "MGC"
        assert body["status"] == "complete"

    def test_generate_unknown_symbol_returns_404(self, tmp_manifest):
        gen = _mock_generator()
        reg = _mock_registry(symbols=["MGC"])
        app = _make_app(manifest_path=tmp_manifest, generator=gen, registry=reg)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post("/api/datasets/generate", json={"symbol": "UNKNOWN"})
        assert resp.status_code == 404

    def test_generate_returns_503_when_no_generator(self, client_no_manifest):
        resp = client_no_manifest.post("/api/datasets/generate", json={})
        assert resp.status_code == 503

    def test_generate_null_symbol_runs_all(self, tmp_manifest):
        gen = _mock_generator()
        reg = _mock_registry()
        app = _make_app(manifest_path=tmp_manifest, generator=gen, registry=reg)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post("/api/datasets/generate", json={"symbol": None})
        assert resp.status_code == 200
        gen.generate_all.assert_called_once()

    def test_generate_calls_generate_for_symbol(self, tmp_manifest):
        gen = _mock_generator()
        reg = _mock_registry(symbols=["MES"])
        app = _make_app(manifest_path=tmp_manifest, generator=gen, registry=reg)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post("/api/datasets/generate", json={"symbol": "MES"})
        gen.generate_for_symbol.assert_called_once()


# ===========================================================================
# Edge cases and manifest parsing
# ===========================================================================


class TestManifestParsing:
    """Edge cases around manifest file handling."""

    def test_missing_manifest_file_returns_empty(self):
        """When the manifest path doesn't exist on disk, endpoints degrade gracefully."""
        app = _make_app(
            manifest_path=Path("/tmp/definitely_does_not_exist_12345.json"),
            generator=_mock_generator(),
        )
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/datasets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0

    def test_corrupt_manifest_returns_empty(self, tmp_path):
        """A corrupt manifest.json should not crash the API."""
        manifest = tmp_path / "manifest.json"
        manifest.write_text("this is not valid JSON {{{{", encoding="utf-8")
        app = _make_app(manifest_path=manifest, generator=_mock_generator())
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/datasets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0

    def test_manifest_without_datasets_key(self, tmp_path):
        """A manifest.json missing the 'datasets' key returns empty."""
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"generated_at": "now"}), encoding="utf-8")
        app = _make_app(manifest_path=manifest, generator=_mock_generator())
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/datasets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0

    def test_generated_at_passed_through(self, tmp_manifest):
        app = _make_app(manifest_path=tmp_manifest, generator=_mock_generator())
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/datasets")
        body = resp.json()
        assert body["generated_at"] == "2025-01-06T08:00:00+00:00"
