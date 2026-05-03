"""
Comprehensive tests for the net worth API endpoints.

Covers:
  GET /api/net-worth          — JSON aggregation across all exchanges
  GET /api/net-worth/history  — Historical net worth snapshots
  GET /api/net-worth/html     — HTMX dashboard fragment
  GET /net-worth              — Full standalone page
"""

from __future__ import annotations

import os

# Must be set before any project imports so Redis connections are skipped.
os.environ.setdefault("DISABLE_REDIS", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """Minimal FastAPI app containing only the net_worth router."""
    from lib.services.data.api.net_worth import router as net_worth_router

    app = FastAPI()
    app.include_router(net_worth_router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# TestNetWorthJson — GET /api/net-worth
# ===========================================================================


class TestNetWorthJson:
    """Tests for GET /api/net-worth (JSON aggregation endpoint)."""

    def test_returns_200(self, client):
        resp = client.get("/api/net-worth")
        assert resp.status_code == 200

    def test_has_total_usd(self, client):
        resp = client.get("/api/net-worth")
        data = resp.json()
        assert "total_usd" in data
        assert isinstance(data["total_usd"], (int, float))

    def test_has_total_cad(self, client):
        resp = client.get("/api/net-worth")
        data = resp.json()
        assert "total_cad" in data
        assert isinstance(data["total_cad"], (int, float))

    def test_has_usdcad_rate(self, client):
        resp = client.get("/api/net-worth")
        data = resp.json()
        assert "usdcad_rate" in data
        rate = data["usdcad_rate"]
        assert isinstance(rate, (int, float))
        assert rate > 0

    def test_has_sources(self, client):
        resp = client.get("/api/net-worth")
        data = resp.json()
        assert "sources" in data
        sources = data["sources"]
        assert isinstance(sources, dict)
        assert "kraken_spot" in sources
        assert "kraken_futures" in sources
        assert "rithmic" in sources

    def test_has_allocation(self, client):
        resp = client.get("/api/net-worth")
        data = resp.json()
        assert "allocation" in data
        assert isinstance(data["allocation"], list)

    def test_allocation_pcts_sum_to_100(self, client):
        resp = client.get("/api/net-worth")
        data = resp.json()
        total_usd = data.get("total_usd", 0.0)
        if total_usd > 0:
            pcts = [item["pct"] for item in data["allocation"] if "pct" in item]
            assert abs(sum(pcts) - 100.0) < 1.0, f"Allocation pcts sum to {sum(pcts):.2f}, expected ~100"

    def test_has_updated_at(self, client):
        resp = client.get("/api/net-worth")
        data = resp.json()
        assert "updated_at" in data
        assert isinstance(data["updated_at"], str)
        assert len(data["updated_at"]) > 0

    def test_total_usd_is_non_negative(self, client):
        resp = client.get("/api/net-worth")
        data = resp.json()
        assert data["total_usd"] >= 0.0

    def test_sources_have_total_usd(self, client):
        resp = client.get("/api/net-worth")
        data = resp.json()
        for key, source in data["sources"].items():
            assert "total_usd" in source, f"Source '{key}' is missing 'total_usd'"


# ===========================================================================
# TestNetWorthHistory — GET /api/net-worth/history
# ===========================================================================


class TestNetWorthHistory:
    """Tests for GET /api/net-worth/history."""

    def test_returns_200(self, client):
        resp = client.get("/api/net-worth/history")
        assert resp.status_code == 200

    def test_has_history_key(self, client):
        resp = client.get("/api/net-worth/history")
        data = resp.json()
        assert "history" in data
        assert isinstance(data["history"], list)

    def test_has_count_key(self, client):
        resp = client.get("/api/net-worth/history")
        data = resp.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_count_matches_history_len(self, client):
        resp = client.get("/api/net-worth/history")
        data = resp.json()
        assert data["count"] == len(data["history"])

    def test_history_snapshot_has_ts(self, client):
        resp = client.get("/api/net-worth/history")
        data = resp.json()
        history = data["history"]
        if history:
            assert "ts" in history[0], "First history snapshot is missing 'ts' field"

    def test_history_snapshot_has_total_usd(self, client):
        resp = client.get("/api/net-worth/history")
        data = resp.json()
        history = data["history"]
        if history:
            assert "total_usd" in history[0], "First history snapshot is missing 'total_usd' field"


# ===========================================================================
# TestNetWorthHtml — GET /api/net-worth/html
# ===========================================================================


class TestNetWorthHtml:
    """Tests for GET /api/net-worth/html (HTMX fragment)."""

    def test_returns_200(self, client):
        resp = client.get("/api/net-worth/html")
        assert resp.status_code == 200

    def test_content_type_is_html(self, client):
        resp = client.get("/api/net-worth/html")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_has_net_worth_content(self, client):
        resp = client.get("/api/net-worth/html")
        assert "NET WORTH" in resp.text

    def test_has_total_div(self, client):
        resp = client.get("/api/net-worth/html")
        assert "Total" in resp.text

    def test_has_refresh_button(self, client):
        resp = client.get("/api/net-worth/html")
        assert 'hx-get="/api/net-worth/html"' in resp.text


# ===========================================================================
# TestNetWorthPage — GET /net-worth
# ===========================================================================


class TestNetWorthPage:
    """Tests for GET /net-worth (full standalone page)."""

    def test_returns_200(self, client):
        resp = client.get("/net-worth")
        assert resp.status_code == 200

    def test_content_type_is_html(self, client):
        resp = client.get("/net-worth")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_has_chart_js(self, client):
        resp = client.get("/net-worth")
        assert "chart.js" in resp.text.lower()
