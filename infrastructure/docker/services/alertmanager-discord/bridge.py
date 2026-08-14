#!/usr/bin/env python3
"""
Alertmanager Discord Bridge

Receives webhooks from Prometheus Alertmanager and formats them as rich Discord messages.
This bridge transforms Prometheus alert payloads into Discord-compatible embeds with proper
formatting, colors, and fields.

Usage:
    python alertmanager-discord-bridge.py

Environment Variables:
    DISCORD_WEBHOOK_GENERAL  — General alerts, critical/warning, system health (required, primary fallback)
    DISCORD_WEBHOOK_SIGNALS  — Trade signal alerts (falls back to DISCORD_WEBHOOK_GENERAL)
    DISCORD_WEBHOOK_ANALYSIS — Performance/quality analysis alerts (falls back to DISCORD_WEBHOOK_GENERAL)
    DISCORD_BOT_TOKEN        — Discord bot token (reserved for future use)
    DISCORD_WEBHOOK_GENERAL      — Legacy alias for DISCORD_WEBHOOK_GENERAL
    BRIDGE_PORT              — Port to listen on (default: 9094)
    BRIDGE_HOST              — Host to bind to (default: 0.0.0.0)
    LOG_LEVEL                — Logging level (default: INFO)

Features:
    - Rich Discord embeds with severity-based colors
    - Multi-channel routing by path (/signals, /analysis) or alert label (category)
    - Alert grouping and deduplication
    - Resolved alert notifications
    - Runbook and dashboard links
    - Error handling and retry logic
    - /health reports "degraded" (still HTTP 200) when Discord delivery is
      disabled/unconfigured, so an unpaged blind spot is visible in the body
      even though the process itself is up
"""

import json
import logging
import os
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

import requests

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Multi-channel Discord configuration
# DISCORD_WEBHOOK_GENERAL is the primary fallback channel for all unrouted alerts
DISCORD_WEBHOOK_GENERAL = os.getenv("DISCORD_WEBHOOK_GENERAL") or os.getenv("DISCORD_WEBHOOK_GENERAL", "")
DISCORD_WEBHOOK_SIGNALS = os.getenv("DISCORD_WEBHOOK_SIGNALS", "")
DISCORD_WEBHOOK_ANALYSIS = os.getenv("DISCORD_WEBHOOK_ANALYSIS", "")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

BRIDGE_PORT = int(os.getenv("BRIDGE_PORT", "9094"))
BRIDGE_HOST = os.getenv("BRIDGE_HOST", "0.0.0.0")

# Discord embed color codes
SEVERITY_COLORS = {
    "critical": 0xFF0000,  # Red
    "warning": 0xFFA500,  # Orange
    "info": 0x00BFFF,  # Blue
    "resolved": 0x00FF00,  # Green
}

# Emoji mappings
SEVERITY_EMOJI = {
    "critical": "🚨",
    "warning": "⚠️",
    "info": "ℹ️",
    "resolved": "✅",
}


def validate_config() -> bool:
    """Validate required configuration."""
    has_general = bool(DISCORD_WEBHOOK_GENERAL)
    has_signals = bool(DISCORD_WEBHOOK_SIGNALS)
    has_analysis = bool(DISCORD_WEBHOOK_ANALYSIS)

    if not has_general and not has_signals and not has_analysis:
        logger.warning("DISCORD_WEBHOOK_GENERAL environment variable is not set!")
        logger.warning("Get webhook URL from: Discord Server Settings > Integrations > Webhooks")
        logger.warning("Bridge will run in DISABLED mode - webhooks will be acknowledged but not forwarded")
        logger.info(f"Bridge will listen on {BRIDGE_HOST}:{BRIDGE_PORT}")
        return False

    if not has_general:
        logger.warning(
            "DISCORD_WEBHOOK_GENERAL is not set — alerts that cannot be routed to a specific "
            "channel will be dropped. Consider setting DISCORD_WEBHOOK_GENERAL as a fallback."
        )

    # Validate general webhook URL format when present
    if has_general:
        parsed = urlparse(DISCORD_WEBHOOK_GENERAL)
        if not parsed.scheme or not parsed.netloc or "discord" not in parsed.netloc:
            logger.error(f"Invalid DISCORD_WEBHOOK_GENERAL URL: {DISCORD_WEBHOOK_GENERAL}")
            logger.error("URL should be in format: https://discord.com/api/webhooks/...")
            logger.warning("Bridge will run in DISABLED mode due to invalid webhook URL")
            logger.info(f"Bridge will listen on {BRIDGE_HOST}:{BRIDGE_PORT}")
            return False
        logger.info(f"Discord webhook (general) configured: {parsed.scheme}://{parsed.netloc}/...")

    general_mark = "✓" if has_general else "✗"
    signals_mark = "✓" if has_signals else "✗"
    analysis_mark = "✓" if has_analysis else "✗"
    logger.info(
        f"Discord channels configured:  general={general_mark}  signals={signals_mark}  analysis={analysis_mark}"
    )
    logger.info(f"Bridge will listen on {BRIDGE_HOST}:{BRIDGE_PORT}")
    return True


def get_webhook_for_alert(payload: dict[str, Any], path_channel: str = "auto") -> str:
    """Determine which Discord webhook URL to use.

    Resolution order:
      1. Explicit path channel (/signals or /analysis)
      2. Alert label ``category`` for automatic routing
      3. Fall back to DISCORD_WEBHOOK_GENERAL

    Category routing:
      category=trade-signal  → DISCORD_WEBHOOK_SIGNALS   (→ GENERAL fallback)
      category=performance   → DISCORD_WEBHOOK_ANALYSIS  (→ GENERAL fallback)
      category=quality       → DISCORD_WEBHOOK_ANALYSIS  (→ GENERAL fallback)
      everything else        → DISCORD_WEBHOOK_GENERAL
    """
    if path_channel == "signals":
        return DISCORD_WEBHOOK_SIGNALS or DISCORD_WEBHOOK_GENERAL
    if path_channel == "analysis":
        return DISCORD_WEBHOOK_ANALYSIS or DISCORD_WEBHOOK_GENERAL

    # Auto-route by payload label
    alerts = payload.get("alerts", [])
    category = alerts[0].get("labels", {}).get("category", "") if alerts else ""

    if category == "trade-signal":
        return DISCORD_WEBHOOK_SIGNALS or DISCORD_WEBHOOK_GENERAL
    if category in ("performance", "quality"):
        return DISCORD_WEBHOOK_ANALYSIS or DISCORD_WEBHOOK_GENERAL
    return DISCORD_WEBHOOK_GENERAL


def format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp to human-readable format."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return timestamp_str


def get_alert_color(alert: dict[str, Any], status: str) -> int:
    """Determine the color for an alert based on severity and status."""
    if status == "resolved":
        return SEVERITY_COLORS["resolved"]

    severity = alert.get("labels", {}).get("severity", "info")
    return SEVERITY_COLORS.get(severity, SEVERITY_COLORS["info"])


def create_embed(alert: dict[str, Any], status: str) -> dict[str, Any]:
    """Create a Discord embed for a single alert."""
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})

    # Determine severity
    severity = labels.get("severity", "info")
    alertname = labels.get("alertname", "Unknown Alert")

    # Build title with emoji
    emoji = SEVERITY_EMOJI.get("resolved" if status == "resolved" else severity, "📊")
    title = f"{emoji} {severity.upper()}: {alertname}"
    if status == "resolved":
        title = f"✅ RESOLVED: {alertname}"

    # Build description
    summary = annotations.get("summary", "No summary available")
    description = annotations.get("description", "")

    desc_text = f"**{summary}**"
    if description and description != summary:
        desc_text += f"\n\n{description}"

    # Build fields
    fields = []

    # Service/Component
    if "component" in labels:
        fields.append({"name": "Component", "value": labels["component"], "inline": True})

    if "service" in labels:
        fields.append({"name": "Service", "value": labels["service"], "inline": True})

    # Instance/Host
    if "instance" in labels:
        fields.append({"name": "Instance", "value": labels["instance"], "inline": True})

    # Timestamp
    starts_at = alert.get("startsAt", "")
    if starts_at:
        fields.append({"name": "Started At", "value": format_timestamp(starts_at), "inline": True})

    if status == "resolved":
        ends_at = alert.get("endsAt", "")
        if ends_at:
            fields.append(
                {
                    "name": "Resolved At",
                    "value": format_timestamp(ends_at),
                    "inline": True,
                }
            )

    # Build footer with links
    footer_parts = []

    # Runbook link
    runbook_url = annotations.get("runbook_url")
    if runbook_url:
        footer_parts.append(f"[Runbook]({runbook_url})")

    # Dashboard link
    dashboard_url = annotations.get("dashboard_url")
    if dashboard_url:
        footer_parts.append(f"[Dashboard]({dashboard_url})")

    # Alertmanager link
    fingerprint = alert.get("fingerprint", "")
    if fingerprint:
        am_url = f"http://alertmanager:9093/#/alerts?silenced=false&inhibited=false&filter=%7Bfingerprint%3D%22{fingerprint}%22%7D"
        footer_parts.append(f"[Silence]({am_url})")

    # Create embed
    embed = {
        "title": title,
        "description": desc_text,
        "color": get_alert_color(alert, status),
        "fields": fields,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Add footer if we have links
    if footer_parts:
        embed["footer"] = {"text": " • ".join(footer_parts)}

    return embed


def process_alert_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Process Alertmanager webhook payload and create Discord embeds."""
    embeds: list[dict[str, Any]] = []

    status = payload.get("status", "firing")
    alerts = payload.get("alerts", [])

    logger.info(f"Processing {len(alerts)} alerts with status: {status}")

    # Group by alertname for cleaner messages
    alerts_by_name: dict[str, list[dict[str, Any]]] = {}
    for alert in alerts:
        alertname = alert.get("labels", {}).get("alertname", "Unknown")
        if alertname not in alerts_by_name:
            alerts_by_name[alertname] = []
        alerts_by_name[alertname].append(alert)

    # Create embeds (limit to 10 per message as per Discord limits)
    for _alertname, alert_group in alerts_by_name.items():
        if len(embeds) >= 10:
            logger.warning("Reached Discord embed limit (10), truncating remaining alerts")
            break

        # Take first alert from group for the embed
        # If there are multiple instances, mention it in the description
        primary_alert = alert_group[0]
        embed = create_embed(primary_alert, status)

        if len(alert_group) > 1:
            instances = [a.get("labels", {}).get("instance", "unknown") for a in alert_group]
            embed["description"] += f"\n\n*Affects {len(alert_group)} instances: {', '.join(instances[:3])}*"
            if len(instances) > 3:
                embed["description"] += f" and {len(instances) - 3} more"

        embeds.append(embed)

    return embeds


def send_to_discord(embeds: list[dict[str, Any]], webhook_url: str, enabled: bool = True) -> bool:
    """Send embeds to the specified Discord webhook URL."""
    if not embeds:
        logger.warning("No embeds to send")
        return True

    if not enabled or not webhook_url:
        logger.debug(f"Discord disabled/unconfigured - would have sent {len(embeds)} alerts")
        return True

    payload = {"username": "FKS Alerts", "embeds": embeds}

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 204:
            logger.info(f"Successfully sent {len(embeds)} alerts to Discord")
            return True
        elif response.status_code == 429:
            # Rate limited
            retry_after = response.json().get("retry_after", 1)
            logger.warning(f"Discord rate limit hit, retry after {retry_after}s")
            return False
        else:
            logger.error(f"Discord webhook failed: {response.status_code} - {response.text}")
            return False

    except requests.exceptions.Timeout:
        logger.error("Discord webhook request timed out")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Discord webhook request failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending to Discord: {e}")
        return False


def get_health_status(discord_enabled: bool) -> dict[str, Any]:
    """Build the ``/health`` response body.

    The process being up and the Discord delivery path being usable are two
    different things. Collapsing them into a single ``"ok"`` meant a
    disabled/misconfigured webhook — which makes ``send_to_discord`` silently
    acknowledge and drop every alert (see its ``not enabled or not
    webhook_url`` short-circuit) — looked byte-for-byte identical to a fully
    working bridge. Discord is the platform's only out-of-band paging path,
    so that blind spot is real: something could break delivery and the
    health check would never say so.

    Reports ``"degraded"`` (still HTTP 200 — the *process* is healthy; a
    container restart cannot fix a missing webhook env var, so this must not
    look like a process failure to a Docker healthcheck) when Discord is
    disabled/unconfigured, ``"ok"`` otherwise. A Prometheus alert rule can
    still distinguish the two by inspecting the response body.
    """
    status_info: dict[str, Any] = {
        "status": "ok" if discord_enabled else "degraded",
        "discord_enabled": discord_enabled,
        "channels": {
            "general": bool(DISCORD_WEBHOOK_GENERAL),
            "signals": bool(DISCORD_WEBHOOK_SIGNALS),
            "analysis": bool(DISCORD_WEBHOOK_ANALYSIS),
        },
    }
    if not discord_enabled:
        status_info["reason"] = "discord webhook not configured"
    return status_info


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Alertmanager webhooks."""

    discord_enabled: bool = True  # Will be set in main()
    path_channel: str = "auto"

    def log_message(self, format: str, *args: Any) -> None:  # type: ignore[override]
        """Override to use our logger."""
        logger.debug(f"{self.address_string()} - {format % args}")

    def do_GET(self):
        """Handle GET requests (health check)."""
        if self.path == "/health":
            status_info = get_health_status(self.discord_enabled)
            # Always HTTP 200 here — see get_health_status() docstring: a
            # degraded Discord delivery path is not a process failure, so it
            # must not trip a Docker healthcheck restart loop.
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            _ = self.wfile.write(json.dumps(status_info).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle POST requests (webhook payloads)."""
        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            # Parse JSON payload
            payload = json.loads(body.decode("utf-8"))
            logger.debug(f"Received payload: {json.dumps(payload, indent=2)}")

            # Determine routing channel from request path
            path = self.path.rstrip("/").lstrip("/")
            if path == "signals":
                path_channel = "signals"
            elif path == "analysis":
                path_channel = "analysis"
            else:
                path_channel = "auto"

            # Resolve target webhook
            webhook_url = get_webhook_for_alert(payload, path_channel)

            # Process alerts
            embeds = process_alert_payload(payload)

            # Send to Discord (or acknowledge if disabled)
            success = send_to_discord(embeds, webhook_url, enabled=self.discord_enabled)

            if success:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                _ = self.wfile.write(json.dumps({"status": "ok"}).encode())
            else:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                _ = self.wfile.write(json.dumps({"status": "error", "message": "Failed to send to Discord"}).encode())

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON payload: {e}")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            _ = self.wfile.write(json.dumps({"status": "error", "message": "Invalid JSON"}).encode())

        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            _ = self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Alertmanager Discord Bridge")
    logger.info("=" * 60)

    # Validate configuration and determine if Discord is enabled
    discord_enabled = validate_config()

    # Set class variable for handlers
    WebhookHandler.discord_enabled = discord_enabled

    # Log per-channel status
    logger.info(f"Channel general  : {'configured' if DISCORD_WEBHOOK_GENERAL else 'not configured'}")
    logger.info(f"Channel signals  : {'configured' if DISCORD_WEBHOOK_SIGNALS else 'not configured'}")
    logger.info(f"Channel analysis : {'configured' if DISCORD_WEBHOOK_ANALYSIS else 'not configured'}")

    # Create HTTP server
    server_address = (BRIDGE_HOST, BRIDGE_PORT)
    httpd = HTTPServer(server_address, WebhookHandler)

    logger.info("Bridge started successfully")
    logger.info(f"Mode: {'ENABLED' if discord_enabled else 'DISABLED (no webhook configured)'}")
    logger.info(f"Listening on http://{BRIDGE_HOST}:{BRIDGE_PORT}")
    logger.info(f"Alertmanager webhook URL (general)  : http://<bridge-host>:{BRIDGE_PORT}/")
    logger.info(f"Alertmanager webhook URL (signals)  : http://<bridge-host>:{BRIDGE_PORT}/signals")
    logger.info(f"Alertmanager webhook URL (analysis) : http://<bridge-host>:{BRIDGE_PORT}/analysis")
    logger.info(f"Health check: http://<bridge-host>:{BRIDGE_PORT}/health")
    logger.info("=" * 60)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down bridge...")
        httpd.shutdown()
        logger.info("Bridge stopped")


if __name__ == "__main__":
    main()
