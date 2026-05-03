"""
CNN Retraining Scheduler

Drop this into the supervisor loop alongside the existing Optuna scheduler.
It watches per-asset F1 scores and triggers a CNN retrain when:
  1. A scheduled interval has elapsed (default: 24h)
  2. A per-asset directional F1 drops below a drift threshold

Usage in main.py supervisor:
    from src.ml.cnn_scheduler import CNNRetrainScheduler

    # In supervisor __init__ or setup:
    self.cnn_scheduler = CNNRetrainScheduler(
        redis=self.redis,
        gpu_url=os.getenv("GPU_TRAINER_URL"),
        models_dir=Path(config.ml.models_dir),
    )

    # In supervisor._supervisor_loop() alongside the Optuna check:
    await self.cnn_scheduler.tick(self.task_runner)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("cnn_scheduler")

# ── Constants ─────────────────────────────────────────────────────────────────

_LAST_RETRAIN_KEY   = "futures:cnn:last_retrain"
_RETRAIN_LOCK_KEY   = "futures:cnn:retrain_lock"
_F1_SNAPSHOT_KEY    = "futures:cnn:f1_snapshot"       # hash: asset → last_known_f1
_LOCK_TTL           = 3600 * 8                        # 8h lock prevents double-trigger

DEFAULT_INTERVAL_H  = 24     # retrain at least every 24h
DEFAULT_DRIFT_DELTA = 0.08   # trigger if avg directional F1 drops >8 points
DEFAULT_MIN_ASSETS  = 3      # need at least this many assets to bother retraining


class CNNRetrainScheduler:
    """
    Periodically checks whether a CNN retrain is warranted and triggers one
    via the TaskRunner.  Designed to run once per supervisor tick (every 60s).

    Two trigger conditions (either one fires a retrain):
      SCHEDULED  — `interval_hours` have passed since last retrain
      DRIFT      — avg directional F1 across live models has dropped by
                   more than `drift_delta` since the last recorded snapshot

    Retraining is off by default in the config (ml.enabled=false) but the
    scheduler still snapshots F1 scores so it's ready to go when you enable it.
    """

    def __init__(
        self,
        redis: Any,
        gpu_url: str | None = None,
        models_dir: Path | None = None,
        interval_hours: float = DEFAULT_INTERVAL_H,
        drift_delta: float = DEFAULT_DRIFT_DELTA,
        min_assets: int = DEFAULT_MIN_ASSETS,
        task_key_gpu: str = "gpu_train_standard",
        task_key_local: str = "train_standard",
    ) -> None:
        self._redis         = redis
        self._gpu_url       = gpu_url
        self._models_dir    = models_dir or Path("/app/models")
        self._interval      = timedelta(hours=interval_hours)
        self._drift_delta   = drift_delta
        self._min_assets    = min_assets
        self._task_key_gpu  = task_key_gpu
        self._task_key_local = task_key_local

    # ── Public ────────────────────────────────────────────────────────────────

    async def tick(self, task_runner: Any) -> None:
        """Call once per supervisor loop iteration."""
        try:
            await self._check_and_maybe_retrain(task_runner)
        except Exception:
            log.exception("CNN scheduler tick failed")

    async def record_inference_f1(self, asset: str, directional_f1: float) -> None:
        """
        Called by AssetWorker after each inference cycle to keep the F1
        snapshot up to date.  The scheduler uses this to detect drift.
        """
        await self._redis.hset(
            _F1_SNAPSHOT_KEY, asset, f"{directional_f1:.6f}"
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _check_and_maybe_retrain(self, task_runner: Any) -> None:
        # Acquire a non-blocking distributed lock
        acquired = await self._redis.set(
            _RETRAIN_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL
        )
        if not acquired:
            return   # another process/tick already holds the lock

        try:
            trigger, reason = await self._should_retrain()
            if not trigger:
                return

            log.info("CNN retrain triggered: %s", reason)
            key = self._task_key_gpu if self._gpu_url else self._task_key_local
            task_id = await task_runner.submit(key)
            log.info("CNN retrain task submitted: task_id=%s key=%s", task_id, key)

            await self._redis.set(
                _LAST_RETRAIN_KEY,
                datetime.now(tz=timezone.utc).isoformat(),
            )
            # Refresh snapshot baseline after submitting so we don't
            # immediately re-trigger on the same drift
            await self._refresh_snapshot_baseline()

        finally:
            # Release lock only if we just set it (avoid deleting someone else's)
            val = await self._redis.get(_RETRAIN_LOCK_KEY)
            if val == b"1":
                await self._redis.delete(_RETRAIN_LOCK_KEY)

    async def _should_retrain(self) -> tuple[bool, str]:
        # 1. Scheduled interval
        last_raw = await self._redis.get(_LAST_RETRAIN_KEY)
        if last_raw is None:
            return True, "no previous retrain recorded"

        last_dt = datetime.fromisoformat(
            last_raw.decode() if isinstance(last_raw, bytes) else last_raw
        )
        if datetime.now(tz=timezone.utc) - last_dt >= self._interval:
            return True, f"scheduled interval ({self._interval}) elapsed"

        # 2. F1 drift detection — compare on-disk model F1 vs live inference F1
        disk_f1   = self._read_disk_f1()
        live_f1   = await self._read_live_f1()

        if len(disk_f1) < self._min_assets or len(live_f1) < self._min_assets:
            return False, "not enough assets to detect drift"

        common = set(disk_f1) & set(live_f1)
        if len(common) < self._min_assets:
            return False, "not enough overlapping assets"

        drops = {a: disk_f1[a] - live_f1[a] for a in common}
        avg_drop = sum(drops.values()) / len(drops)

        if avg_drop > self._drift_delta:
            worst = max(drops, key=drops.__getitem__)
            return True, (
                f"F1 drift detected: avg drop={avg_drop:.3f} "
                f"(threshold={self._drift_delta}), "
                f"worst={worst} drop={drops[worst]:.3f}"
            )

        return False, "no trigger condition met"

    def _read_disk_f1(self) -> dict[str, float]:
        """Read directional F1 from the saved .json sidecar files."""
        result: dict[str, float] = {}
        for jf in self._models_dir.glob("cnn_*.json"):
            if jf.stem == "cnn_master":
                continue
            try:
                data = json.loads(jf.read_text())
                pc   = data.get("per_class", {})
                lf1  = float((pc.get("long",  {}) or {}).get("f1") or 0)
                sf1  = float((pc.get("short", {}) or {}).get("f1") or 0)
                asset = jf.stem[len("cnn_"):]
                result[asset] = (lf1 + sf1) / 2.0
            except Exception:  # noqa: BLE001
                continue
        return result

    async def _read_live_f1(self) -> dict[str, float]:
        """Read per-asset F1 values recorded by record_inference_f1()."""
        raw = await self._redis.hgetall(_F1_SNAPSHOT_KEY)
        result: dict[str, float] = {}
        for asset, val in raw.items():
            asset_str = asset.decode() if isinstance(asset, bytes) else asset
            val_str   = val.decode()   if isinstance(val,   bytes) else val
            try:
                result[asset_str] = float(val_str)
            except ValueError:
                continue
        return result

    async def _refresh_snapshot_baseline(self) -> None:
        """After a retrain is queued, reset the live snapshot to disk values."""
        disk = self._read_disk_f1()
        if disk:
            await self._redis.hset(_F1_SNAPSHOT_KEY, mapping={
                k: f"{v:.6f}" for k, v in disk.items()
            })

    # ── Diagnostics ───────────────────────────────────────────────────────────

    async def status(self) -> dict[str, Any]:
        last_raw = await self._redis.get(_LAST_RETRAIN_KEY)
        lock_raw = await self._redis.get(_RETRAIN_LOCK_KEY)
        disk_f1  = self._read_disk_f1()
        live_f1  = await self._read_live_f1()

        return {
            "last_retrain":   (last_raw.decode() if isinstance(last_raw, bytes) else last_raw),
            "locked":         lock_raw is not None,
            "interval_hours": self._interval.total_seconds() / 3600,
            "drift_threshold":self._drift_delta,
            "disk_f1":        disk_f1,
            "live_f1":        live_f1,
            "drift":          {
                a: round(disk_f1.get(a, 0) - live_f1.get(a, 0), 4)
                for a in set(disk_f1) | set(live_f1)
            },
        }
