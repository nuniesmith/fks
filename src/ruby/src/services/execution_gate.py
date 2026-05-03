"""
Execution gate chain — centralized entry filtering.

Replaces scattered if-continue blocks in the trading loop with a single
evaluate() call. Each gate is a private method that returns a verdict.
The chain runs gates in priority order and stops at the first BLOCK.

All block reasons are logged at DEBUG level and counted in Redis for
dashboard visibility.

Redis keys used:
    futures:gate_blocks:{asset}:{reason}  — per-reason block counters
    futures:gate_evals:{asset}            — total evaluations counter
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any

from utils.logging_config import get_logger

logger = get_logger("execution_gate")


class GateVerdict(Enum):
    """Result of an execution gate evaluation."""

    PASS = auto()
    BLOCK_CIRCUIT_BREAKER = auto()
    BLOCK_RISK = auto()
    BLOCK_VOL_FILTER = auto()
    BLOCK_QUALITY = auto()
    BLOCK_AO_DIVERGENCE = auto()
    BLOCK_FEE_VIABILITY = auto()
    BLOCK_CNN_DISAGREE = auto()
    BLOCK_CNN_CONFIDENCE = auto()
    BLOCK_CORRELATION = auto()


class ExecutionGate:
    """Chain-of-responsibility gate for trade entries.

    Evaluates a series of gates in priority order. Returns the first
    BLOCK verdict encountered, or PASS if all gates clear.

    Parameters
    ----------
    store : RedisStore
        For counter tracking.
    circuit_breaker : ConsecutiveLossBreaker
        Circuit breaker instance.
    adaptive_threshold : AdaptiveThreshold or None
        Adaptive confidence threshold (or None if disabled).
    """

    def __init__(
        self,
        store: Any,
        circuit_breaker: Any,
        adaptive_threshold: Any = None,
        correlation_guard: Any = None,
    ) -> None:
        self._store = store
        self._circuit_breaker = circuit_breaker
        self._adaptive_threshold = adaptive_threshold
        self._correlation_guard = correlation_guard

    async def evaluate(
        self,
        asset_key: str,
        tag: str,
        signal: str,
        is_add: bool,
        context: dict,
    ) -> tuple[GateVerdict, str]:
        """Run all gates and return (verdict, reason).

        Parameters
        ----------
        asset_key : str
            Short asset name (e.g. "btc").
        tag : str
            Log prefix (e.g. "[BTC]").
        signal : str
            "buy" or "sell".
        is_add : bool
            True if this is a stack add (not first entry).
        context : dict
            Must contain keys:

            - "can_trade": bool - result of _risk_can_trade()
            - "risk_reason": str - reason from _risk_can_trade()
            - "vol_pct": float
            - "vol_entry_min": float
            - "vol_entry_max": float
            - "quality": float
            - "qual_min": float
            - "ao": float
            - "tp_pct": float
            - "fee_taker": float
            - "fee_slip": float
            - "cnn_result": InferenceResult or None
            - "cnn_enabled": bool
            - "min_confidence": float

        Returns
        -------
        (GateVerdict, str) — PASS with empty string, or BLOCK_* with reason.
        """
        # Track evaluation
        try:
            await self._store.increment_counter(f"gate_evals:{asset_key}")
        except Exception:
            pass

        # Run gates in priority order
        gates = [
            self._check_circuit_breaker,
            self._check_risk,
            self._check_vol_filter,
        ]

        # Entry-specific gates (not for adds — adds use their own
        # wave/regime/pullback gates inline in the trading loop)
        if not is_add:
            gates.extend(
                [
                    self._check_quality,
                    self._check_ao_divergence,
                ]
            )

        gates.extend(
            [
                self._check_fee_viability,
                self._check_cnn_agreement,
                self._check_cnn_confidence,
                self._check_correlation,
            ]
        )

        for gate_fn in gates:
            verdict, reason = await gate_fn(asset_key, tag, signal, context)
            if verdict != GateVerdict.PASS:
                # Log and count the block
                logger.debug("%s Gate %s: %s", tag, verdict.name, reason)
                try:
                    await self._store.increment_counter(
                        f"gate_blocks:{asset_key}:{verdict.name.lower()}"
                    )
                except Exception:
                    pass
                return verdict, reason

        return GateVerdict.PASS, ""

    # ── Individual gate checks ────────────────────────────────────

    async def _check_circuit_breaker(
        self, asset_key: str, tag: str, signal: str, ctx: dict
    ) -> tuple[GateVerdict, str]:
        try:
            if await self._circuit_breaker.is_breaker_open(asset_key):
                remaining = await self._circuit_breaker.cooldown_remaining(asset_key)
                count = await self._circuit_breaker.get_loss_count(asset_key)
                return (
                    GateVerdict.BLOCK_CIRCUIT_BREAKER,
                    f"{count} consecutive losses, cooldown {remaining}s remaining",
                )
        except Exception:
            pass  # graceful degradation
        return GateVerdict.PASS, ""

    async def _check_risk(
        self, asset_key: str, tag: str, signal: str, ctx: dict
    ) -> tuple[GateVerdict, str]:
        if not ctx.get("can_trade", True):
            return GateVerdict.BLOCK_RISK, ctx.get("risk_reason", "risk limit")
        return GateVerdict.PASS, ""

    async def _check_vol_filter(
        self, asset_key: str, tag: str, signal: str, ctx: dict
    ) -> tuple[GateVerdict, str]:
        vol_pct = ctx.get("vol_pct", 0.5)
        vol_min = ctx.get("vol_entry_min", 0.15)
        vol_max = ctx.get("vol_entry_max", 0.90)
        if vol_pct < vol_min:
            return (
                GateVerdict.BLOCK_VOL_FILTER,
                f"volatility too low ({vol_pct:.0%} < {vol_min:.0%})",
            )
        if vol_pct > vol_max:
            return (
                GateVerdict.BLOCK_VOL_FILTER,
                f"volatility too high ({vol_pct:.0%} > {vol_max:.0%})",
            )
        return GateVerdict.PASS, ""

    async def _check_quality(
        self, asset_key: str, tag: str, signal: str, ctx: dict
    ) -> tuple[GateVerdict, str]:
        quality = ctx.get("quality", 0.0)
        qual_min = ctx.get("qual_min", 50.0)
        if quality < qual_min:
            return (
                GateVerdict.BLOCK_QUALITY,
                f"quality {quality:.0f} < {qual_min:.0f} minimum",
            )
        return GateVerdict.PASS, ""

    async def _check_ao_divergence(
        self, asset_key: str, tag: str, signal: str, ctx: dict
    ) -> tuple[GateVerdict, str]:
        ao = ctx.get("ao", 0.0)
        if signal == "buy" and ao <= 0:
            return GateVerdict.BLOCK_AO_DIVERGENCE, f"AO={ao:.4f} <= 0 for buy signal"
        if signal == "sell" and ao >= 0:
            return GateVerdict.BLOCK_AO_DIVERGENCE, f"AO={ao:.4f} >= 0 for sell signal"
        return GateVerdict.PASS, ""

    async def _check_fee_viability(
        self, asset_key: str, tag: str, signal: str, ctx: dict
    ) -> tuple[GateVerdict, str]:
        tp_pct = ctx.get("tp_pct", 0.004)
        fee_taker = ctx.get("fee_taker", 0.0006)
        fee_slip = ctx.get("fee_slip", 0.0001)
        round_trip = 2.0 * (fee_taker + fee_slip)
        ratio = round_trip / tp_pct if tp_pct > 0 else 1.0
        if ratio > 0.30:
            return (
                GateVerdict.BLOCK_FEE_VIABILITY,
                f"fee/TP ratio {ratio:.0%} > 30% (RT={round_trip:.4%}, TP={tp_pct:.4%})",
            )
        return GateVerdict.PASS, ""

    async def _check_cnn_agreement(
        self, asset_key: str, tag: str, signal: str, ctx: dict
    ) -> tuple[GateVerdict, str]:
        if not ctx.get("cnn_enabled", False):
            return GateVerdict.PASS, ""
        cnn_result = ctx.get("cnn_result")
        if cnn_result is None:
            return GateVerdict.PASS, ""
        if not cnn_result.agrees_with(signal):
            return (
                GateVerdict.BLOCK_CNN_DISAGREE,
                f"CNN says {cnn_result.signal} (conf={cnn_result.confidence:.2f}), signal={signal}",
            )
        return GateVerdict.PASS, ""

    async def _check_cnn_confidence(
        self, asset_key: str, tag: str, signal: str, ctx: dict
    ) -> tuple[GateVerdict, str]:
        if not ctx.get("cnn_enabled", False):
            return GateVerdict.PASS, ""
        cnn_result = ctx.get("cnn_result")
        if cnn_result is None:
            return GateVerdict.PASS, ""

        # Use adaptive threshold if available
        threshold = ctx.get("min_confidence", 0.60)
        if self._adaptive_threshold is not None:
            try:
                threshold = await self._adaptive_threshold.get_threshold(asset_key)
            except Exception:
                pass

        if cnn_result.confidence < threshold:
            return (
                GateVerdict.BLOCK_CNN_CONFIDENCE,
                f"confidence {cnn_result.confidence:.2f} < {threshold:.2f} threshold",
            )
        return GateVerdict.PASS, ""

    async def _check_correlation(
        self, asset_key: str, tag: str, signal: str, ctx: dict
    ) -> tuple[GateVerdict, str]:
        """Block entry when too many open positions are highly correlated."""
        guard = self._correlation_guard
        if guard is None:
            return GateVerdict.PASS, ""
        open_assets: list[str] = ctx.get("open_assets", [])
        try:
            if guard.would_exceed_limit(asset_key, open_assets):
                count = guard.get_correlated_count(asset_key, open_assets)
                return (
                    GateVerdict.BLOCK_CORRELATION,
                    f"{count} open positions correlated >= {guard.corr_threshold:.0%} with {asset_key}",
                )
        except Exception:
            pass
        return GateVerdict.PASS, ""

    async def get_block_stats(self, asset_key: str) -> dict[str, int]:
        """Get block counts per reason for an asset (for dashboards)."""
        stats: dict[str, int] = {}
        for verdict in GateVerdict:
            if verdict == GateVerdict.PASS:
                continue
            try:
                count = await self._store.get_counter(
                    f"gate_blocks:{asset_key}:{verdict.name.lower()}"
                )
                if count > 0:
                    stats[verdict.name] = count
            except Exception:
                pass
        try:
            stats["total_evals"] = await self._store.get_counter(f"gate_evals:{asset_key}")
        except Exception:
            pass
        return stats
