"""
Discord webhook notification service for the futures trading bot.

Sends rich embed notifications for trade events, risk alerts, daily
summaries, and operational messages.  Uses aiohttp for async HTTP and
a sliding-window rate limiter to stay under Discord's webhook limits.

All public methods are fire-and-forget safe — Discord errors are logged
as warnings and never propagate to the caller.

Usage::

    from services.config_loader import DiscordConfig
    from services.discord_notify import DiscordNotifier

    notifier = DiscordNotifier(config.discord, sim_mode=config.is_sim)
    await notifier.startup(mode="sim", assets=["BTCUSDT", "ETHUSDT"], capital=150_000)
    ...
    await notifier.close()
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import aiohttp

from services.config_loader import DiscordConfig
from utils.logging_config import get_logger

logger = get_logger("discord_notify")

# Discord embed field value max length
_FIELD_MAX = 1024
# Discord embed description max length
_DESC_MAX = 4096


class DiscordNotifier:
    """Async Discord webhook notifier with rate limiting and sim-mode support.

    Parameters
    ----------
    config:
        Parsed ``DiscordConfig`` from the YAML config.
    sim_mode:
        When ``True``, all message titles are prefixed with ``[SIM]``.
    """

    # ------------------------------------------------------------------ #
    #  Init / teardown
    # ------------------------------------------------------------------ #

    def __init__(self, config: DiscordConfig, *, sim_mode: bool = False) -> None:
        self._webhook_url: str = (config.webhook_url or "").strip()
        self._enabled: bool = config.enabled
        self._timeout: float = max(config.timeout_sec, 1)
        self._rate_limit: int = max(config.rate_limit_per_min, 1)
        self._colors: dict[str, int] = dict(config.colors) if config.colors else {}
        self._alerts: dict[str, bool] = dict(config.alerts) if config.alerts else {}
        self._sim_mode: bool = sim_mode

        # Sliding-window rate limiter state
        self._send_times: list[float] = []

        # Lazy-initialised aiohttp session
        self._session: aiohttp.ClientSession | None = None

    # ── colour helpers ────────────────────────────────────────────────

    def _color(self, name: str) -> int:
        """Return the integer colour value for *name*, falling back to grey."""
        return self._colors.get(name, 0x9E9E9E)

    # ── prefix helper ─────────────────────────────────────────────────

    def _prefix(self, title: str) -> str:
        """Prepend ``[SIM]`` to *title* when running in simulation mode."""
        if self._sim_mode:
            return f"[SIM] {title}"
        return title

    # ── session helper ────────────────────────────────────────────────

    def _get_session(self) -> aiohttp.ClientSession:
        """Return the shared ``aiohttp.ClientSession``, creating it lazily."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close the underlying aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------ #
    #  Rate limiter
    # ------------------------------------------------------------------ #

    def _rate_ok(self) -> bool:
        """Sliding-window rate-limit check.

        Returns ``True`` if we are below ``rate_limit_per_min`` sends in the
        last 60 seconds, and records the current timestamp.  Returns
        ``False`` (and does **not** record) when the limit is reached.
        """
        now = time.time()
        self._send_times = [t for t in self._send_times if now - t < 60]
        if len(self._send_times) >= self._rate_limit:
            return False
        self._send_times.append(now)
        return True

    # ------------------------------------------------------------------ #
    #  Core send
    # ------------------------------------------------------------------ #

    async def _send_embed(
        self,
        title: str,
        description: str,
        color: int,
        fields: list[dict[str, Any]] | None = None,
        footer: str | None = None,
    ) -> None:
        """POST a single embed to the Discord webhook.

        Silently returns (with a log message) on any error so the caller
        is never interrupted.
        """
        # Gate checks
        if not self._enabled or not self._webhook_url:
            return

        if not self._rate_ok():
            logger.warning("discord rate limit reached — dropping message: %s", title)
            return

        embed: dict[str, Any] = {
            "title": title[:256],
            "description": description[:_DESC_MAX],
            "color": color,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }

        if fields:
            embed["fields"] = [
                {
                    "name": str(f.get("name", ""))[:256],
                    "value": str(f.get("value", ""))[:_FIELD_MAX],
                    "inline": f.get("inline", True),
                }
                for f in fields
            ]

        if footer:
            embed["footer"] = {"text": footer[:2048]}

        payload = {"embeds": [embed]}

        try:
            session = self._get_session()
            async with session.post(
                self._webhook_url,
                json=payload,
            ) as resp:
                if resp.status == 429:
                    retry_after = (await resp.json()).get("retry_after", "?")
                    logger.warning(
                        "discord 429 rate-limited (retry_after=%s) — dropped: %s",
                        retry_after,
                        title,
                    )
                elif resp.status >= 400:
                    body = await resp.text()
                    logger.warning(
                        "discord webhook %d for '%s': %s",
                        resp.status,
                        title,
                        body[:300],
                    )
        except aiohttp.ClientError as exc:
            logger.warning("discord webhook network error: %s", exc)
        except Exception as exc:
            logger.warning("discord webhook unexpected error: %s", exc)

    # ------------------------------------------------------------------ #
    #  Alert helpers
    # ------------------------------------------------------------------ #

    def _alert_enabled(self, name: str) -> bool:
        """Return ``True`` if the named alert is turned on in config."""
        return self._alerts.get(name, False)

    # ------------------------------------------------------------------ #
    #  Public alert methods
    # ------------------------------------------------------------------ #

    async def trade_opened(
        self,
        asset: str,
        direction: str,
        price: float,
        size: float,
        leverage: int,
        confidence: float = 0.0,
    ) -> None:
        """Entry notification with direction arrow and entry details."""
        if not self._alert_enabled("trade_entry"):
            return

        arrow = "🟢 ⬆" if direction.upper() == "LONG" else "🔴 ⬇"
        title = self._prefix(f"{arrow} {asset} — {direction.upper()} Opened")
        color = self._color("green") if direction.upper() == "LONG" else self._color("red")

        fields = [
            {"name": "Entry Price", "value": f"`${price:,.4f}`", "inline": True},
            {"name": "Size", "value": f"`{size:,.6f}`", "inline": True},
            {"name": "Leverage", "value": f"`{leverage}x`", "inline": True},
        ]
        if confidence > 0:
            fields.append({"name": "Confidence", "value": f"`{confidence:.1%}`", "inline": True})

        await self._send_embed(title=title, description="", color=color, fields=fields)

    async def trade_closed(
        self,
        asset: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        hold_duration: str,
        fees: float = 0.0,
    ) -> None:
        """Close notification with PnL and colour based on profit/loss."""
        if not self._alert_enabled("trade_close"):
            return

        emoji = "✅" if pnl >= 0 else "❌"
        title = self._prefix(f"{emoji} {asset} — {direction.upper()} Closed")
        color = self._color("green") if pnl >= 0 else self._color("red")

        sign = "+" if pnl >= 0 else ""
        fields = [
            {"name": "Entry", "value": f"`${entry_price:,.4f}`", "inline": True},
            {"name": "Exit", "value": f"`${exit_price:,.4f}`", "inline": True},
            {"name": "PnL", "value": f"`{sign}${pnl:,.4f}`", "inline": True},
            {"name": "Duration", "value": f"`{hold_duration}`", "inline": True},
        ]
        if fees > 0:
            fields.append({"name": "Fees", "value": f"`${fees:,.4f}`", "inline": True})

        await self._send_embed(title=title, description="", color=color, fields=fields)

    async def stop_loss_hit(
        self,
        asset: str,
        direction: str,
        entry_price: float,
        sl_price: float,
        loss: float,
    ) -> None:
        """Stop-loss alert with red colour."""
        if not self._alert_enabled("stop_loss"):
            return

        title = self._prefix(f"🛑 {asset} — Stop Loss Hit")
        fields = [
            {"name": "Direction", "value": f"`{direction.upper()}`", "inline": True},
            {"name": "Entry", "value": f"`${entry_price:,.4f}`", "inline": True},
            {"name": "Stop Price", "value": f"`${sl_price:,.4f}`", "inline": True},
            {"name": "Loss", "value": f"`-${abs(loss):,.4f}`", "inline": True},
        ]

        await self._send_embed(
            title=title,
            description="",
            color=self._color("red"),
            fields=fields,
        )

    async def daily_summary(
        self,
        date: str,
        total_pnl: float,
        total_trades: int,
        win_rate: float,
        per_asset: dict[str, Any],
        gate_stats: dict[str, dict[str, int]] | None = None,
        regime_stats: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """End-of-day summary embed with per-asset breakdown.

        ``per_asset`` is expected as::

            {
                "BTCUSDT": {"trades": 12, "win_rate": 0.67, "pnl": 0.18},
                "ETHUSDT": {"trades": 8, "win_rate": 0.50, "pnl": -0.02},
            }

        Uses embed fields (since Discord embeds don't render Markdown tables).
        """
        if not self._alert_enabled("daily_summary"):
            return

        title = self._prefix(f"📊 Daily Summary — {date}")
        sign = "+" if total_pnl >= 0 else ""
        color = self._color("green") if total_pnl >= 0 else self._color("red")

        fields: list[dict[str, Any]] = []

        # Per-asset rows
        for asset_name, stats in per_asset.items():
            a_trades = stats.get("trades", 0)
            a_wr = stats.get("win_rate", 0.0)
            a_pnl = stats.get("pnl", 0.0)
            a_sign = "+" if a_pnl >= 0 else ""
            fields.append(
                {
                    "name": asset_name,
                    "value": (
                        f"Trades: **{a_trades}** · "
                        f"Win: **{a_wr:.0%}** · "
                        f"PnL: **{a_sign}${a_pnl:,.4f}**"
                    ),
                    "inline": False,
                }
            )

        # Totals separator
        fields.append(
            {
                "name": "─── TOTAL ───",
                "value": (
                    f"Trades: **{total_trades}** · "
                    f"Win: **{win_rate:.0%}** · "
                    f"PnL: **{sign}${total_pnl:,.4f}**"
                ),
                "inline": False,
            }
        )

        # Gate performance summary
        if gate_stats:
            total_evals = sum(gs.get("total_evals", 0) for gs in gate_stats.values())
            total_blocks = sum(
                count
                for gs in gate_stats.values()
                for reason, count in gs.items()
                if reason != "total_evals"
            )
            pass_rate = ((total_evals - total_blocks) / total_evals * 100) if total_evals > 0 else 0

            # Aggregate top block reasons
            reason_totals: dict[str, int] = {}
            for gs in gate_stats.values():
                for reason, count in gs.items():
                    if reason != "total_evals":
                        # Clean up reason name for display
                        display = reason.replace("BLOCK_", "").replace("_", " ").title()
                        reason_totals[display] = reason_totals.get(display, 0) + count

            top_reasons = sorted(reason_totals.items(), key=lambda x: -x[1])[:5]
            reason_lines = (
                " · ".join(f"{r}: **{c}**" for r, c in top_reasons) if top_reasons else "None"
            )

            fields.append(
                {
                    "name": "🚧 Gate Summary",
                    "value": (
                        f"Evals: **{total_evals}** · "
                        f"Blocked: **{total_blocks}** · "
                        f"Pass: **{pass_rate:.0f}%**\n"
                        f"Top blocks: {reason_lines}"
                    ),
                    "inline": False,
                }
            )

        # Regime distribution summary
        if regime_stats:
            # Aggregate across all assets
            total_regime: dict[str, int] = {}
            for asset_dist in regime_stats.values():
                for regime_name, count in asset_dist.items():
                    total_regime[regime_name] = total_regime.get(regime_name, 0) + count

            total_ticks = sum(total_regime.values())
            if total_ticks > 0:
                regime_parts = []
                for regime_name, count in sorted(total_regime.items(), key=lambda x: -x[1]):
                    pct = count / total_ticks * 100
                    display_name = regime_name.replace("_", " ").title()
                    regime_parts.append(f"{display_name}: **{pct:.0f}%**")

                fields.append(
                    {
                        "name": "📊 Regime Distribution",
                        "value": " · ".join(regime_parts),
                        "inline": False,
                    }
                )

        mode_label = "SIMULATION" if self._sim_mode else "LIVE"
        footer = f"Mode: {mode_label}"

        await self._send_embed(
            title=title,
            description="",
            color=color,
            fields=fields,
            footer=footer,
        )

    async def risk_alert(
        self,
        alert_type: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Risk limit hit, circuit breaker, margin cap, etc."""
        if not self._alert_enabled("risk_limit_hit"):
            return

        title = self._prefix(f"⚠️ Risk Alert — {alert_type}")
        fields: list[dict[str, Any]] = []
        if details:
            for k, v in details.items():
                fields.append({"name": k, "value": f"`{v}`", "inline": True})

        await self._send_embed(
            title=title,
            description=message,
            color=self._color("yellow"),
            fields=fields or None,
        )

    async def startup(
        self,
        mode: str,
        assets: list[str],
        capital: float,
    ) -> None:
        """Bot startup notification."""
        if not self._alert_enabled("startup"):
            return

        title = self._prefix("🚀 Bot Started")
        asset_list = ", ".join(assets) if assets else "—"
        fields = [
            {"name": "Mode", "value": f"`{mode.upper()}`", "inline": True},
            {"name": "Capital", "value": f"`${capital:,.2f}`", "inline": True},
            {"name": "Assets", "value": f"`{asset_list}`", "inline": False},
        ]

        await self._send_embed(
            title=title,
            description="",
            color=self._color("blue"),
            fields=fields,
        )

    async def worker_restart(self, asset: str, reason: str) -> None:
        """Worker crash / restart notification."""
        if not self._alert_enabled("worker_restart"):
            return

        title = self._prefix(f"🔄 Worker Restarted — {asset}")
        fields = [
            {"name": "Asset", "value": f"`{asset}`", "inline": True},
            {"name": "Reason", "value": f"`{reason}`", "inline": False},
        ]

        await self._send_embed(
            title=title,
            description="",
            color=self._color("yellow"),
            fields=fields,
        )

    async def signal_reversal(
        self,
        asset: str,
        old_signal: str,
        new_signal: str,
    ) -> None:
        """Signal direction change."""
        if not self._alert_enabled("signal_reversal"):
            return

        title = self._prefix(f"🔀 Signal Reversal — {asset}")
        fields = [
            {"name": "Previous", "value": f"`{old_signal.upper()}`", "inline": True},
            {"name": "New", "value": f"`{new_signal.upper()}`", "inline": True},
        ]

        await self._send_embed(
            title=title,
            description="",
            color=self._color("purple"),
            fields=fields,
        )

    async def optuna_update(
        self,
        asset: str,
        old_params: dict[str, Any],
        new_params: dict[str, Any],
        improvement: float,
    ) -> None:
        """Optuna found better parameters."""
        if not self._alert_enabled("optuna_update"):
            return

        title = self._prefix(f"🧪 Optuna Update — {asset}")

        # Build a compact diff of changed parameters
        changed_lines: list[str] = []
        all_keys = sorted(set(list(old_params.keys()) + list(new_params.keys())))
        for key in all_keys:
            old_val = old_params.get(key)
            new_val = new_params.get(key)
            if old_val != new_val:
                changed_lines.append(f"{key}: `{old_val}` → `{new_val}`")

        diff_text = "\n".join(changed_lines[:15]) if changed_lines else "No parameter changes"

        fields = [
            {"name": "Improvement", "value": f"`{improvement:+.2%}`", "inline": True},
            {"name": "Changed Parameters", "value": diff_text[:_FIELD_MAX], "inline": False},
        ]

        await self._send_embed(
            title=title,
            description="",
            color=self._color("purple"),
            fields=fields,
        )

    async def ws_error(self, asset: str, error: str) -> None:
        """WebSocket connection error."""
        if not self._alert_enabled("ws_error"):
            return

        title = self._prefix(f"🔌 WebSocket Error — {asset}")
        fields = [
            {"name": "Asset", "value": f"`{asset}`", "inline": True},
            {"name": "Error", "value": f"```{error[:900]}```", "inline": False},
        ]

        await self._send_embed(
            title=title,
            description="",
            color=self._color("red"),
            fields=fields,
        )

    # ------------------------------------------------------------------ #
    #  Convenience: sim trade (delegates to trade_opened / trade_closed)
    # ------------------------------------------------------------------ #

    async def sim_trade(
        self,
        asset: str,
        direction: str,
        action: str,
        price: float,
        pnl: float = 0.0,
    ) -> None:
        """Lightweight simulated-trade alert (for ``sim_trade`` alert type).

        This is a standalone notification for simulated fills when
        ``alerts.sim_trade`` is enabled, providing a simpler alternative
        to the full ``trade_opened`` / ``trade_closed`` pair.
        """
        if not self._alert_enabled("sim_trade"):
            return

        emoji = "📝"
        title = self._prefix(f"{emoji} Sim Trade — {asset}")
        sign = "+" if pnl >= 0 else ""
        color = self._color("grey")

        fields = [
            {"name": "Direction", "value": f"`{direction.upper()}`", "inline": True},
            {"name": "Action", "value": f"`{action.upper()}`", "inline": True},
            {"name": "Price", "value": f"`${price:,.4f}`", "inline": True},
        ]
        if action.upper() == "CLOSE":
            fields.append({"name": "PnL", "value": f"`{sign}${pnl:,.4f}`", "inline": True})

        await self._send_embed(
            title=title,
            description="",
            color=color,
            fields=fields,
        )

    async def grok_report(self, report_type: str, summary: str) -> None:
        """Post a Grok AI report summary to Discord.

        Parameters
        ----------
        report_type:
            One of "daily", "weekly", "monthly", "highlights".
        summary:
            The report text (will be truncated to fit Discord embed limits).
        """
        if not self._alert_enabled("daily_summary"):
            return

        emoji_map = {
            "daily": "📊",
            "weekly": "📈",
            "monthly": "📅",
            "highlights": "⭐",
        }
        emoji = emoji_map.get(report_type, "📋")
        title = self._prefix(f"{emoji} Grok {report_type.title()} Report")

        # Discord embed description max is 4096 chars
        desc = summary[:4000] + "…" if len(summary) > 4000 else summary

        await self._send_embed(
            title=title,
            description=desc,
            color=self._color("purple"),
            footer=f"Generated by Grok AI • {report_type.title()} Report",
        )
