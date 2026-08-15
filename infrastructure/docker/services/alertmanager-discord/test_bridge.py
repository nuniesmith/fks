#!/usr/bin/env python3
"""Tests for the Alertmanager Discord bridge.

Covers the /health blind spot: `/health` used to hardcode `"status": "ok"`
whenever the process was up, even when `discord_enabled` was False (no
webhook configured) — meaning `send_to_discord()` was silently
acknowledging and dropping every alert (its `not enabled or not
webhook_url` short-circuit returns True without sending anything) while the
health check reported everything fine. Discord is the platform's only
out-of-band paging path, so that's a real blind spot.

This asserts:
  * disabled/unconfigured  -> "/health" reports "degraded" + a reason, HTTP 200
    (still 200 on purpose: the *process* is healthy, a Docker healthcheck
    restart can't fix a missing webhook env var — see
    bridge.get_health_status()'s docstring)
  * enabled and working    -> "/health" reports "ok", HTTP 200
  * an actual Discord send failure (the pre-existing failure path) still
    surfaces "status": "error" on the webhook POST response, unaffected by
    the /health change above

No external dependencies beyond `requests` (already required by bridge.py).
Run:
    python3 -m unittest infrastructure/docker/services/alertmanager-discord/test_bridge.py
  or, from this directory:
    python3 test_bridge.py
"""

from __future__ import annotations

import importlib
import json
import pathlib
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from typing import Any
from unittest import mock

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

bridge = importlib.import_module("bridge")


# ---------------------------------------------------------------------------
# Direct tests of the pure status-building function
# ---------------------------------------------------------------------------


class GetHealthStatusTests(unittest.TestCase):
    """bridge.get_health_status() in isolation, no HTTP involved."""

    def setUp(self) -> None:
        # Isolate from whatever the real process environment happened to set.
        for name, value in (
            ("DISCORD_WEBHOOK_GENERAL", "https://discord.com/api/webhooks/1/abc"),
            ("DISCORD_WEBHOOK_SIGNALS", ""),
            ("DISCORD_WEBHOOK_ANALYSIS", ""),
        ):
            patcher = mock.patch.object(bridge, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_disabled_reports_degraded_with_reason(self) -> None:
        status = bridge.get_health_status(discord_enabled=False)
        self.assertEqual(status["status"], "degraded")
        self.assertIs(status["discord_enabled"], False)
        self.assertIn("reason", status)
        self.assertTrue(status["reason"], "reason must explain why, not be empty")

    def test_enabled_reports_ok_with_no_reason(self) -> None:
        status = bridge.get_health_status(discord_enabled=True)
        self.assertEqual(status["status"], "ok")
        self.assertIs(status["discord_enabled"], True)
        self.assertNotIn("reason", status)

    def test_channels_reflect_configured_webhooks(self) -> None:
        status = bridge.get_health_status(discord_enabled=True)
        self.assertEqual(
            status["channels"],
            {"general": True, "signals": False, "analysis": False},
        )


# ---------------------------------------------------------------------------
# Black-box HTTP tests against the real WebhookHandler over a socket
# ---------------------------------------------------------------------------

_ALERT_PAYLOAD = {
    "status": "firing",
    "alerts": [
        {
            "labels": {"alertname": "TestAlert", "severity": "critical"},
            "annotations": {"summary": "test alert"},
            "startsAt": "2026-08-14T00:00:00Z",
        }
    ],
}


class _BridgeServer:
    """Runs the real bridge.WebhookHandler on an ephemeral localhost port."""

    def __init__(self, discord_enabled: bool) -> None:
        bridge.WebhookHandler.discord_enabled = discord_enabled
        self._httpd = HTTPServer(("127.0.0.1", 0), bridge.WebhookHandler)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self) -> "_BridgeServer":
        self._thread.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)

    def get(self, path: str) -> tuple[int, dict[str, Any]]:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())

    def post(self, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read().decode())


class HealthEndpointIntegrationTests(unittest.TestCase):
    """Hits the real do_GET handler over a socket, not just the pure function."""

    def test_disabled_health_endpoint_is_200_degraded(self) -> None:
        with _BridgeServer(discord_enabled=False) as server:
            status_code, body = server.get("/health")
        self.assertEqual(
            status_code, 200, "a degraded Discord path must not fail a Docker healthcheck restart loop"
        )
        self.assertEqual(body["status"], "degraded")
        self.assertIn("reason", body)

    def test_enabled_health_endpoint_is_200_ok(self) -> None:
        with mock.patch.object(bridge, "DISCORD_WEBHOOK_GENERAL", "https://discord.com/api/webhooks/1/abc"):
            with _BridgeServer(discord_enabled=True) as server:
                status_code, body = server.get("/health")
        self.assertEqual(status_code, 200)
        self.assertEqual(body["status"], "ok")
        self.assertNotIn("reason", body)


class WebhookPostErrorStatusTests(unittest.TestCase):
    """The pre-existing 'status': 'error' POST response must be unaffected."""

    def test_discord_send_failure_still_reports_error_status(self) -> None:
        fake_response = mock.Mock()
        fake_response.status_code = 500
        fake_response.text = "internal server error"

        with (
            mock.patch.object(bridge.requests, "post", return_value=fake_response),
            mock.patch.object(bridge, "DISCORD_WEBHOOK_GENERAL", "https://discord.com/api/webhooks/1/abc"),
        ):
            with _BridgeServer(discord_enabled=True) as server:
                status_code, body = server.post("/", _ALERT_PAYLOAD)

        self.assertEqual(status_code, 500)
        self.assertEqual(body["status"], "error")

    def test_invalid_json_still_reports_error_status(self) -> None:
        with _BridgeServer(discord_enabled=False) as server:
            req = urllib.request.Request(
                f"http://127.0.0.1:{server.port}/",
                data=b"not json",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(req, timeout=5)
                self.fail("expected HTTPError for invalid JSON")
            except urllib.error.HTTPError as e:
                with e:
                    self.assertEqual(e.code, 400)
                    body = json.loads(e.read().decode())
                self.assertEqual(body["status"], "error")


if __name__ == "__main__":
    unittest.main()
