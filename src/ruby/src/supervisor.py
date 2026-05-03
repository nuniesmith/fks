"""
supervisor.py
=============
Multi-asset supervisor — loads config, initialises shared services,
spawns per-asset workers, runs the web dashboard, and monitors the
portfolio-level risk circuit breakers.

Entry point: main()  (called from src/main.py)
"""

from __future__ import annotations

import asyncio
import os
import signal
import time

import ccxt.pro as ccxt
import optuna
import uvicorn

from services.config_loader import load_config
from services.correlation_guard import CorrelationGuard
from services.discord_notify import DiscordNotifier
from services.redis_store import RedisStore
from services.report_generator import ReportGenerator
from services.task_runner import TaskRunner
from utils.indicators import build_candles
from utils.logging_config import get_logger, setup_logging
from utils.optimizer import OPTUNA_POOL
from utils.system_monitor import MaintenanceChecker, MemoryMonitor
from workers.asset_worker import AssetWorker

optuna.logging.set_verbosity(optuna.logging.WARNING)

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Exchange helpers
# ═══════════════════════════════════════════════════════════════════


async def _fetch_exchange_balance(exchange) -> float | None:
    """Fetch the USDT balance from KuCoin Futures account.

    Returns the total USDT balance, or None if the fetch fails.
    """
    try:
        balance = await exchange.fetch_balance()
        usdt = balance.get("USDT", {})
        total = usdt.get("total")
        if total is not None:
            return float(total)
        # Fallback: some ccxt versions nest under balance['total']['USDT']
        total_map = balance.get("total", {})
        if "USDT" in total_map and total_map["USDT"] is not None:
            return float(total_map["USDT"])
        logger.warning("Could not parse USDT balance from exchange response")
        return None
    except Exception as exc:
        logger.warning("Failed to fetch exchange balance: %s", exc)
        return None


def _build_exchange(config) -> ccxt.kucoinfutures:
    """Construct a fresh KuCoin Futures ccxt instance from config credentials."""
    return ccxt.kucoinfutures(
        {
            "apiKey": config.exchange.credentials.api_key,
            "secret": config.exchange.credentials.api_secret,
            "password": config.exchange.credentials.passphrase,
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        }
    )


# ═══════════════════════════════════════════════════════════════════
# Contract spec helpers
# ═══════════════════════════════════════════════════════════════════


def _build_contract_specs(config, exchange) -> dict[str, dict]:
    """Build per-asset contract specifications from exchange market data.

    ccxt keys markets by unified symbol (e.g. "BTC/USDT:USDT") but our
    config uses the exchange-native ID (e.g. "XBTUSDTM").  We index by
    native ID so lookups are O(1).
    """
    markets_by_id: dict = {}
    for _mkt_key, _mkt_val in getattr(exchange, "markets", {}).items():
        eid = _mkt_val.get("id")
        if eid:
            markets_by_id[eid] = _mkt_val

    contract_specs: dict[str, dict] = {}
    for name, asset in config.enabled_assets.items():
        spec: dict = {
            "contract_size": 1.0,
            "lot_step": 1.0,
            "max_lots": 1_000_000,
            "precision_amount": 0,
        }
        if asset.symbol in markets_by_id:
            mkt = markets_by_id[asset.symbol]

            cs = mkt.get("contractSize")
            if cs is not None and float(cs) > 0:
                spec["contract_size"] = float(cs)

            limits = mkt.get("limits", {})
            amount_limits = limits.get("amount", {})
            if amount_limits.get("min") is not None:
                spec["lot_step"] = float(amount_limits["min"])
            if amount_limits.get("max") is not None:
                spec["max_lots"] = float(amount_limits["max"])

            precision = mkt.get("precision", {})
            if precision.get("amount") is not None:
                spec["precision_amount"] = int(precision["amount"])

            logger.info(
                "  %-10s %s  contract=%.6f %s  lot_step=%s  max=%s",
                name,
                asset.symbol,
                spec["contract_size"],
                asset.base,
                spec["lot_step"],
                spec["max_lots"],
            )
        else:
            logger.warning(
                "  %-10s %s  NOT FOUND in exchange markets — using defaults",
                name,
                asset.symbol,
            )

        contract_specs[name] = spec

    return contract_specs


# ═══════════════════════════════════════════════════════════════════
# Main supervisor entry point
# ═══════════════════════════════════════════════════════════════════


async def main() -> None:
    """Load config, start all services, run the supervisor loop."""
    setup_logging()
    config = load_config()

    # ── Redis ─────────────────────────────────────────────────────
    store = RedisStore(
        redis_url=config.redis_url,
        password=config.redis_password or None,
        prefix=config.redis.key_prefix,
    )
    await store.connect()

    # ── Discord notifier ──────────────────────────────────────────
    discord = DiscordNotifier(config.discord, sim_mode=config.is_sim)

    # ── Exchange (shared across all workers) ──────────────────────
    exchange = _build_exchange(config)

    try:
        await exchange.load_markets()
        logger.info("Loaded %d markets from KuCoin Futures", len(exchange.markets))
    except Exception as exc:
        logger.warning("Could not load markets: %s (will use defaults)", exc)

    contract_specs = _build_contract_specs(config, exchange)

    # ── Sync capital with real exchange balance (live mode) ───────
    config_capital = config.capital.balance_usdt
    if config.is_live:
        real_balance = await _fetch_exchange_balance(exchange)
        if real_balance is not None:
            config.capital.balance_usdt = real_balance
            logger.info("Live balance from KuCoin: $%.2f USDT", real_balance)
        else:
            logger.warning(
                "Could not fetch live balance — falling back to config capital $%.2f",
                config_capital,
            )
    else:
        logger.info("Sim mode — using config capital $%.2f", config_capital)

    logger.info("=" * 60)
    logger.info("  Futures Multi-Asset Trader")
    logger.info("  Mode: %s", "SIMULATION" if config.is_sim else "LIVE")
    logger.info("  Assets: %d enabled", len(config.enabled_assets))
    for name, asset in config.enabled_assets.items():
        logger.info(
            "    %-10s %s  lev=%dx  margin=%.0f%%",
            name,
            asset.symbol,
            asset.leverage,
            asset.margin_pct * 100,
        )

    asyncio.create_task(
        discord.startup(
            mode="sim" if config.is_sim else "live",
            assets=[a.base for a in config.enabled_assets.values()],
            capital=config.capital.balance_usdt,
        )
    )

    # ── Shutdown coordination ─────────────────────────────────────
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_event.set)

    # ── Clear stale heartbeats for disabled assets ────────────────
    try:
        existing_heartbeats = await store.get_heartbeats()
        for asset_key in existing_heartbeats:
            if asset_key not in config.enabled_assets:
                await store.clear_heartbeat(asset_key)
                logger.info("Cleared stale heartbeat for disabled asset: %s", asset_key)
    except Exception as exc:
        logger.debug("Could not clear stale heartbeats: %s", exc)

    # ── Correlation guard (shared singleton) ──────────────────────
    cg_cfg = config.risk.correlation_guard
    shared_correlation_guard: CorrelationGuard | None = None
    shared_positions: dict[str, bool] = {}
    if cg_cfg.enabled:
        shared_correlation_guard = CorrelationGuard(
            window=cg_cfg.window,
            max_correlated=cg_cfg.max_correlated_positions,
            corr_threshold=cg_cfg.correlation_threshold,
        )
        shared_positions = {k: False for k in config.enabled_assets}
        logger.info(
            "Correlation guard enabled: window=%d  max_correlated=%d  threshold=%.2f",
            cg_cfg.window,
            cg_cfg.max_correlated_positions,
            cg_cfg.correlation_threshold,
        )

    # ── Spawn one worker per enabled asset ────────────────────────
    worker_tasks: list[asyncio.Task] = []
    worker_instances: list[AssetWorker] = []

    for name, asset in config.enabled_assets.items():
        worker = AssetWorker(
            asset,
            config,
            exchange,
            store,
            shutdown_event,
            contract_spec=contract_specs.get(name),
            discord=discord,
            correlation_guard=shared_correlation_guard,
            shared_positions=shared_positions if shared_correlation_guard else None,
        )
        worker_instances.append(worker)
        task = asyncio.create_task(worker.run(), name=f"worker-{name}")
        worker_tasks.append(task)
        logger.info(
            "  Spawned worker: %s (%s) @ %dx leverage, margin=%.0f%%",
            name,
            asset.symbol,
            asset.leverage,
            asset.margin_pct * 100,
        )

    # ── Task runner (needs worker_instances populated first) ──────
    task_runner = TaskRunner(
        worker_instances=worker_instances,
        store=store,
        config=config,
        max_concurrent=2,
    )

    # ── Report generator ──────────────────────────────────────────
    report_gen = ReportGenerator(redis_store=store, discord=discord)
    report_task = asyncio.create_task(
        report_gen.run_scheduled(),
        name="report-scheduler",
    )
    logger.info("  Spawned report scheduler")

    # ── Web dashboard (embedded uvicorn) ──────────────────────────
    from web.app import create_app

    web_port = int(os.getenv("WEB_PORT", "8080"))
    web_app = create_app(store=store, config=config, task_runner=task_runner)

    uvi_config = uvicorn.Config(
        web_app,
        host="0.0.0.0",
        port=web_port,
        log_level="warning",
        access_log=False,
    )
    uvi_server = uvicorn.Server(uvi_config)
    web_task = asyncio.create_task(
        uvi_server.serve(),
        name="web-dashboard",
    )
    logger.info("  Spawned web dashboard on port %d", web_port)

    # ── System monitors ───────────────────────────────────────────
    mem_monitor = MemoryMonitor(alert_threshold_mb=1024, discord=discord)
    maint_checker = MaintenanceChecker(exchange=exchange, discord=discord)

    # ── MasterCNN — loaded once, pushed to worker flags each cycle ─
    _master_cnn = None
    _last_master_check: float = 0.0
    if config.ml.enabled:
        try:
            from ml.inference import MasterInference

            _master_cnn = MasterInference.load(
                models_dir=config.ml.models_dir,
                n_assets=len(worker_instances),
                risk_threshold=config.ml.master_risk_threshold,
            )
        except Exception as exc:
            logger.warning("MasterCNN load error (non-fatal): %s", exc)
            _master_cnn = None

    # ── Supervisor loop state ─────────────────────────────────────
    worker_timeout = config.monitoring.worker_timeout_sec
    summary_interval = config.monitoring.summary_interval_sec
    last_summary = time.time()
    _portfolio_last_state: bool = False
    _start_time = time.time()
    _last_session_recycle = time.time()
    session_recycle_sec = config.exchange.session_recycle_sec

    # ═══════════════════════════════════════════════════════════════
    # Supervisor loop
    # ═══════════════════════════════════════════════════════════════
    try:
        while not shutdown_event.is_set():
            now = time.time()

            # ── Restart crashed workers ───────────────────────────
            for i, task in enumerate(worker_tasks):
                if task.done() and not task.cancelled():
                    exc = task.exception()
                    if exc:
                        name = task.get_name()
                        logger.error("Worker %s crashed: %s — restarting", name, exc)
                        asyncio.create_task(
                            discord.worker_restart(
                                asset=name.replace("worker-", ""), reason=str(exc)
                            )
                        )
                        w = worker_instances[i]
                        worker_tasks[i] = asyncio.create_task(w.run(), name=name)

            # ── Stale heartbeat check ─────────────────────────────
            try:
                heartbeats = await store.get_heartbeats()
                for asset_key, hb in heartbeats.items():
                    last_seen = hb.get("last_seen", 0)
                    age = now - last_seen
                    if age > worker_timeout:
                        logger.warning(
                            "Worker %s heartbeat stale (%.0fs ago, timeout=%ds)",
                            asset_key,
                            age,
                            worker_timeout,
                        )
            except Exception as exc:
                logger.debug("Heartbeat check error: %s", exc)

            # ── Portfolio unrealized loss circuit breaker ─────────
            try:
                breaker_pct = config.risk.portfolio_max_unrealized_loss_pct
                balance = config.capital.balance_usdt
                threshold_usdt = -balance * breaker_pct
                total_unrealized = sum(w._unrealized_pnl_usdt() for w in worker_instances)
                breaker_active = total_unrealized < threshold_usdt

                for w in worker_instances:
                    w._portfolio_halted = breaker_active

                if breaker_active and not _portfolio_last_state:
                    logger.warning(
                        "🔴 Portfolio circuit breaker TRIPPED — "
                        "unrealized: $%.4f | threshold: $%.4f (%.1f%% of $%.2f) "
                        "— new entries halted on all %d workers",
                        total_unrealized,
                        threshold_usdt,
                        breaker_pct * 100,
                        balance,
                        len(worker_instances),
                    )
                    asyncio.create_task(
                        discord.risk_alert(
                            alert_type="Portfolio Circuit Breaker",
                            message=(
                                f"Unrealized loss ${total_unrealized:.4f} exceeded "
                                f"threshold ${threshold_usdt:.4f}"
                            ),
                            details={
                                "Unrealized": f"${total_unrealized:.4f}",
                                "Threshold": f"${threshold_usdt:.4f}",
                                "Workers Halted": str(len(worker_instances)),
                            },
                        )
                    )
                elif not breaker_active and _portfolio_last_state:
                    logger.info(
                        "🟢 Portfolio circuit breaker CLEARED — "
                        "unrealized: $%.4f (threshold: $%.4f)",
                        total_unrealized,
                        threshold_usdt,
                    )
                _portfolio_last_state = breaker_active
            except Exception as exc:
                logger.debug("Portfolio breaker check error: %s", exc)

            # ── Portfolio margin cap ──────────────────────────────
            try:
                balance = config.capital.balance_usdt
                if balance > 0:
                    total_margin = sum(w._estimated_margin_usdt() for w in worker_instances)
                    margin_pct = total_margin / balance
                    over_margin = margin_pct > config.risk.max_portfolio_margin_pct
                    for w in worker_instances:
                        w._portfolio_over_margin = over_margin
                    if over_margin:
                        logger.warning(
                            "⚠️  Margin cap: %.1f%% of $%.2f in use (limit %.0f%%) "
                            "— new entries halted",
                            margin_pct * 100,
                            balance,
                            config.risk.max_portfolio_margin_pct * 100,
                        )
                        asyncio.create_task(
                            discord.risk_alert(
                                alert_type="Margin Cap",
                                message=(
                                    f"Portfolio margin {margin_pct * 100:.1f}% exceeds "
                                    f"{config.risk.max_portfolio_margin_pct * 100:.0f}% limit"
                                ),
                                details={
                                    "Margin Used": f"{margin_pct * 100:.1f}%",
                                    "Limit": f"{config.risk.max_portfolio_margin_pct * 100:.0f}%",
                                    "Total Margin": f"${total_margin:.2f}",
                                },
                            )
                        )
            except Exception as exc:
                logger.debug("Margin cap check error: %s", exc)

            # ── Exchange session recycling ─────────────────────────
            if now - _last_session_recycle > session_recycle_sec:
                age_sec = now - _last_session_recycle
                logger.info(
                    "♻️  Recycling exchange session (age: %dh %dm)",
                    int(age_sec // 3600),
                    int((age_sec % 3600) // 60),
                )
                old_exchange = exchange
                try:
                    await old_exchange.close()
                    await asyncio.sleep(0.5)

                    exchange = _build_exchange(config)
                    await exchange.load_markets()

                    for w in worker_instances:
                        w.exchange = exchange
                    maint_checker._exchange = exchange

                    logger.info(
                        "♻️  Exchange session recycled (%d markets, %d workers updated)",
                        len(exchange.markets),
                        len(worker_instances),
                    )
                except Exception as exc:
                    logger.warning(
                        "⚠️  Exchange session recycle failed: %s — continuing with existing session",
                        exc,
                    )
                    # If a new exchange was created but load_markets failed, still
                    # hand it to workers so the old closed one isn't used.
                    if exchange is not old_exchange:
                        for w in worker_instances:
                            w.exchange = exchange
                finally:
                    _last_session_recycle = now  # avoid retry storm

            # ── Memory monitoring ─────────────────────────────────
            try:
                mem_mb = await mem_monitor.check()
                if mem_mb > 0:
                    logger.debug("RSS memory: %.0f MB", mem_mb)
            except Exception as exc:
                logger.debug("Memory monitor error: %s", exc)

            # ── Exchange maintenance window check ─────────────────
            try:
                await maint_checker.check(worker_instances)
            except Exception as exc:
                logger.debug("Maintenance checker error: %s", exc)

            # ── MasterCNN portfolio risk check ────────────────────
            if (
                config.ml.enabled
                and _master_cnn is not None
                and now - _last_master_check > config.ml.master_check_interval_sec
            ):
                _last_master_check = now
                try:
                    from ml.features import extract_features

                    asset_feature_arrays = []
                    for w in worker_instances:
                        feat = None
                        try:
                            w_candles = build_candles(w.trades, w.config.candles.min_ticks)
                            feat = extract_features(
                                candles=w_candles,
                                imbalance=1.0,
                                vol_pct=0.5,
                                wave_ratio=w.wave_state.wave_ratio,
                                fast_period=w.best_params["fast"],
                                slow_period=w.best_params["slow"],
                            )
                        except Exception:
                            pass
                        asset_feature_arrays.append(feat)

                    master_result = _master_cnn.portfolio_risk(asset_feature_arrays)

                    for w in worker_instances:
                        w._master_risk_score = master_result.risk_score
                        w._master_halted = master_result.should_halt

                    if master_result.enabled and master_result.should_halt:
                        logger.warning(
                            "🧠 MasterCNN risk=%.3f > %.2f — new entries halted on all workers",
                            master_result.risk_score,
                            config.ml.master_risk_threshold,
                        )
                        asyncio.create_task(
                            discord.risk_alert(
                                alert_type="MasterCNN Risk Gate",
                                message=(
                                    f"Portfolio risk score {master_result.risk_score:.3f} "
                                    f"exceeds threshold {config.ml.master_risk_threshold:.2f}"
                                ),
                                details={
                                    "Risk Score": f"{master_result.risk_score:.3f}",
                                    "Threshold": f"{config.ml.master_risk_threshold:.2f}",
                                },
                            )
                        )
                except Exception as exc:
                    logger.debug("MasterCNN check error: %s", exc)

            # ── Publish supervisor status to Redis ────────────────
            try:
                await store.set_bot_status(
                    {
                        "running": True,
                        "mode": "sim" if config.is_sim else "live",
                        "workers": len(worker_tasks),
                        "workers_alive": sum(1 for t in worker_tasks if not t.done()),
                        "capital": config.capital.balance_usdt,
                        "uptime": now - _start_time,
                        "timestamp": now,
                    }
                )
            except Exception as exc:
                logger.debug("Status publish error: %s", exc)

            # ── Poll worker control commands from web UI ──────────
            for i, (name, _asset) in enumerate(config.enabled_assets.items()):
                try:
                    action = await store.get_worker_action(name)
                    if action is None:
                        continue
                    cmd = action.get("action", "")
                    if cmd == "stop":
                        task = worker_tasks[i]
                        if not task.done():
                            task.cancel()
                            logger.info("⏹ Worker %s stopped via web UI", name)
                    elif cmd == "restart":
                        task = worker_tasks[i]
                        if not task.done():
                            task.cancel()
                            try:
                                await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
                            except (asyncio.CancelledError, asyncio.TimeoutError):
                                pass
                        w = worker_instances[i]
                        worker_tasks[i] = asyncio.create_task(w.run(), name=f"worker-{name}")
                        logger.info("🔄 Worker %s restarted via web UI", name)
                    elif cmd == "start":
                        task = worker_tasks[i]
                        if task.done():
                            w = worker_instances[i]
                            worker_tasks[i] = asyncio.create_task(w.run(), name=f"worker-{name}")
                            logger.info("▶ Worker %s started via web UI", name)
                except Exception as exc:
                    logger.debug("Control poll error for %s: %s", name, exc)

            # ── Portfolio summary log ─────────────────────────────
            if now - last_summary > summary_interval:
                try:
                    total_daily = await store.get_daily_pnl()
                    logger.info(
                        "── Portfolio Summary ── Daily PnL: $%.4f | Workers: %d running | Mode: %s",
                        total_daily,
                        sum(1 for t in worker_tasks if not t.done()),
                        "SIM" if config.is_sim else "LIVE",
                    )
                    for name in config.enabled_assets:
                        asset_pnl = await store.get_daily_pnl(asset=name)
                        if asset_pnl != 0:
                            logger.info("  %-10s daily PnL: $%.4f", name, asset_pnl)
                except Exception as exc:
                    logger.debug("Summary error: %s", exc)
                last_summary = now

            # ── Sleep until next check ────────────────────────────
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=min(config.monitoring.heartbeat_interval_sec, 30),
                )
            except TimeoutError:
                pass

    except asyncio.CancelledError:
        pass

    # ═══════════════════════════════════════════════════════════════
    # Graceful shutdown
    # ═══════════════════════════════════════════════════════════════
    finally:
        logger.info("Shutdown signal received — stopping all workers...")

        shutdown_event.set()

        # Close exchange first — tears down WS connections before task
        # cancellation so ccxt doesn't raise NetworkError on orphaned futures.
        try:
            await exchange.close()
        except Exception:
            pass

        await asyncio.sleep(0.2)

        for task in worker_tasks:
            task.cancel()

        report_task.cancel()

        uvi_server.should_exit = True
        web_task.cancel()

        # Shut down background task runner thread pool
        task_runner.shutdown()

        all_tasks = worker_tasks + [report_task, web_task]
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        for task, result in zip(all_tasks, results):
            if result is None or isinstance(result, asyncio.CancelledError):
                continue
            if isinstance(result, Exception):
                err_name = type(result).__name__
                if "NetworkError" in err_name or "ConnectionClosed" in err_name:
                    continue
                logger.warning(
                    "Unexpected error during shutdown of %s: %s",
                    task.get_name(),
                    result,
                )

        try:
            await store.close()
        except Exception:
            pass

        try:
            await discord.close()
        except Exception:
            pass

        OPTUNA_POOL.shutdown(wait=False)

        logger.info("=" * 60)
        logger.info("  Shutdown complete")
        logger.info("=" * 60)
