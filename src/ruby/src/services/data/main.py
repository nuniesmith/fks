"""
Ruby — Data Service
============================
Standalone FastAPI microservice that handles all market data, caching,
REST API, and HTMX dashboard rendering.

Architecture:
    Browser → Web (8080) → Data Service (8000) → Redis / Postgres / Massive / Kraken
                                                ↑
                                         Engine (8100) publishes focus/risk to Redis

Responsibilities:
  - REST + SSE API for the dashboard (GET /, /api/focus, /sse/dashboard, …)
  - Bar cache management (Postgres + Redis, gap-fill via Massive / Kraken)
  - Kraken WebSocket live crypto feed
  - Grok AI analyst streaming
  - Trade journal, positions, risk state reads
  - All HTMX fragment endpoints

The Data Service is STATELESS with respect to computation — it reads engine
output from Redis and never runs the DashboardEngine or engine scheduler.
The Engine service (lib.services.engine.main) runs in its own container and
publishes computed focus / risk / ORB state to Redis for the Data Service to
serve.

Usage (from project root):
    PYTHONPATH=src uvicorn lib.services.data.main:app --host 0.0.0.0 --port 8000

Docker:
    ENV PYTHONPATH="/app/src"
    CMD ["uvicorn", "lib.services.data.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

import asyncio
import json
import math
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# All imports use fully-qualified `lib.*` paths.
# PYTHONPATH only needs /app/src so that `lib` is discoverable.
# ---------------------------------------------------------------------------
from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.middleware.gzip import GZipMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402


# ---------------------------------------------------------------------------
# Custom JSON encoder that replaces inf / NaN with null instead of crashing.
# Backtesting and optimization routines can produce inf Sharpe ratios or
# NaN win-rates, which the stdlib json encoder rejects.
# ---------------------------------------------------------------------------
class _SafeFloatEncoder(json.JSONEncoder):
    """JSON encoder that converts inf/-inf/NaN to None."""

    def default(self, o: Any) -> Any:
        return super().default(o)

    def encode(self, o: Any) -> str:
        return super().encode(_sanitize(o))


def _sanitize(obj: Any) -> Any:
    """Recursively replace non-finite floats with None."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


class SafeJSONResponse(JSONResponse):
    """JSONResponse subclass that handles inf/NaN floats gracefully."""

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            cls=_SafeFloatEncoder,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")


# ---------------------------------------------------------------------------
# Logging — structured via structlog
# ---------------------------------------------------------------------------
from core.logging_config import (  # noqa: E402  # pylint: disable=wrong-import-position
    get_logger,
    setup_logging,
)

setup_logging(service="data-service")
logger = get_logger("data_service")

# ---------------------------------------------------------------------------
# Import routers — these live under src/services/data/api/
# Bare imports like `from cache import ...` resolve via PYTHONPATH (/app/src).
# ---------------------------------------------------------------------------
from core.models import init_db  # noqa: E402
from services.data.api.actions import (  # noqa: E402
    router as actions_router,
)
from services.data.api.actions import (  # noqa: E402
    set_engine as actions_set_engine,
)
from services.data.api.analysis import (  # noqa: E402
    router as analysis_router,
)
from services.data.api.analysis import (  # noqa: E402
    set_engine as analysis_set_engine,
)
from services.data.api.analysis_tools import router as analysis_tools_router  # noqa: E402
from services.data.api.audit import router as audit_router  # noqa: E402
from services.data.api.auth import require_api_key  # noqa: E402
from services.data.api.backup import auto_backup_task  # noqa: E402
from services.data.api.backup import html_router as backup_html_router  # noqa: E402
from services.data.api.backup import router as backup_router  # noqa: E402
from services.data.api.bars import (  # noqa: E402
    router as bars_router,
)
from services.data.api.bars import (  # noqa: E402
    startup_warm_caches,
)
from services.data.api.charting_proxy import router as charting_proxy_router  # noqa: E402
from services.data.api.chat import router as chat_router  # noqa: E402
from services.data.api.chat import set_engine as chat_set_engine  # noqa: E402
from services.data.api.cnn import router as cnn_router  # noqa: E402
from services.data.api.dashboard import (  # noqa: E402
    router as dashboard_router,
)
from services.data.api.docs_viewer import router as docs_viewer_router  # noqa: E402
from services.data.api.execution_gate_routes import (  # noqa: E402
    router as execution_gate_router,
)
from services.data.api.grok import router as grok_router  # noqa: E402
from services.data.api.grok import set_engine as grok_set_engine  # noqa: E402
from services.data.api.health import (  # noqa: E402
    router as health_router,
)
from services.data.api.journal import (  # noqa: E402
    router as journal_router,
)
from services.data.api.kraken import router as kraken_router  # noqa: E402
from services.data.api.live_risk import (  # noqa: E402
    router as live_risk_router,
)
from services.data.api.market_data import (  # noqa: E402
    router as market_data_router,
)
from services.data.api.metrics import PrometheusMiddleware  # noqa: E402
from services.data.api.metrics import (  # noqa: E402
    router as metrics_router,
)
from services.data.api.news import router as news_router  # noqa: E402
from services.data.api.pipeline import (  # noqa: E402
    router as pipeline_router,
)
from services.data.api.posint import router as posint_router  # noqa: E402
from services.data.api.positions import (  # noqa: E402
    router as positions_router,
)
from services.data.api.rate_limit import (  # noqa: E402
    setup_rate_limiting,
)
from services.data.api.reddit import router as reddit_router  # noqa: E402
from services.data.api.risk import router as risk_router  # noqa: E402
from services.data.api.settings import (  # noqa: E402
    router as settings_router,
)
from services.data.api.simulation_api import (  # noqa: E402
    router as sim_router,
)
from services.data.api.simulation_api import (  # noqa: E402
    sse_router as sim_sse_router,
)
from services.data.api.sse import router as sse_router  # noqa: E402
from services.data.api.sweep import router as sweep_router  # noqa: E402
from services.data.api.swing_actions import (  # noqa: E402
    router as swing_actions_router,
)
from services.data.api.tasks import router as tasks_router  # noqa: E402
from services.data.api.trades import (  # noqa: E402
    router as trades_router,
)
from services.data.api.trainer import (  # noqa: E402
    router as trainer_router,
)
from services.data.sync import (  # noqa: E402
    DataSyncService,
    get_sync_service,
    sync_router,
)

# ---------------------------------------------------------------------------
# Engine mode — always "remote" when running as standalone data service.
# The data service NEVER embeds the engine; it reads published state from Redis.
# ENGINE_MODE=embedded is retained only for local dev / smoke-testing without
# a separate engine container.
# ---------------------------------------------------------------------------
_ENGINE_MODE = os.getenv("ENGINE_MODE", "remote")  # default: remote (separate engine)

_engine: Any = None


class _RemoteEngineProxy:
    """Lightweight proxy that reads engine state from Redis.

    When the engine runs in a separate container, it publishes status,
    backtest results, and strategy history to Redis keys.  This proxy
    reads those keys so the API routers work without modification.
    """

    def __init__(self):
        self.interval = os.getenv("ENGINE_INTERVAL", "5m")
        self.period = os.getenv("ENGINE_PERIOD", "5d")

    def _redis_get_json(self, key: str, default: Any = None) -> Any:
        try:
            from core.cache import cache_get  # noqa: E402

            raw = cache_get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return default

    def get_status(self) -> dict[str, Any]:
        return self._redis_get_json(
            "engine:status",
            {
                "engine": "remote",
                "data_refresh": {"last": None, "status": "unknown"},
                "optimization": {"last": None, "status": "unknown"},
                "backtest": {"last": None, "status": "unknown"},
                "live_feed": {"status": "unknown"},
            },
        )

    def get_backtest_results(self) -> list[Any]:
        return self._redis_get_json("engine:backtest_results", [])

    def get_strategy_history(self) -> dict[str, Any]:
        return self._redis_get_json("engine:strategy_history", {})

    def get_live_feed_status(self) -> dict[str, Any]:
        return self._redis_get_json(
            "engine:live_feed_status",
            {
                "status": "unknown",
                "connected": False,
                "data_source": "unknown",
            },
        )

    def force_refresh(self) -> None:
        try:
            from core.cache import flush_all

            flush_all()
        except Exception:
            pass

    def start_live_feed(self) -> bool:
        return False

    async def stop_live_feed(self) -> None:
        pass

    def upgrade_live_feed(self) -> None:
        pass

    def downgrade_live_feed(self) -> None:
        pass

    def update_settings(self, **kwargs) -> None:
        pass

    async def stop(self) -> None:
        pass


def get_current_engine():
    """Return the running engine instance (or remote proxy). Used by health router."""
    global _engine
    if _engine is None:
        raise RuntimeError("Engine not initialised — service is still starting up")
    return _engine


# ---------------------------------------------------------------------------
# Lifespan helpers — each initialises or tears down one subsystem.
# Defined as module-private functions above the ``lifespan()`` orchestrator.
# ---------------------------------------------------------------------------


async def _init_database(app: FastAPI) -> None:
    """Step 1 + 1b: Initialise the database and bootstrap API-key tables."""
    # 1. Initialise the database
    try:
        init_db()
        logger.info(
            "Database initialised (DB_PATH=%s)",
            os.getenv("DB_PATH", "futures_journal.db"),
        )
    except Exception as exc:
        logger.error("Database init failed: %s", exc)

    # 1b. Bootstrap api_keys + api_key_audit tables (idempotent, non-fatal)
    try:
        from core.key_manager import ensure_tables_exist

        ensure_tables_exist()
    except Exception as exc:
        logger.warning("api_keys table bootstrap failed (non-fatal): %s", exc)


async def _start_engine(app: FastAPI) -> None:
    """Steps 2-3: Read configuration and start engine (embedded) or proxy (remote)."""
    global _engine

    # 2. Read configuration from environment
    account_size = int(os.getenv("ACCOUNT_SIZE", os.getenv("DEFAULT_ACCOUNT_SIZE", "150000")))
    interval = os.getenv("ENGINE_INTERVAL", os.getenv("DEFAULT_INTERVAL", "5m"))
    period = os.getenv("ENGINE_PERIOD", os.getenv("DEFAULT_PERIOD", "5d"))

    # 3. Start engine (embedded) or connect proxy (remote)
    if _ENGINE_MODE == "remote":
        _engine = _RemoteEngineProxy()
        logger.info("Using remote engine proxy (reads from Redis)")
    else:
        from trading.engine import get_engine

        _engine = get_engine(
            account_size=account_size,
            interval=interval,
            period=period,
        )
        logger.info(
            "Embedded engine started: account=$%s  interval=%s  period=%s",
            f"{account_size:,}",
            interval,
            period,
        )

    app.state.engine = _engine


async def _start_redis(app: FastAPI) -> None:
    """Step 4: Initialise async Redis client and attach to app.state."""
    try:
        import redis.asyncio as _aioredis_state

        _redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _async_redis_client = _aioredis_state.from_url(_redis_url, decode_responses=False)
        app.state.redis = _async_redis_client
        logger.info("app.state.redis initialised (async, url=%s)", _redis_url.split("@")[-1])
    except Exception as exc:
        app.state.redis = None
        logger.warning("app.state.redis setup failed (non-fatal): %s", exc)


async def _inject_engine_into_routers(app: FastAPI) -> None:
    """Step 4b: Inject engine into routers that need it."""
    analysis_set_engine(_engine)
    actions_set_engine(_engine)
    grok_set_engine(_engine)
    chat_set_engine(_engine)


async def _start_reddit_watcher(app: FastAPI) -> None:
    """Step 4c: Start Reddit watcher + aggregation job (non-fatal if credentials missing)."""
    try:
        from analysis.sentiment.reddit_sentiment import get_full_snapshot as _reddit_snapshot
        from integrations.reddit_watcher import RedditWatcher

        _reddit_watcher = RedditWatcher(
            redis=app.state.redis,
            pg_pool=getattr(app.state, "pg_pool", None),
            mode=os.getenv("REDDIT_MODE", "poll"),
        )
        asyncio.create_task(_reddit_watcher.run())

        async def _reddit_aggregation_job():
            while True:
                try:
                    await _reddit_snapshot(app.state.redis)
                except Exception as exc:
                    logger.warning("Reddit aggregation error: %s", exc)
                await asyncio.sleep(300)

        asyncio.create_task(_reddit_aggregation_job())
        logger.info("Reddit watcher + aggregation job started")
    except Exception as exc:
        logger.warning("Reddit watcher startup skipped (non-fatal): %s", exc)


async def _start_live_risk_publisher(app: FastAPI) -> None:
    """Step 4c: Wire LiveRiskPublisher into the live_risk API module.

    In embedded mode the standalone engine loop (main.py) is NOT running,
    so we create a LiveRiskPublisher here that the /api/live-risk/refresh
    endpoint and the HTMX polling strip can use.
    In remote mode there is no local RiskManager/PositionManager — the
    live_risk API falls back to reading from Redis (published by the
    separate engine container).
    """
    if _ENGINE_MODE == "remote":
        return
    try:
        from services.data.api.live_risk import set_publisher as lr_set_publisher
        from services.engine.live_risk import LiveRiskPublisher

        # Try to get RiskManager and PositionManager from the engine
        _rm = getattr(_engine, "risk_manager", None) if _engine else None
        _pm = getattr(_engine, "position_manager", None) if _engine else None

        _live_risk_publisher = LiveRiskPublisher(
            risk_manager=_rm,
            position_manager=_pm,
            interval_seconds=5.0,
        )
        lr_set_publisher(_live_risk_publisher)

        # Force an initial publish so the dashboard risk strip has data
        # immediately on first load.
        _live_risk_publisher.force_publish()
        logger.info(
            "LiveRiskPublisher wired into data-service (rm=%s, pm=%s)",
            "yes" if _rm else "no",
            "yes" if _pm else "no",
        )
    except Exception as exc:
        logger.warning("LiveRiskPublisher setup failed (non-fatal): %s", exc)


async def _log_data_source(app: FastAPI) -> None:
    """Step 5: Log the primary data source."""
    try:
        from core.cache import get_data_source

        ds = get_data_source()
        logger.info("Primary data source: %s", ds)
    except Exception:
        logger.info("Primary data source: yfinance (default)")


async def _start_kraken_feed(app: FastAPI) -> None:
    """Step 5b: Start Kraken WebSocket feed for live crypto data (if enabled)."""
    app.state.kraken_feed = None
    try:
        from core.models import ENABLE_KRAKEN_CRYPTO

        if ENABLE_KRAKEN_CRYPTO:
            from integrations.kraken_client import start_kraken_feed

            _kraken_feed = start_kraken_feed()
            app.state.kraken_feed = _kraken_feed
            logger.info(
                "Kraken WebSocket feed started: %d pairs",
                len(_kraken_feed._pairs),
            )
        else:
            logger.info("Kraken crypto disabled (ENABLE_KRAKEN_CRYPTO=0)")
    except ImportError:
        logger.debug("Kraken client not available — crypto feed disabled")
    except Exception as exc:
        logger.warning("Kraken feed startup failed (non-fatal): %s", exc)


async def _warm_caches(app: FastAPI) -> None:
    """Step 6: Warm Redis bar caches from Postgres.

    Runs in a thread pool (asyncio.to_thread) so blocking synchronous
    DB + Redis I/O doesn't delay the event loop from accepting requests.
    """

    async def _background_warm():
        try:
            await asyncio.to_thread(startup_warm_caches, days_back=7)
        except Exception as exc:
            logger.warning("Startup cache warm failed (non-fatal): %s", exc)

    asyncio.create_task(_background_warm())
    logger.info("Startup cache warm scheduled as background task")


async def _start_data_sync_service(app: FastAPI) -> None:
    """Step 7: Start the background DataSyncService.

    Maintains rolling 1-year window of 1-min bars in Postgres with
    incremental 5-min refreshes.
    """
    try:
        _sync_service = get_sync_service()
        _sync_task = asyncio.create_task(_sync_service.run())
        _sync_service._task = _sync_task
        app.state.sync_service = _sync_service
        logger.info("DataSyncService background task started")
    except Exception as exc:
        app.state.sync_service = None
        logger.warning("DataSyncService startup failed (non-fatal): %s", exc)


async def _start_paper_trading_manager(app: FastAPI) -> None:
    """Step 8: Start PaperTradingManager (session orchestrator for paper trading)."""
    try:
        paper_trading_enabled = os.getenv("PAPER_TRADING_ENABLED", "0").strip().lower() in ("1", "true", "yes")
        if paper_trading_enabled:
            from services.engine.paper_trading_manager import get_paper_trading_manager

            _paper_trading_manager = await get_paper_trading_manager()
            app.state.paper_trading_manager = _paper_trading_manager
            logger.info("PaperTradingManager initialised and attached to app.state")
        else:
            logger.info("PaperTradingManager disabled (PAPER_TRADING_ENABLED=0)")
    except Exception as exc:
        logger.warning("PaperTradingManager startup failed (non-fatal): %s", exc)


async def _start_bot_supervisor(app: FastAPI) -> None:
    """Step 8b-i: Start BotSupervisor (managed bot subprocess orchestration)."""
    try:
        from services.engine.bot_supervisor import get_bot_supervisor

        _bot_supervisor = get_bot_supervisor()
        await _bot_supervisor.initialise(app.state.redis)
        app.state.bot_supervisor = _bot_supervisor
        logger.info("BotSupervisor initialised and attached to app.state")
    except Exception as exc:
        logger.warning("BotSupervisor startup failed (non-fatal): %s", exc)
        app.state.bot_supervisor = None


async def _start_janus_ai_manager(app: FastAPI) -> None:
    """Step 8b-ii: Start JanusAISessionManager (AI trading session orchestration)."""
    try:
        from services.engine.janus_ai_session import get_janus_ai_manager

        _janus_ai_manager = await get_janus_ai_manager()
        await _janus_ai_manager.initialise(app.state.redis)
        app.state.janus_ai_manager = _janus_ai_manager
        logger.info("JanusAISessionManager initialised and attached to app.state")
    except Exception as exc:
        logger.warning("JanusAISessionManager startup failed (non-fatal): %s", exc)
        app.state.janus_ai_manager = None


async def _start_alertmanager_monitor(app: FastAPI) -> None:
    """Step 8b-iii: Start AlertmanagerSignalMonitor poll loop.

    The primary path is the webhook (POST /api/signals/webhook called by
    Alertmanager).  This polling task is a fallback that also catches signals
    if the webhook delivery fails.  It is non-fatal: a misconfigured
    Alertmanager URL won't prevent service startup.
    """
    try:
        from services.engine.alertmanager_monitor import get_monitor  # noqa: PLC0415

        _am_monitor = get_monitor()
        _am_poll_task = asyncio.create_task(_am_monitor.poll_loop())
        app.state.am_monitor = _am_monitor
        app.state.am_poll_task = _am_poll_task
        logger.info("AlertmanagerSignalMonitor poll loop started")
    except Exception as exc:
        app.state.am_monitor = None
        app.state.am_poll_task = None
        logger.warning("AlertmanagerSignalMonitor startup failed (non-fatal): %s", exc)


async def _start_janus_signal_bridge(app: FastAPI) -> None:
    """Step 8b-iii½: Start JanusSignalBridge.

    Direct Redis bridge from janus:signals to fks:signals:incoming, bypassing
    Alertmanager.  Gated by ENABLE_SIGNAL_BRIDGE=1 (default off) so it
    doesn't interfere with the Alertmanager path when that is already
    configured and running.
    """
    try:
        _enable_bridge = os.getenv("ENABLE_SIGNAL_BRIDGE", "0").strip().lower() in ("1", "true", "yes")
        if _enable_bridge and getattr(app.state, "redis", None) is not None:
            from services.engine.janus_signal_bridge import JanusSignalBridge

            _signal_bridge = JanusSignalBridge(redis=app.state.redis)
            _signal_bridge_task = asyncio.create_task(
                _signal_bridge.run(),
                name="janus-signal-bridge",
            )
            _signal_bridge._task = _signal_bridge_task
            app.state.signal_bridge = _signal_bridge
            logger.info("JanusSignalBridge started (janus:signals → fks:signals:incoming)")
        else:
            app.state.signal_bridge = None
            if not _enable_bridge:
                logger.info("JanusSignalBridge disabled (ENABLE_SIGNAL_BRIDGE=0)")
            else:
                logger.info("JanusSignalBridge skipped — app.state.redis not available")
    except Exception as exc:
        logger.warning("JanusSignalBridge startup failed (non-fatal): %s", exc)
        app.state.signal_bridge = None


async def _start_deposit_monitor(app: FastAPI) -> None:
    """Step 8b-iv: Start DepositMonitor (auto-deploy new Kraken stablecoin deposits).

    The monitor polls Kraken balance every 5 min and buys underweight assets
    when new USDT/USDC above the threshold is detected.  It is non-fatal and
    runs only if the Kraken portfolio rebalancer is available (KRAKEN_API_KEY
    must be configured).  dry_run=True by default — no real orders without
    explicit opt-in via the /api/crypto/portfolio/config endpoint.
    """
    try:
        from services.data.api.crypto_portfolio_routes import _get_rebalancer_or_none
        from services.engine.crypto_portfolio import get_deposit_monitor

        _rebalancer = _get_rebalancer_or_none(app)
        if _rebalancer is not None:
            _deposit_monitor = get_deposit_monitor(
                _rebalancer,
                min_deposit_usd=float(os.getenv("DEPOSIT_MONITOR_THRESHOLD_USD", "50")),
                poll_interval_seconds=int(os.getenv("DEPOSIT_MONITOR_POLL_SECONDS", "300")),
            )
            await _deposit_monitor.start()
            app.state.deposit_monitor = _deposit_monitor
            logger.info("DepositMonitor started (dry_run=%s)", _rebalancer.config.dry_run)
        else:
            app.state.deposit_monitor = None
            logger.info("DepositMonitor skipped — Kraken rebalancer not available")
    except Exception as exc:
        logger.warning("DepositMonitor startup failed (non-fatal): %s", exc)
        app.state.deposit_monitor = None


async def _start_simulation_engine(app: FastAPI) -> None:
    """Step 8b: Start SimulationEngine for paper-trading with live Kraken tick data."""
    try:
        sim_enabled = os.getenv("SIM_ENABLED", "0").strip().lower() in ("1", "true", "yes")
        if sim_enabled:
            from services.engine.simulation import create_sim_engine

            _sim_engine = create_sim_engine()
            _sim_engine.start()
            app.state.sim_engine = _sim_engine
            logger.info(
                "SimulationEngine started (balance=$%s, source=%s)",
                f"{_sim_engine._account_balance:,.2f}",
                os.getenv("SIM_DATA_SOURCE", "kraken"),
            )
        else:
            logger.info("SimulationEngine disabled (SIM_ENABLED=0)")
    except Exception as exc:
        logger.warning("SimulationEngine startup failed (non-fatal): %s", exc)


async def _start_tv_tick_bridge(app: FastAPI) -> None:
    """Step 8c: Start TVTickBridge.

    Forwards TradingView Redis ticks to SimulationEngine instances.  Active
    whenever TV_SESSION_ID is set, regardless of whether SIM_ENABLED /
    PAPER_TRADING_ENABLED are on — the bridge is zero-cost when no callbacks
    are registered.
    """
    try:
        tv_session_id = os.getenv("TV_SESSION_ID", "").strip()
        if tv_session_id:
            from services.engine.tv_tick_bridge import get_tv_tick_bridge

            _tv_tick_bridge = get_tv_tick_bridge()
            _tv_bridge_task = asyncio.create_task(
                _tv_tick_bridge.run(),
                name="tv-tick-bridge",
            )
            _tv_tick_bridge._task = _tv_bridge_task
            app.state.tv_tick_bridge = _tv_tick_bridge
            logger.info("TVTickBridge started — subscribing to tv:ticks:* Redis channels")
        else:
            logger.info(
                "TVTickBridge skipped — TV_SESSION_ID not set "
                "(set it to enable TradingView → SimulationEngine tick forwarding)"
            )
    except Exception as exc:
        logger.warning("TVTickBridge startup failed (non-fatal): %s", exc)


async def _start_auto_backup(app: FastAPI) -> None:
    """Step 9: Start daily auto-backup scheduler (non-fatal)."""
    try:
        asyncio.create_task(auto_backup_task())
        logger.info("Auto-backup scheduler started")
    except Exception as exc:
        logger.warning("Auto-backup scheduler startup failed (non-fatal): %s", exc)


async def _start_data_factory(app: FastAPI) -> None:
    """Step 10: Bootstrap DataFactory async deps.

    Async Redis + async SQLAlchemy engine + AssetRegistry.  These are used
    exclusively by the /factory/* API routes.  The factory coordinator
    (supervisord) owns all heavy writes; the data service only reads
    coverage/health state and handles enable/disable calls.
    """
    _factory_redis = None
    _factory_engine = None
    try:
        import redis.asyncio as _aioredis
        from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

        from data_factory.registry.asset_registry import AssetRegistry as _AssetRegistry

        _redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _factory_redis = _aioredis.from_url(_redis_url, decode_responses=False)

        _db_url = os.getenv("DATABASE_URL", "")
        # Ensure we use the psycopg3 async dialect — the sync URL already has
        # the right scheme (postgresql+psycopg://); psycopg2 URLs need rewriting.
        if _db_url.startswith("postgresql+psycopg2://"):
            _async_db_url = _db_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
        elif _db_url.startswith("postgresql://") and "+" not in _db_url.split("://")[0]:
            _async_db_url = "postgresql+psycopg://" + _db_url[len("postgresql://") :]
        else:
            _async_db_url = _db_url  # already postgresql+psycopg:// or postgresql+asyncpg://

        if _async_db_url and _async_db_url.startswith("postgresql"):
            _factory_engine = _create_async_engine(
                _async_db_url,
                pool_size=3,
                max_overflow=5,
                pool_pre_ping=True,
            )
            _registry = _AssetRegistry(redis=_factory_redis, engine=_factory_engine)
            await _registry.bootstrap()
            _all_assets = await _registry.all_assets()
            app.state.factory_redis = _factory_redis
            app.state.factory_engine = _factory_engine
            app.state.asset_registry = _registry
            logger.info(
                "DataFactory registry bootstrapped (%d assets in catalog)",
                len(_all_assets),
            )

            # Wire the Dataset API router with Redis + manifest path so that
            # read-only endpoints (list, download, status, coverage) work even
            # though the generator daemon runs in the coordinator process.
            try:
                from data_factory.dataset_api import configure as _dataset_api_configure

                _dataset_output = os.getenv("DATASET_OUTPUT_DIR", "data/datasets")
                _dataset_api_configure(
                    dataset_generator=None,  # generator runs in coordinator process
                    registry=_registry,
                    redis_client=_factory_redis,
                    manifest_path=os.path.join(_dataset_output, "manifest.json"),
                )
                logger.info("Dataset API configured (manifest=%s/manifest.json)", _dataset_output)
            except Exception as _dapi_exc:
                logger.warning("Dataset API configure failed (non-fatal): %s", _dapi_exc)
        else:
            logger.warning("DataFactory registry skipped — DATABASE_URL is not a Postgres URL")
            app.state.factory_redis = None
            app.state.factory_engine = None
            app.state.asset_registry = None
    except Exception as exc:
        logger.warning("DataFactory registry bootstrap failed (non-fatal): %s", exc, exc_info=True)
        app.state.factory_redis = _factory_redis
        app.state.factory_engine = _factory_engine
        app.state.asset_registry = None


async def _start_rithmic_engine(app: FastAPI) -> None:
    """Step 11: Start RithmicPositionEngine.

    Connects TICKER_PLANT + PNL_PLANT and subscribes to the symbols in
    RITHMIC_SYMBOLS.  Gated by RITHMIC_LIVE_DATA=1; safe no-op when that
    variable is absent.
    """
    try:
        from services.engine.rithmic_position_engine import RithmicPositionEngine

        _rithmic_engine = RithmicPositionEngine()
        _rithmic_connected = await _rithmic_engine.connect()
        app.state.rithmic_engine = _rithmic_engine
        if _rithmic_connected:
            logger.info(
                "RithmicPositionEngine connected: account=%s symbols=%s",
                _rithmic_engine._account_key,
                _rithmic_engine._subscribed_symbols,
            )
        else:
            import os as _os

            if _os.getenv("RITHMIC_LIVE_DATA", "0") == "1":
                logger.warning(
                    "RithmicPositionEngine: RITHMIC_LIVE_DATA=1 but connect() returned False "
                    "— check account credentials in the Rithmic settings panel"
                )
            else:
                logger.info(
                    "RithmicPositionEngine: offline/mock mode "
                    "(set RITHMIC_LIVE_DATA=1 to enable live Rithmic streaming)"
                )
    except Exception as exc:
        logger.warning("RithmicPositionEngine startup failed (non-fatal): %s", exc, exc_info=True)
        app.state.rithmic_engine = None


# ---------------------------------------------------------------------------
# Shutdown helpers — each tears down one subsystem.
# ---------------------------------------------------------------------------


async def _stop_bot_supervisor(app: FastAPI) -> None:
    """Shutdown BotSupervisor."""
    _bot_supervisor = getattr(app.state, "bot_supervisor", None)
    if _bot_supervisor is not None:
        try:
            await _bot_supervisor.shutdown()
            logger.info("BotSupervisor stopped cleanly")
        except Exception as exc:
            logger.warning("BotSupervisor stop error (non-fatal): %s", exc)


async def _stop_janus_ai_manager(app: FastAPI) -> None:
    """Shutdown JanusAISessionManager."""
    _janus_ai_manager = getattr(app.state, "janus_ai_manager", None)
    if _janus_ai_manager is not None:
        try:
            await _janus_ai_manager.shutdown()
            logger.info("JanusAISessionManager stopped cleanly")
        except Exception as exc:
            logger.warning("JanusAISessionManager stop error (non-fatal): %s", exc)


async def _stop_alertmanager_monitor(app: FastAPI) -> None:
    """Shutdown AlertmanagerSignalMonitor poll loop."""
    _am_monitor = getattr(app.state, "am_monitor", None)
    _am_poll_task = getattr(app.state, "am_poll_task", None)
    if _am_monitor is not None:
        _am_monitor.stop()
    if _am_poll_task is not None:
        _am_poll_task.cancel()
        try:
            await _am_poll_task
        except asyncio.CancelledError:
            pass
        logger.info("AlertmanagerSignalMonitor poll loop stopped")


async def _stop_janus_signal_bridge(app: FastAPI) -> None:
    """Shutdown JanusSignalBridge."""
    _signal_bridge = getattr(app.state, "signal_bridge", None)
    if _signal_bridge is not None:
        try:
            await _signal_bridge.stop()
            logger.info("JanusSignalBridge stopped cleanly")
        except Exception as exc:
            logger.warning("JanusSignalBridge stop error (non-fatal): %s", exc)


async def _stop_deposit_monitor(app: FastAPI) -> None:
    """Shutdown DepositMonitor."""
    _deposit_monitor = getattr(app.state, "deposit_monitor", None)
    if _deposit_monitor is not None:
        try:
            await _deposit_monitor.stop()
            logger.info("DepositMonitor stopped cleanly")
        except Exception as exc:
            logger.warning("DepositMonitor stop error (non-fatal): %s", exc)


async def _stop_paper_trading_manager(app: FastAPI) -> None:
    """Shutdown PaperTradingManager."""
    _paper_trading_manager = getattr(app.state, "paper_trading_manager", None)
    if _paper_trading_manager is not None:
        try:
            from services.engine.paper_trading_manager import reset_paper_trading_manager

            await reset_paper_trading_manager()
            logger.info("PaperTradingManager stopped cleanly")
        except Exception as exc:
            logger.warning("PaperTradingManager stop error (non-fatal): %s", exc)


async def _stop_simulation_engine(app: FastAPI) -> None:
    """Shutdown SimulationEngine."""
    _sim_engine = getattr(app.state, "sim_engine", None)
    if _sim_engine is not None:
        try:
            _sim_engine.stop()
            logger.info("SimulationEngine stopped cleanly")
        except Exception as exc:
            logger.warning("SimulationEngine stop error (non-fatal): %s", exc)


async def _stop_tv_tick_bridge(app: FastAPI) -> None:
    """Shutdown TVTickBridge."""
    _tv_tick_bridge = getattr(app.state, "tv_tick_bridge", None)
    if _tv_tick_bridge is not None:
        try:
            await _tv_tick_bridge.stop()
            logger.info("TVTickBridge stopped cleanly")
        except Exception as exc:
            logger.warning("TVTickBridge stop error (non-fatal): %s", exc)


async def _stop_rithmic_engine(app: FastAPI) -> None:
    """Shutdown RithmicPositionEngine (disconnect all plants)."""
    _rithmic_engine_state = getattr(app.state, "rithmic_engine", None)
    if _rithmic_engine_state is not None:
        try:
            await _rithmic_engine_state.disconnect()
            logger.info("RithmicPositionEngine disconnected cleanly")
        except Exception as exc:
            logger.warning("RithmicPositionEngine stop error (non-fatal): %s", exc)


async def _stop_data_sync_service(app: FastAPI) -> None:
    """Shutdown DataSyncService."""
    _sync_service = getattr(app.state, "sync_service", None)
    if _sync_service is not None:
        try:
            await _sync_service.stop()
            logger.info("DataSyncService stopped cleanly")
        except Exception as exc:
            logger.warning("DataSyncService stop error (non-fatal): %s", exc)


async def _stop_kraken_feed(app: FastAPI) -> None:
    """Shutdown Kraken WebSocket feed."""
    _kraken_feed = getattr(app.state, "kraken_feed", None)
    if _kraken_feed is not None:
        try:
            await _kraken_feed.stop()
            logger.info("Kraken feed stopped cleanly")
        except Exception as exc:
            logger.warning("Kraken feed stop error (non-fatal): %s", exc)


async def _stop_engine(app: FastAPI) -> None:
    """Shutdown engine (embedded or proxy)."""
    if _engine is not None:
        try:
            await _engine.stop()
            logger.info("Engine stopped cleanly")
        except Exception as exc:
            logger.warning("Engine stop error (non-fatal): %s", exc)


async def _stop_redis(app: FastAPI) -> None:
    """Shutdown async Redis client."""
    _app_redis_state = getattr(app.state, "redis", None)
    if _app_redis_state is not None:
        try:
            await _app_redis_state.aclose()
            logger.info("app.state.redis closed")
        except Exception as exc:
            logger.warning("app.state.redis close error (non-fatal): %s", exc)


async def _stop_data_factory(app: FastAPI) -> None:
    """Shutdown DataFactory async clients (Redis + SQLAlchemy engine)."""
    _factory_redis_state = getattr(app.state, "factory_redis", None)
    if _factory_redis_state is not None:
        try:
            await _factory_redis_state.aclose()
            logger.info("DataFactory Redis client closed")
        except Exception as exc:
            logger.warning("DataFactory Redis close error (non-fatal): %s", exc)

    _factory_engine_state = getattr(app.state, "factory_engine", None)
    if _factory_engine_state is not None:
        try:
            await _factory_engine_state.dispose()
            logger.info("DataFactory DB engine disposed")
        except Exception as exc:
            logger.warning("DataFactory engine dispose error (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Lifespan: start engine + background tasks on startup, clean up on shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("  Data Service starting up (engine_mode=%s)", _ENGINE_MODE)
    logger.info("=" * 60)

    # --- Startup (order matters: e.g. Redis must be up before dependents) ---
    await _init_database(app)
    await _start_engine(app)
    await _start_redis(app)
    await _inject_engine_into_routers(app)
    await _start_reddit_watcher(app)
    await _start_live_risk_publisher(app)
    await _log_data_source(app)
    await _start_kraken_feed(app)
    await _warm_caches(app)
    await _start_data_sync_service(app)
    await _start_paper_trading_manager(app)
    await _start_bot_supervisor(app)
    await _start_janus_ai_manager(app)
    await _start_alertmanager_monitor(app)
    await _start_janus_signal_bridge(app)
    await _start_deposit_monitor(app)
    await _start_simulation_engine(app)
    await _start_tv_tick_bridge(app)
    await _start_auto_backup(app)
    await _start_data_factory(app)
    await _start_rithmic_engine(app)

    logger.info("=" * 60)
    logger.info("  Data Service ready — accepting requests")
    logger.info("=" * 60)

    yield

    # --- Shutdown (reverse order) ---
    logger.info("=" * 60)
    logger.info("  Data Service shutting down")
    logger.info("=" * 60)

    await _stop_bot_supervisor(app)
    await _stop_janus_ai_manager(app)
    await _stop_alertmanager_monitor(app)
    await _stop_janus_signal_bridge(app)
    await _stop_deposit_monitor(app)
    await _stop_paper_trading_manager(app)
    await _stop_simulation_engine(app)
    await _stop_tv_tick_bridge(app)
    await _stop_rithmic_engine(app)
    await _stop_data_sync_service(app)
    await _stop_kraken_feed(app)
    await _stop_engine(app)
    await _stop_redis(app)
    await _stop_data_factory(app)

    logger.info("Data Service stopped")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Ruby Data Service",
    description=(
        "Background data service for Ruby. "
        "Runs the DashboardEngine, Massive WS listener, and all FKS "
        "computation modules. Exposes REST endpoints and an HTMX dashboard."
    ),
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=SafeJSONResponse,
    dependencies=[Depends(require_api_key)],
)


# ---------------------------------------------------------------------------
# Structured error responses — consistent JSON shape for all error types
# ---------------------------------------------------------------------------
# Every error response follows:
#   { "error": "<short_code>", "detail": "<human message>", "status": <int> }
# This replaces FastAPI's default {"detail": ...} shape so clients can
# rely on a single schema for error handling.
# ---------------------------------------------------------------------------


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle all HTTP exceptions (404, 403, 405, 422, 500, etc.)."""
    status = exc.status_code
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    # Map common status codes to short error codes
    code_map = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
        429: "rate_limit_exceeded",
        500: "internal_error",
        502: "bad_gateway",
        503: "service_unavailable",
    }
    error_code = code_map.get(status, f"http_{status}")

    return JSONResponse(
        status_code=status,
        content={
            "error": error_code,
            "detail": detail,
            "status": status,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic / query-param validation errors with structured JSON."""
    errors = exc.errors()
    # Build a human-readable summary from the validation error list
    messages = []
    for err in errors:
        loc = " → ".join(str(part) for part in err.get("loc", []))
        msg = err.get("msg", "invalid")
        messages.append(f"{loc}: {msg}" if loc else msg)

    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": "; ".join(messages) if messages else "Request validation failed",
            "status": 422,
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — log and return structured 500."""
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": f"Internal server error: {type(exc).__name__}",
            "status": 500,
        },
    )


# CORS — allow local dev origins + Tailscale IPs
# NOTE: allow_credentials must be False when using wildcard origins.
# The SSE StreamingResponse also must NOT set Access-Control-Allow-Origin
# manually — let this middleware handle it consistently to avoid the
# "wildcard + credentials" conflict that makes browsers drop EventSource.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics middleware — records request count + latency (TASK-704)
app.add_middleware(PrometheusMiddleware)

# Rate limiting (TASK-703) — slowapi-based per-client rate limits
setup_rate_limiting(app)

# GZip compression — compresses responses larger than 1 KB.
# Added last so it is the outermost middleware layer and compresses the
# final response (after CORS headers and metrics are applied).
# Benchmarks on bar-data endpoints show 70–85% size reduction for JSON
# payloads; HTMX HTML partials compress to ~40% of original size.
# Excluded automatically by Starlette for already-compressed content types
# and for SSE streams (Transfer-Encoding: chunked bypasses GZip).
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------


def _register_routers(app: FastAPI) -> None:
    """Register all API routers with the FastAPI application.

    All ``app.include_router()`` calls are consolidated here so that adding a
    new router requires editing only this one function.  Imports that were
    previously inlined between individual ``include_router`` calls are
    collected as local imports at the top of this function; Python's module
    cache means there is no double-loading penalty.

    To add a new router:
        1. Add ``from services.data.api.<module> import router as <name>_router``
           in the "Late imports" block below (keep it alphabetically sorted).
        2. Add ``app.include_router(<name>_router, ...)`` in the appropriate
           domain section further down.
    """
    # ------------------------------------------------------------------
    # Late imports — routers that were previously imported inline between
    # individual app.include_router() calls.  Modules already imported at
    # the top of this file (dashboard_router, bars_router, etc.) are used
    # directly without re-importing.
    # ------------------------------------------------------------------
    from data_factory.dataset_api import router as dataset_api_router
    from integrations.rithmic_client import router as rithmic_router
    from services.data.api.asset_search import router as asset_search_router
    from services.data.api.bot_routes import router as bot_router
    from services.data.api.chain import router as chain_router
    from services.data.api.chart_indicators import router as chart_indicators_router
    from services.data.api.copy_trade import router as copy_trade_router
    from services.data.api.crypto_portfolio_routes import router as crypto_portfolio_router
    from services.data.api.db_tools import router as db_tools_router
    from services.data.api.dom import router as dom_router
    from services.data.api.dom import sse_router as dom_sse_router
    from services.data.api.factory_coverage import router as factory_coverage_router
    from services.data.api.factory_news import router as factory_news_router
    from services.data.api.factory_registry import router as factory_registry_router
    from services.data.api.indicator_catalog import router as indicator_catalog_router
    from services.data.api.janus_ai_routes import router as janus_ai_router
    from services.data.api.janus_config_routes import router as janus_config_router
    from services.data.api.monitoring import router as monitoring_router
    from services.data.api.net_worth import router as net_worth_router
    from services.data.api.overview import router as overview_router
    from services.data.api.paper_trading_routes import router as paper_trading_router
    from services.data.api.paper_trading_routes import sse_router as paper_trading_sse_router
    from services.data.api.pine import router as pine_router
    from services.data.api.pretrade import router as pretrade_router
    from services.data.api.pretrade import sse_router as pretrade_sse_router
    from services.data.api.registry_sync import router as registry_sync_router
    from services.data.api.routes.workspaces.analysis import router as ws_analysis_router
    from services.data.api.routes.workspaces.chains import router as ws_chains_router
    from services.data.api.routes.workspaces.charts import router as ws_charts_router
    from services.data.api.routes.workspaces.crypto import router as ws_crypto_router
    from services.data.api.routes.workspaces.data import router as ws_data_router
    from services.data.api.routes.workspaces.db_tools import router as ws_db_tools_router
    from services.data.api.routes.workspaces.docs import router as ws_docs_router
    from services.data.api.routes.workspaces.dom import router as ws_dom_router
    from services.data.api.routes.workspaces.janus_ai import router as ws_janus_ai_router
    from services.data.api.routes.workspaces.journal import router as ws_journal_router
    from services.data.api.routes.workspaces.monitoring import router as ws_monitoring_router
    from services.data.api.routes.workspaces.news import router as ws_news_router
    from services.data.api.routes.workspaces.paper_trading import router as ws_paper_router
    from services.data.api.routes.workspaces.posint import router as ws_posint_router
    from services.data.api.routes.workspaces.settings import router as ws_settings_router
    from services.data.api.routes.workspaces.simulations import router as ws_simulations_router
    from services.data.api.routes.workspaces.trading import router as ws_trading_router
    from services.data.api.routes.workspaces.trainer import router as ws_trainer_router
    from services.data.api.ruby import router as ruby_router
    from services.data.api.session_report_routes import router as session_report_router
    from services.data.api.signal_webhook import router as signal_webhook_router
    from services.data.api.static_pages import router as static_pages_router
    from services.data.api.strip import router as strip_router
    from services.data.api.symbols import router as symbols_router
    from services.data.api.tailscale_identity import router as tailscale_identity_router
    from services.data.api.trade_executor_routes import router as trade_executor_router
    from services.data.api.tv_charts import router as tv_charts_router
    from services.data.source_router import source_api_router

    # ------------------------------------------------------------------
    # Dashboard & shell
    # ------------------------------------------------------------------

    # Dashboard: / (HTML page), /api/focus, /api/focus/html, /api/time, etc.
    # NOTE: dashboard_router is mounted WITHOUT a prefix so GET / serves the HTML
    # dashboard and /api/focus, /api/focus/html etc. are top-level paths.
    app.include_router(dashboard_router, tags=["Dashboard"])

    # Charting proxy: /charting-proxy/* → charting container (reverse proxy)
    # Allows the Charts iframe to work from any machine by proxying through the
    # data service instead of requiring direct access to charting:8003.
    app.include_router(charting_proxy_router, tags=["Charting Proxy"])

    # SSE: /sse/dashboard (live event stream), /sse/health
    # NOTE: sse_router is mounted WITHOUT a prefix so /sse/dashboard is top-level.
    app.include_router(sse_router, tags=["SSE"])

    # ------------------------------------------------------------------
    # Core trading
    # ------------------------------------------------------------------

    # Analysis: /analysis/latest, /analysis/latest/{ticker}, /analysis/status, etc.
    app.include_router(analysis_router, prefix="/analysis", tags=["Analysis"])

    # Actions: /actions/force_refresh, /actions/optimize_now, /actions/update_settings, etc.
    app.include_router(actions_router, prefix="/actions", tags=["Actions"])

    # Positions: /positions/, /positions/update, etc.  (broker-agnostic position management)
    app.include_router(positions_router, prefix="/positions", tags=["Positions"])

    # Position Intelligence: /api/positions/intelligence/{symbol}, /api/positions/intelligence,
    #                        /api/positions/risk
    # On-demand ICT analysis, confluence scoring, volume profile, CVD momentum, regime detection.
    # NOTE: posint_router is mounted WITHOUT a prefix — routes are defined with /api/positions/ paths.
    app.include_router(posint_router, tags=["Position Intelligence"])

    # Trades: /trades, /trades/{id}/close, /log_trade, etc.  (trade CRUD)
    # Mounted at both "" and "/api" so that legacy /trades/* and newer /api/trades/* both resolve.
    app.include_router(trades_router, prefix="", tags=["Trades"])
    app.include_router(trades_router, prefix="/api", tags=["Trades"])

    # Risk: /risk/status, /risk/check, /risk/history  (risk engine API)
    app.include_router(risk_router, prefix="/risk", tags=["Risk"])

    # Audit: /audit/risk, /audit/orb, /audit/summary  (persistent event history)
    app.include_router(audit_router, prefix="/audit", tags=["Audit"])

    # Journal: /journal/save, /journal/entries, /journal/stats, /journal/today
    # Mounted at both /journal and /api/journal so HTMX workspace calls
    # (which use /api/journal/*) resolve alongside the original paths.
    app.include_router(journal_router, prefix="/journal", tags=["Journal"])
    app.include_router(journal_router, prefix="/api/journal", tags=["Journal"])

    # Market Data: /data/ohlcv, /data/daily, /data/source  (OHLCV proxy for thin client)
    app.include_router(market_data_router, prefix="/data", tags=["Market Data"])

    # Bars: /bars/{symbol}, /bars/bulk, /bars/status, /bars/assets
    #       /bars/{symbol}/gaps, /bars/{symbol}/fill, /bars/fill/all, /bars/fill/status
    # Historical bar store — serves data from Postgres with auto gap-fill from Massive.
    # Primary data source for CNN dataset generation, engine backtesting, and web charts.
    app.include_router(bars_router, tags=["Bars"])

    # Live Risk: /api/live-risk, /api/live-risk/html, /api/live-risk/summary,
    #            /api/live-risk/refresh, /api/live-risk/position/{asset_name}/html
    app.include_router(live_risk_router, tags=["Live Risk"])

    # Swing Actions: /api/swing/accept/{asset}, /api/swing/ignore/{asset}, etc.
    app.include_router(swing_actions_router, tags=["Swing Actions"])

    # Execution Gate: /api/execution_gate/status, /api/execution_gate/config, etc.
    # EXEC-GATE — confidence gate, circuit breaker, idempotency, manual confirm queue.
    app.include_router(execution_gate_router)

    # Simulation: /api/sim/status, /api/sim/order, /api/sim/close/{symbol}, etc.
    # Gated by SIM_ENABLED=1 env var at the engine level; routes always registered
    # but return 503 when the engine is not running.
    app.include_router(sim_router, tags=["Simulation"])
    app.include_router(sim_sse_router, tags=["Simulation SSE"])

    # Paper Trading Manager: /api/paper-trading/sessions, /api/paper-trading/accounts, etc.
    # Routes always registered; return 503 when PaperTradingManager is not initialised.
    app.include_router(paper_trading_router, tags=["Paper Trading"])
    app.include_router(paper_trading_sse_router, tags=["Paper Trading SSE"])

    # Trade Executor: /api/trade/engage, /api/trade/active, /api/trade/active/{symbol}, etc.
    # Staged trade execution with stop-hunt protection and plan-aware management.
    app.include_router(trade_executor_router, tags=["Trade Executor"])

    # Copy Trade: /api/copy-trade/send, /api/copy-trade/send-from-ticker, etc.
    # RITHMIC-F: WebUI "SEND ALL" button + prop-firm compliant copy trading.
    app.include_router(copy_trade_router, tags=["Copy Trade"])

    # Ruby Signal Engine: internal signal processing routes.
    app.include_router(ruby_router, tags=["Ruby Signal Engine"])

    # Rithmic: /api/rithmic/accounts, /api/rithmic/status, /api/rithmic/status/html, etc.
    # NOTE: rithmic_router is mounted WITHOUT a prefix — routes are defined with full paths.
    app.include_router(rithmic_router, tags=["Rithmic"])

    # DOM (Depth of Market): /api/dom/snapshot, /api/dom/config, /sse/dom
    app.include_router(dom_router, tags=["DOM"])
    app.include_router(dom_sse_router, tags=["DOM SSE"])

    # ------------------------------------------------------------------
    # Analysis & intelligence
    # ------------------------------------------------------------------

    # CNN: /cnn/status, /cnn/retrain, /cnn/retrain/status, /cnn/history, /cnn/status/html
    # NOTE: cnn_router is mounted WITHOUT a prefix — routes are defined with /cnn/ paths.
    app.include_router(cnn_router, tags=["CNN"])

    # Grok: /api/grok/latest, /api/grok/briefing, /api/grok/trigger/briefing, etc.
    # NOTE: grok_router is mounted WITHOUT a prefix — routes are defined with full paths.
    app.include_router(grok_router, tags=["Grok"])

    # Sweeps: /api/sweeps/bracket/run, /api/sweeps/bracket/status, etc.
    # RETRAIN-I2 (bracket TP/SL optimization) and RETRAIN-I3 (trailing stop optimization).
    app.include_router(sweep_router, tags=["Sweeps"])

    # Analysis Tools: /api/analysis/correlation, /api/analysis/checklist, /api/analysis/scanner
    app.include_router(analysis_tools_router, tags=["Analysis Tools"])

    # Pipeline: /api/pipeline/run, /api/pipeline/status, /api/pipeline/reset, etc.
    # Morning workflow pipeline — SSE-driven analysis, plan management, live trading.
    # NOTE: pipeline_router is mounted WITHOUT a prefix — routes are defined with full paths.
    app.include_router(pipeline_router, tags=["Pipeline"])

    # Pre-Trade Analysis: /api/pretrade/assets, /api/pretrade/analyze, etc.
    # KRAKEN-SIM-C: Asset selection & opportunity scoring for pre-session workflow.
    app.include_router(pretrade_router, tags=["Pre-Trade Analysis"])
    app.include_router(pretrade_sse_router, tags=["Pre-Trade SSE"])

    # Chart Indicators: /api/chart/{symbol}/indicators, /api/chart/{symbol}/regime, /api/chart/assets
    app.include_router(chart_indicators_router, tags=["Chart Indicators"])

    # Indicator Catalog: /api/indicators/catalog, /api/indicators/compute/{symbol}
    # Static metadata catalog for the indicator builder UI.
    app.include_router(indicator_catalog_router, tags=["Indicator Catalog"])

    # Session Reports: /api/reports/pre-session, /api/reports/post-session, etc.
    # Daily pre/post session reports for performance tracking and system improvement.
    app.include_router(session_report_router, tags=["Session Reports"])

    # Janus AI Session API: /api/janus-ai/sessions, /api/janus-ai/overview
    app.include_router(janus_ai_router, tags=["Janus AI Sessions"])

    # Janus Config API: /api/janus/config, /api/janus/memories/bootstrap
    app.include_router(janus_config_router, tags=["Janus Config"])

    # ------------------------------------------------------------------
    # Data sources & market data
    # ------------------------------------------------------------------

    # Kraken: /kraken/health, /kraken/status, /kraken/pairs, /kraken/ticker/{pair}, etc.
    # NOTE: kraken_router is mounted WITHOUT a prefix — routes are defined with /kraken/ paths.
    app.include_router(kraken_router, tags=["Kraken"])

    # Data Sync: /api/data/sync/status, /api/data/sync/trigger, /api/data/bars
    # NOTE: sync_router is mounted WITHOUT a prefix — routes are defined with full paths.
    app.include_router(sync_router, tags=["Data Sync"])

    # Data Source Router: /api/sources/symbols, /api/sources/status
    app.include_router(source_api_router, tags=["Data Sources"])

    # TradingView Charts: /api/tv/chart/{symbol}, /api/tv/chart/{symbol}/data, etc.
    # TV-DATA-B: Server-side chart HTML generation using Lightweight Charts CDN.
    app.include_router(tv_charts_router, tags=["TradingView Charts"])

    # Symbols: /api/symbols/search, /api/symbols/assets, /api/symbols/{symbol}/info
    app.include_router(symbols_router, tags=["Symbols"])

    # Net Worth: /api/net-worth, /api/net-worth/html, /net-worth, /kraken/account/stable
    # MULTI-EXCHANGE-D: Unified net worth dashboard aggregating Kraken spot, Kraken futures, etc.
    app.include_router(net_worth_router, tags=["Net Worth"])

    # Crypto Portfolio: /api/crypto/portfolio, /api/crypto/portfolio/rebalance, etc.
    # Kraken spot portfolio manager — current allocations, drift detection, rebalancing engine.
    app.include_router(crypto_portfolio_router, tags=["Crypto Portfolio"])

    # On-Chain Monitoring: /api/chain/whale/recent, /api/chain/flows/{chain}, etc.
    # NOTE: chain_router is mounted WITHOUT a prefix — routes are defined with /api/chain/ paths.
    app.include_router(chain_router, tags=["Chain"])

    # ------------------------------------------------------------------
    # DataFactory
    # ------------------------------------------------------------------

    # DataFactory Registry: /factory/assets, /factory/assets/{symbol}, etc.
    # Asset catalog management — enable/disable assets and update per-asset config.
    app.include_router(factory_registry_router, prefix="/factory", tags=["Factory Registry"])

    # Unified Asset Search: /api/assets/search, /api/assets/list, /api/assets/{name}, etc.
    app.include_router(asset_search_router, prefix="/api/assets", tags=["Asset Search"])

    # Registry Sync: /api/registry/sync, /api/registry/sync/v1
    # Serves the full merged asset catalog in Janus-compatible format.
    app.include_router(registry_sync_router, tags=["Registry Sync"])

    # DataFactory Coverage: /factory/coverage, /factory/coverage/{symbol}, etc.
    # Window coverage reports and provider circuit-breaker state.
    app.include_router(factory_coverage_router, prefix="/factory", tags=["Factory Coverage"])

    # DataFactory News: /factory/news/recent, /factory/news/search, etc.
    # News article queries against the news_articles / news_asset_links tables.
    app.include_router(factory_news_router, prefix="/factory", tags=["Factory News"])

    # DataFactory Datasets: /api/datasets, /api/datasets/manifest, etc.
    # Auto-generated training, backtest, and feature datasets from historical bars.
    # NOTE: dataset_api_router is mounted WITHOUT a prefix — routes are defined with /api/datasets/ prefix.
    app.include_router(dataset_api_router, tags=["Datasets"])

    # ------------------------------------------------------------------
    # Monitoring & observability
    # ------------------------------------------------------------------

    # Health: /health, /metrics  (no prefix — top-level)
    app.include_router(health_router, tags=["Health"])

    # Prometheus metrics: /metrics/prometheus  (TASK-704)
    app.include_router(metrics_router, tags=["Metrics"])

    # System Health: /api/health, /api/health/html
    app.include_router(health_router, tags=["System Health"])

    # Monitoring Proxy: /api/metrics/query, /api/metrics/query_range, etc.
    # PromQL proxy, alert rules, Alertmanager alerts, Grafana embed URL, layout CRUD.
    app.include_router(monitoring_router, tags=["Monitoring Proxy"])

    # Trade Signals: /api/signals/webhook, /api/signals/active, /api/signals/history
    # Alertmanager trade signal webhook receiver.
    app.include_router(signal_webhook_router, tags=["Trade Signals"])

    # ------------------------------------------------------------------
    # System & utilities
    # ------------------------------------------------------------------

    # Settings: /settings (HTML page)
    # NOTE: settings_router is mounted WITHOUT a prefix — route is defined with /settings path.
    app.include_router(settings_router, tags=["Settings"])

    # Trainer: /trainer (HTML page), /trainer/api/* (proxy to trainer service), etc.
    # NOTE: trainer_router is mounted WITHOUT a prefix — routes are defined with /trainer/ paths.
    app.include_router(trainer_router, tags=["Trainer"])

    # Tasks: /api/tasks, /api/tasks/{id}, /api/tasks/{id}/github, /api/tasks/html
    app.include_router(tasks_router, tags=["Tasks"])

    # Backup & Restore: /api/backup/status, /api/backup/export, /backup (HTML page), etc.
    app.include_router(backup_router, tags=["Backup"])
    app.include_router(backup_html_router, tags=["Backup"])

    # Chat: /api/chat, /sse/chat, /api/chat/history, /api/chat/status
    # RustAssistant-powered multi-turn chat with RA→Grok fallback.
    app.include_router(chat_router, tags=["Chat"])

    # Reddit Sentiment: /api/reddit/signal/{asset}, /api/reddit/snapshot, etc.
    # NOTE: reddit_router is mounted WITHOUT a prefix — routes are defined with full paths.
    app.include_router(reddit_router, tags=["Reddit Sentiment"])

    # News Sentiment: /api/news/sentiment, /api/news/headlines, etc.
    # NOTE: news_router is mounted WITHOUT a prefix — routes are defined with full paths.
    app.include_router(news_router, tags=["News Sentiment"])

    # Pine Script Generator: /pine (HTML page), /api/pine/modules, etc.
    # NOTE: pine_router is mounted WITHOUT a prefix — routes are defined with full paths.
    app.include_router(pine_router, tags=["Pine Script Generator"])

    # Tailscale Auth: /api/tailscale/identity, /api/tailscale/status
    app.include_router(tailscale_identity_router, tags=["Tailscale Auth"])

    # DB Tools: /api/db/redis/*, /api/db/postgres/*, /api/db/questdb/*, /api/janus/*
    # Database and service explorer — Redis key browser, Postgres/QuestDB query runner.
    app.include_router(db_tools_router, tags=["DB Tools"])

    # Bot Supervisor API: /api/bots/status, /api/bots/{id}/stop
    app.include_router(bot_router, tags=["Bot Supervisor"])

    # Docs Viewer: /docs-viewer/, /docs-viewer/view/{path}, /docs-viewer/browse/{path}, etc.
    # NOTE: docs_viewer_router is mounted WITHOUT a prefix — routes are defined with /docs-viewer/ prefix.
    app.include_router(docs_viewer_router, tags=["Docs Viewer"])

    # ------------------------------------------------------------------
    # Terminal UI — strip, overview, workspaces
    # ------------------------------------------------------------------

    # Strip: /api/strip/focus, /api/strip/pnl, /api/strip/risk, /api/strip/ticker, etc.
    # Each cell refreshes at its own cadence via HTMX polling.
    app.include_router(strip_router, tags=["Terminal Strip"])

    # Overview / Terminal shell: /terminal, /overview, /partials/market-table, etc.
    # NOTE: overview_router is mounted WITHOUT a prefix — routes are defined with full paths.
    app.include_router(overview_router, tags=["Terminal Overview"])

    # Static Pages: /chat, /sweeps — serve standalone HTML from static/
    # Redirects: /dom, /posint, /paper-trading, /journal, /analysis, /settings, /chart, /pretrade
    # Standalone iframe sources: /dom/standalone, /posint/standalone, /paper-trading/standalone
    app.include_router(static_pages_router, tags=["Static Pages"])

    # ── WEBUI-TERMINAL-G: Workspace Routes — Lazy-Loaded Tab Content ──
    #
    # Each workspace route returns a bare HTML fragment (just panes, no shell).
    # HTMX swaps the fragment into the already-rendered .fks-page div when the
    # user clicks a workspace tab.  The persistent strip never re-renders.
    #
    # Routes:
    #   GET /workspaces/trading      — chart, order entry, open positions, signals
    #   GET /workspaces/analysis     — asset scoring, AI briefing, regime overview
    #   GET /workspaces/charts       — full-width chart with symbol/TF selector
    #   GET /workspaces/news         — news feed, sentiment overview, whale alerts
    #   GET /workspaces/data         — factory coverage, gap scanner, backfill status
    #   GET /workspaces/journal      — trade log, analytics, daily notes
    #   GET /workspaces/settings     — data sources, connections, risk controls, system info
    #   GET /workspaces/chains       — whale activity, mempool, signal correlation, CMC macro
    #   GET /workspaces/dom          — DOM ladder (iframe embed of /dom/standalone)
    #   GET /workspaces/posint       — position intelligence (iframe embed of /posint/standalone)
    #   GET /workspaces/paper        — paper trading (iframe embed of /paper-trading/standalone)
    #   GET /workspaces/trainer      — CNN trainer (iframe embed of /trainer/standalone)
    #   GET /workspaces/docs         — docs viewer (iframe embed of /docs-viewer/)
    #   GET /workspaces/db           — DB Explorer (Redis patterns, PG/QDB tables, Janus links)
    #   GET /workspaces/simulations  — Simulation Supervisor
    #   GET /workspaces/monitoring   — Monitoring workspace fragment
    #   GET /workspaces/janus-ai     — Janus AI session dashboard
    #   GET /workspaces/crypto       — Crypto Portfolio workspace
    app.include_router(ws_trading_router, tags=["Workspace: Trading"])
    app.include_router(ws_analysis_router, tags=["Workspace: Analysis"])
    app.include_router(ws_charts_router, tags=["Workspace: Charts"])
    app.include_router(ws_news_router, tags=["Workspace: News"])
    app.include_router(ws_data_router, tags=["Workspace: Data"])
    app.include_router(ws_trainer_router, tags=["Workspace: Trainer"])
    app.include_router(ws_journal_router, tags=["Workspace: Journal"])
    app.include_router(ws_settings_router, tags=["Workspace: Settings"])
    app.include_router(ws_chains_router, tags=["Workspace: Chains"])
    app.include_router(ws_dom_router, tags=["Workspace: DOM"])
    app.include_router(ws_posint_router, tags=["Workspace: Positions"])
    app.include_router(ws_paper_router, tags=["Workspace: Paper Trading"])
    app.include_router(ws_docs_router, tags=["Workspace: Docs"])
    app.include_router(ws_db_tools_router, tags=["Workspace: DB Explorer"])
    app.include_router(ws_simulations_router, tags=["Workspace: Simulations"])
    app.include_router(ws_monitoring_router, tags=["Workspace: Monitoring"])
    app.include_router(ws_janus_ai_router, tags=["Workspace: Janus AI"])
    app.include_router(ws_crypto_router, tags=["Workspace: Crypto Portfolio"])


_register_routers(app)


# ---------------------------------------------------------------------------
# Static files — serve /static/* from the static/ directory so that widgets
# like chat-widget.js are accessible at /static/chat-widget.js from the browser.
# Path resolution mirrors _STATIC_CANDIDATES in static_pages.py:
#   Dev:    src/ruby/lib/services/data/main.py → ../../../../.. → src/web/
#   Docker: /app/static
# ---------------------------------------------------------------------------
_STATIC_DIR_CANDIDATES: list[Path] = [
    Path("/app/static"),
    Path(__file__).resolve().parent.parent.parent.parent.parent / "web",
]
_static_dir: Path | None = next((p for p in _STATIC_DIR_CANDIDATES if p.is_dir()), None)
if _static_dir is not None:
    app.mount(
        "/static",
        StaticFiles(directory=str(_static_dir)),
        name="static",
    )
else:
    logger.warning(
        "Static directory not found in candidates %s — /static/* will not be served",
        _STATIC_DIR_CANDIDATES,
    )


# ---------------------------------------------------------------------------
# Root endpoint — now served by dashboard_router (GET / returns HTML dashboard)
# The old JSON root is moved to /api/info for programmatic consumers.
# ---------------------------------------------------------------------------
@app.get("/api/info")
def api_info():
    """Service info and links to docs (formerly GET /)."""
    return {
        "service": "futures-data-service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "dashboard": "/",
            "focus_json": "/api/focus",
            "focus_html": "/api/focus/html",
            "sse_dashboard": "/sse/dashboard",
            "sse_health": "/sse/health",
            "analysis": "/analysis/latest",
            "status": "/analysis/status",
            "force_refresh": "/actions/force_refresh",
            "positions": "/positions/",
            "trades": "/trades",
            "journal": "/journal/entries",
            "market_data": "/data/ohlcv",
            "daily_data": "/data/daily",
            "data_source": "/data/source",
            "health": "/health",
            "metrics": "/metrics",
            "system_health": "/api/health",
            "system_health_html": "/api/health/html",
            "cnn_status": "/cnn/status",
            "cnn_status_html": "/cnn/status/html",
            "cnn_retrain": "/cnn/retrain",
            "cnn_retrain_status": "/cnn/retrain/status",
            "cnn_retrain_log": "/cnn/retrain/log",
            "cnn_retrain_cancel": "/cnn/retrain/cancel",
            "cnn_history": "/cnn/history",
            "cnn_sync": "/cnn/sync",
            "cnn_sync_status": "/cnn/sync/status",
            "cnn_watcher_status": "/cnn/watcher/status",
            "kraken_health": "/kraken/health",
            "kraken_status": "/kraken/status",
            "kraken_pairs": "/kraken/pairs",
            "kraken_ticker": "/kraken/ticker/{pair}",
            "kraken_tickers": "/kraken/tickers",
            "kraken_ohlcv": "/kraken/ohlcv/{pair}",
            "kraken_health_html": "/kraken/health/html",
            "trainer_page": "/trainer",
            "trainer_config": "/trainer/config",
            "trainer_service_status": "/trainer/service_status",
            "trainer_api": "/trainer/api/{path}",
            "live_risk": "/api/live-risk",
            "live_risk_html": "/api/live-risk/html",
            "live_risk_summary": "/api/live-risk/summary",
            "bars": "/bars/{symbol}",
            "bars_bulk": "/bars/bulk",
            "bars_status": "/bars/status",
            "bars_assets": "/bars/assets",
            "bars_gaps": "/bars/{symbol}/gaps",
            "bars_fill": "/bars/{symbol}/fill",
            "bars_fill_all": "/bars/fill/all",
            "bars_fill_status": "/bars/fill/status",
            "pine": "/pine",
            "pine_api": "/api/pine/modules",
            "backup_status": "/api/backup/status",
            "backup_export": "/api/backup/export",
            "backup_page": "/backup",
        },
    }


# ---------------------------------------------------------------------------
# Favicon — return 204 No Content to suppress browser 404 errors.
# The HTML dashboard uses an inline SVG data-URI favicon in <link rel="icon">,
# but browsers still request /favicon.ico automatically on first load.
# ---------------------------------------------------------------------------
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# DataFactory metrics — separate Prometheus registry from the main data service
# metrics so that the factory coordinator (running under supervisord) and the
# data service (running in the same container) can each maintain independent
# metric state without duplicate-registration errors.
#
# The factory coordinator writes Prometheus text to Redis under key
# ``ruby:factory:metrics`` on each HealthReporter cycle (60 s).  This
# endpoint reads that cached blob and forwards it to Prometheus.
# If the key is absent (factory not yet started) it falls back to calling
# ``metrics_output()`` directly from the health_reporter module.
# ---------------------------------------------------------------------------


@app.get("/factory/metrics", include_in_schema=False)
async def factory_metrics(request: Request) -> Response:
    """Expose DataFactory Prometheus metrics for scraping.

    Returns Prometheus text-format metrics from the DataFactory HealthReporter.
    The factory coordinator publishes metrics every 60 s; this endpoint serves
    the most recently cached snapshot.
    """
    try:
        from data_factory.health_reporter import metrics_output

        body, content_type = metrics_output()
        return Response(content=body, media_type=content_type)
    except Exception as exc:
        import logging

        logging.getLogger("api.factory_metrics").warning("factory_metrics error: %s", exc)
        return Response(content=b"", media_type="text/plain; version=0.0.4", status_code=200)


# ---------------------------------------------------------------------------
# Run directly: python -m lib.services.data.main
# or via entrypoint: python -m entrypoints.data.main
# ---------------------------------------------------------------------------
def main() -> None:
    """Start the Data Service via uvicorn. Called by entrypoints/data/main.py."""
    import uvicorn

    host = os.getenv("DATA_SERVICE_HOST", "0.0.0.0")
    port = int(os.getenv("DATA_SERVICE_PORT", "8000"))
    log_level = os.getenv("LOG_LEVEL", "info")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
