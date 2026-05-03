"""
workers/asset_worker.py
========================
Self-contained trading worker for a single asset.

One instance is spawned per enabled asset by the supervisor.
Each worker owns:
  - WebSocket trade + order-book feeds
  - In-memory position stack
  - Per-asset risk state
  - Optuna parameter optimisation
  - CNN inference (optional, loaded lazily)
  - ADL / leverage management
"""

from __future__ import annotations

import asyncio
import time
from collections import deque

import ccxt.pro as ccxt

from services.adaptive_threshold import AdaptiveThreshold
from services.circuit_breaker import ConsecutiveLossBreaker
from services.config_loader import AssetConfig, FuturesConfig
from services.correlation_guard import CorrelationGuard
from services.discord_notify import DiscordNotifier
from services.execution_gate import ExecutionGate, GateVerdict
from services.multi_tp import MultiTPManager, parse_tp_levels
from services.redis_store import RedisStore
from services.risk_engine import RiskEngine, RiskProfile
from utils.indicators import (
    adaptive_add_threshold,
    adaptive_tp,
    build_candles,
    compute_ao,
    compute_atr,
    compute_quality,
    compute_regime,
    compute_vol_pct,
    fmt_price,
    regime_stack_ok,
    update_wave_state,
    wave_gate_ok,
)
from utils.logging_config import get_logger
from utils.optimizer import OPTUNA_POOL, run_optuna_sync
from utils.state import SignalStreak, WaveState

logger = get_logger(__name__)


class AssetWorker:
    """Self-contained trading worker for one asset."""

    def __init__(
        self,
        asset: AssetConfig,
        config: FuturesConfig,
        exchange: ccxt.kucoinfutures,
        store: RedisStore,
        shutdown_event: asyncio.Event,
        contract_spec: dict | None = None,
        discord: DiscordNotifier | None = None,
        correlation_guard: CorrelationGuard | None = None,
        shared_positions: dict | None = None,
    ) -> None:
        self.asset = asset
        self.config = config
        self.exchange = exchange
        self.store = store
        self.shutdown = shutdown_event
        self.discord = discord
        self.tag = f"[{asset.base}]"
        self.asset_key = asset.key

        self.contract_spec: dict = contract_spec or {}

        self._consecutive_order_failures: int = 0
        self._order_backoff_until: float = 0.0

        # ── Per-worker state ──────────────────────────────────────
        self.trades: deque = deque(maxlen=config.candles.tick_buffer)
        self.orderbook: dict = {"bids": [], "asks": []}

        self.stack: dict = {
            "direction": None,
            "count": 0,
            "prices": [],
            "sizes": [],
            "entry_time": 0.0,
        }

        sl_default = asset.sl_pct if asset.sl_pct else config.strategy.sl_pct
        self.best_params: dict = {
            "fast": config.strategy.fast_ema,
            "slow": config.strategy.slow_ema,
            "imbalance_thresh": config.strategy.imbalance_thresh,
            "sl_pct": sl_default,
            "quality_min": config.wave.quality_min,
            "wave_pct_gate": config.wave.wave_pct_gate,
        }

        self.wave_state = WaveState()
        self._signal_streak = SignalStreak()

        # ── Portfolio-level flags (set by supervisor) ─────────────
        self._portfolio_halted: bool = False
        self._portfolio_over_margin: bool = False
        self._master_halted: bool = False
        self._master_risk_score: float = 0.0

        # ── Per-worker risk state ─────────────────────────────────
        self.risk_state: dict = {
            "daily_pnl": 0.0,
            "daily_trades": 0,
            "consecutive_losses": 0,
            "last_loss_time": 0.0,
            "day_start": "",
            "paused": False,
            "pause_reason": "",
            "_alerted": False,
        }

        # ── Timing ────────────────────────────────────────────────
        self.last_optimize: float = 0.0
        self.last_heartbeat: float = 0.0
        self.last_status_log: float = 0.0
        self._last_reversal_held_log: float = 0.0

        # ── ADL / leverage management ─────────────────────────────
        self._active_leverage: int = asset.leverage
        self._adl_level: int = 0
        self.last_adl_check: float = 0.0

        # ── Dynamic risk engine ───────────────────────────────────────
        # Re-evaluated every _risk_update_interval seconds in the trading loop.
        # Produces effective_leverage (set on exchange) and effective_margin_pct
        # (used in _calc_size instead of the static asset.margin_pct).
        self._risk_engine: RiskEngine = RiskEngine(config)
        self._risk_profile: RiskProfile = RiskProfile(
            effective_leverage=asset.leverage,
            effective_margin_pct=asset.margin_pct,
            leverage_scalar=1.0,
            margin_scalar=1.0,
        )
        self._effective_margin_pct: float = asset.margin_pct
        self._last_risk_update: float = 0.0
        self._risk_update_interval: float = 30.0  # re-evaluate every 30 s

        # ── Risk exposure tracking ────────────────────────────────
        self._risk_per_trade_usdt: float = 0.0
        self._risk_per_trade_pct: float = 0.0

        # ── CNN inference ─────────────────────────────────────────
        self._cnn = None
        self._cnn_signal: str = "flat"
        self._cnn_confidence: float = 0.0

        # ── Optuna interval ───────────────────────────────────────
        optuna_cfg = config.optuna
        if asset.key in optuna_cfg.fast_assets:
            self.optuna_interval = optuna_cfg.intervals.get(
                "fast_sec", optuna_cfg.intervals.get("default_sec", 1200)
            )
        elif asset.key in optuna_cfg.slow_assets:
            self.optuna_interval = optuna_cfg.intervals.get(
                "slow_sec", optuna_cfg.intervals.get("default_sec", 1200)
            )
        else:
            self.optuna_interval = optuna_cfg.intervals.get("default_sec", 1200)

        # ── Adaptive confidence threshold ─────────────────────────
        self._adaptive_threshold: AdaptiveThreshold | None = (
            AdaptiveThreshold(
                store=store,
                base_threshold=config.ml.min_confidence,
                learning_rate=config.ml.threshold_learning_rate,
                max_adjustment=config.ml.threshold_max_adjustment,
                target_win_rate=config.ml.target_win_rate,
            )
            if config.ml.adaptive_threshold
            else None
        )

        # ── Circuit breaker ───────────────────────────────────────
        self._circuit_breaker = ConsecutiveLossBreaker(
            store=store,
            loss_limit=config.risk.max_consecutive_losses,
            cooldown_sec=config.risk.consecutive_loss_cooldown_sec,
        )

        # ── Multi-TP ──────────────────────────────────────────────
        self._multi_tp: MultiTPManager | None = None
        self._tp_levels = parse_tp_levels(config.strategy.multi_tp_levels)

        # ── Correlation guard ─────────────────────────────────────
        self._correlation_guard: CorrelationGuard | None = correlation_guard
        self._shared_positions: dict | None = shared_positions
        self._last_corr_log: float = 0.0

        # ── Execution gate chain ──────────────────────────────────
        self._gate = ExecutionGate(
            store=store,
            circuit_breaker=self._circuit_breaker,
            adaptive_threshold=self._adaptive_threshold,
            correlation_guard=correlation_guard,
        )

    # ══════════════════════════════════════════════════════════════
    # Stack helpers
    # ══════════════════════════════════════════════════════════════

    def _stack_avg_price(self) -> float:
        if not self.stack["prices"]:
            return 0.0
        total_sz = sum(self.stack["sizes"])
        if total_sz == 0:
            return 0.0
        return sum(p * s for p, s in zip(self.stack["prices"], self.stack["sizes"])) / total_sz

    def _stack_total_size(self) -> float:
        return sum(self.stack["sizes"])

    def _stack_clear(self) -> None:
        self.stack.update(direction=None, count=0, prices=[], sizes=[], entry_time=0.0)
        self._multi_tp = None
        if self._shared_positions is not None:
            self._shared_positions[self.asset_key] = False

    def _unrealized_pnl_usdt(self) -> float:
        """Estimate current unrealized P&L in USDT for the open stack."""
        if not self.stack["direction"] or not self.trades:
            return 0.0
        price = float(self.trades[-1]["price"])
        avg = self._stack_avg_price()
        total_size = self._stack_total_size()
        if avg == 0.0 or total_size == 0.0:
            return 0.0
        direction = self.stack["direction"]
        contract_size = self.contract_spec.get("contract_size", 1.0)
        raw_pct = (price - avg) / avg if direction == "buy" else (avg - price) / avg
        return raw_pct * total_size * contract_size * avg

    # ══════════════════════════════════════════════════════════════
    # Risk management
    # ══════════════════════════════════════════════════════════════

    def _risk_check_daily_reset(self) -> None:
        today = time.strftime("%Y-%m-%d")
        if self.risk_state["day_start"] != today:
            self.risk_state.update(
                daily_pnl=0.0,
                daily_trades=0,
                paused=False,
                pause_reason="",
                _alerted=False,
                day_start=today,
            )
            logger.info("%s New trading day: %s — counters reset", self.tag, today)

    def _risk_record_trade(self, pnl_usdt: float, was_stop: bool) -> None:
        self.risk_state["daily_pnl"] += pnl_usdt
        self.risk_state["daily_trades"] += 1
        if pnl_usdt < 0:
            self.risk_state["consecutive_losses"] += 1
            if was_stop:
                self.risk_state["last_loss_time"] = time.time()
        else:
            self.risk_state["consecutive_losses"] = 0

    def _risk_can_trade(self) -> tuple[bool, str]:
        self._risk_check_daily_reset()

        if self._portfolio_halted:
            return False, "Portfolio unrealized loss circuit breaker active — new entries halted"
        if self._portfolio_over_margin:
            return False, "Portfolio margin utilization too high — new entries halted"
        if self._master_halted:
            return (
                False,
                f"MasterCNN portfolio risk too high ({self._master_risk_score:.2f}) — new entries halted",
            )

        cfg = self.config
        capital = cfg.capital.balance_usdt
        max_asset_loss = capital * cfg.risk.max_asset_daily_loss_pct

        if self.risk_state["daily_pnl"] <= -max_asset_loss:
            reason = (
                f"Asset daily loss limit hit "
                f"({self.risk_state['daily_pnl']:.2f} / -{max_asset_loss:.2f})"
            )
            self.risk_state["paused"] = True
            self.risk_state["pause_reason"] = reason
            return False, reason

        max_consec = cfg.risk.max_consecutive_losses
        if self.risk_state["consecutive_losses"] >= max_consec:
            reason = (
                f"Consecutive losses: {self.risk_state['consecutive_losses']} (limit {max_consec})"
            )
            self.risk_state["paused"] = True
            self.risk_state["pause_reason"] = reason
            return False, reason

        cooldown = cfg.risk.cooldown_after_loss_sec
        if self.risk_state["last_loss_time"] > 0:
            elapsed = time.time() - self.risk_state["last_loss_time"]
            if elapsed < cooldown:
                return False, f"Post-SL cooldown: {cooldown - elapsed:.0f}s remaining"

        asset_limit = cfg.risk.asset_trade_limit
        if self.risk_state["daily_trades"] >= asset_limit:
            reason = f"Asset trade limit reached ({asset_limit})"
            self.risk_state["paused"] = True
            self.risk_state["pause_reason"] = reason
            return False, reason

        if self.risk_state["paused"]:
            self.risk_state["paused"] = False
            self.risk_state["pause_reason"] = ""

        return True, ""

    # ══════════════════════════════════════════════════════════════
    # Order sizing
    # ══════════════════════════════════════════════════════════════

    def _calc_size(self, price: float, vol_pct: float = 0.5, regime: str = "NEUTRAL") -> float:
        """Calculate order size in contracts.

        Risk exactly risk_usd dollars per add, regardless of leverage.
        Leverage determines required margin, not notional exposure.
        """
        cfg = self.config
        # Use the dynamically computed margin fraction (shrinks in bad conditions)
        capital = cfg.capital.balance_usdt * self._effective_margin_pct
        sl_dist = self.best_params["sl_pct"]
        leverage = self._active_leverage
        risk_usd = capital * cfg.capital.risk_per_add_pct

        self._risk_per_trade_usdt = risk_usd
        bal = cfg.capital.balance_usdt
        self._risk_per_trade_pct = (risk_usd / bal * 100) if bal > 0 else 0.0

        raw_tokens = (risk_usd / sl_dist) / price

        contract_size = self.contract_spec.get("contract_size", 1.0)
        lot_step = self.contract_spec.get("lot_step", 1.0)
        max_lots = self.contract_spec.get("max_lots", 1_000_000)
        raw_lots = raw_tokens / contract_size

        if lot_step >= 1.0:
            lots = max(int(raw_lots), 1)
        else:
            lots = max(round(raw_lots / lot_step) * lot_step, lot_step)

        # Enforce minimum notional
        min_usdt = max(self.asset.min_order_usdt, cfg.capital.min_order_usdt)
        if lots * contract_size * price / leverage < min_usdt:
            min_lots = (min_usdt * leverage) / (contract_size * price)
            lots = (
                max(int(min_lots) + 1, 1)
                if lot_step >= 1.0
                else max(round(min_lots / lot_step) * lot_step, lot_step)
            )

        # Margin cap per add
        max_stack = max(cfg.capital.max_stack, 1)
        max_margin_per_add = capital / max_stack
        margin_cap_lots = (max_margin_per_add * leverage) / (contract_size * price)
        if lot_step >= 1.0:
            margin_cap_lots = int(margin_cap_lots)
        else:
            margin_cap_lots = int(margin_cap_lots / lot_step) * lot_step

        if margin_cap_lots >= 1 and lots > margin_cap_lots:
            logger.info(
                "%s _calc_size: margin-capped %s → %s lots", self.tag, lots, margin_cap_lots
            )
            lots = margin_cap_lots
        elif margin_cap_lots < 1:
            if lots > 1:
                lots = 1
            logger.info("%s _calc_size: 1 lot exceeds margin cap; using min lot", self.tag)

        lots = min(lots, max_lots)

        if isinstance(lots, float):
            precision = self.contract_spec.get("precision_amount", 0)
            if precision > 0:
                lots = round(lots, precision)

        # Regime scaling
        regime_mults = cfg.volatility.regime_position_multipliers
        if regime_mults:
            regime_key = "trending" if regime.lower().startswith("trending") else regime.lower()
            regime_mult = regime_mults.get(regime_key, 1.0)
            if regime_mult != 1.0:
                adjusted = lots * regime_mult
                adjusted = (
                    max(int(adjusted), 1)
                    if lot_step >= 1.0
                    else max(round(adjusted / lot_step) * lot_step, lot_step)
                )
                lots = adjusted

        return lots

    # ══════════════════════════════════════════════════════════════
    # Order execution
    # ══════════════════════════════════════════════════════════════

    async def _place_order(
        self, side: str, size: float, price: float, reduce_only: bool = False
    ) -> bool:
        """Place order — real in live mode, simulated in sim mode."""
        if self._order_backoff_until > 0:
            now = time.time()
            if now < self._order_backoff_until:
                logger.debug(
                    "%s Order skipped — backoff %.0fs remaining",
                    self.tag,
                    self._order_backoff_until - now,
                )
                return False
            logger.info(
                "%s Order backoff expired — retrying (%d failures)",
                self.tag,
                self._consecutive_order_failures,
            )
            self._consecutive_order_failures = 0
            self._order_backoff_until = 0.0

        if self.config.is_sim:
            slippage = self.config.simulation.slippage_pct
            fill_price = price * (1 + slippage if side == "buy" else 1 - slippage)
            logger.info(
                "%s %s SIM %s %.1f @ %.6f (fill %.6f, slip %.4f%%)",
                self.tag,
                self.config.simulation.log_prefix,
                side,
                size,
                price,
                fill_price,
                slippage * 100,
            )
            return True

        params: dict = {"leverage": self._active_leverage}
        if reduce_only:
            params["reduceOnly"] = True

        use_limit = (
            not reduce_only
            and getattr(self.config.strategy, "use_post_only_entries", False)
            and self.orderbook.get("bids")
            and self.orderbook.get("asks")
        )

        if use_limit:
            limit_price = (
                float(self.orderbook["bids"][0][0])
                if side == "buy"
                else float(self.orderbook["asks"][0][0])
            )
            params["postOnly"] = True
            try:
                order = await self.exchange.create_order(
                    symbol=self.asset.symbol,
                    type="limit",
                    side=side,
                    amount=size,
                    price=limit_price,
                    params=params,
                )
                await asyncio.sleep(3)
                try:
                    status = await self.exchange.fetch_order(order["id"], self.asset.symbol)
                    if status.get("status") == "closed":
                        self._consecutive_order_failures = 0
                        return True
                    await self.exchange.cancel_order(order["id"], self.asset.symbol)
                    return False
                except Exception:
                    try:
                        await self.exchange.cancel_order(order["id"], self.asset.symbol)
                    except Exception:
                        pass
                    return False
            except Exception as exc:
                logger.debug("%s Limit order rejected, falling back to market: %s", self.tag, exc)
                params.pop("postOnly", None)

        try:
            await self.exchange.create_order(
                symbol=self.asset.symbol,
                type="market",
                side=side,
                amount=size,
                params=params,
            )
            self._consecutive_order_failures = 0
            return True
        except Exception as exc:
            self._consecutive_order_failures += 1
            failures = self._consecutive_order_failures
            backoff = min(10 * (2 ** (failures - 1)), 300)
            self._order_backoff_until = time.time() + backoff
            logger.error(
                "%s Order error (attempt %d, backoff %ds): %s | side=%s size=%s price=%.6f",
                self.tag,
                failures,
                backoff,
                exc,
                side,
                size,
                price,
            )
            if failures >= 5:
                self.risk_state["paused"] = True
                self.risk_state["pause_reason"] = (
                    f"Order failures: {failures} consecutive errors — last: {exc}"
                )
                logger.warning(
                    "%s PAUSED after %d consecutive order failures. Will retry in %ds.",
                    self.tag,
                    failures,
                    backoff,
                )
            return False

    async def _close_position(
        self, reason: str, price: float, ruby_ctx: dict | None = None
    ) -> None:
        """Close the current stack and record P&L."""
        direction = self.stack["direction"]
        avg = self._stack_avg_price()
        total_size = self._stack_total_size()

        if total_size == 0 or direction is None:
            self._stack_clear()
            return

        close_side = "sell" if direction == "buy" else "buy"
        success = await self._place_order(close_side, total_size, price, reduce_only=True)

        if success:
            raw_pct = (price - avg) / avg if direction == "buy" else (avg - price) / avg
            lev_pct = raw_pct * self._active_leverage * 100
            contract_size = self.contract_spec.get("contract_size", 1.0)
            usdt_pnl = raw_pct * total_size * contract_size * avg
            sign = "+" if raw_pct >= 0 else ""

            logger.info(
                "%s CLOSED %s | avg=%.4f exit=%.4f | %s%.2f%% lev (%s%.4f USDT) | adds=%d | reason=%s",
                self.tag,
                direction,
                avg,
                price,
                sign,
                lev_pct,
                sign,
                usdt_pnl,
                self.stack["count"],
                reason,
            )

            trade_info: dict = {
                "direction": direction,
                "avg_entry": avg,
                "exit_price": price,
                "size": total_size,
                "adds": self.stack["count"],
                "reason": reason,
                "lev_pct": round(lev_pct, 4),
            }
            if "[SIM]" in self.tag:
                fee_rate = self.asset_config.maker_fee
                notional = avg * total_size * self.contract_size
                fee = 2 * notional * fee_rate  # Approximate for entry and exit
                usdt_pnl -= fee
                trade_info["maker_fee"] = fee
                trade_info["taker_fee"] = 0.0
                trade_info["total_fees"] = fee

            if ruby_ctx:
                trade_info.update(
                    {
                        "regime": ruby_ctx.get("regime", "?"),
                        "quality": ruby_ctx.get("quality", 0),
                        "wave_ratio": ruby_ctx.get("wave_ratio", 0),
                        "ao": ruby_ctx.get("ao", 0),
                        "vol_pct": ruby_ctx.get("vol_pct", 0),
                    }
                )

            await self.store.record_pnl(
                asset=self.asset_key,
                pnl_usdt=round(usdt_pnl, 6),
                pnl_pct=round(raw_pct, 6),
                trade_info=trade_info,
            )
            await self.store.record_order(
                asset=self.asset_key,
                order={
                    "side": close_side,
                    "size": total_size,
                    "price": price,
                    "type": "close",
                    "reason": reason,
                    "pnl_usdt": round(usdt_pnl, 6),
                    "timestamp": time.time(),
                },
            )

            if self.discord:
                hold_secs = time.time() - self.stack.get("entry_time", 0)
                hold_str = (
                    f"{int(hold_secs)}s"
                    if hold_secs < 60
                    else f"{int(hold_secs / 60)}m {int(hold_secs % 60)}s"
                )
                is_sl = "Stop Loss" in reason
                if is_sl:
                    asyncio.create_task(
                        self.discord.stop_loss_hit(
                            asset=self.asset.base,
                            direction=direction,
                            entry_price=avg,
                            sl_price=price,
                            loss=usdt_pnl,
                        )
                    )
                else:
                    asyncio.create_task(
                        self.discord.trade_closed(
                            asset=self.asset.base,
                            direction=direction,
                            entry_price=avg,
                            exit_price=price,
                            pnl=usdt_pnl,
                            hold_duration=hold_str,
                        )
                    )

            self._risk_record_trade(usdt_pnl, "Stop Loss" in reason)

            try:
                await self._circuit_breaker.record_outcome(self.asset_key, usdt_pnl >= 0)
                if usdt_pnl < 0:
                    breaker_status = await self._circuit_breaker.status(self.asset_key)
                    if breaker_status["open"]:
                        logger.warning(
                            "%s CIRCUIT BREAKER TRIPPED — %d consecutive losses, cooling down %dm",
                            self.tag,
                            breaker_status["consecutive_losses"],
                            breaker_status["cooldown_remaining_sec"] // 60,
                        )
                        if self.discord:
                            asyncio.create_task(
                                self.discord.risk_alert(
                                    alert_type="Circuit Breaker",
                                    message=(
                                        f"{self.asset.base}: "
                                        f"{breaker_status['consecutive_losses']} consecutive losses"
                                        f" — pausing {breaker_status['cooldown_remaining_sec'] // 60}m"
                                    ),
                                    details={
                                        "Asset": self.asset.base,
                                        "Losses": breaker_status["consecutive_losses"],
                                        "Cooldown": f"{breaker_status['cooldown_remaining_sec']}s",
                                    },
                                )
                            )
            except Exception as exc:
                logger.debug("%s Circuit breaker record failed: %s", self.tag, exc)

            if self._adaptive_threshold is not None:
                try:
                    await self._adaptive_threshold.record_outcome(self.asset_key, usdt_pnl >= 0)
                except Exception as exc:
                    logger.debug("%s Adaptive threshold update failed: %s", self.tag, exc)

            self._stack_clear()
            self._signal_streak = SignalStreak()
        else:
            logger.warning(
                "%s Close order FAILED — stack retained for retry. reason=%s price=%.6f",
                self.tag,
                reason,
                price,
            )

    # ══════════════════════════════════════════════════════════════
    # Position recovery on restart
    # ══════════════════════════════════════════════════════════════

    async def _recover_position(self) -> None:
        """Sync in-memory stack with any open position on the exchange."""
        if self.config.is_sim:
            return
        try:
            positions = await self.exchange.fetch_positions([self.asset.symbol])
            for pos in positions:
                contracts = float(pos.get("contracts") or 0)
                if contracts == 0:
                    continue
                side = pos.get("side", "")
                avg_entry = float(
                    pos.get("entryPrice") or pos.get("info", {}).get("avgEntryPrice", 0) or 0
                )
                if avg_entry == 0:
                    logger.warning(
                        "%s Could not determine avg entry price for recovered position", self.tag
                    )
                direction = "buy" if side == "long" else "sell"
                recovered_entry_time = time.time() - 86400
                self.stack.update(
                    direction=direction,
                    count=1,
                    prices=[avg_entry],
                    sizes=[contracts],
                    entry_time=recovered_entry_time,
                )
                logger.warning(
                    "%s Recovered open %s @ %.6f (entry_time set to 24h ago for hold check)",
                    self.tag,
                    direction,
                    avg_entry,
                )
        except Exception as exc:
            logger.warning("%s Position recovery failed (non-fatal): %s", self.tag, exc)

    # ══════════════════════════════════════════════════════════════
    # WebSocket feeds
    # ══════════════════════════════════════════════════════════════

    async def _handle_trades(self) -> None:
        logger.info("%s Trade feed connecting for %s...", self.tag, self.asset.symbol)
        reconnect_delay = self.config.streams.reconnect_delay_sec
        max_delay = self.config.streams.reconnect_max_delay_sec
        backoff = self.config.streams.reconnect_backoff_factor
        delay = reconnect_delay

        while not self.shutdown.is_set():
            try:
                trade_data = await self.exchange.watch_trades(self.asset.symbol)
                delay = reconnect_delay
                for t in trade_data:
                    p = float(t["price"])
                    self.trades.append(
                        {
                            "timestamp": t["timestamp"],
                            "price": p,
                            "qty": float(t["amount"]),
                            "open": p,
                            "high": p,
                            "low": p,
                        }
                    )
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("%s Trade WS error (retry in %.0fs): %s", self.tag, delay, exc)
                await asyncio.sleep(delay)
                delay = min(delay * backoff, max_delay)

    async def _handle_orderbook(self) -> None:
        logger.info("%s Orderbook feed connecting for %s...", self.tag, self.asset.symbol)
        depth = self.config.streams.orderbook_depth
        display = self.config.streams.orderbook_display
        reconnect_delay = self.config.streams.reconnect_delay_sec
        max_delay = self.config.streams.reconnect_max_delay_sec
        backoff = self.config.streams.reconnect_backoff_factor
        delay = reconnect_delay

        while not self.shutdown.is_set():
            try:
                book = await self.exchange.watch_order_book(self.asset.symbol, limit=depth)
                delay = reconnect_delay
                self.orderbook = {
                    "bids": book["bids"][:display],
                    "asks": book["asks"][:display],
                }
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("%s Book WS error (retry in %.0fs): %s", self.tag, delay, exc)
                await asyncio.sleep(delay)
                delay = min(delay * backoff, max_delay)

    # ══════════════════════════════════════════════════════════════
    # Optuna optimisation
    # ══════════════════════════════════════════════════════════════

    async def _maybe_optimize(self) -> None:
        now = time.time()
        if now - self.last_optimize < self.optuna_interval:
            return
        self.last_optimize = now

        cfg = self.config
        fees = cfg.optuna.fees
        fee_per_trade = fees.get("taker_pct", 0.0006) + fees.get("slippage_pct", 0.0001)
        trades_snapshot = list(self.trades)

        loop = asyncio.get_running_loop()
        t_start = time.time()
        new_params = await loop.run_in_executor(
            OPTUNA_POOL,
            run_optuna_sync,
            trades_snapshot,
            cfg.candles.min_ticks,
            cfg.awesome_oscillator.fast,
            cfg.awesome_oscillator.slow,
            cfg.optuna.search_space,
            cfg.optuna.n_trials,
            cfg.optuna.timeout_sec,
            fee_per_trade,
        )

        if new_params:
            self.best_params.update(new_params)
            params_str = " ".join(
                f"{k}={round(v, 4) if isinstance(v, float) else v}" for k, v in new_params.items()
            )
            logger.info(
                "%s Optuna complete (%d trials, %.1fs) → %s",
                self.tag,
                cfg.optuna.n_trials,
                time.time() - t_start,
                params_str,
            )
        else:
            logger.debug("%s Optuna skipped — not enough candle data", self.tag)

    # ══════════════════════════════════════════════════════════════
    # Heartbeat
    # ══════════════════════════════════════════════════════════════

    async def _send_heartbeat(
        self, candles_count: int = 0, regime: str = "?", quality: float = 0.0
    ) -> None:
        breaker_info: dict = {}
        try:
            breaker_info = await self._circuit_breaker.status(self.asset_key)
        except Exception:
            pass

        adaptive_thresh = 0.0
        try:
            if self._adaptive_threshold is not None:
                adaptive_thresh = await self._adaptive_threshold.get_threshold(self.asset_key)
        except Exception:
            pass

        regime_dist: dict = {}
        try:
            await self.store.record_regime_tick(self.asset_key, regime)
            dist_data = await self.store.get_regime_distribution(asset=self.asset_key)
            regime_dist = dist_data.get(self.asset_key, {})
        except Exception:
            pass

        tp_hit_counts: dict = {}
        try:
            for level_idx in range(4):
                count = await self.store.get_counter(f"tp_hits:{self.asset_key}:{level_idx}")
                if count > 0:
                    tp_hit_counts[f"tp{level_idx + 1}"] = count
        except Exception:
            pass

        status = {
            "ticks": len(self.trades),
            "candles": candles_count,
            "stack_dir": self.stack["direction"],
            "stack_count": self.stack["count"],
            "daily_pnl": round(self.risk_state["daily_pnl"], 4),
            "daily_trades": self.risk_state["daily_trades"],
            "regime": regime,
            "quality": round(quality, 1),
            "params": {
                k: round(v, 4) if isinstance(v, float) else v for k, v in self.best_params.items()
            },
            "adl_level": self._adl_level,
            "active_leverage": self._active_leverage,
            "target_leverage": self.asset.leverage,
            "effective_margin_pct": round(self._effective_margin_pct, 4),
            "target_margin_pct": self.asset.margin_pct,
            "risk_leverage_scalar": self._risk_profile.leverage_scalar,
            "risk_margin_scalar": self._risk_profile.margin_scalar,
            "risk_factors": self._risk_profile.factors,
            "risk_summary": self._risk_profile.summary,
            "risk_per_trade_usdt": round(self._risk_per_trade_usdt, 4),
            "risk_per_trade_pct": round(self._risk_per_trade_pct, 2),
            "margin_used_usdt": round(self._estimated_margin_usdt(), 4),
            "cnn_enabled": self._cnn is not None and self._cnn.enabled,
            "cnn_signal": self._cnn_signal,
            "cnn_confidence": round(self._cnn_confidence, 3),
            "master_risk_score": round(self._master_risk_score, 3),
            "master_halted": self._master_halted,
            "breaker_open": breaker_info.get("open", False),
            "breaker_consec_losses": breaker_info.get("consecutive_losses", 0),
            "breaker_cooldown_sec": breaker_info.get("cooldown_remaining_sec", 0),
            "breaker_loss_limit": breaker_info.get("loss_limit", 3),
            "adaptive_threshold": round(adaptive_thresh, 4),
            "regime_dist": regime_dist,
            "tp_hits": tp_hit_counts,
        }

        try:
            await self.store.heartbeat(self.asset_key, status)
        except Exception as exc:
            logger.debug("%s Heartbeat error: %s", self.tag, exc)

    # ══════════════════════════════════════════════════════════════
    # ADL & leverage management
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _adl_bar_from_percentile(pct: float) -> int:
        if pct >= 0.8:
            return 5
        if pct >= 0.6:
            return 4
        if pct >= 0.4:
            return 3
        if pct >= 0.2:
            return 2
        return 1

    def _estimated_margin_usdt(self) -> float:
        if self.stack["count"] == 0 or not self.stack["prices"]:
            return 0.0
        contract_size = self.contract_spec.get("contract_size", 1.0)
        leverage = max(self._active_leverage, 1)
        return sum(
            (size * contract_size * price) / leverage
            for price, size in zip(self.stack["prices"], self.stack["sizes"])
        )

    async def _set_leverage(self, new_leverage: int, reason: str = "") -> None:
        new_leverage = max(1, min(new_leverage, self.asset.max_leverage))
        if new_leverage == self._active_leverage:
            return
        try:
            await self.exchange.setLeverage(leverage, self.asset_key, {"marginMode": "cross"})
            old = self._active_leverage
            self._active_leverage = new_leverage
            logger.info(
                "%s Leverage %dx → %dx%s",
                self.tag,
                old,
                new_leverage,
                f" [{reason}]" if reason else "",
            )
        except Exception as exc:
            logger.warning("%s set_leverage(%dx) failed: %s", self.tag, new_leverage, exc)

    async def _check_adl_and_adjust_leverage(self) -> None:
        if not self.config.is_live:
            return
        adl_cfg = self.config.adl

        if self.stack["count"] == 0:
            if self._active_leverage != self.asset.leverage:
                await self._set_leverage(
                    self.asset.leverage, reason="position closed — restoring target leverage"
                )
            self._adl_level = 0
            return

        try:
            positions = await self.exchange.fetch_positions([self.asset.symbol])
            for pos in positions:
                if float(pos.get("contracts") or 0) == 0:
                    continue
                raw_adl = pos.get("info", {}).get("adlRankingPercentile")
                if raw_adl is None:
                    return
                adl_level = self._adl_bar_from_percentile(float(raw_adl))
                if adl_level != self._adl_level:
                    logger.info(
                        "%s ADL level %d/5 (percentile=%.2f) — leverage %dx",
                        self.tag,
                        adl_level,
                        float(raw_adl),
                        self._active_leverage,
                    )
                self._adl_level = adl_level

                if adl_level >= adl_cfg.reduce_at_level:
                    new_lev = max(
                        int(self._active_leverage * adl_cfg.leverage_reduce_factor),
                        adl_cfg.min_leverage,
                    )
                    if new_lev < self._active_leverage:
                        await self._set_leverage(
                            new_lev, reason=f"ADL {adl_level}/5 bars — reducing"
                        )
                elif (
                    adl_level <= adl_cfg.restore_at_level
                    and self._active_leverage < self.asset.leverage
                ):
                    new_lev = min(
                        int(self._active_leverage / adl_cfg.leverage_reduce_factor),
                        self.asset.leverage,
                    )
                    if new_lev > self._active_leverage:
                        await self._set_leverage(
                            new_lev, reason=f"ADL {adl_level}/5 bars — restoring"
                        )
                return
        except Exception as exc:
            logger.warning("%s ADL check error (non-fatal): %s", self.tag, exc)

    async def _update_dynamic_risk(
        self,
        vol_pct: float,
        regime: str,
        quality: float,
    ) -> None:
        """Re-compute effective leverage and margin from live risk signals.

        Called once every ``_risk_update_interval`` seconds inside the
        trading loop.  When the computed effective leverage differs from
        the current active leverage by ≥ 1 step *and* the engine is
        enabled, the new leverage is pushed to the exchange (live mode
        only) and the effective margin fraction is updated in-memory.

        The update is intentionally rate-limited so it doesn't thrash the
        exchange API or react to every micro-fluctuation in vol_pct.
        """
        if not self.config.risk_engine.enabled:
            return

        balance = self.config.capital.balance_usdt
        daily_pnl = self.risk_state["daily_pnl"]
        consec = self.risk_state["consecutive_losses"]

        profile = self._risk_engine.compute_risk_profile(
            asset=self.asset,
            vol_pct=vol_pct,
            regime=regime,
            quality=quality,
            daily_pnl_usdt=daily_pnl,
            balance_usdt=balance,
            consecutive_losses=consec,
        )

        self._risk_profile = profile
        self._effective_margin_pct = profile.effective_margin_pct

        # Push leverage change to exchange only if it differs meaningfully
        if profile.effective_leverage != self._active_leverage:
            reason = (
                f"dynamic-risk lev×{profile.leverage_scalar:.2f} "
                f"marg×{profile.margin_scalar:.2f} [{profile.summary}]"
            )
            await self._set_leverage(profile.effective_leverage, reason=reason)
            logger.info(
                "%s DynamicRisk: lev %dx→%dx margin %.1f%%→%.1f%% | %s",
                self.tag,
                self._active_leverage,
                profile.effective_leverage,
                self.asset.margin_pct * 100,
                profile.effective_margin_pct * 100,
                profile.summary,
            )

    # ══════════════════════════════════════════════════════════════
    # Core trading loop
    # ══════════════════════════════════════════════════════════════

    async def _trading_loop(self) -> None:  # noqa: C901
        cfg = self.config
        loop_sleep = cfg.monitoring.loop_sleep_sec
        heartbeat_interval = cfg.monitoring.heartbeat_interval_sec
        ao_fast = cfg.awesome_oscillator.fast
        ao_slow = cfg.awesome_oscillator.slow
        vol_entry_min = cfg.volatility.entry_filter_min_percentile
        vol_entry_max = cfg.volatility.entry_filter_max_percentile
        max_stack = cfg.capital.max_stack

        fees = cfg.optuna.fees
        fee_floor = (fees.get("taker_pct", 0.0006) + fees.get("slippage_pct", 0.0001)) * 2 * 1.5
        tp_pct_floor = max(cfg.strategy.tp_pct_floor, fee_floor)

        logger.info("%s Waiting for tick data (need %d ticks)...", self.tag, cfg.candles.min_ticks)
        while not self.shutdown.is_set() and len(self.trades) < cfg.candles.min_ticks:
            await asyncio.sleep(2)
        if self.shutdown.is_set():
            return
        logger.info("%s Tick data ready — entering trading loop", self.tag)

        while not self.shutdown.is_set():
            now = time.time()

            try:
                await self._maybe_optimize()
            except Exception as exc:
                logger.warning("%s Optuna error: %s", self.tag, exc)

            candles = build_candles(self.trades, cfg.candles.min_ticks)
            if len(candles) < 35:
                await asyncio.sleep(loop_sleep)
                continue

            if not self.orderbook["bids"] or not self.orderbook["asks"]:
                await asyncio.sleep(loop_sleep)
                continue

            # ── Indicators ────────────────────────────────────────
            self.wave_state = update_wave_state(
                candles,
                self.wave_state,
                ema_period=cfg.wave.ema_period,
                rma_alpha=cfg.wave.rma_alpha,
            )
            vol_pct = compute_vol_pct(
                candles,
                atr_period=cfg.volatility.atr_period,
                lookback=cfg.volatility.percentile_lookback,
            )
            regime, _ = compute_regime(
                candles,
                sma_period=cfg.regime.sma_period,
                slope_lookback=cfg.regime.slope_lookback,
                slope_threshold=cfg.regime.slope_trending_threshold,
                vol_volatile=cfg.regime.vol_volatile_threshold,
                vol_ranging=cfg.regime.vol_ranging_threshold,
            )
            ao = compute_ao(candles, fast=ao_fast, slow=ao_slow)
            fast_ema = float(
                candles["close"].ewm(span=self.best_params["fast"], adjust=False).mean().iloc[-1]
            )
            slow_ema = float(
                candles["close"].ewm(span=self.best_params["slow"], adjust=False).mean().iloc[-1]
            )
            bid_vol = sum(float(b[1]) for b in self.orderbook["bids"])
            ask_vol = sum(float(a[1]) for a in self.orderbook["asks"])
            imbalance = bid_vol / ask_vol if ask_vol > 0 else 1.0
            quality = compute_quality(
                candles,
                ao,
                vol_pct,
                fast_ema,
                slow_ema,
                imbalance,
                regime,
                quality_cfg=cfg.quality,
            )
            tp_pct = max(
                adaptive_tp(vol_pct, regime, cfg.strategy.tp_pct_base, vol_cfg=cfg.volatility),
                tp_pct_floor,
            )
            add_thresh = adaptive_add_threshold(vol_pct, cfg.strategy.add_threshold_base)
            qual_min = float(self.best_params.get("quality_min", cfg.wave.quality_min))
            wave_gate = float(self.best_params.get("wave_pct_gate", cfg.wave.wave_pct_gate))

            ruby_ctx = {
                "regime": regime,
                "wave_ratio": self.wave_state.wave_ratio,
                "wr_pct": self.wave_state.wr_pct,
                "cur_ratio": self.wave_state.cur_ratio,
                "ao": ao,
                "vol_pct": vol_pct,
                "quality": quality,
                "tp_pct": tp_pct,
                "imbalance": imbalance,
                "fast_ema": fast_ema,
                "slow_ema": slow_ema,
            }

            # ── Dynamic risk update ───────────────────────────────────
            if now - self._last_risk_update >= self._risk_update_interval:
                await self._update_dynamic_risk(
                    vol_pct=vol_pct,
                    regime=regime,
                    quality=quality,
                )
                self._last_risk_update = now

            # ── ADL check ─────────────────────────────────────────
            if self.config.is_live and now - self.last_adl_check > cfg.adl.check_interval_sec:
                await self._check_adl_and_adjust_leverage()
                self.last_adl_check = now

            # ── Correlation guard update ──────────────────────────
            if self._correlation_guard is not None and len(candles) >= 2:
                try:
                    import math as _math

                    _c0 = float(candles["close"].iloc[-2])
                    _c1 = float(candles["close"].iloc[-1])
                    if _c0 > 0:
                        self._correlation_guard.update(self.asset_key, _math.log(_c1 / _c0))
                except Exception:
                    pass

            # ── Heartbeat ─────────────────────────────────────────
            if now - self.last_heartbeat > heartbeat_interval:
                await self._send_heartbeat(
                    candles_count=len(candles), regime=regime, quality=quality
                )
                if self._correlation_guard is not None and now - self._last_corr_log > 21600:
                    self._correlation_guard.log_matrix()
                    self._last_corr_log = now
                logger.info(
                    "%s regime=%s wave=%.2f(p%.0f%%) bias=%s ao=%s "
                    "vol_pct=%.0f%% quality=%.0f tp=%.2f%% imb=%.2f "
                    "stack=%d/%d(%s) daily_pnl=%.4f trades=%d streak=%s×%d",
                    self.tag,
                    regime,
                    self.wave_state.wave_ratio,
                    self.wave_state.wr_pct * 100,
                    self.wave_state.bias,
                    fmt_price(ao),
                    vol_pct * 100,
                    quality,
                    tp_pct * 100,
                    imbalance,
                    self.stack["count"],
                    max_stack,
                    self.stack["direction"] or "flat",
                    self.risk_state["daily_pnl"],
                    self.risk_state["daily_trades"],
                    self._signal_streak.direction,
                    self._signal_streak.count,
                )
                self.last_heartbeat = now

            if not self.trades:
                await asyncio.sleep(loop_sleep)
                continue

            price = float(self.trades[-1]["price"])
            direction = self.stack["direction"]
            avg = self._stack_avg_price()
            sl_pct = self.best_params["sl_pct"]

            # ── TP / SL check ─────────────────────────────────────
            if direction is not None and avg > 0:
                if self._multi_tp is not None and cfg.strategy.multi_tp_enabled:
                    tp_action = self._multi_tp.check(price)
                    if tp_action.action == "partial_close":
                        close_size = tp_action.close_size
                        close_side = "sell" if direction == "buy" else "buy"
                        success = await self._place_order(
                            close_side, close_size, price, reduce_only=True
                        )
                        if success:
                            logger.info(
                                "%s Multi-TP: %s — closed %.1f contracts",
                                self.tag,
                                tp_action.reason,
                                close_size,
                            )
                            try:
                                await self.store.increment_counter(
                                    f"tp_hits:{self.asset_key}:{tp_action.level_hit}"
                                )
                            except Exception:
                                pass
                            if self.stack["sizes"]:
                                self.stack["sizes"][-1] = max(
                                    0, self.stack["sizes"][-1] - close_size
                                )
                        await asyncio.sleep(loop_sleep)
                        continue

                    elif tp_action.action == "full_close":
                        if tp_action.level_hit >= 0:
                            try:
                                await self.store.increment_counter(
                                    f"tp_hits:{self.asset_key}:{tp_action.level_hit}"
                                )
                            except Exception:
                                pass
                        is_stop = "Stop Loss" in tp_action.reason
                        await self._close_position(
                            f"Multi-TP: {tp_action.reason} {'🛑' if is_stop else '✅'}",
                            price,
                            ruby_ctx,
                        )
                        self._multi_tp = None
                        await asyncio.sleep(loop_sleep)
                        continue
                else:
                    if direction == "buy" and price >= avg * (1 + tp_pct):
                        await self._close_position("Take Profit ✅", price, ruby_ctx)
                        await asyncio.sleep(loop_sleep)
                        continue
                    if direction == "sell" and price <= avg * (1 - tp_pct):
                        await self._close_position("Take Profit ✅", price, ruby_ctx)
                        await asyncio.sleep(loop_sleep)
                        continue
                    if direction == "buy" and price <= avg * (1 - sl_pct):
                        await self._close_position("Stop Loss 🛑", price, ruby_ctx)
                        await asyncio.sleep(loop_sleep)
                        continue
                    if direction == "sell" and price >= avg * (1 + sl_pct):
                        await self._close_position("Stop Loss 🛑", price, ruby_ctx)
                        await asyncio.sleep(loop_sleep)
                        continue

            # ── Entry signal ──────────────────────────────────────
            raw_signal: str | None = None
            imb_thresh = self.best_params["imbalance_thresh"]
            if fast_ema > slow_ema and imbalance > imb_thresh:
                raw_signal = "buy"
            elif fast_ema < slow_ema and imbalance < (2.0 - imb_thresh):
                raw_signal = "sell"

            self._signal_streak.update(raw_signal)
            if raw_signal is None or not self._signal_streak.confirmed():
                await asyncio.sleep(loop_sleep)
                continue

            signal = raw_signal

            # ── Opposite signal — maybe close ─────────────────────
            if direction is not None and signal != direction:
                raw_move = (price - avg) / avg if direction == "buy" else (avg - price) / avg
                hold_elapsed = now - self.stack["entry_time"]
                min_profit = cfg.strategy.min_profit_close_pct
                min_hold = cfg.strategy.min_hold_sec

                if raw_move >= min_profit:
                    await self._close_position("Signal Reversal ✅", price, ruby_ctx)
                elif hold_elapsed < min_hold:
                    logger.debug(
                        "%s Signal reversal BLOCKED — hold %.0fs < %.0fs",
                        self.tag,
                        hold_elapsed,
                        min_hold,
                    )
                    await asyncio.sleep(loop_sleep)
                    continue
                elif raw_move < -cfg.strategy.sl_pct * 0.8:
                    await self._close_position("Signal Reversal 🔄 (losing)", price, ruby_ctx)
                else:
                    _now_rev = time.time()
                    if _now_rev - self._last_reversal_held_log > 60:
                        logger.info(
                            "%s Signal reversal HELD — move %.4f%% (held %.0fs). Waiting for TP/SL.",
                            self.tag,
                            raw_move * 100,
                            hold_elapsed,
                        )
                        self._last_reversal_held_log = _now_rev
                    await asyncio.sleep(loop_sleep)
                    continue

            direction = self.stack["direction"]

            if direction == signal and self.stack["count"] >= max_stack:
                await asyncio.sleep(loop_sleep)
                continue

            is_add = direction == signal and self.stack["count"] > 0

            # ── Add-specific gates ────────────────────────────────
            if is_add:
                if not wave_gate_ok(ws=self.wave_state, direction=signal, gate=wave_gate):
                    await asyncio.sleep(loop_sleep)
                    continue
                if not regime_stack_ok(regime=regime, direction=signal):
                    await asyncio.sleep(loop_sleep)
                    continue
                if signal == "buy" and price >= avg * (1 - add_thresh):
                    await asyncio.sleep(loop_sleep)
                    continue
                if signal == "sell" and price <= avg * (1 + add_thresh):
                    await asyncio.sleep(loop_sleep)
                    continue

            # ── CNN inference ─────────────────────────────────────
            cnn_result = None
            if self._cnn is not None and self._cnn.enabled and cfg.ml.enabled:
                cnn_result = self._cnn.predict(
                    candles=candles,
                    imbalance=imbalance,
                    vol_pct=vol_pct,
                    wave_ratio=self.wave_state.wave_ratio,
                    fast_ema=fast_ema,
                    slow_ema=slow_ema,
                    fast_period=self.best_params["fast"],
                    slow_period=self.best_params["slow"],
                )
                self._cnn_signal = cnn_result.signal
                self._cnn_confidence = cnn_result.confidence

            # ── Execution gate chain ──────────────────────────────
            can_trade, risk_reason = self._risk_can_trade()
            _open_assets: list[str] = []
            if self._shared_positions is not None:
                _open_assets = [
                    k for k, v in self._shared_positions.items() if v and k != self.asset_key
                ]

            gate_verdict, gate_reason = await self._gate.evaluate(
                asset_key=self.asset_key,
                tag=self.tag,
                signal=signal,
                is_add=is_add,
                context={
                    "can_trade": can_trade,
                    "risk_reason": risk_reason,
                    "vol_pct": vol_pct,
                    "vol_entry_min": vol_entry_min,
                    "vol_entry_max": vol_entry_max,
                    "quality": quality,
                    "qual_min": qual_min,
                    "ao": ao,
                    "tp_pct": tp_pct,
                    "fee_taker": fees.get("taker_pct", 0.0006),
                    "fee_slip": fees.get("slippage_pct", 0.0001),
                    "cnn_result": cnn_result,
                    "cnn_enabled": self._cnn is not None and self._cnn.enabled and cfg.ml.enabled,
                    "min_confidence": cfg.ml.min_confidence,
                    "open_assets": _open_assets,
                },
            )

            if gate_verdict != GateVerdict.PASS:
                if gate_verdict == GateVerdict.BLOCK_RISK:
                    if not self.risk_state["_alerted"]:
                        logger.warning("%s RISK GATE: %s", self.tag, gate_reason)
                        self.risk_state["_alerted"] = True
                elif self.risk_state["_alerted"]:
                    self.risk_state["_alerted"] = False
                    logger.info("%s Risk conditions cleared — trading resumed", self.tag)
                await asyncio.sleep(loop_sleep)
                continue

            if self.risk_state["_alerted"]:
                self.risk_state["_alerted"] = False
                logger.info("%s Risk conditions cleared — trading resumed", self.tag)

            # ── Calculate size ────────────────────────────────────
            size = self._calc_size(price, vol_pct=vol_pct, regime=regime)

            if (
                self._cnn is not None
                and self._cnn.enabled
                and cfg.ml.enabled
                and cfg.ml.size_scale_by_confidence
                and self._cnn_confidence > 0
            ):
                lot_step = self.contract_spec.get("lot_step", 1.0)
                scaled = size * self._cnn_confidence
                size = (
                    max(int(scaled), 1)
                    if lot_step >= 1.0
                    else max(round(scaled / lot_step) * lot_step, lot_step)
                )

            # ── Place order ───────────────────────────────────────
            success = await self._place_order(signal, size, price)

            if success:
                if self._shared_positions is not None:
                    self._shared_positions[self.asset_key] = True

                if self.stack["count"] == 0:
                    self.stack["entry_time"] = now
                    if cfg.strategy.multi_tp_enabled and self._tp_levels:
                        atr_series = compute_atr(candles)
                        current_atr = (
                            float(atr_series.iloc[-1]) if len(atr_series) > 0 else price * 0.003
                        )
                        self._multi_tp = MultiTPManager(
                            entry_price=price,
                            direction=signal,
                            total_size=size,
                            atr=current_atr,
                            sl_pct=self.best_params["sl_pct"],
                            levels=self._tp_levels,
                        )

                self.stack["direction"] = signal
                self.stack["count"] += 1
                self.stack["prices"].append(price)
                self.stack["sizes"].append(size)

                if self._multi_tp is not None and self.stack["count"] > 1:
                    self._multi_tp.total_size = self._stack_total_size()
                    self._multi_tp.remaining_size = self._stack_total_size()
                    self._multi_tp.entry_price = self._stack_avg_price()

                avg_now = self._stack_avg_price()
                add_label = f"Add #{self.stack['count']}" if self.stack["count"] > 1 else "Entry #1"
                tp_target = avg_now * (1 + tp_pct if signal == "buy" else 1 - tp_pct)

                logger.info(
                    "%s %s %s %.1f@%s | avg=%s | tp_target=%s | "
                    "regime=%s qual=%.0f wr=%.2f(p%.0f%%) ao=%.4f tp=%.2f%%",
                    self.tag,
                    add_label,
                    signal,
                    size,
                    fmt_price(price),
                    fmt_price(avg_now),
                    fmt_price(tp_target),
                    regime,
                    quality,
                    self.wave_state.wave_ratio,
                    self.wave_state.wr_pct * 100,
                    ao,
                    tp_pct * 100,
                )

                if self.discord:
                    asyncio.create_task(
                        self.discord.trade_opened(
                            asset=self.asset.base,
                            direction="LONG" if signal == "buy" else "SHORT",
                            price=price,
                            size=size,
                            leverage=self._active_leverage,
                            confidence=self._cnn_confidence,
                        )
                    )

                await self.store.record_signal(
                    self.asset_key,
                    {
                        "side": signal,
                        "price": price,
                        "size": size,
                        "add_label": add_label,
                        "avg_entry": avg_now,
                        "tp_target": tp_target,
                        "tp_pct": tp_pct,
                        "sl_pct": sl_pct,
                        "regime": regime,
                        "quality": quality,
                        "ao": ao,
                        "vol_pct": vol_pct,
                        "imbalance": imbalance,
                        "wave_ratio": self.wave_state.wave_ratio,
                        "wr_pct": self.wave_state.wr_pct,
                        "bias": self.wave_state.bias,
                        "cur_ratio": self.wave_state.cur_ratio,
                        "stack_count": self.stack["count"],
                        "mode": "sim" if cfg.is_sim else "live",
                    },
                )
                await self.store.record_order(
                    self.asset_key,
                    {
                        "side": signal,
                        "size": size,
                        "price": price,
                        "type": "entry",
                        "add_label": add_label,
                        "timestamp": time.time(),
                    },
                )

            await asyncio.sleep(loop_sleep)

    # ══════════════════════════════════════════════════════════════
    # Main entry point
    # ══════════════════════════════════════════════════════════════

    async def run(self) -> None:
        """Start WebSocket feeds and enter the trading loop."""
        logger.info(
            "%s Starting worker for %s (%s) @ %dx leverage",
            self.tag,
            self.asset.symbol,
            self.asset.base,
            self.asset.leverage,
        )

        if self.config.ml.enabled:
            try:
                from ml.inference import CNNInference

                self._cnn = CNNInference.load(
                    asset_key=self.asset_key,
                    models_dir=self.config.ml.models_dir,
                    min_confidence=self.config.ml.min_confidence,
                )
            except Exception as exc:
                logger.warning(
                    "%s CNN load error (non-fatal — running without CNN): %s", self.tag, exc
                )
                self._cnn = None

        if self.config.is_live:
            try:
                await self.exchange.set_leverage(self.asset.leverage, self.asset.symbol)
                logger.info(
                    "%s Leverage set to %dx for %s",
                    self.tag,
                    self.asset.leverage,
                    self.asset.symbol,
                )
            except Exception as exc:
                exc_msg = str(exc)
                if "marginMode" in exc_msg or "already" in exc_msg.lower():
                    logger.debug("%s Leverage note (non-fatal): %s", self.tag, exc_msg)
                else:
                    logger.warning("%s Leverage setup issue: %s", self.tag, exc)

            await self._recover_position()

        trade_task = asyncio.create_task(self._handle_trades(), name=f"ws-trades-{self.asset_key}")
        book_task = asyncio.create_task(self._handle_orderbook(), name=f"ws-book-{self.asset_key}")

        try:
            await self._trading_loop()
        except asyncio.CancelledError:
            logger.info("%s Worker cancelled — shutting down", self.tag)
        except Exception as exc:
            logger.exception("%s Worker crashed: %s", self.tag, exc)
        finally:
            trade_task.cancel()
            book_task.cancel()
            for task in (trade_task, book_task):
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            logger.info("%s Worker stopped", self.tag)
