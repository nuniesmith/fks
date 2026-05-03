"""
Breakout CNN — Training, evaluation, and model comparison.

Contains ``TrainResult``, ``train_model``, ``evaluate_model``,
``compare_models``, and Docker/worker helpers (``_detect_docker``,
``_safe_num_workers``).
"""

from __future__ import annotations

import contextlib
import os
from datetime import datetime
from typing import Any, NamedTuple

import numpy as np
import pandas as pd

from analysis.ml.breakout_constants import (
    _TORCH_AVAILABLE,
    DEFAULT_MODEL_DIR,
    MODEL_PREFIX,
    NUM_TABULAR,
    logger,
)
from analysis.ml.breakout_dataset import (
    BreakoutDataset,
    get_inference_transform,
    get_training_transform,
)
from analysis.ml.breakout_loading import (
    _build_model_from_checkpoint,
    invalidate_model_cache,
)
from analysis.ml.breakout_model import (
    ASSET_CLASS_EMBED_DIM,
    ASSET_ID_EMBED_DIM,
    HybridBreakoutCNN,
    get_device,
)

# Re-import torch & friends conditionally
if _TORCH_AVAILABLE:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader


# ---------------------------------------------------------------------------
# TrainResult
# ---------------------------------------------------------------------------


class TrainResult(NamedTuple):
    """Return value from :func:`train_model`.

    Attributes:
        model_path:     Absolute path to the saved ``.pt`` checkpoint.
        best_epoch:     1-based epoch index that achieved the best validation
                        accuracy (None if no validation was performed).
        epochs_trained: Total number of epochs completed.
    """

    model_path: str
    best_epoch: int | None
    epochs_trained: int


# ---------------------------------------------------------------------------
# Docker / worker helpers
# ---------------------------------------------------------------------------


def _detect_docker() -> bool:
    """Return True if we appear to be running inside a Docker container."""
    try:
        if os.path.exists("/.dockerenv"):
            return True
        with open("/proc/1/cgroup") as f:
            return any("docker" in line or "containerd" in line for line in f)
    except Exception:
        return False


def _safe_num_workers(requested: int) -> int:
    """Clamp DataLoader num_workers to 0 inside Docker when /dev/shm is small.

    PyTorch multiprocess DataLoader workers communicate via shared memory.
    Docker's default /dev/shm is only 64 MB, which causes:
        RuntimeError: unable to allocate shared memory(shm)
    Setting num_workers=0 forces single-process loading (slower but safe).
    """
    if requested == 0:
        return 0

    if not _detect_docker():
        return requested

    # Check /dev/shm size — need at least 512 MB for multi-worker loading
    try:
        stat = os.statvfs("/dev/shm")
        shm_bytes = stat.f_frsize * stat.f_blocks
        shm_mb = shm_bytes / (1024 * 1024)
        if shm_mb >= 512:
            logger.info("Docker detected with %.0f MB /dev/shm — using %d DataLoader workers", shm_mb, requested)
            return requested
        else:
            logger.warning(
                "Docker detected with only %.0f MB /dev/shm (need ≥512 MB) — "
                "forcing num_workers=0 to avoid shared memory crash. "
                "Fix: add 'shm_size: 2gb' to docker-compose.yml",
                shm_mb,
            )
            return 0
    except Exception:
        logger.warning("Docker detected but cannot check /dev/shm — forcing num_workers=0 for safety")
        return 0


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def train_model(
    data_csv: str,
    val_csv: str | None = None,
    epochs: int = 80,
    batch_size: int = 32,
    lr: float = 2e-4,
    weight_decay: float = 2e-4,
    freeze_epochs: int = 5,
    model_dir: str = DEFAULT_MODEL_DIR,
    image_root: str | None = None,
    num_workers: int = 4,
    save_best: bool = True,
    patience: int = 12,
    grad_accum_steps: int = 4,
    mixup_alpha: float = 0.2,
    warmup_epochs: int = 5,
    auto_adapt: bool = True,
    min_delta: float = 0.0,
) -> TrainResult | None:
    """Train the HybridBreakoutCNN model (v8 recipe).

    Two-phase training with cosine warmup:
      1. Freeze CNN backbone for ``freeze_epochs`` epochs — trains only the
         tabular head, embeddings, and classifier on your data.
      2. Unfreeze backbone and fine-tune everything with separate LR groups.

    v8 training recipe additions:
      - Gradient accumulation (effective batch = batch_size × grad_accum_steps)
      - Mixup augmentation on tabular features (α=0.2)
      - Label smoothing 0.15 (up from 0.10)
      - Cosine warmup (warmup_epochs linear warmup before cosine decay)
      - Separate param groups: backbone LR vs tabular head + embeddings LR
      - Early stopping with patience

    v10 small-dataset adaptations (auto_adapt=True):
      When the training set has fewer samples than the thresholds below, the
      training recipe is automatically adjusted to prevent catastrophic
      forgetting of pretrained backbone features:

      - **< 200 samples ("tiny"):** Backbone stays frozen for ALL epochs
        (feature extraction only).  Backbone LR set to 0.  Patience raised
        to max(patience, 25).  min_delta set to 0.5%.
      - **< 400 samples ("small"):** freeze_epochs extended to
        min(20, epochs // 2).  Backbone LR reduced 5×.  Patience raised to
        max(patience, 20).  min_delta set to 0.3%.
      - **< 800 samples ("medium"):** freeze_epochs extended by +3.
        Backbone LR reduced 2×.  Patience raised to max(patience, 15).

      This specifically fixes M2K (Russell 2000) per-asset training which
      peaked at epoch 4 (frozen phase) and degraded after backbone unfreeze,
      early-stopping at epoch 16 with only 71.4% accuracy.

    Args:
        data_csv: Path to training CSV (see BreakoutDataset for format).
        val_csv: Optional validation CSV.  If None, 15% of training data
                 is held out automatically.
        epochs: Total training epochs (default 80).
        batch_size: Batch size (default 32 — halved from v8 to keep VRAM under
                    16 GiB when the EfficientNetV2-S backbone is unfrozen;
                    effective batch stays 128 via grad_accum_steps=4).
        lr: Learning rate for backbone (default 2e-4).
        weight_decay: AdamW weight decay (default 1e-4).
        freeze_epochs: Number of epochs to freeze the CNN backbone (default 5).
        model_dir: Directory to save the trained model (default "models").
        image_root: Optional root directory to prepend to image_path values.
        num_workers: DataLoader workers (default 4).
        save_best: If True and val_csv is provided, save the best model by
                   validation accuracy instead of the final epoch.
        patience: Early stopping patience — stop if val acc doesn't improve
                  for this many epochs (default 15).
        grad_accum_steps: Gradient accumulation steps (default 4, effective
                          batch = 32×4 = 128 — same effective batch as before
                          but half the per-step activation memory).
        mixup_alpha: Mixup interpolation alpha for tabular features (default 0.2).
                     Set to 0.0 to disable mixup.
        warmup_epochs: Linear LR warmup epochs before cosine decay (default 5).
        auto_adapt: Automatically adjust hyperparameters for small datasets
                    (default True).  Extends freeze phase, lowers backbone LR,
                    and raises patience when training set is small.
        min_delta: Minimum improvement in val accuracy (percentage points)
                   required to reset the early stopping patience counter
                   (default 0.0 — any improvement counts).

    Returns:
        :class:`TrainResult` with ``model_path``, ``best_epoch``, and
        ``epochs_trained``, or ``None`` if training failed.
    """
    if not _TORCH_AVAILABLE:
        logger.error("PyTorch is not installed — cannot train model")
        return None

    device = torch.device(get_device())
    logger.info("Training on device: %s", device)

    # Clamp num_workers for Docker shared memory safety
    num_workers = _safe_num_workers(num_workers)

    # --- Datasets ---
    train_transform = get_training_transform()
    val_transform = get_inference_transform()

    train_dataset = BreakoutDataset(data_csv, transform=train_transform, image_root=image_root)

    # ── v10: Adaptive small-dataset training ─────────────────────────────
    # Detect training set size and automatically adjust hyperparameters to
    # prevent catastrophic forgetting when fine-tuning a large backbone on
    # a small per-asset dataset.  This fixes the M2K problem: best_epoch=4
    # (frozen phase) with degradation after backbone unfreeze.
    _n_train = len(train_dataset)
    _adapted = False

    if auto_adapt and _n_train > 0:
        if _n_train < 200:
            # ── Tiny dataset: feature extraction only (never unfreeze) ────
            freeze_epochs = epochs  # backbone stays frozen for all epochs
            lr = 0.0  # backbone LR = 0 (no backbone gradients)
            patience = max(patience, 25)
            min_delta = max(min_delta, 0.5)
            warmup_epochs = min(warmup_epochs, 3)
            _adapted = True
            logger.info(
                "Auto-adapt TINY dataset (%d samples): backbone frozen ALL %d epochs, patience=%d, min_delta=%.1f%%",
                _n_train,
                epochs,
                patience,
                min_delta,
            )
        elif _n_train < 400:
            # ── Small dataset: extended freeze + reduced backbone LR ──────
            freeze_epochs = min(20, max(freeze_epochs, epochs // 2))
            lr = lr / 5.0  # backbone LR reduced 5×
            patience = max(patience, 20)
            min_delta = max(min_delta, 0.3)
            _adapted = True
            logger.info(
                "Auto-adapt SMALL dataset (%d samples): freeze_epochs=%d, "
                "backbone_lr=%.2e, patience=%d, min_delta=%.1f%%",
                _n_train,
                freeze_epochs,
                lr,
                patience,
                min_delta,
            )
        elif _n_train < 800:
            # ── Medium dataset: modest adjustments ────────────────────────
            freeze_epochs = freeze_epochs + 3
            lr = lr / 2.0  # backbone LR reduced 2×
            patience = max(patience, 15)
            _adapted = True
            logger.info(
                "Auto-adapt MEDIUM dataset (%d samples): freeze_epochs=%d, backbone_lr=%.2e, patience=%d",
                _n_train,
                freeze_epochs,
                lr,
                patience,
            )
        else:
            logger.info(
                "Dataset size %d — no auto-adapt needed (thresholds: tiny<200, small<400, medium<800)",
                _n_train,
            )

    if val_csv:
        val_dataset = BreakoutDataset(val_csv, transform=val_transform, image_root=image_root)
    else:
        # Auto-split: 85% train / 15% val
        n = len(train_dataset)
        n_val = max(1, int(n * 0.15))
        n_train = n - n_val
        split_train, split_val = torch.utils.data.random_split(train_dataset, [n_train, n_val])  # type: ignore[arg-type]
        train_dataset = split_train  # type: ignore[assignment]
        val_dataset = split_val  # type: ignore[assignment]
        logger.info("Auto-split: %d train / %d val", n_train, n_val)

    # ── v9: WeightedRandomSampler for strategy imbalance ─────────────────
    # Access the underlying DataFrame rows whether train_dataset is a plain
    # BreakoutDataset or a torch Subset produced by the auto-split above.
    if isinstance(train_dataset, torch.utils.data.Subset):
        _subset_df = train_dataset.dataset.df.iloc[train_dataset.indices]  # type: ignore[union-attr,attr-defined]
    else:
        _subset_df = train_dataset.df  # type: ignore[union-attr]

    # 1. Label-frequency weights
    _label_counts = _subset_df["label"].value_counts().to_dict()
    _label_weights: dict[str, float] = {lbl: 1.0 / max(cnt, 1) for lbl, cnt in _label_counts.items()}

    # 2. Breakout-type multipliers — boost minority strategy types
    _MINORITY_TYPES = {"BollingerSqueeze", "Fibonacci", "Consolidation", "Monthly", "Weekly", "InsideDay"}
    _MAJORITY_TYPES = {"ORB", "PrevDay", "InitialBalance"}
    _bt_series = _subset_df.get("breakout_type", pd.Series(dtype=str))

    def _bt_multiplier(bt: Any) -> float:
        if pd.isna(bt) or str(bt) not in _MINORITY_TYPES:
            return 1.0
        return 3.0

    # 3. Build per-sample weight tensor
    _sample_weights: list[float] = []
    for _idx in range(len(_subset_df)):
        _row = _subset_df.iloc[_idx]
        _lw = _label_weights.get(str(_row["label"]), 1.0)
        _bt = _row.get("breakout_type", None) if "breakout_type" in _subset_df.columns else None
        _bm = _bt_multiplier(_bt)
        _sample_weights.append(_lw * _bm)

    _weights_tensor = torch.tensor(_sample_weights, dtype=torch.float64)
    sampler = torch.utils.data.WeightedRandomSampler(
        _weights_tensor.tolist(),
        num_samples=len(_weights_tensor),
        replacement=True,  # type: ignore[arg-type]
    )
    logger.info(
        "WeightedRandomSampler: %d samples, label weights: %s, minority boost: 3x for %s",
        len(_weights_tensor),
        {k: round(v, 5) for k, v in _label_weights.items()},
        sorted(_MINORITY_TYPES),
    )

    train_loader = DataLoader(
        train_dataset,  # type: ignore[arg-type]
        batch_size=batch_size,
        shuffle=False,  # cannot use shuffle=True with a sampler
        sampler=sampler,
        num_workers=num_workers,
        pin_memory=(device.type == "cuda"),
        drop_last=True,
        collate_fn=BreakoutDataset.skip_invalid_collate,
    )
    # Val loader intentionally does NOT use pin_memory — it runs after the
    # training loop so the pinned pages would sit idle on the GPU during
    # training, wasting ~0.5–1 GiB of locked memory on a 16 GiB card.
    val_loader = DataLoader(
        val_dataset,  # type: ignore[arg-type]
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=False,
        collate_fn=BreakoutDataset.skip_invalid_collate,
    )

    # --- Model ---
    model = HybridBreakoutCNN(pretrained=True, use_asset_embeddings=True)
    logger.info(
        "HybridBreakoutCNN v8: %d tabular features + asset embeddings (%d+%d dims)",
        NUM_TABULAR,
        ASSET_CLASS_EMBED_DIM,
        ASSET_ID_EMBED_DIM,
    )
    model = model.to(device)  # type: ignore[union-attr]

    # --- AMP GradScaler for mixed-precision training (FP16 forward pass) ---
    # Cuts activation memory roughly in half during the forward pass with no
    # accuracy loss.  Only active on CUDA; CPU/MPS training stays in FP32.
    _use_amp = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=_use_amp)  # type: ignore[attr-defined]
    logger.info("AMP mixed-precision training: %s", "enabled (FP16)" if _use_amp else "disabled (FP32)")

    # --- Optimizer with separate param groups (v8-E) ---
    # Backbone gets lower LR; tabular head + embeddings get higher LR
    backbone_params = list(model.cnn.parameters())
    head_params = list(model.tabular_head.parameters()) + list(model.classifier.parameters())
    embedding_params: list[Any] = []
    if model.use_asset_embeddings:
        embedding_params = list(model.asset_class_embedding.parameters()) + list(model.asset_id_embedding.parameters())
    head_lr = lr * 5  # 1e-3 for tabular head + embeddings

    optimizer = torch.optim.AdamW(
        [
            {"params": backbone_params, "lr": lr},
            {"params": head_params + embedding_params, "lr": head_lr},
        ],
        weight_decay=weight_decay,
    )

    # Learning rate scheduler: linear warmup then cosine annealing (v8-D)
    def _lr_lambda(epoch: int) -> float:
        if epoch < warmup_epochs:
            return (epoch + 1) / warmup_epochs  # linear warmup
        # Cosine decay from warmup_epochs to total epochs
        progress = (epoch - warmup_epochs) / max(1, epochs - warmup_epochs)
        return max(0.01, 0.5 * (1.0 + np.cos(np.pi * progress)))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=_lr_lambda)

    # --- Loss (v8-D: label smoothing 0.15) ---
    criterion: Any = nn.CrossEntropyLoss(label_smoothing=0.15)

    # --- Training loop ---
    best_val_acc = 0.0
    best_model_path: str | None = None
    best_epoch: int | None = None
    epochs_completed: int = 0
    epochs_since_improvement = 0
    os.makedirs(model_dir, exist_ok=True)

    # Write intermediate checkpoints to a subdirectory — only the final
    # champion gets copied to model_dir by the trainer server.
    checkpoint_dir = os.path.join(model_dir, "_checkpoints")
    os.makedirs(checkpoint_dir, exist_ok=True)

    for epoch in range(epochs):
        # Phase management: freeze/unfreeze backbone
        if epoch < freeze_epochs:
            if epoch == 0:
                model.freeze_backbone()
        elif epoch == freeze_epochs:
            # Flush the CUDA cache before unfreezing — the frozen epochs only
            # trained the small head, so most backbone activation memory was
            # never allocated.  Clearing the cache now gives the full fine-tune
            # phase a clean VRAM slate and avoids OOM on the first unfrozen
            # forward pass (where EfficientNetV2-S allocates all layer gradients).
            if device.type == "cuda":
                import gc as _gc

                _gc.collect()
                torch.cuda.empty_cache()
                free_gb = torch.cuda.mem_get_info()[0] / 1024**3
                logger.info("CUDA cache cleared before backbone unfreeze — %.2f GiB free", free_gb)
            model.unfreeze_backbone()
            logger.info("Backbone unfrozen at epoch %d — full fine-tuning begins", epoch + 1)

        # --- Train ---
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        optimizer.zero_grad(set_to_none=True)

        for batch_idx, batch in enumerate(train_loader):
            # skip_invalid_collate returns None when every sample was invalid
            if batch is None:
                continue
            imgs, tabs, labels, asset_class_ids, asset_ids = batch
            imgs = imgs.to(device, non_blocking=True)
            tabs = tabs.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            asset_class_ids = asset_class_ids.to(device, non_blocking=True)
            asset_ids = asset_ids.to(device, non_blocking=True)

            # ── v9: Mixup augmentation on BOTH images AND tabular features ────────
            if mixup_alpha > 0.0 and imgs.size(0) > 1:
                lam = float(np.random.beta(mixup_alpha, mixup_alpha))
                perm = torch.randperm(imgs.size(0), device=device)
                imgs = lam * imgs + (1 - lam) * imgs[perm]
                tabs = lam * tabs + (1 - lam) * tabs[perm]
                # Note: labels are NOT mixed — mixup acts as regulariser only.
                # Using hard labels with mixed inputs is a known effective shortcut.

            with torch.amp.autocast("cuda", enabled=_use_amp):  # type: ignore[attr-defined]
                outputs = model(imgs, tabs, asset_class_ids=asset_class_ids, asset_ids=asset_ids)
                loss = criterion(outputs, labels) / grad_accum_steps

            # NaN guard — skip batch if loss explodes
            if torch.isnan(loss) or torch.isinf(loss):
                logger.warning("NaN/Inf loss at batch %d — skipping", batch_idx)
                continue

            scaler.scale(loss).backward()  # type: ignore[union-attr]

            # ── v8-D: Gradient accumulation ───────────────────────────────
            if (batch_idx + 1) % grad_accum_steps == 0 or (batch_idx + 1) == len(train_loader):
                # Gradient clipping for stability (unscale first for AMP)
                scaler.unscale_(optimizer)  # type: ignore[union-attr]
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                scaler.step(optimizer)  # type: ignore[union-attr]
                scaler.update()  # type: ignore[union-attr]
                optimizer.zero_grad(set_to_none=True)

            train_loss += loss.item() * grad_accum_steps * imgs.size(0)
            _, predicted = outputs.max(1)
            train_correct += predicted.eq(labels).sum().item()
            train_total += labels.size(0)

        scheduler.step()

        avg_train_loss = train_loss / max(train_total, 1)
        train_acc = train_correct / max(train_total, 1) * 100

        # --- Validate ---
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for batch in val_loader:
                if batch is None:
                    continue
                imgs, tabs, labels, asset_class_ids, asset_ids = batch
                imgs = imgs.to(device, non_blocking=True)
                tabs = tabs.to(device, non_blocking=True)
                labels = labels.to(device, non_blocking=True)
                asset_class_ids = asset_class_ids.to(device, non_blocking=True)
                asset_ids = asset_ids.to(device, non_blocking=True)

                with torch.amp.autocast("cuda", enabled=_use_amp):  # type: ignore[attr-defined]
                    outputs = model(imgs, tabs, asset_class_ids=asset_class_ids, asset_ids=asset_ids)
                    loss = criterion(outputs, labels)

                val_loss += loss.item() * imgs.size(0)
                _, predicted = outputs.max(1)
                val_correct += predicted.eq(labels).sum().item()
                val_total += labels.size(0)

        avg_val_loss = val_loss / max(val_total, 1)
        val_acc = val_correct / max(val_total, 1) * 100

        current_lr = optimizer.param_groups[0]["lr"]
        phase = "frozen" if epoch < freeze_epochs else "fine-tune"

        logger.info(
            "Epoch %d/%d [%s] — Train Loss: %.4f Acc: %.1f%% | Val Loss: %.4f Acc: %.1f%% | LR: %.2e",
            epoch + 1,
            epochs,
            phase,
            avg_train_loss,
            train_acc,
            avg_val_loss,
            val_acc,
            current_lr,
        )

        # --- Save best model ---
        if save_best and val_acc > best_val_acc + min_delta:
            best_val_acc = val_acc
            best_epoch = epoch + 1  # 1-based
            epochs_since_improvement = 0
            # Save to _checkpoints subdir (not model_dir) to avoid polluting
            # the models directory with hundreds of intermediate files.
            prev_best = best_model_path
            best_model_path = os.path.join(
                checkpoint_dir, f"{MODEL_PREFIX}{datetime.now():%Y%m%d_%H%M%S}_acc{val_acc:.0f}.pt"
            )
            torch.save(model.state_dict(), best_model_path)
            logger.info("New best model saved: %s (val_acc=%.1f%%)", best_model_path, val_acc)
            # Delete previous best checkpoint to save disk space
            if prev_best and os.path.exists(prev_best):
                with contextlib.suppress(OSError):
                    os.remove(prev_best)
        else:
            epochs_since_improvement += 1

        epochs_completed = epoch + 1

        # ── v8-E: Early stopping (v10: min_delta support) ────────────────
        if patience > 0 and epochs_since_improvement >= patience:
            logger.info(
                "Early stopping at epoch %d — no improvement%s for %d epochs (best val_acc=%.1f%%)",
                epochs_completed,
                f" ≥{min_delta:.1f}pp" if min_delta > 0 else "",
                patience,
                best_val_acc,
            )
            break

    # --- Save final model (if not saving best, or as fallback) ---
    final_path = os.path.join(checkpoint_dir, f"{MODEL_PREFIX}{datetime.now():%Y%m%d_%H%M%S}_final.pt")
    torch.save(model.state_dict(), final_path)
    logger.info("Final model saved: %s", final_path)

    result_path = best_model_path if (save_best and best_model_path) else final_path
    logger.info(
        "Training complete — best val accuracy: %.1f%% — model: %s (best_epoch=%s, epochs_trained=%d)",
        best_val_acc,
        result_path,
        best_epoch,
        epochs_completed,
    )

    # Invalidate cached model so next inference picks up the new one
    invalidate_model_cache()

    return TrainResult(
        model_path=result_path,
        best_epoch=best_epoch,
        epochs_trained=epochs_completed,
    )


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_model(
    model_path: str,
    val_csv: str,
    image_root: str | None = None,
    batch_size: int = 32,
    num_workers: int = 4,
) -> dict[str, Any] | None:
    """Evaluate a trained model checkpoint against a validation CSV.

    Computes accuracy, precision, and recall (macro-averaged) on the
    validation set.  Intended to be called by the trainer server after
    :func:`train_model` completes, so the pipeline can gate promotion on
    concrete metrics.

    Args:
        model_path: Path to a ``.pt`` state-dict checkpoint.
        val_csv: Path to the validation CSV (same format as training CSV).
        image_root: Optional root directory prepended to ``image_path``
                    values in the CSV.
        batch_size: Evaluation batch size (default 32).
        num_workers: DataLoader workers (default 4).

    Returns:
        Dict with keys ``val_accuracy``, ``val_precision``, ``val_recall``
        (all 0.0–1.0 floats), or ``None`` if evaluation failed.
    """
    if not _TORCH_AVAILABLE:
        logger.error("PyTorch is not installed — cannot evaluate model")
        return None

    try:
        from sklearn.metrics import accuracy_score, precision_score, recall_score

        device = torch.device(get_device())
        num_workers = _safe_num_workers(num_workers)

        # Load model — auto-detect num_tabular from checkpoint
        try:
            state_dict = torch.load(model_path, map_location=device, weights_only=True)
        except TypeError:
            state_dict = torch.load(model_path, map_location=device)  # type: ignore[call-overload]
        model = _build_model_from_checkpoint(state_dict)
        if model is None:
            logger.error("Failed to build model from checkpoint %s", model_path)
            return None
        model = model.to(device)

        # Build validation loader
        val_transform = get_inference_transform()
        val_dataset = BreakoutDataset(val_csv, transform=val_transform, image_root=image_root)

        if len(val_dataset) == 0:
            logger.warning("Validation dataset is empty — cannot evaluate")
            return None

        val_loader = DataLoader(
            val_dataset,  # type: ignore[arg-type]
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            pin_memory=(device.type == "cuda"),
            collate_fn=BreakoutDataset.skip_invalid_collate,
        )

        all_preds: list[int] = []
        all_labels: list[int] = []

        with torch.no_grad():
            for batch in val_loader:
                if batch is None:
                    continue
                imgs, tabs, labels, asset_class_ids, asset_ids = batch
                imgs = imgs.to(device, non_blocking=True)
                tabs = tabs.to(device, non_blocking=True)
                labels = labels.to(device, non_blocking=True)
                asset_class_ids = asset_class_ids.to(device, non_blocking=True)
                asset_ids = asset_ids.to(device, non_blocking=True)

                if model.use_asset_embeddings:
                    outputs = model(imgs, tabs, asset_class_ids=asset_class_ids, asset_ids=asset_ids)
                else:
                    outputs = model(imgs, tabs)
                _, predicted = outputs.max(1)

                all_preds.extend(predicted.cpu().tolist())
                all_labels.extend(labels.cpu().tolist())

        if not all_labels:
            logger.warning("No valid samples evaluated — cannot compute metrics")
            return None

        acc = accuracy_score(all_labels, all_preds)
        # Use zero_division=0.0 so we don't crash when a class is absent
        prec = precision_score(all_labels, all_preds, average="macro", zero_division=0.0)  # type: ignore[arg-type]
        rec = recall_score(all_labels, all_preds, average="macro", zero_division=0.0)  # type: ignore[arg-type]

        logger.info(
            "Evaluation complete — accuracy: %.1f%%, precision: %.1f%%, recall: %.1f%% (%d samples)",
            acc * 100,
            prec * 100,
            rec * 100,
            len(all_labels),
        )

        return {
            "val_accuracy": round(float(acc), 4),
            "val_precision": round(float(prec), 4),
            "val_recall": round(float(rec), 4),
            "num_samples": len(all_labels),
        }

    except Exception as exc:
        logger.error("Model evaluation failed: %s", exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Model comparison
# ---------------------------------------------------------------------------


def compare_models(
    model_a_path: str,
    model_b_path: str,
    val_csv: str,
    image_root: str | None = None,
    batch_size: int = 32,
    label_a: str = "model_a",
    label_b: str = "model_b",
) -> dict[str, Any] | None:
    """Compare two model checkpoints against the same validation set.

    Returns a comparison dict with:
    - per-model metrics (accuracy, precision, recall, per-class accuracy)
    - delta metrics (model_b - model_a)
    - winner declaration
    - per-sample agreement/disagreement counts

    Args:
        model_a_path: Path to the first model checkpoint (``.pt`` file).
        model_b_path: Path to the second model checkpoint (``.pt`` file).
        val_csv: Path to the shared validation CSV.
        image_root: Optional root directory prepended to ``image_path`` values.
        batch_size: Evaluation batch size (default 32).
        label_a: Human-readable label for model A (default ``"model_a"``).
        label_b: Human-readable label for model B (default ``"model_b"``).

    Returns:
        A structured comparison dict, or ``None`` if either evaluation failed.
    """
    logger.info(
        "Comparing models: %s (%s) vs %s (%s) on %s",
        label_a,
        model_a_path,
        label_b,
        model_b_path,
        val_csv,
    )

    metrics_a = evaluate_model(
        model_a_path,
        val_csv,
        image_root=image_root,
        batch_size=batch_size,
    )
    if metrics_a is None:
        logger.error("compare_models: evaluation of %s (%s) failed", label_a, model_a_path)
        return None

    metrics_b = evaluate_model(
        model_b_path,
        val_csv,
        image_root=image_root,
        batch_size=batch_size,
    )
    if metrics_b is None:
        logger.error("compare_models: evaluation of %s (%s) failed", label_b, model_b_path)
        return None

    delta_acc = metrics_b["val_accuracy"] - metrics_a["val_accuracy"]
    delta_prec = metrics_b["val_precision"] - metrics_a["val_precision"]
    delta_rec = metrics_b["val_recall"] - metrics_a["val_recall"]

    winner = label_b if delta_acc > 0 else label_a

    result: dict[str, Any] = {
        label_a: metrics_a,
        label_b: metrics_b,
        "delta": {
            "accuracy": round(delta_acc, 4),
            "precision": round(delta_prec, 4),
            "recall": round(delta_rec, 4),
        },
        "winner": winner,
        "winner_margin_pct": round(abs(delta_acc) * 100, 4),
        "model_a_path": model_a_path,
        "model_b_path": model_b_path,
    }

    logger.info(
        "Model comparison complete — winner: %s (margin: %.2f%%) | "
        "accuracy: %s=%.1f%% %s=%.1f%% | "
        "precision: %s=%.1f%% %s=%.1f%% | "
        "recall: %s=%.1f%% %s=%.1f%%",
        winner,
        abs(delta_acc) * 100,
        label_a,
        metrics_a["val_accuracy"] * 100,
        label_b,
        metrics_b["val_accuracy"] * 100,
        label_a,
        metrics_a["val_precision"] * 100,
        label_b,
        metrics_b["val_precision"] * 100,
        label_a,
        metrics_a["val_recall"] * 100,
        label_b,
        metrics_b["val_recall"] * 100,
    )

    return result
