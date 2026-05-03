"""
web/routes/tasks.py
====================
FastAPI routes for the background task runner — JSON API only.

Mount these on the main application via:

    from web.routes.tasks import create_task_router
    app.include_router(create_task_router(task_runner, config), prefix="/tasks")

Routes
------
  GET  /tasks/api/list             — JSON list of all tasks (last 50)
  GET  /tasks/api/{id}             — JSON status of one task
  GET  /tasks/api/types            — JSON list of available task type definitions
  POST /tasks/api/run              — Submit a new task → {task_id}
  POST /tasks/api/{id}/cancel      — Cancel a running task
  GET  /tasks/api/{id}/stream      — SSE stream of task output
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from services.task_runner import TaskRunner


def create_task_router(
    task_runner: TaskRunner,
    config: Any,
) -> APIRouter:
    """Build and return the tasks APIRouter (JSON only).

    Args:
        task_runner: Shared TaskRunner instance from supervisor.
        config:      FuturesConfig — used to enumerate enabled assets.

    Returns:
        APIRouter ready to be included on the FastAPI app.
    """
    router = APIRouter(tags=["tasks"])

    # ── JSON API ──────────────────────────────────────────────────

    @router.get("/api/types")
    async def task_types() -> JSONResponse:
        """Return the list of available task type definitions."""
        assets = list(config.enabled_assets.keys()) if config else []
        return JSONResponse({"types": _task_type_definitions(assets)})

    @router.get("/api/list")
    async def list_tasks(limit: int = 50) -> JSONResponse:
        """Return JSON list of tasks (most recent first)."""
        tasks = task_runner.list_tasks(limit=limit)
        task_runner.evict_old_tasks()
        return JSONResponse({"tasks": tasks, "count": len(tasks)})

    @router.get("/api/{task_id}")
    async def get_task(task_id: str) -> JSONResponse:
        """Return JSON status of a single task."""
        status = task_runner.status(task_id)
        if status is None:
            return JSONResponse({"error": "Not found"}, status_code=404)
        return JSONResponse(status)

    @router.post("/api/run")
    async def run_task(body: dict) -> JSONResponse:
        """Submit a new task. Body: {task_type, asset?, params?}."""
        task_type = body.get("task_type")
        asset = body.get("asset")
        params = body.get("params", {})
        if not task_type:
            return JSONResponse({"error": "task_type required"}, status_code=400)
        task_id = task_runner.submit(task_type, asset=asset, params=params)
        return JSONResponse({"task_id": task_id, "status": "queued"})

    @router.post("/api/{task_id}/cancel")
    async def cancel_task(task_id: str) -> JSONResponse:
        """Cancel a running task."""
        ok = task_runner.cancel(task_id)
        if not ok:
            return JSONResponse({"error": "Not found or already finished"}, status_code=404)
        return JSONResponse({"ok": True, "task_id": task_id})

    @router.get("/api/{task_id}/stream")
    async def stream_task(task_id: str) -> StreamingResponse:
        """SSE stream of task output lines. Each event is a JSON object."""

        async def generator():
            async for line in task_runner.stream_output(task_id):
                import json

                yield f"data: {json.dumps({'line': line})}\n\n"
            yield 'data: {"done": true}\n\n'

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return router


# ═══════════════════════════════════════════════════════════════════
# Task type metadata returned to the frontend
# ═══════════════════════════════════════════════════════════════════


def _task_type_definitions(assets: list[str]) -> list[dict]:
    """Return the list of task type definitions for the UI."""
    return [
        {
            "id": "optuna_single",
            "label": "Optimise EMA params (single asset)",
            "description": (
                "Runs Optuna to find the best fast/slow EMA periods for one asset "
                "using its live tick buffer. Applies best params immediately."
            ),
            "needs_asset": True,
            "params": [],
        },
        {
            "id": "optuna_all",
            "label": "Optimise EMA params (all assets)",
            "description": (
                "Runs Optuna sequentially for every enabled asset. "
                "Takes longer but ensures all workers have fresh params."
            ),
            "needs_asset": False,
            "params": [],
        },
        {
            "id": "full_pipeline",
            "label": "Full optimisation pipeline",
            "description": (
                "Extended Optuna run with 80/20 train/hold-out split, "
                "param importance analysis, and hold-out P&L validation. "
                "Uses 2× the normal trial count."
            ),
            "needs_asset": True,
            "params": [
                {
                    "name": "n_trials",
                    "type": "number",
                    "default": 200,
                    "help": "Number of Optuna trials (default 2× config)",
                },
                {
                    "name": "sampler",
                    "type": "select",
                    "options": ["tpe", "random"],
                    "default": "tpe",
                    "help": "Optuna sampler algorithm",
                },
            ],
        },
        {
            "id": "train_cnn",
            "label": "Train CNN model",
            "description": (
                "Launch ml.train for one asset (or all if no asset selected). "
                "Streams training output live. This may take several minutes."
            ),
            "needs_asset": True,
            "params": [
                {"name": "epochs", "type": "number", "default": 50, "help": "Training epochs"},
                {"name": "lookback", "type": "number", "default": 60, "help": "Candle lookback window (bars)"},
            ],
        },
        {
            "id": "evaluate_cnn",
            "label": "Evaluate CNN model",
            "description": (
                "Run ml.evaluate to score the current model on recent data and print accuracy, precision, recall, F1."
            ),
            "needs_asset": True,
            "params": [],
        },
        {
            "id": "backtest",
            "label": "Backtest strategy",
            "description": (
                "Run ml.backtest using the current best_params and CNN model "
                "on recent OHLCV data. Reports win rate, Sharpe, max drawdown."
            ),
            "needs_asset": True,
            "params": [
                {"name": "days", "type": "number", "default": 30, "help": "Days of history to backtest over"},
            ],
        },
    ]
