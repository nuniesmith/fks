"""
services/task_runner.py
========================
Async background task registry for web-triggered training and optimisation jobs.

Tasks run in a ThreadPoolExecutor so they don't block the event loop.
stdout / stderr is captured line-by-line and stored in a bounded ring buffer
per task so the web UI can stream live output via SSE.

Supported task types
--------------------
  optuna_single   — run Optuna optimisation for one asset (uses live tick data
                    from the worker's deque if *worker_instances* is wired in)
  optuna_all      — run Optuna for every enabled asset sequentially
  full_pipeline   — extended optimisation with hold-out validation + diagnostics
  custom_cmd      — run an arbitrary shell command (whitelisted)
  train_cnn       — launch CNN training as a subprocess
  evaluate_cnn    — launch CNN evaluation as a subprocess
  backtest        — launch backtest as a subprocess

Lifecycle
---------
  1. POST /api/tasks/run  → TaskRunner.submit() → returns task_id (UUID)
  2. GET  /api/tasks/{id} → TaskRunner.status() → JSON {state, output, result}
  3. GET  /api/tasks/{id}/stream → SSE stream of output lines (HTMX-friendly)
  4. POST /api/tasks/{id}/cancel → TaskRunner.cancel()
  5. GET  /api/tasks        → TaskRunner.list_tasks() → all tasks

Redis persistence
-----------------
Tasks are written to Redis on state changes so the web dashboard can read
them even across process restarts.  The in-memory registry is the source of
truth for running tasks; Redis is used for history.
"""

from __future__ import annotations

import asyncio
import subprocess
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from utils.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Whitelist: each entry is the exact sequence of leading tokens that a command
# must match.  A raw startswith() check is NOT used because it can be tricked
# by appending shell metacharacters or extra path components.
# ---------------------------------------------------------------------------
_ALLOWED_COMMAND_PREFIXES: list[tuple[str, ...]] = [
    ("python3.13", "-m", "ml.train"),
    ("python3.13", "-m", "ml.train_master"),
    ("python3.13", "-m", "ml.backtest"),
    ("python3.13", "-m", "ml.evaluate"),
    ("python3.13", "-m", "scripts.full_pipeline"),
    ("python3.13", "-m", "scripts.param_sweep"),
    ("python3.13", "-m", "scripts.export_features"),
]

# Max lines of output buffered per task.  Older lines are dropped automatically
# because output_lines is a deque with maxlen.
_OUTPUT_BUFFER_SIZE = 2000

# How long completed/failed tasks are kept in the in-memory registry (seconds).
_TASK_TTL = 3600 * 6  # 6 hours

# How often the background eviction loop runs (seconds).
_EVICT_INTERVAL = 300  # 5 minutes


# ═══════════════════════════════════════════════════════════════════
# Data model
# ═══════════════════════════════════════════════════════════════════


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskRecord:
    """In-memory record for one background task."""

    task_id: str
    task_type: str
    label: str
    asset: str | None
    params: dict
    state: TaskState = TaskState.PENDING
    submitted_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    # deque gives O(1) append + automatic eviction of old lines — no list
    # replacement needed, so shared references (used by optuna_all) stay valid.
    output_lines: deque[str] = field(default_factory=lambda: deque(maxlen=_OUTPUT_BUFFER_SIZE))
    result: dict | None = None
    error: str | None = None

    # Internal handles — not exposed via to_dict()
    _future: Any = field(default=None, repr=False)  # asyncio.Future
    _proc: subprocess.Popen | None = field(default=None, repr=False)  # active subprocess
    _output_lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False
    )  # guards output_lines reads/writes across threads

    @property
    def duration_sec(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.finished_at or time.time()
        return end - self.started_at

    def to_dict(self) -> dict:
        with self._output_lock:
            # Snapshot the last 200 lines for the API response.
            output_snapshot = list(self.output_lines)[-200:]
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "label": self.label,
            "asset": self.asset,
            "params": self.params,
            "state": self.state.value,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_sec": self.duration_sec,
            "output_lines": output_snapshot,
            "result": self.result,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _is_command_allowed(cmd_parts: list[str]) -> bool:
    """Return True only when *cmd_parts* begins with an allowed prefix tuple.

    Each prefix in ``_ALLOWED_COMMAND_PREFIXES`` is compared token-by-token
    against the leading tokens of *cmd_parts*, so extra CLI flags after the
    module name are fine, but shell metacharacters or unexpected module paths
    cannot smuggle through a startswith() match.
    """
    for prefix in _ALLOWED_COMMAND_PREFIXES:
        if len(cmd_parts) >= len(prefix) and tuple(cmd_parts[: len(prefix)]) == prefix:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════
# Task runner
# ═══════════════════════════════════════════════════════════════════


class TaskRunner:
    """Registry and executor for background training / optimisation tasks.

    Wiring
    ------
    Pass *worker_instances* from the supervisor so Optuna tasks can read
    live tick data directly from the worker deques without a Redis round-trip.

    Pass *store* so task results are persisted to Redis for the web UI.

    Usage
    -----
        runner = TaskRunner(worker_instances=workers, store=redis_store)
        task_id = await runner.submit("optuna_single", asset="btc", params={})
        status  = runner.status(task_id)
    """

    def __init__(
        self,
        worker_instances: list | None = None,
        store=None,
        config=None,
        max_concurrent: int = 2,
    ) -> None:
        self._workers = worker_instances or []
        self._store = store
        self._config = config
        self._pool = ThreadPoolExecutor(
            max_workers=max_concurrent, thread_name_prefix="task_runner"
        )
        self._tasks: dict[str, TaskRecord] = {}
        self._registry_lock = asyncio.Lock()
        self._evict_task: asyncio.Task | None = None

    # ── Lifecycle ──────────────────────────────────────────────────

    async def start(self) -> None:
        """Start background maintenance loop.  Call once after the event loop is running."""
        self._evict_task = asyncio.create_task(self._evict_loop(), name="task-runner-evict")

    async def _evict_loop(self) -> None:
        """Periodically remove completed tasks older than _TASK_TTL."""
        while True:
            await asyncio.sleep(_EVICT_INTERVAL)
            removed = self.evict_old_tasks()
            if removed:
                logger.debug("Evicted %d old task(s)", removed)

    # ── Public API ─────────────────────────────────────────────────

    async def submit(
        self,
        task_type: str,
        asset: str | None = None,
        params: dict | None = None,
        label: str | None = None,
    ) -> str:
        """Schedule a task and return its UUID.

        Args:
            task_type: One of the supported task type strings.
            asset:     Asset key (e.g. "btc") for per-asset tasks.
            params:    Extra parameters forwarded to the task function.
            label:     Human-readable label shown in the UI.

        Returns:
            task_id string (UUID4).

        Raises:
            ValueError: For unknown task types or disallowed commands.
        """
        task_id = str(uuid.uuid4())
        params = params or {}
        label = label or self._default_label(task_type, asset)

        rec = TaskRecord(
            task_id=task_id,
            task_type=task_type,
            label=label,
            asset=asset,
            params=params,
        )
        async with self._registry_lock:
            self._tasks[task_id] = rec

        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(self._pool, self._run_sync, task_id)
        rec._future = future

        # Background watcher — persists state to Redis when the future resolves.
        asyncio.create_task(
            self._watch(task_id, future),
            name=f"task-watch-{task_id[:8]}",
        )

        logger.info("Task submitted: %s [%s] asset=%s", task_id[:8], task_type, asset)
        return task_id

    def status(self, task_id: str) -> dict | None:
        """Return task status dict or None if not found."""
        rec = self._tasks.get(task_id)
        return rec.to_dict() if rec else None

    def list_tasks(self, limit: int = 50) -> list[dict]:
        """Return most recent *limit* tasks, newest first."""
        tasks = sorted(
            self._tasks.values(),
            key=lambda r: r.submitted_at,
            reverse=True,
        )
        return [t.to_dict() for t in tasks[:limit]]

    async def cancel(self, task_id: str) -> bool:
        """Request cancellation of a running task.

        Cancels the asyncio future *and* sends SIGTERM to any live subprocess
        so the OS-level process actually stops.

        Returns True if the task was found; False otherwise.
        """
        rec = self._tasks.get(task_id)
        if rec is None:
            return False

        # Cancel the asyncio future (prevents _run_sync from starting if still pending).
        if rec._future is not None and not rec._future.done():
            rec._future.cancel()

        # Terminate the subprocess if one is active.
        if rec._proc is not None and rec._proc.poll() is None:
            try:
                rec._proc.terminate()
                # Give it a moment; escalate to SIGKILL if needed.
                try:
                    rec._proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    rec._proc.kill()
                    logger.warning("Task %s: subprocess killed after SIGTERM timeout", task_id[:8])
            except OSError as exc:
                logger.warning("Task %s: error terminating subprocess: %s", task_id[:8], exc)

        if rec.state in (TaskState.PENDING, TaskState.RUNNING):
            rec.state = TaskState.CANCELLED
            rec.finished_at = time.time()

        logger.info("Task cancelled: %s", task_id[:8])
        return True

    async def output_stream(self, task_id: str):
        """Async generator that yields output lines as they arrive.

        Designed for use with SSE endpoints.  Yields previously buffered
        lines first, then polls for new lines until the task finishes.

        Args:
            task_id: Task UUID.

        Yields:
            str — SSE-formatted data line (``data: …\\n\\n``).
        """
        rec = self._tasks.get(task_id)
        if rec is None:
            yield "data: [task not found]\n\n"
            return

        sent_idx = 0

        # Yield buffered history first, then poll for new lines.
        while True:
            with rec._output_lock:
                current_lines = list(rec.output_lines)

            new_lines = current_lines[sent_idx:]
            for line in new_lines:
                yield f"data: {line}\n\n"
                sent_idx += 1

            if rec.state not in (TaskState.PENDING, TaskState.RUNNING):
                break

            await asyncio.sleep(0.25)

        # Final flush — any lines emitted between last poll and state change.
        with rec._output_lock:
            final_lines = list(rec.output_lines)
        for line in final_lines[sent_idx:]:
            yield f"data: {line}\n\n"

        yield "data: [DONE]\n\n"

    # ── Internal: sync task dispatch ───────────────────────────────

    def _run_sync(self, task_id: str) -> None:
        """Called in the thread pool — dispatch to the correct handler."""
        rec = self._tasks.get(task_id)
        if rec is None:
            logger.warning("_run_sync: task %s not found in registry", task_id[:8])
            return

        rec.state = TaskState.RUNNING
        rec.started_at = time.time()
        logger.info("Task started: %s [%s]", task_id[:8], rec.task_type)

        try:
            handler = self._get_handler(rec.task_type)
            result = handler(rec)
            rec.result = result
            rec.state = TaskState.SUCCESS
            logger.info("Task success: %s → %s", task_id[:8], result)
        except Exception as exc:
            rec.error = str(exc)
            # Don't overwrite CANCELLED state if cancel() raced us here.
            if rec.state != TaskState.CANCELLED:
                rec.state = TaskState.FAILED
            logger.error("Task failed: %s — %s", task_id[:8], exc, exc_info=True)
        finally:
            rec.finished_at = time.time()

    def _get_handler(self, task_type: str) -> Callable:
        handlers: dict[str, Callable] = {
            "optuna_single": self._handle_optuna_single,
            "optuna_all": self._handle_optuna_all,
            "full_pipeline": self._handle_full_pipeline,
            "custom_cmd": self._handle_custom_cmd,
            "train_cnn": self._handle_train_cnn,
            "evaluate_cnn": self._handle_evaluate_cnn,
            "backtest": self._handle_backtest,
        }
        if task_type not in handlers:
            raise ValueError(f"Unknown task type: {task_type!r}")
        return handlers[task_type]

    # ── Task handlers ──────────────────────────────────────────────

    def _handle_optuna_single(self, rec: TaskRecord) -> dict:
        """Run Optuna for a single asset using live tick data."""
        from utils.optimizer import run_optuna_sync

        asset_key = rec.asset
        worker = self._find_worker(asset_key)
        if worker is None:
            raise RuntimeError(f"No live worker found for asset: {asset_key!r}")

        cfg = self._config
        trades_snapshot = list(worker.trades)
        fees = cfg.optuna.fees
        # blended when post-only entries are enabled
        use_post_only = getattr(cfg.strategy, "use_post_only_entries", True)
        if use_post_only:
            fee_per_trade = (
                fees.get("maker_pct", 0.0002) + fees.get("taker_pct", 0.0006)
            ) / 2 + fees.get("slippage_pct", 0.0001)
        else:
            fee_per_trade = fees.get("taker_pct", 0.0006) + fees.get("slippage_pct", 0.0001)

        self._emit(rec, f"[optuna_single] Asset={asset_key}  ticks={len(trades_snapshot)}")
        self._emit(rec, f"  n_trials={cfg.optuna.n_trials}  timeout={cfg.optuna.timeout_sec}s")

        result = run_optuna_sync(
            trades_snapshot=trades_snapshot,
            min_ticks=cfg.candles.min_ticks,
            ao_fast=cfg.awesome_oscillator.fast,
            ao_slow=cfg.awesome_oscillator.slow,
            search_space=cfg.optuna.search_space,
            n_trials=cfg.optuna.n_trials,
            timeout_sec=cfg.optuna.timeout_sec,
            fee_per_trade=fee_per_trade,
        )

        if result is None:
            raise RuntimeError("Not enough candle data to optimise")

        worker.best_params.update(result)
        self._emit(rec, f"  → best_params: {result}")
        self._emit(rec, "  ✓ Params applied to live worker")

        return result

    def _handle_optuna_all(self, rec: TaskRecord) -> dict:
        """Run Optuna for every enabled asset sequentially."""
        results: dict[str, dict] = {}
        for worker in self._workers:
            self._emit(rec, f"\n── Optimising {worker.asset_key} ──")
            sub_rec = TaskRecord(
                task_id=rec.task_id,
                task_type="optuna_single",
                label=f"optuna_single:{worker.asset_key}",
                asset=worker.asset_key,
                params=rec.params,
            )
            # Share the parent's output buffer so all sub-task lines appear in
            # one stream.  deque mutation is in-place, so the reference stays
            # valid even as the deque grows and old entries are evicted.
            sub_rec.output_lines = rec.output_lines
            sub_rec._output_lock = rec._output_lock
            try:
                result = self._handle_optuna_single(sub_rec)
                results[worker.asset_key] = result
            except Exception as exc:
                results[worker.asset_key] = {"error": str(exc)}
                self._emit(rec, f"  ✗ {exc}")

        self._emit(rec, "\n── All assets complete ──")
        return results

    def _handle_full_pipeline(self, rec: TaskRecord) -> dict:
        """Extended optimisation with train/hold-out split and diagnostics."""
        from utils.optimizer import run_full_pipeline_sync

        asset_key = rec.asset
        worker = self._find_worker(asset_key)
        if worker is None:
            raise RuntimeError(f"No live worker found for asset: {asset_key!r}")

        cfg = self._config
        trades_snapshot = list(worker.trades)
        fees = cfg.optuna.fees
        fee_per_trade = fees.get("taker_pct", 0.0006) + fees.get("slippage_pct", 0.0001)

        n_trials = int(rec.params.get("n_trials", cfg.optuna.n_trials * 2))
        sampler = rec.params.get("sampler", "tpe")

        self._emit(rec, f"[full_pipeline] Asset={asset_key}  ticks={len(trades_snapshot)}")
        self._emit(rec, f"  n_trials={n_trials}  sampler={sampler}  fee={fee_per_trade:.4f}")
        self._emit(rec, "  80/20 train/hold-out split")

        result = run_full_pipeline_sync(
            trades_snapshot=trades_snapshot,
            min_ticks=cfg.candles.min_ticks,
            ao_fast=cfg.awesome_oscillator.fast,
            ao_slow=cfg.awesome_oscillator.slow,
            search_space=cfg.optuna.search_space,
            n_trials=n_trials,
            timeout_sec=cfg.optuna.timeout_sec * 2,
            fee_per_trade=fee_per_trade,
            sampler=sampler,
            min_holdout_pnl=-fee_per_trade * 4,  # reject clearly overfit params
        )

        if "error" in result:
            raise RuntimeError(result["error"])

        self._emit(rec, "\n  ── Results ──")
        self._emit(rec, f"  best_params     : {result['best_params']}")
        self._emit(rec, f"  train PnL       : {result['best_value']:+.6f}")
        self._emit(rec, f"  hold-out PnL    : {result['hold_out_pnl']:+.6f}")
        self._emit(rec, f"  trials completed: {result['n_trials_completed']}")
        diag = result.get("diagnostics", {})
        if diag.get("param_importance"):
            self._emit(rec, f"  param importance: {diag['param_importance']}")

        worker.best_params.update(result["best_params"])
        self._emit(rec, "  ✓ Params applied to live worker")

        return result

    def _handle_train_cnn(self, rec: TaskRecord) -> dict:
        """Launch CNN training as a subprocess and stream stdout."""
        asset_key = rec.asset
        models_dir = self._config.ml.models_dir if self._config else "models"

        cmd_parts = ["python3.13", "-m", "ml.train"]
        if asset_key:
            cmd_parts += ["--asset", asset_key]
        else:
            # No asset selected → train all enabled assets + master model
            cmd_parts += ["--all"]
        cmd_parts += ["--models-dir", models_dir]

        # Map UI param names to train.py CLI flag names.
        # The UI form uses "lookback" as the display label but train.py
        # expects --window.  "epochs" maps directly.
        _param_map = {"lookback": "window"}
        for k, v in rec.params.items():
            flag = _param_map.get(k, k)
            cmd_parts += [f"--{flag.replace('_', '-')}", str(v)]

        return self._run_subprocess(rec, cmd_parts)

    def _handle_evaluate_cnn(self, rec: TaskRecord) -> dict:
        """Launch CNN evaluation as a subprocess and stream stdout."""
        asset_key = rec.asset
        models_dir = self._config.ml.models_dir if self._config else "models"

        cmd_parts = ["python3.13", "-m", "ml.evaluate"]
        if asset_key:
            cmd_parts += ["--asset", asset_key]
        cmd_parts += ["--models-dir", models_dir]

        return self._run_subprocess(rec, cmd_parts)

    def _handle_backtest(self, rec: TaskRecord) -> dict:
        """Launch backtest as a subprocess and stream stdout."""
        asset_key = rec.asset
        cmd_parts = ["python3.13", "-m", "ml.backtest"]
        if asset_key:
            cmd_parts += ["--asset", asset_key]

        days = rec.params.get("days", 30)
        cmd_parts += ["--days", str(days)]

        return self._run_subprocess(rec, cmd_parts)

    def _handle_custom_cmd(self, rec: TaskRecord) -> dict:
        """Run an arbitrary whitelisted shell command.

        The command string is split into tokens and matched token-by-token
        against ``_ALLOWED_COMMAND_PREFIXES`` so that shell metacharacters or
        unexpected module paths cannot bypass the whitelist via a naive
        startswith() check.
        """
        cmd_str = rec.params.get("cmd", "").strip()
        cmd_parts = cmd_str.split()

        if not _is_command_allowed(cmd_parts):
            allowed_strs = [" ".join(p) for p in _ALLOWED_COMMAND_PREFIXES]
            raise ValueError(
                f"Command not in allowlist: {cmd_str!r}\n"
                f"Allowed prefixes:\n" + "\n".join(f"  {s}" for s in sorted(allowed_strs))
            )

        return self._run_subprocess(rec, cmd_parts)

    # ── Subprocess helper ──────────────────────────────────────────

    def _run_subprocess(self, rec: TaskRecord, cmd: list[str]) -> dict:
        """Run *cmd* as a subprocess, capturing and streaming output.

        The ``Popen`` object is stored on *rec* so that ``cancel()`` can
        send SIGTERM/SIGKILL to the OS-level process.

        Args:
            rec: TaskRecord whose output_lines buffer receives each line.
            cmd: Command + arguments list (never passed to a shell).

        Returns:
            Dict with returncode and last 20 output lines.

        Raises:
            RuntimeError: When the process exits with a non-zero code.
        """
        self._emit(rec, f"$ {' '.join(cmd)}")
        self._emit(rec, "─" * 60)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # line-buffered
        )
        rec._proc = proc

        for line in proc.stdout:  # type: ignore[union-attr]
            self._emit(rec, line.rstrip())

        proc.wait()
        rec._proc = None  # Process is done; clear the handle.

        self._emit(rec, "─" * 60)
        self._emit(rec, f"Exit code: {proc.returncode}")

        if proc.returncode != 0:
            raise RuntimeError(f"Subprocess exited with code {proc.returncode}")

        return {
            "returncode": proc.returncode,
            "output_tail": list(rec.output_lines)[-20:],
        }

    # ── Internals ─────────────────────────────────────────────────

    def _emit(self, rec: TaskRecord, line: str) -> None:
        """Append *line* to the task's output buffer (thread-safe).

        The deque's maxlen handles eviction automatically — no list replacement
        needed, so shared references from ``_handle_optuna_all`` remain valid.
        """
        ts = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {line}"
        with rec._output_lock:
            rec.output_lines.append(entry)

    def _find_worker(self, asset_key: str | None):
        """Return the AssetWorker for *asset_key*, or None."""
        if not asset_key:
            return None
        for w in self._workers:
            if w.asset_key == asset_key:
                return w
        return None

    async def _watch(self, task_id: str, future: asyncio.Future) -> None:
        """Wait for the executor future and persist result to Redis."""
        try:
            await future
        except asyncio.CancelledError:
            logger.debug("Task %s: future cancelled", task_id[:8])
        except Exception as exc:
            # _run_sync already sets rec.state = FAILED, but log here too so
            # unexpected raises don't vanish silently.
            logger.error("Task %s: unexpected watcher error: %s", task_id[:8], exc, exc_info=True)

        rec = self._tasks.get(task_id)
        if rec is None:
            logger.warning("_watch: task %s disappeared from registry", task_id[:8])
            return

        # Persist to Redis.
        if self._store is not None:
            try:
                await self._store.record_task(task_id, rec.to_dict())
            except Exception as exc:
                logger.warning("Task %s: Redis persist error: %s", task_id[:8], exc)

    @staticmethod
    def _default_label(task_type: str, asset: str | None) -> str:
        labels = {
            "optuna_single": "Optimise params",
            "optuna_all": "Optimise all assets",
            "full_pipeline": "Full pipeline (train+validate)",
            "train_cnn": "Train CNN model",
            "evaluate_cnn": "Evaluate CNN model",
            "backtest": "Backtest strategy",
            "custom_cmd": "Custom command",
        }
        base = labels.get(task_type, task_type)
        return f"{base} — {asset}" if asset else base

    # ── Cleanup ───────────────────────────────────────────────────

    def evict_old_tasks(self) -> int:
        """Remove completed tasks older than _TASK_TTL.  Returns eviction count."""
        cutoff = time.time() - _TASK_TTL
        to_remove = [
            tid
            for tid, rec in self._tasks.items()
            if rec.state not in (TaskState.PENDING, TaskState.RUNNING)
            and rec.finished_at is not None
            and rec.finished_at < cutoff
        ]
        for tid in to_remove:
            del self._tasks[tid]
        return len(to_remove)

    def shutdown(self) -> None:
        """Shut down the thread pool (call from supervisor finally block)."""
        if self._evict_task is not None:
            self._evict_task.cancel()
        self._pool.shutdown(wait=False)
