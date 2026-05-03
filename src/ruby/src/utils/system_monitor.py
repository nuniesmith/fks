"""
System monitoring utilities for the futures trading bot.

Provides:
- **MemoryMonitor** — periodic RSS memory tracking with configurable alert
  threshold.  Uses ``/proc/self/status`` on Linux (zero-dependency, works on
  Raspberry Pi) with a ``psutil`` fallback for other platforms.
- **MaintenanceChecker** — polls KuCoin exchange status via
  ``exchange.fetch_status()`` and halts all workers when a maintenance window
  is detected.

Wiring into main.py
--------------------
Add the following **imports** near the top of ``main.py``::

    from utils.system_monitor import MemoryMonitor, MaintenanceChecker

Then, **before** the supervisor ``while`` loop (around the block that sets up
``_portfolio_last_state``, ``_start_time``, etc.)::

    # ── System monitors (tasks 14.5 & 14.6) ──────────────────────
    mem_monitor = MemoryMonitor(alert_threshold_mb=1024, discord=discord)
    maint_checker = MaintenanceChecker(exchange=exchange, discord=discord)

Finally, **inside** the supervisor ``while not shutdown_event.is_set():`` loop,
add these two calls right after the ``# ── Exchange session recycling``
block (and before the MasterCNN block)::

    # ── Memory monitoring (task 14.5) ─────────────────────────────
    try:
        mem_mb = await mem_monitor.check()
        if mem_mb > 0:
            logger.debug("RSS memory: %.0f MB", mem_mb)
    except Exception as exc:
        logger.debug("Memory monitor error: %s", exc)

    # ── Exchange maintenance window (task 14.6) ───────────────────
    try:
        in_maint = await maint_checker.check(worker_instances)
    except Exception as exc:
        logger.debug("Maintenance checker error: %s", exc)

NOTE: After a session recycle, update the checker's exchange reference::

    maint_checker._exchange = exchange  # keep in sync after recycle

That single line should go right after the existing block that does
``w.exchange = exchange`` for every worker, inside the session-recycle
``try`` block.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from utils.logging_config import get_logger

if TYPE_CHECKING:
    # Avoid importing heavy libs at module level; these are only used for
    # type-checking by mypy / pyright.
    pass

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Task 14.5 — Memory Monitor
# ═══════════════════════════════════════════════════════════════════════════


class MemoryMonitor:
    """Track process RSS memory and alert when it exceeds a threshold.

    Parameters
    ----------
    alert_threshold_mb:
        Memory usage (in MB) above which a warning is emitted and an
        optional Discord alert is sent.  Default 1024 MB.
    check_interval_sec:
        Minimum seconds between checks.  The ``check()`` coroutine is a
        no-op if called more frequently than this.  Default 300 s (5 min).
    discord:
        Optional ``DiscordNotifier`` instance.  When provided, a
        ``risk_alert`` message is sent the first time the threshold is
        exceeded.
    """

    def __init__(
        self,
        alert_threshold_mb: float = 1024,
        check_interval_sec: int = 300,
        discord: Any | None = None,
    ) -> None:
        self._threshold = alert_threshold_mb
        self._interval = check_interval_sec
        self._last_check: float = 0.0
        self._discord = discord
        self._alerted: bool = False

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def get_memory_mb() -> float:
        """Return current process RSS in megabytes.

        Strategy:
        1. Parse ``/proc/self/status`` (Linux — no external dependency,
           ideal for Raspberry Pi deployments).
        2. Fall back to ``psutil`` if available (macOS / Windows dev boxes).
        3. Return ``0.0`` if neither source works.
        """
        # Fast path: /proc/self/status (Linux)
        try:
            with open("/proc/self/status") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        # Line format: "VmRSS:    123456 kB"
                        return int(line.split()[1]) / 1024.0  # kB → MB
        except (FileNotFoundError, ValueError, IndexError, OSError):
            pass

        # Fallback: psutil (cross-platform, but requires pip install)
        try:
            import psutil  # type: ignore[import-untyped]

            return psutil.Process().memory_info().rss / (1024.0 * 1024.0)
        except ImportError:
            pass

        return 0.0

    # ── public API ────────────────────────────────────────────────

    async def check(self) -> float:
        """Check memory usage if the check interval has elapsed.

        Returns
        -------
        float
            Current RSS in MB, or ``0.0`` if the check was skipped (too
            soon) or memory could not be read.

        Side-effects
        ------------
        * Logs a **warning** the first time usage exceeds the threshold.
        * Sends a Discord ``risk_alert`` (if a notifier was provided).
        * Logs an **info** message when usage drops back below 90 % of
          the threshold (hysteresis to avoid flapping).
        """
        now = time.time()
        if now - self._last_check < self._interval:
            return 0.0
        self._last_check = now

        mb = self.get_memory_mb()
        if mb <= 0:
            return 0.0

        if mb > self._threshold and not self._alerted:
            logger.warning(
                "⚠️ Memory usage: %.0f MB (threshold: %.0f MB)",
                mb,
                self._threshold,
            )
            self._alerted = True
            if self._discord:
                try:
                    await self._discord.risk_alert(
                        alert_type="Memory Warning",
                        message=(
                            f"Process memory {mb:.0f} MB exceeds {self._threshold:.0f} MB threshold"
                        ),
                        details={
                            "Current": f"{mb:.0f} MB",
                            "Threshold": f"{self._threshold:.0f} MB",
                        },
                    )
                except Exception:
                    pass  # Discord failure should never crash the bot

        elif mb <= self._threshold * 0.9 and self._alerted:
            # Hysteresis: only clear alert when we drop to 90 % of threshold
            logger.info("✅ Memory usage back to normal: %.0f MB", mb)
            self._alerted = False

        return mb


# ═══════════════════════════════════════════════════════════════════════════
# Task 14.6 — KuCoin Maintenance-Window Checker
# ═══════════════════════════════════════════════════════════════════════════


class MaintenanceChecker:
    """Detect KuCoin maintenance windows and halt workers.

    Uses ``exchange.fetch_status()`` (a ccxt unified method) which returns
    a dict like::

        {
            "status": "ok" | "maintenance" | "error" | …,
            "updated": <timestamp_ms>,
            "eta": <timestamp_ms> | None,
            "url": "…",
            "msg": "…",
        }

    When maintenance is detected, every worker's ``_portfolio_halted``
    flag is set to ``True`` so no new entries are placed.  When
    maintenance ends, the flag is **not** automatically cleared — the
    normal portfolio circuit-breaker logic in the supervisor loop will
    re-evaluate and clear it on the next iteration.

    Parameters
    ----------
    exchange:
        A ccxt async exchange instance (e.g. ``ccxt.pro.kucoinfutures``).
    check_interval_sec:
        Minimum seconds between status polls.  Default 300 s (5 min).
    discord:
        Optional ``DiscordNotifier`` instance for alerts.
    """

    def __init__(
        self,
        exchange: Any,
        check_interval_sec: int = 300,
        discord: Any | None = None,
    ) -> None:
        self._exchange = exchange
        self._interval = check_interval_sec
        self._last_check: float = 0.0
        self._discord = discord
        self._in_maintenance: bool = False

    # ── public API ────────────────────────────────────────────────

    async def check(self, worker_instances: list[Any]) -> bool:
        """Poll exchange status and halt workers if maintenance is active.

        Parameters
        ----------
        worker_instances:
            List of ``AssetWorker`` objects whose ``_portfolio_halted``
            flag will be set when maintenance is detected.

        Returns
        -------
        bool
            ``True`` if the exchange is currently in maintenance.
        """
        now = time.time()
        if now - self._last_check < self._interval:
            return self._in_maintenance
        self._last_check = now

        try:
            status: dict[str, Any] = await self._exchange.fetch_status()
            # ccxt returns "ok" under normal operation.  Some exchanges
            # also set an "eta" field when scheduled maintenance is
            # imminent — treat that as maintenance too.
            is_maint = status.get("status") == "maintenance" or status.get("eta") is not None

            if is_maint and not self._in_maintenance:
                logger.warning(
                    "🔧 Exchange maintenance detected — halting all %d workers",
                    len(worker_instances),
                )
                for w in worker_instances:
                    w._portfolio_halted = True
                self._in_maintenance = True

                if self._discord:
                    eta = status.get("eta", "unknown")
                    msg = status.get("msg", "No details")
                    try:
                        await self._discord.risk_alert(
                            alert_type="Exchange Maintenance",
                            message=f"KuCoin maintenance detected. ETA: {eta}",
                            details={
                                "Status": str(status.get("status")),
                                "Message": str(msg)[:200],
                                "ETA": str(eta),
                            },
                        )
                    except Exception:
                        pass  # Discord failure should never crash the bot

            elif not is_maint and self._in_maintenance:
                logger.info("✅ Exchange maintenance ended — resuming trading")
                # NOTE: We intentionally do NOT unset _portfolio_halted here.
                # The normal portfolio circuit-breaker logic in the supervisor
                # loop will re-evaluate unrealized loss and clear the flag on
                # its own.  This avoids a race where we clear the halt while
                # the circuit breaker still wants it active.
                self._in_maintenance = False

                if self._discord:
                    try:
                        await self._discord.risk_alert(
                            alert_type="Maintenance Ended",
                            message="KuCoin maintenance window has ended. "
                            "Trading will resume on next supervisor cycle.",
                            details={"Status": str(status.get("status"))},
                        )
                    except Exception:
                        pass

        except Exception as exc:
            # fetch_status can fail due to network issues, rate limits,
            # or the exchange being truly unreachable.  Log at debug to
            # avoid spamming during actual outages.
            logger.debug("Exchange status check failed: %s", exc)

        return self._in_maintenance
