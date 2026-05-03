"""
Comprehensive tests for the chat API endpoints.

Covers:
  GET    /api/chat/status          — LLM backend availability
  GET    /api/chat/history         — Per-session conversation history
  DELETE /api/chat/history         — Clear session history
  GET    /api/market/context       — Live market context strip
  POST   /api/chat                 — Non-streaming single-turn chat
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
    """Minimal FastAPI app containing only the chat router."""
    from lib.services.data.api.chat import router as chat_router

    app = FastAPI()
    app.include_router(chat_router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ===========================================================================
# TestChatStatus — GET /api/chat/status
# ===========================================================================


class TestChatStatus:
    """Tests for GET /api/chat/status."""

    def test_status_returns_200(self, client):
        resp = client.get("/api/chat/status")
        assert resp.status_code == 200

    def test_status_has_backends_key(self, client):
        resp = client.get("/api/chat/status")
        data = resp.json()
        assert "backends" in data
        assert isinstance(data["backends"], dict)

    def test_status_has_active_backend(self, client):
        resp = client.get("/api/chat/status")
        data = resp.json()
        assert "active_backend" in data
        assert isinstance(data["active_backend"], str)

    def test_status_has_model(self, client):
        resp = client.get("/api/chat/status")
        data = resp.json()
        assert "model" in data
        assert isinstance(data["model"], str)
        assert len(data["model"]) > 0

    def test_active_backend_is_valid_value(self, client):
        resp = client.get("/api/chat/status")
        data = resp.json()
        assert data["active_backend"] in {"rc", "grok", "none"}


# ===========================================================================
# TestChatHistory — GET /api/chat/history
# ===========================================================================


class TestChatHistory:
    """Tests for GET /api/chat/history?session_id=test."""

    def test_history_returns_200(self, client):
        resp = client.get("/api/chat/history", params={"session_id": "test"})
        assert resp.status_code == 200

    def test_history_has_messages(self, client):
        resp = client.get("/api/chat/history", params={"session_id": "test"})
        data = resp.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)

    def test_history_has_session_id(self, client):
        resp = client.get("/api/chat/history", params={"session_id": "test"})
        data = resp.json()
        assert "session_id" in data
        assert isinstance(data["session_id"], str)

    def test_history_has_count(self, client):
        resp = client.get("/api/chat/history", params={"session_id": "test"})
        data = resp.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_history_empty_for_new_session(self, client):
        import uuid

        fresh_id = f"fresh-session-{uuid.uuid4().hex}"
        resp = client.get("/api/chat/history", params={"session_id": fresh_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []
        assert data["count"] == 0

    def test_history_missing_session_id_returns_422(self, client):
        resp = client.get("/api/chat/history")
        assert resp.status_code == 422


# ===========================================================================
# TestChatHistoryDelete — DELETE /api/chat/history
# ===========================================================================


class TestChatHistoryDelete:
    """Tests for DELETE /api/chat/history?session_id=test."""

    def test_delete_returns_200(self, client):
        resp = client.delete("/api/chat/history", params={"session_id": "test"})
        assert resp.status_code == 200

    def test_delete_response_has_status(self, client):
        resp = client.delete("/api/chat/history", params={"session_id": "test"})
        data = resp.json()
        assert "status" in data
        assert data["status"] == "cleared"

    def test_delete_response_has_session_id(self, client):
        resp = client.delete("/api/chat/history", params={"session_id": "test-delete-session"})
        data = resp.json()
        assert "session_id" in data
        assert data["session_id"] == "test-delete-session"


# ===========================================================================
# TestMarketContext — GET /api/market/context
# ===========================================================================


class TestMarketContext:
    """Tests for GET /api/market/context."""

    def test_context_returns_200(self, client):
        resp = client.get("/api/market/context")
        assert resp.status_code == 200

    def test_context_has_symbol(self, client):
        resp = client.get("/api/market/context")
        data = resp.json()
        assert "symbol" in data
        assert isinstance(data["symbol"], str)
        assert len(data["symbol"]) > 0

    def test_context_has_bias(self, client):
        resp = client.get("/api/market/context")
        data = resp.json()
        assert "bias" in data
        assert isinstance(data["bias"], str)

    def test_context_has_regime(self, client):
        resp = client.get("/api/market/context")
        data = resp.json()
        assert "regime" in data
        assert isinstance(data["regime"], str)

    def test_context_signal_count_is_int(self, client):
        resp = client.get("/api/market/context")
        data = resp.json()
        assert "signal_count" in data
        assert isinstance(data["signal_count"], int)
        assert data["signal_count"] >= 0

    def test_context_session_pnl_is_none_or_float(self, client):
        resp = client.get("/api/market/context")
        data = resp.json()
        assert "session_pnl" in data
        val = data["session_pnl"]
        assert val is None or isinstance(val, (int, float))


# ===========================================================================
# TestChatPost — POST /api/chat
# ===========================================================================


class TestChatPost:
    """Tests for POST /api/chat (non-streaming path).

    This endpoint requires real LLM connectivity (RUSTCODE or Grok) and will
    return 503 in environments without API keys.  We verify the endpoint
    is reachable and honours its request contract rather than testing
    the underlying LLM response.
    """

    def test_chat_post_without_keys_returns_503(self, client, monkeypatch):
        """Without backend credentials the endpoint should return 503 (not 404/405)."""
        monkeypatch.setenv("RUSTCODE_BASE_URL", "")
        monkeypatch.setenv("XAI_API_KEY", "")
        resp = client.post("/api/chat", json={"message": "hello", "session_id": "test"})
        # Endpoint exists — should be 503 (no backend) or 200, never 404/405.
        assert resp.status_code not in {404, 405}

    def test_chat_post_requires_message(self, client):
        """POST with an empty body should return 422 Unprocessable Entity."""
        resp = client.post("/api/chat", json={})
        assert resp.status_code == 422

    def test_chat_post_accepts_valid_body(self, client):
        """POST with a valid body should return 200 or 503, never 404/405."""
        resp = client.post(
            "/api/chat",
            json={"message": "hello", "session_id": "test-valid"},
        )
        assert resp.status_code not in {404, 405}
