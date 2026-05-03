"""
web/app.py
===========
Trading API — FastAPI JSON-only Backend
=======================================
Pure REST/JSON API. All HTML rendering has been removed.
The Svelte frontend in src/web/ consumes these endpoints.

API Routes:
    GET  /api/health                 — JSON health check
    GET  /api/dashboard              — Dashboard data (workers, stats, PnL, gate)
    GET  /api/workers                — Worker heartbeats
    GET  /api/assets                 — Asset registry
    GET  /api/signals                — Recent signals feed (?asset=&limit=)
    GET  /api/reports                — AI report (?period=day|week|month&date=)
    GET  /api/pnl                    — PnL summary (?days=)
    GET  /api/cnn/status             — CNN/ML status per asset
    GET  /api/trades                 — Trade history (?days=&asset=)
    GET  /api/trades/export          — CSV trade export (?days=&asset=)
    GET  /api/logs/dates             — Available log file dates
    GET  /api/logs/live              — Live ring-buffer log entries (?since=&level=&name=)
    GET  /api/logs/file              — File log entries (?date=&level=&name=)
    GET  /api/logs/export            — Download log file (?date=)
    GET  /api/export/bundle          — ZIP bundle (trades + signals + logs) (?days=)

Bot Control:
    GET  /api/bot/status             — Supervisor + worker status
    POST /api/bot/worker/{asset}/stop
    POST /api/bot/worker/{asset}/start
    POST /api/bot/worker/{asset}/restart

Tasks (mounted at /tasks):
    GET  /tasks/api/list             — All tasks
    GET  /tasks/api/{id}             — Single task status
    POST /tasks/api/run              — Submit a task
    POST /tasks/api/{id}/cancel      — Cancel a task
    GET  /tasks/api/{id}/stream      — SSE stream of task output

Environment:
    REDIS_URL           redis://localhost:6379/0
    REDIS_PASSWORD      redis auth password
    WEB_HOST            0.0.0.0
    WEB_PORT            8080
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from services.asset_registry import ASSET_REGISTRY
from services.config_loader import load_config
from services.redis_store import RedisStore
from services.task_runner import TaskRunner
from utils.logging_config import get_logger, get_ring_buffer, setup_logging
from web.routes.tasks import create_task_router

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
setup_logging(service="web")
logger = get_logger("web")


# ---------------------------------------------------------------------------
# Helper utilities (used in JSON serialisation, not templates)
# ---------------------------------------------------------------------------


def _pnl_class(val: float) -> str:
    if val > 0:
        return "pos"
    if val < 0:
        return "neg"
    return "zero"


def _fmt_pnl(val: float) -> str:
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.4f}"


def _age(ts: float) -> str:
    diff = time.time() - ts
    if diff < 60:
        return f"{int(diff)}s ago"
    if diff < 3600:
        return f"{int(diff / 60)}m ago"
    return f"{int(diff / 3600)}h ago"


def _heartbeat_alive(ts: float, ttl: int = 120) -> bool:
    return (time.time() - ts) < ttl


def _fmt_pct(val: float) -> str:
    return f"{val * 100:.1f}%"


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m {int(seconds % 60)}s"
    return f"{int(seconds / 3600)}h {int((seconds % 3600) / 60)}m"


def _fmt_fee(val: float) -> str:
    if val == 0:
        return "$0.00"
    return f"-${abs(val):.6f}"


def _enrich_heartbeat(asset_key: str, data: dict) -> dict:
    """Attach derived fields (alive, age_str, dir_display) to a heartbeat dict."""
    last_seen = data.get("last_seen", 0)
    status = data.get("status", {})
    alive = _heartbeat_alive(last_seen)
    stack_dir = status.get("stack_dir")
    if stack_dir == "buy":
        dir_display = "LONG"
    elif stack_dir == "sell":
        dir_display = "SHORT"
    else:
        dir_display = "FLAT"
    return {
        "asset": asset_key,
        "alive": alive,
        "last_seen": last_seen,
        "age_str": _age(last_seen) if last_seen else None,
        "dir_display": dir_display,
        **data,
    }


# ---------------------------------------------------------------------------
# Log helpers
# ---------------------------------------------------------------------------


def _list_log_dates() -> list[str]:
    log_dir_env = os.getenv("LOG_DIR", "").strip()
    if not log_dir_env:
        return []
    log_dir = Path(log_dir_env)
    if not log_dir.is_dir():
        return []
    dates = []
    for p in log_dir.glob("*.log"):
        stem = p.stem
        if len(stem) == 10 and stem[4] == "-" and stem[7] == "-":
            dates.append(stem)
    today_file = log_dir / "futures.log"
    if today_file.exists():
        today_str = time.strftime("%Y-%m-%d", time.gmtime())
        if today_str not in dates:
            dates.append(today_str)
    return sorted(dates, reverse=True)


def _read_log_file(date_str: str) -> str:
    log_dir_env = os.getenv("LOG_DIR", "").strip()
    if not log_dir_env:
        return ""
    log_dir = Path(log_dir_env)
    today_str = time.strftime("%Y-%m-%d", time.gmtime())
    candidate = log_dir / "futures.log" if date_str == today_str else log_dir / f"{date_str}.log"
    if not candidate.exists():
        return ""
    try:
        return candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _parse_log_lines(raw: str, level: str = "", name: str = "") -> list[dict]:
    entries: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        lv = "INFO"
        for candidate in ("ERROR", "WARNING", "WARN", "DEBUG", "CRITICAL"):
            if f"[{candidate}]" in line:
                lv = candidate
                break
        if level and level.upper() not in lv:
            continue
        if name and name.lower() not in line.lower():
            continue
        entries.append({"ts": 0.0, "level": lv, "name": "", "msg": line})
    return entries


def _build_trades_csv(trades: list[dict]) -> str:
    fieldnames = [
        "timestamp",
        "date",
        "asset",
        "side",
        "entry_price",
        "exit_price",
        "size_lots",
        "contract_size",
        "notional_usdt",
        "pnl_usdt",
        "pnl_pct",
        "maker_fee",
        "taker_fee",
        "total_fees",
        "net_pnl",
        "regime",
        "quality",
        "duration_sec",
        "entry_type",
        "exit_type",
    ]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    for t in trades:
        w.writerow({k: t.get(k, "") for k in fieldnames})
    return buf.getvalue()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(
    store: RedisStore | None = None,
    config: Any | None = None,
    task_runner: TaskRunner | None = None,
) -> FastAPI:
    """Create the FastAPI application (API-only, no templates)."""

    _resolved_config = config or load_config()
    state: dict[str, Any] = {
        "store": store,
        "config": _resolved_config,
        "task_runner": task_runner,
    }

    _configured_assets = {key: ac for key, ac in _resolved_config.assets.items()}

    # ── Lifespan ──────────────────────────────────────────────────

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state["store"] is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            redis_pw = os.getenv("REDIS_PASSWORD") or None
            s = RedisStore(redis_url=redis_url, password=redis_pw)
            await s.connect()
            state["store"] = s
            logger.info("Trading API started (standalone) — redis=%s", redis_url)
            yield
            await s.close()
        else:
            logger.info("Trading API started (embedded)")
            yield
        logger.info("Trading API stopped")

    # ── Create app ────────────────────────────────────────────────

    application = FastAPI(
        title="Trading API",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
    )

    # Allow the Svelte dev server (or any configured frontend origin) to call this API.
    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Task router ───────────────────────────────────────────────

    task_router = create_task_router(
        task_runner=state["task_runner"],
        config=state["config"],
    )
    application.include_router(task_router, prefix="/tasks")

    # ── Store accessor ────────────────────────────────────────────

    def get_store() -> RedisStore:
        s = state["store"]
        if s is None:
            raise RuntimeError("Redis store not yet initialised")
        return s

    # ── Signal fetch helper ───────────────────────────────────────

    async def _fetch_signals(s: RedisStore, asset: str = "", limit: int = 100) -> list[dict]:
        if asset:
            sigs = await s.get_signals(asset, limit=limit)
            for sig in sigs:
                sig.setdefault("_asset", asset)
            return sigs
        heartbeats = await s.get_heartbeats()
        all_sigs: list[dict] = []
        for a in heartbeats:
            sigs = await s.get_signals(a, limit=20)
            for sig in sigs:
                sig.setdefault("_asset", a)
            all_sigs.extend(sigs)
        all_sigs.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return all_sigs[:limit]

    # ================================================================== #
    #  Health
    # ================================================================== #

    @application.get("/api/health")
    async def health() -> JSONResponse:
        s = get_store()
        bot_status = await s.get_bot_status()
        return JSONResponse(
            {
                "status": "ok",
                "redis": s.connected,
                "bot": bot_status,
                "timestamp": time.time(),
            }
        )

    # ================================================================== #
    #  Dashboard
    # ================================================================== #

    @application.get("/api/dashboard")
    async def dashboard() -> JSONResponse:
        s = get_store()
        heartbeats = await s.get_heartbeats()
        stats = await s.get_aggregate_stats(days=1)
        daily_pnl = await s.get_daily_pnl()
        bot = await s.get_bot_status()
        gate_stats = await s.get_gate_stats_all()
        return JSONResponse(
            {
                "workers": {k: _enrich_heartbeat(k, v) for k, v in heartbeats.items()},
                "stats": stats,
                "daily_pnl": daily_pnl,
                "bot_status": bot,
                "gate_stats": gate_stats,
                "timestamp": time.time(),
            }
        )

    # ================================================================== #
    #  Workers
    # ================================================================== #

    @application.get("/api/workers")
    async def workers() -> JSONResponse:
        s = get_store()
        heartbeats = await s.get_heartbeats()
        return JSONResponse({k: _enrich_heartbeat(k, v) for k, v in heartbeats.items()})

    # ================================================================== #
    #  Bot Control
    # ================================================================== #

    @application.get("/api/bot/status")
    async def bot_status() -> JSONResponse:
        s = get_store()
        status = await s.get_bot_status()
        heartbeats = await s.get_heartbeats()
        return JSONResponse(
            {
                "status": status,
                "workers": {
                    k: {
                        "alive": _heartbeat_alive(v.get("last_seen", 0)),
                        "last_seen": v.get("last_seen", 0),
                        "age_str": _age(v.get("last_seen", 0)) if v.get("last_seen") else None,
                        "status": v.get("status", {}),
                    }
                    for k, v in heartbeats.items()
                },
            }
        )

    @application.post("/api/bot/worker/{asset}/stop")
    async def stop_worker(asset: str) -> JSONResponse:
        s = get_store()
        await s.request_worker_action(asset, "stop")
        logger.info("API requested STOP for worker: %s", asset)
        return JSONResponse({"ok": True, "action": "stop", "asset": asset})

    @application.post("/api/bot/worker/{asset}/start")
    async def start_worker(asset: str) -> JSONResponse:
        s = get_store()
        await s.request_worker_action(asset, "start")
        logger.info("API requested START for worker: %s", asset)
        return JSONResponse({"ok": True, "action": "start", "asset": asset})

    @application.post("/api/bot/worker/{asset}/restart")
    async def restart_worker(asset: str) -> JSONResponse:
        s = get_store()
        await s.request_worker_action(asset, "restart")
        logger.info("API requested RESTART for worker: %s", asset)
        return JSONResponse({"ok": True, "action": "restart", "asset": asset})

    # ================================================================== #
    #  Assets
    # ================================================================== #

    @application.get("/api/assets")
    async def assets_list() -> JSONResponse:
        data = [
            {
                "key": key,
                "symbol": ac.symbol,
                "base": ac.base,
                "leverage": ac.leverage,
                "margin_pct": ac.margin_pct,
                "enabled": ac.enabled,
                "spec": ASSET_REGISTRY.get(key),
            }
            for key, ac in _configured_assets.items()
        ]
        return JSONResponse({"assets": data})

    # ================================================================== #
    #  Signals
    # ================================================================== #

    @application.get("/api/signals")
    async def signals(asset: str = "", limit: int = 100) -> JSONResponse:
        s = get_store()
        sigs = await _fetch_signals(s, asset=asset, limit=limit)
        heartbeats = await s.get_heartbeats()
        return JSONResponse(
            {
                "signals": sigs,
                "known_assets": sorted(heartbeats.keys()),
                "selected_asset": asset,
                "limit": limit,
            }
        )

    @application.post("/api/signals/{signal_id}/approve")
    async def approve_signal(signal_id: str) -> JSONResponse:
        """Mark a staged signal as approved."""
        s = get_store()
        ok = await s.update_signal_status(signal_id, "approved")
        if not ok:
            return JSONResponse({"error": "Signal not found"}, status_code=404)
        logger.info("Signal approved: %s", signal_id)
        return JSONResponse({"ok": True, "id": signal_id, "status": "approved"})

    @application.post("/api/signals/{signal_id}/reject")
    async def reject_signal(signal_id: str) -> JSONResponse:
        """Mark a staged signal as rejected."""
        s = get_store()
        ok = await s.update_signal_status(signal_id, "rejected")
        if not ok:
            return JSONResponse({"error": "Signal not found"}, status_code=404)
        logger.info("Signal rejected: %s", signal_id)
        return JSONResponse({"ok": True, "id": signal_id, "status": "rejected"})

    @application.get("/api/alerts")
    async def alerts(limit: int = 20) -> JSONResponse:
        """Return recent system alerts (circuit breaker trips, risk events, etc.)."""
        s = get_store()
        raw = await s.get_alerts(limit=limit)
        return JSONResponse({"alerts": raw})

    # ================================================================== #
    #  Reports
    # ================================================================== #

    @application.get("/api/reports")
    async def reports(period: str = "day", date: str = "") -> JSONResponse:
        s = get_store()
        available_dates = await s.list_report_dates(period)
        if date and date != "latest":
            report = await s.get_report_by_date(period, date)
            selected_date = date
        else:
            report = await s.get_latest_report(period)
            selected_date = available_dates[0] if available_dates else ""
        return JSONResponse(
            {
                "report": report,
                "period": period,
                "selected_date": selected_date,
                "available_dates": available_dates,
            }
        )

    # ================================================================== #
    #  PnL
    # ================================================================== #

    @application.get("/api/pnl")
    async def pnl(days: int = 7) -> JSONResponse:
        s = get_store()
        stats = await s.get_aggregate_stats(days=days)
        history = await s.get_pnl_history(days=days)
        daily_pnl = await s.get_daily_pnl()
        fee_summary = await s.get_fee_summary(days=days)
        return JSONResponse(
            {
                "stats": stats,
                "history": history,
                "daily_pnl": daily_pnl,
                "fee_summary": fee_summary,
                "days": days,
            }
        )

    # ================================================================== #
    #  CNN Status
    # ================================================================== #

    @application.get("/api/cnn/status")
    async def cnn_status() -> JSONResponse:
        s = get_store()
        heartbeats = await s.get_heartbeats()
        models_dir = Path(state["config"].ml.models_dir)
        ml_config = state["config"].ml
        result: dict[str, Any] = {}
        for asset_key, data in heartbeats.items():
            hb_status = data.get("status", {})
            meta_path = models_dir / f"cnn_{asset_key}.json"
            meta = None
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                except Exception:
                    pass
            result[asset_key] = {
                "cnn_enabled": hb_status.get("cnn_enabled", False),
                "cnn_signal": hb_status.get("cnn_signal", "flat"),
                "cnn_confidence": hb_status.get("cnn_confidence", 0.0),
                "master_risk_score": hb_status.get("master_risk_score", 0.0),
                "master_halted": hb_status.get("master_halted", False),
                "model_meta": meta,
            }
        return JSONResponse(
            {
                "assets": result,
                "ml_config": {
                    "enabled": ml_config.enabled,
                    "min_confidence": ml_config.min_confidence,
                    "master_risk_threshold": ml_config.master_risk_threshold,
                },
            }
        )

    # ================================================================== #
    #  Trades
    # ================================================================== #

    @application.get("/api/trades")
    async def trades(days: int = 7, asset: str = "") -> JSONResponse:
        s = get_store()
        trades_list = await s.get_trades_for_export(days=days, asset=asset if asset else None)
        fee_summary = await s.get_fee_summary(days=days)
        heartbeats = await s.get_heartbeats()
        return JSONResponse(
            {
                "trades": trades_list,
                "fee_summary": fee_summary,
                "known_assets": sorted(heartbeats.keys()),
                "selected_asset": asset,
                "days": days,
            }
        )

    @application.get("/api/trades/export")
    async def export_trades_csv(days: int = 30, asset: str = "") -> StreamingResponse:
        s = get_store()
        trades_list = await s.get_trades_for_export(
            days=days,
            asset=asset if asset else None,
        )
        csv_content = _build_trades_csv(trades_list)
        filename = f"futures_trades_{days}d" + (f"_{asset}" if asset else "") + ".csv"
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    # ================================================================== #
    #  Logs
    # ================================================================== #

    @application.get("/api/logs/dates")
    async def log_dates() -> JSONResponse:
        return JSONResponse({"dates": _list_log_dates()})

    @application.get("/api/logs/live")
    async def logs_live(since: float = 0.0, level: str = "", name: str = "") -> JSONResponse:
        ring = get_ring_buffer()
        entries: list[dict] = []
        if ring is not None:
            entries = ring.get_since(since_ts=since, level=level, name=name)
        return JSONResponse(
            {
                "entries": entries,
                "has_live": ring is not None,
                "ts": time.time(),
            }
        )

    @application.get("/api/logs/file")
    async def logs_file(date: str = "", level: str = "", name: str = "") -> JSONResponse:
        if not date:
            date = time.strftime("%Y-%m-%d", time.gmtime())
        available_dates = _list_log_dates()
        raw = _read_log_file(date)
        entries = _parse_log_lines(raw, level=level, name=name) if raw else []
        return JSONResponse(
            {
                "entries": entries,
                "date": date,
                "available_dates": available_dates,
                "has_files": bool(available_dates),
            }
        )

    @application.get("/api/logs/export")
    async def export_log_file(date: str = "") -> StreamingResponse:
        if not date:
            date = time.strftime("%Y-%m-%d", time.gmtime())
        content = _read_log_file(date) or f"# No log file found for {date}\n"
        return StreamingResponse(
            iter([content]),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=futures_logs_{date}.txt"},
        )

    @application.get("/api/export/bundle")
    async def export_bundle(days: int = 7) -> StreamingResponse:
        s = get_store()

        trades_list = await s.get_trades_for_export(days=days)
        trades_csv = _build_trades_csv(trades_list)

        heartbeats = await s.get_heartbeats()
        all_signals: list[dict] = []
        for asset_key in heartbeats:
            sigs = await s.get_signals(asset_key, limit=500)
            for sig in sigs:
                sig.setdefault("_asset", asset_key)
            all_signals.extend(sigs)
        all_signals.sort(key=lambda x: x.get("timestamp", 0))

        sig_fields = ["timestamp", "_asset", "side", "price", "size", "quality", "regime", "reason"]
        sig_buf = io.StringIO()
        sig_writer = csv.DictWriter(sig_buf, fieldnames=sig_fields, extrasaction="ignore")
        sig_writer.writeheader()
        for sig in all_signals:
            sig_writer.writerow({k: sig.get(k, "") for k in sig_fields})

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("trades.csv", trades_csv)
            zf.writestr("signals.csv", sig_buf.getvalue())
            for date_str in _list_log_dates()[:days]:
                content = _read_log_file(date_str)
                if content:
                    zf.writestr(f"logs/{date_str}.log", content)

        zip_buf.seek(0)
        today = time.strftime("%Y-%m-%d", time.gmtime())
        return StreamingResponse(
            iter([zip_buf.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=futures_export_{today}_{days}d.zip"},
        )

    return application


# ---------------------------------------------------------------------------
# Standalone app instance — for ``uvicorn web.app:app`` in dev
# ---------------------------------------------------------------------------
app = create_app()
