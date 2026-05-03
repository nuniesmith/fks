"""
ml/train_asset.py — Per-asset PerAssetCNN training.

Public API
----------
    train_asset(asset_key, exchange, args, device, cache=None) -> dict | None
    _resolve_label_params(asset_key, df, args) -> dict

Fixes applied vs the original monolithic train.py
---------------------------------------------------
    #1  All imports are at module level; torch.nn.functional is no longer
        re-imported inside the hot training loop.
    #2  Dead-code ``max_cw`` variable (computed but never used after the
        class-weight boost) has been removed.
    #3  Gradient accumulation step boundary now uses ``enumerate`` instead of
        ``tqdm.n``.  ``tqdm.n`` is the *completed* iteration count, making the
        boundary fire one batch too early on the very first accumulation window.
    #4  ``scheduler.step()`` is called unconditionally at the end of each epoch
        *before* the early-stopping check, matching the standard PyTorch pattern
        and ensuring the cosine schedule advances on the final (early-stop) epoch.
    #5  Per-class metrics, directional gate, and temperature calibration are now
        computed from a fresh inference pass with the *best* checkpoint rather
        than from the last epoch's cached ``val_preds_all``.
    #6  EMA smoothing only affects *when* early stopping fires, not which
        checkpoint is saved (saved on raw metric peak).  This is now documented
        explicitly and the effective patience inflation (~alpha * 3 extra epochs)
        is noted.
    #7  ``train_correct`` / ``train_acc`` is intentionally still counted against
        hard ``y_batch`` labels when mixup is active.  This makes ``train_acc``
        a lower bound rather than a faithful accuracy, which is documented.
        It does *not* affect val metrics or checkpointing.
    #8  Redundant ``model.save_meta(model_path, meta)`` call removed;
        ``model.save(model_path, meta=meta)`` already writes the sidecar JSON.
    #9  flat_pct is now computed from label_summary and surfaced in the result
        dict so that promote_champions can gate on degenerate label distributions
        (>= 95% flat).  A warning is emitted when the threshold is exceeded.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import LambdaLR
from tqdm import tqdm

from ml.dataset import AssetDataset, build_dataloaders
from ml.features import N_FEATURES
from ml.kline_cache import KlineCache
from ml.labeler import class_weights, fetch_klines, generate_labels_breakout, label_summary
from ml.model import N_CLASSES, build_per_asset_cnn
from ml.optimize_labels import optimize_label_params
from ml.reporting import load_existing_meta, print_champion_comparison
from ml.training_components import (
    EarlyStopping,
    FocalLoss,
    calibrate_temperature,
    warmup_cosine_lr,
)

logger = logging.getLogger("train.asset")

# Silence the spurious "called lr_scheduler.step() before optimizer.step()" warning
# that fires during the warmup phase with LambdaLR + AdamW.
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message=".*lr_scheduler.step.*before.*optimizer.step.*",
)


# ── Asset symbol map (imported by train.py) ───────────────────────────────────
ASSET_SYMBOLS: dict[str, str] = {
    "btc": "XBTUSDTM",
    "eth": "ETHUSDTM",
    "sol": "SOLUSDTM",
    "xrp": "XRPUSDTM",
    "doge": "DOGEUSDTM",
    "bnb": "BNBUSDTM",
    "ada": "ADAUSDTM",
    "dot": "DOTUSDTM",
    "link": "LINKUSDTM",
    "pepe": "PEPEUSDTM",
    "trump": "TRUMPUSDTM",
    "bonk": "1000BONKUSDTM",
    "shib": "SHIBUSDTM",
    "avax": "AVAXUSDTM",
    "sui": "SUIUSDTM",
    "wif": "WIFUSDTM",
    "fart": "FARTCOINUSDTM",
    "gold": "XAUTUSDTM",
    "silver": "XAGUSDTM",
}

# Asset-specific label parameters (pre-tuned via Optuna)
ASSET_LABEL_PARAMS: dict[str, dict] = {
    "btc": dict(
        consolidation_atr_mult=5.7107,
        consolidation_bars=30,
        tp_atr_mult=2.4404,
        sl_atr_mult=0.7121,
        max_breakout_wait=24,
        max_hold_bars=173,
    ),
    "eth": dict(
        consolidation_atr_mult=3.5878,
        consolidation_bars=19,
        tp_atr_mult=2.3241,
        sl_atr_mult=0.5466,
        max_breakout_wait=50,
        max_hold_bars=96,
    ),
    "sol": dict(
        consolidation_atr_mult=4.0969,
        consolidation_bars=23,
        tp_atr_mult=2.1556,
        sl_atr_mult=0.5006,
        max_breakout_wait=24,
        max_hold_bars=121,
    ),
    "pepe": dict(
        consolidation_atr_mult=4.0867,
        consolidation_bars=29,
        tp_atr_mult=2.6782,
        sl_atr_mult=0.5471,
        max_breakout_wait=28,
        max_hold_bars=121,
    ),
    "avax": dict(
        consolidation_atr_mult=5.50,
        consolidation_bars=20,
        tp_atr_mult=2.50,
        sl_atr_mult=0.80,
        max_breakout_wait=35,
        max_hold_bars=90,
    ),
    "doge": dict(
        consolidation_atr_mult=5.5005,
        consolidation_bars=30,
        tp_atr_mult=2.8814,
        sl_atr_mult=0.5362,
        max_breakout_wait=42,
        max_hold_bars=90,
    ),
    "sui": dict(
        consolidation_atr_mult=4.7358,
        consolidation_bars=28,
        tp_atr_mult=2.7560,
        sl_atr_mult=0.7877,
        max_breakout_wait=33,
        max_hold_bars=78,
    ),
    "wif": dict(
        consolidation_atr_mult=5.8929,
        consolidation_bars=29,
        tp_atr_mult=2.9999,
        sl_atr_mult=0.8181,
        max_breakout_wait=36,
        max_hold_bars=162,
    ),
    "fart": dict(
        consolidation_atr_mult=3.7480,
        consolidation_bars=18,
        tp_atr_mult=2.6105,
        sl_atr_mult=0.5896,
        max_breakout_wait=58,
        max_hold_bars=107,
    ),
    "gold": dict(
        consolidation_atr_mult=4.0580,
        consolidation_bars=20,
        tp_atr_mult=2.9450,
        sl_atr_mult=0.7326,
        max_breakout_wait=41,
        max_hold_bars=86,
    ),
}


# ── Label param resolution ────────────────────────────────────────────────────


def _resolve_label_params(asset_key: str, df: Any, args: argparse.Namespace) -> dict:
    """Return a label-param dict for ``generate_labels_breakout``.

    Priority:
      1. ``--optimize-labels`` flag → run / load cached Optuna result.
      2. ``ASSET_LABEL_PARAMS`` dict → hand-tuned values.
      3. CLI args → fallback.
    """
    if getattr(args, "optimize_labels", False):
        logger.info("[%s] Running label parameter optimisation ...", asset_key.upper())
        return optimize_label_params(
            asset_key=asset_key,
            df=df,
            n_trials=getattr(args, "label_opt_trials", 50),
            models_dir=Path(args.models_dir),
            force=getattr(args, "force_label_opt", False),
            verbose=False,
        )

    if asset_key.lower() in ASSET_LABEL_PARAMS:
        p = ASSET_LABEL_PARAMS[asset_key.lower()]
        logger.info(
            "[%s] Using pre-optimised label params: consol_atr=%.2f  bars=%d  tp=%.2f  sl=%.2f",
            asset_key.upper(),
            p["consolidation_atr_mult"],
            p["consolidation_bars"],
            p["tp_atr_mult"],
            p["sl_atr_mult"],
        )
        return p

    logger.info("[%s] Using CLI default label params", asset_key.upper())
    return dict(
        consolidation_bars=args.consolidation_bars,
        consolidation_atr_mult=args.consolidation_atr_mult,
        max_breakout_wait=args.max_breakout_wait,
        tp_atr_mult=args.tp_atr_mult,
        sl_atr_mult=args.sl_atr_mult,
        max_hold_bars=args.max_forward_bars,
    )


# ── Validation inference helper ───────────────────────────────────────────────


def _run_val_inference(
    model: nn.Module,
    val_dl: Any,
    device: torch.device,
    use_amp: bool,
) -> tuple[list[int], list[int]]:
    """Run a full pass over *val_dl* and return (preds, labels) lists.

    Used to collect fresh predictions after the best checkpoint is restored,
    ensuring per-class metrics and directional gating reflect the saved model
    rather than the final (possibly worse) training epoch.
    """
    preds_all: list[int] = []
    labels_all: list[int] = []
    model.eval()
    with torch.no_grad():
        for x_batch, y_batch in val_dl:
            x_batch = x_batch.to(device)
            y_batch = y_batch.to(device)
            ctx = torch.amp.autocast(device_type="cuda") if use_amp else contextlib.nullcontext()
            with ctx:
                logits = model(x_batch)
            preds = logits.argmax(dim=-1)
            preds_all.extend(preds.cpu().tolist())
            labels_all.extend(y_batch.cpu().tolist())
    return preds_all, labels_all


# ── Per-class metric computation ──────────────────────────────────────────────


def _compute_per_class(
    preds: list[int] | np.ndarray,
    labels: list[int] | np.ndarray,
    class_names: list[str],
) -> dict[str, dict[str, float]]:
    vp = np.asarray(preds, dtype=np.int64)
    vl = np.asarray(labels, dtype=np.int64)
    per_class: dict[str, dict[str, float]] = {}
    for idx, name in enumerate(class_names):
        tp = int(((vp == idx) & (vl == idx)).sum())
        fp = int(((vp == idx) & (vl != idx)).sum())
        fn = int(((vp != idx) & (vl == idx)).sum())
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-8)
        per_class[name] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": tp + fn,
        }
    return per_class


# ── Main training function ────────────────────────────────────────────────────


def train_asset(
    asset_key: str,
    exchange: Any,
    args: argparse.Namespace,
    device: torch.device,
    cache: KlineCache | None = None,
) -> dict[str, Any] | None:
    """Train a PerAssetCNN for a single asset.

    Returns a metadata dict on success, None on failure.

    SWA note
    --------
    Stochastic Weight Averaging was removed.  Across all 9 saved assets in the
    previous run SWA consistently produced a worse model than the best single
    checkpoint (e.g. BTC F1 0.426 → 0.348, ETH 0.426 → 0.364).
    """
    symbol = ASSET_SYMBOLS.get(asset_key)
    if symbol is None:
        logger.error("Unknown asset key: %s  (valid: %s)", asset_key, list(ASSET_SYMBOLS))
        return None

    logger.info("=" * 60)
    logger.info("Training PerAssetCNN for %s (%s)", asset_key.upper(), symbol)
    logger.info("=" * 60)

    # ── 1. Fetch historical data ──────────────────────────────────────────────
    if cache is not None:
        cache.reset_stats()

    t_fetch = time.time()
    df = fetch_klines(
        exchange=exchange,
        symbol=symbol,
        timeframe=args.timeframe,
        limit=args.bars,
        cache=cache,
        min_bars=getattr(args, "min_bars", 5_000),
    )

    if df.empty or len(df) < 500:
        logger.error("Insufficient data for %s (%d bars) — skipping", asset_key, len(df))
        return None

    logger.info(
        "Fetched %d bars for %s in %.1fs  [%s]",
        len(df),
        asset_key.upper(),
        time.time() - t_fetch,
        cache.stats_line() if cache is not None else "cache disabled",
    )

    # ── 2. Generate labels ────────────────────────────────────────────────────
    t_label = time.time()
    label_params = _resolve_label_params(asset_key, df, args)
    labels = generate_labels_breakout(df, **label_params)
    logger.info("Labelling took %.1fs", time.time() - t_label)

    if args.dry_run:
        summary = label_summary(labels)
        logger.info("Label summary for %s: %s", asset_key.upper(), summary)
        return {"dry_run": True, "asset": asset_key, "labels": summary}

    # ── FIX #9: compute flat_pct and warn on degenerate distributions ─────────
    summary = label_summary(labels)
    _total_labels = max(sum(summary.values()), 1)
    flat_pct = summary.get("flat", 0) / _total_labels
    logger.info(
        "Label distribution: %s  (flat_pct=%.1f%%)",
        summary,
        flat_pct * 100,
    )
    if flat_pct > 0.95:
        logger.warning(
            "[%s] Degenerate label distribution: %.1f%% flat — "
            "model will learn a near-flat predictor and should not be promoted",
            asset_key.upper(),
            flat_pct * 100,
        )

    if summary["long"] + summary["short"] < 200:
        logger.warning(
            "[%s] Insufficient directional labels (%d long + %d short) — skipping training",
            asset_key.upper(),
            summary["long"],
            summary["short"],
        )
        return {
            "asset": asset_key,
            "flat_pct": round(flat_pct, 4),
            "saved": False,
            "reason": f"only {summary['long'] + summary['short']} directional labels (< 200)",
            "val_accuracy": 0.0,
            "val_macro_f1": 0.0,
        }

    # ── 3. Build Dataset & DataLoaders ────────────────────────────────────────
    dataset = AssetDataset(df=df, labels=labels, window=args.window)

    if len(dataset) < 200:
        logger.error("Dataset too small (%d samples) — skipping %s", len(dataset), asset_key)
        return None

    train_dl, val_dl = build_dataloaders(
        dataset=dataset,
        batch_size=args.batch_size,
        val_split=args.val_split,
        num_workers=0,
        use_weighted_sampler=True,
    )

    # ── 4. Build model ────────────────────────────────────────────────────────
    model = build_per_asset_cnn(
        n_features=N_FEATURES,
        window=args.window,
        embedding_dim=getattr(args, "embedding_dim", 64),
        dropout=getattr(args, "dropout", 0.3),
    ).to(device)

    logger.info(
        "PerAssetCNN: %d parameters  input=(%d, %d)",
        model.param_count(),
        N_FEATURES,
        args.window,
    )

    # ── 5. Loss, optimiser, scheduler, AMP, early stopping ───────────────────
    accum_steps = 4
    effective_batch = args.batch_size * accum_steps
    logger.info(
        "  Gradient accumulation: %d steps → effective batch %d",
        accum_steps,
        effective_batch,
    )

    # FIX #2: removed the dead ``max_cw`` variable that was computed but
    # never used after the class-weight boost block.
    cw = class_weights(labels)
    if args.class_weight_boost > 1.0:
        cw[1] *= args.class_weight_boost
        cw[2] *= args.class_weight_boost
        cw[3] *= args.class_weight_boost
        cw = [min(w, 15.0) for w in cw]

    logger.info(
        "  Class weights%s: flat=%.2f  long=%.2f  short=%.2f  loss=%.2f",
        f" (boosted {args.class_weight_boost:.1f}×)" if args.class_weight_boost > 1.0 else "",
        cw[0],
        cw[1],
        cw[2],
        cw[3],
    )
    weight_tensor = torch.tensor(cw, dtype=torch.float32).to(device)

    if args.loss_type == "focal":
        criterion = FocalLoss(
            weight=weight_tensor,
            gamma=args.focal_gamma,
            label_smoothing=args.label_smoothing,
        )
        logger.info(
            "  Loss: FocalLoss(γ=%.1f, smooth=%.2f)", args.focal_gamma, args.label_smoothing
        )
    else:
        criterion = nn.CrossEntropyLoss(weight=weight_tensor, label_smoothing=args.label_smoothing)
        logger.info("  Loss: CrossEntropyLoss(smooth=%.2f)", args.label_smoothing)

    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = LambdaLR(
        optimizer,
        lr_lambda=lambda ep: warmup_cosine_lr(ep, args.warmup_epochs, args.epochs),
    )

    use_amp = device.type == "cuda"
    scaler = torch.amp.GradScaler(device="cuda") if use_amp else None

    es_mode = "max" if args.early_stop_metric == "macro_f1" else "min"
    early_stop = EarlyStopping(patience=args.early_stop_patience, mode=es_mode)
    logger.info(
        "  Early stopping: metric=%s, patience=%d",
        args.early_stop_metric,
        args.early_stop_patience,
    )

    # FIX #6 (documented): EMA smoothing only controls *when* early stopping
    # fires — the best checkpoint is always saved on the raw metric peak.
    # With alpha=0.3 the EMA lags ~3 epochs, making the effective patience
    # approximately (patience + 3).  This is intentional: it prevents stopping
    # on a single noisy valley without delaying recovery detection much.
    _es_ema: float | None = None
    _es_ema_alpha: float = 0.3

    # ── 6. Training loop ──────────────────────────────────────────────────────
    best_val_acc = 0.0
    best_macro_f1 = 0.0
    best_metric = 0.0
    best_epoch = 0
    best_state: dict | None = None
    train_history: list[dict] = []

    t_train = time.time()

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        train_bar = tqdm(
            train_dl,
            desc=f"  [{asset_key.upper()}] Epoch {epoch:2d}/{args.epochs} train",
            leave=False,
            bar_format="{desc} {bar} {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]  {postfix}",
        )
        optimizer.zero_grad()

        # FIX #3: use enumerate() instead of tqdm.n.  tqdm.n is the
        # *completed* iteration count so on the first batch tqdm.n==1, not 0,
        # causing the first accumulation step to fire one batch too early.
        for batch_idx, (x_batch, y_batch) in enumerate(train_bar):
            x_batch = x_batch.to(device)
            y_batch = y_batch.to(device)

            # ── Mixup augmentation ──────────────────────────────────────────
            if args.mixup_alpha > 0:
                lam = float(np.random.beta(args.mixup_alpha, args.mixup_alpha))
                lam = max(lam, 1.0 - lam)
                idx = torch.randperm(x_batch.size(0), device=device)
                x_batch = lam * x_batch + (1.0 - lam) * x_batch[idx]
                y_a = F.one_hot(y_batch, N_CLASSES).float()
                y_b = F.one_hot(y_batch[idx], N_CLASSES).float()
                mixed_y = lam * y_a + (1.0 - lam) * y_b
                use_soft = True
            else:
                use_soft = False

            ctx = torch.amp.autocast(device_type="cuda") if use_amp else contextlib.nullcontext()
            with ctx:
                logits = model(x_batch)
                if use_soft:
                    smooth = args.label_smoothing
                    mixed_y = mixed_y * (1.0 - smooth) + smooth / N_CLASSES
                    log_probs = F.log_softmax(logits, dim=-1)
                    ce = -(mixed_y * log_probs)
                    if hasattr(criterion, "weight") and criterion.weight is not None:
                        ce = ce * criterion.weight.unsqueeze(0)
                    ce = ce.sum(dim=-1)
                    if args.loss_type == "focal" and args.focal_gamma > 0:
                        probs = torch.exp(log_probs)
                        pt = (mixed_y * probs).sum(dim=-1)
                        ce = ((1.0 - pt) ** args.focal_gamma) * ce
                    loss = ce.mean()
                else:
                    loss = criterion(logits, y_batch)

            loss = loss / accum_steps

            if scaler is not None:
                scaler.scale(loss).backward()
            else:
                loss.backward()

            if (batch_idx + 1) % accum_steps == 0 or (batch_idx + 1) == len(train_dl):
                if scaler is not None:
                    scaler.unscale_(optimizer)
                    nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    optimizer.step()
                optimizer.zero_grad()

            batch_loss = loss.item() * accum_steps
            train_bar.set_postfix_str(f"loss={batch_loss:.4f}")
            train_loss += batch_loss * len(y_batch)
            # FIX #7 (documented): when mixup is active, y_batch are the
            # hard labels pre-mix.  Accuracy computed here will read low
            # (because the model was trained on soft targets) but it does not
            # affect val metrics, checkpointing, or early stopping.
            preds = logits.argmax(dim=-1)
            train_correct += int((preds == y_batch).sum())
            train_total += len(y_batch)

        avg_train_loss = train_loss / max(train_total, 1)
        train_acc = train_correct / max(train_total, 1)

        # ── Validation ────────────────────────────────────────────────────────
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        val_preds_all: list[int] = []
        val_labels_all: list[int] = []

        val_bar = tqdm(
            val_dl,
            desc=f"  [{asset_key.upper()}] Epoch {epoch:2d}/{args.epochs} val  ",
            leave=False,
            bar_format="{desc} {bar} {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        )
        with torch.no_grad():
            for x_batch, y_batch in val_bar:
                x_batch = x_batch.to(device)
                y_batch = y_batch.to(device)
                ctx = (
                    torch.amp.autocast(device_type="cuda") if use_amp else contextlib.nullcontext()
                )
                with ctx:
                    logits = model(x_batch)
                    loss = criterion(logits, y_batch)
                val_loss += loss.item() * len(y_batch)
                preds = logits.argmax(dim=-1)
                val_correct += int((preds == y_batch).sum())
                val_total += len(y_batch)
                val_preds_all.extend(preds.cpu().tolist())
                val_labels_all.extend(y_batch.cpu().tolist())

        avg_val_loss = val_loss / max(val_total, 1)
        val_acc = val_correct / max(val_total, 1)

        # Macro F1 (inline to avoid sklearn dependency in hot path)
        _vp = np.array(val_preds_all, dtype=np.int64)
        _vl = np.array(val_labels_all, dtype=np.int64)
        _f1s = []
        for _ci in range(N_CLASSES):
            _tp = int(((_vp == _ci) & (_vl == _ci)).sum())
            _fp = int(((_vp == _ci) & (_vl != _ci)).sum())
            _fn = int(((_vp != _ci) & (_vl == _ci)).sum())
            _p = _tp / max(_tp + _fp, 1)
            _r = _tp / max(_tp + _fn, 1)
            _f1s.append(2 * _p * _r / max(_p + _r, 1e-8))
        macro_f1 = sum(_f1s) / len(_f1s)

        current_metric = macro_f1 if args.early_stop_metric == "macro_f1" else val_acc
        if current_metric > best_metric:
            best_metric = current_metric
            best_val_acc = val_acc
            best_macro_f1 = macro_f1
            best_epoch = epoch
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        train_history.append(
            {
                "epoch": epoch,
                "train_loss": round(avg_train_loss, 4),
                "train_acc": round(train_acc, 4),
                "val_loss": round(avg_val_loss, 4),
                "val_acc": round(val_acc, 4),
                "macro_f1": round(macro_f1, 4),
            }
        )

        tqdm.write(
            f"  [{asset_key.upper()}] Epoch {epoch:3d}/{args.epochs}  "
            f"train_loss={avg_train_loss:.4f}  train_acc={train_acc:.3f}  "
            f"val_loss={avg_val_loss:.4f}  val_acc={val_acc:.3f}  F1={macro_f1:.3f}"
            + ("  ★ best" if epoch == best_epoch else "")
        )

        # FIX #4: scheduler advances every epoch including the early-stop
        # epoch.  The old code placed scheduler.step() after the break, so
        # the LR was never advanced on the final epoch.
        scheduler.step()

        # Early stopping — EMA-smoothed (see FIX #6 comment above)
        es_value_raw = macro_f1 if args.early_stop_metric == "macro_f1" else avg_val_loss
        _es_ema = (
            es_value_raw
            if _es_ema is None
            else _es_ema_alpha * es_value_raw + (1 - _es_ema_alpha) * _es_ema
        )
        if early_stop(_es_ema):
            logger.info(
                "  [%s] Early stopping at epoch %d (patience=%d, best_%s=%.4f)",
                asset_key.upper(),
                epoch,
                args.early_stop_patience,
                args.early_stop_metric,
                early_stop._best,
            )
            break

    elapsed = time.time() - t_train
    logger.info(
        "Training complete for %s in %.1fs  best_val_acc=%.3f  best_macro_f1=%.3f @ epoch %d",
        asset_key.upper(),
        elapsed,
        best_val_acc,
        best_macro_f1,
        best_epoch,
    )

    # ── Restore best checkpoint ───────────────────────────────────────────────
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()

    # FIX #5: re-run inference with the *best* checkpoint.
    # val_preds_all / val_labels_all above were collected during the last
    # training epoch (which may not be the best epoch).  All downstream
    # metrics — per-class P/R/F1, directional gate, temperature calibration —
    # must reflect the saved weights, not the final epoch.
    val_preds_all, val_labels_all = _run_val_inference(model, val_dl, device, use_amp)

    # ── 7. Per-class metrics ──────────────────────────────────────────────────
    class_names = ["flat", "long", "short", "loss"]
    per_class = _compute_per_class(val_preds_all, val_labels_all, class_names)

    logger.info("Validation per-class metrics (best checkpoint):")
    for cls_name, m in per_class.items():
        logger.info(
            "  %-8s  P=%.3f  R=%.3f  F1=%.3f  support=%d",
            cls_name,
            m["precision"],
            m["recall"],
            m["f1"],
            m["support"],
        )

    # ── 7a. Directional gating ────────────────────────────────────────────────
    RECALL_BLIND_THRESHOLD = 0.15
    long_recall = per_class.get("long", {}).get("recall", 0.0)
    short_recall = per_class.get("short", {}).get("recall", 0.0)

    if long_recall < RECALL_BLIND_THRESHOLD and short_recall >= RECALL_BLIND_THRESHOLD:
        directional_gate = "short_only"
        logger.warning(
            "  [%s] Long recall %.1f%% < %.0f%% — model is LONG-BLIND, gating to short-only",
            asset_key.upper(),
            long_recall * 100,
            RECALL_BLIND_THRESHOLD * 100,
        )
    elif short_recall < RECALL_BLIND_THRESHOLD and long_recall >= RECALL_BLIND_THRESHOLD:
        directional_gate = "long_only"
        logger.warning(
            "  [%s] Short recall %.1f%% < %.0f%% — model is SHORT-BLIND, gating to long-only",
            asset_key.upper(),
            short_recall * 100,
            RECALL_BLIND_THRESHOLD * 100,
        )
    elif long_recall < RECALL_BLIND_THRESHOLD and short_recall < RECALL_BLIND_THRESHOLD:
        directional_gate = "flat_only"
        logger.warning(
            "  [%s] Both long (%.1f%%) and short (%.1f%%) recall below %.0f%% — DIRECTION-BLIND",
            asset_key.upper(),
            long_recall * 100,
            short_recall * 100,
            RECALL_BLIND_THRESHOLD * 100,
        )
    else:
        directional_gate = "both"
        logger.info(
            "  [%s] Directional gate: both (long_R=%.1f%%, short_R=%.1f%%)",
            asset_key.upper(),
            long_recall * 100,
            short_recall * 100,
        )

    # ── 7b. Train→Val degradation ─────────────────────────────────────────────
    final_train_acc = train_history[-1]["train_acc"] if train_history else 0.0
    degradation = (final_train_acc - best_val_acc) / (abs(final_train_acc) + 1e-10)
    model_confidence = "high" if degradation < 0.2 else "medium" if degradation < 0.5 else "low"
    logger.info(
        "  [%s] Model confidence: %s  (train_acc=%.3f → val_acc=%.3f, degradation=%.2f)",
        asset_key.upper(),
        model_confidence,
        final_train_acc,
        best_val_acc,
        degradation,
    )

    # ── 8. Quality gate ───────────────────────────────────────────────────────
    save_metric = best_macro_f1 if args.early_stop_metric == "macro_f1" else best_val_acc
    save_metric_name = "macro_f1" if args.early_stop_metric == "macro_f1" else "val_acc"

    # FIX #9: flat_pct is surfaced in _base_result so promote_champions can
    # apply the degenerate-label gate before deciding on first-champion promotion.
    _base_result = {
        "asset": asset_key,
        "flat_pct": round(flat_pct, 4),  # consumed by promote_champions gate
        "best_val_acc": best_val_acc,
        "val_accuracy": round(best_val_acc, 4),
        "val_macro_f1": round(best_macro_f1, 4),
        "model_confidence": model_confidence,
        "degradation": round(degradation, 4),
        "per_class": per_class,
        "directional_gate": directional_gate,
    }

    if save_metric < args.min_val_accuracy:
        logger.warning(
            "Best %s=%.3f < threshold=%.3f — model NOT saved for %s",
            save_metric_name,
            save_metric,
            args.min_val_accuracy,
            asset_key.upper(),
        )
        return {
            **_base_result,
            "saved": False,
            "reason": f"{save_metric_name} {save_metric:.3f} below threshold {args.min_val_accuracy:.3f}",
            "temperature": 1.0,
            "ece_before": 0.0,
            "ece_after": 0.0,
        }

    # ── Temperature calibration ───────────────────────────────────────────────
    models_dir = Path(args.models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / f"cnn_{asset_key.lower()}.pt"
    prev_meta = load_existing_meta(model_path)

    logger.info("  [%s] Calibrating softmax temperature on val set...", asset_key.upper())
    try:
        temperature, ece_before, ece_after = calibrate_temperature(
            model,
            val_dl,
            device,
            n_classes=N_CLASSES,
        )
        logger.info(
            "  [%s] Temperature: %.3f  ECE: %.4f → %.4f",
            asset_key.upper(),
            temperature,
            ece_before,
            ece_after,
        )
    except Exception as exc:
        logger.warning(
            "  [%s] Temperature calibration failed: %s — using T=1.0",
            asset_key.upper(),
            exc,
        )
        temperature, ece_before, ece_after = 1.0, 0.0, 0.0

    meta = {
        **_base_result,
        "symbol": symbol,
        "trained_at": datetime.now(UTC).isoformat(),
        "training_bars": len(df),
        "timeframe": args.timeframe,
        "window": args.window,
        "epochs": args.epochs,
        "best_epoch": best_epoch,
        "temperature": temperature,
        "ece_before": ece_before,
        "ece_after": ece_after,
        "label_distribution": summary,
        "hyperparams": {
            "lr": args.lr,
            "batch_size": args.batch_size,
            "weight_decay": args.weight_decay,
            # Resolved label_params used, not CLI defaults, so the sidecar
            # accurately reflects pre-tuned / Optuna / CLI values.
            "consolidation_bars": label_params["consolidation_bars"],
            "consolidation_atr_mult": label_params["consolidation_atr_mult"],
            "max_breakout_wait": label_params["max_breakout_wait"],
            "tp_atr_mult": label_params["tp_atr_mult"],
            "sl_atr_mult": label_params["sl_atr_mult"],
            "max_forward_bars": label_params["max_hold_bars"],
            "label_smoothing": args.label_smoothing,
            "mixup_alpha": args.mixup_alpha,
            "warmup_epochs": args.warmup_epochs,
            "loss_type": args.loss_type,
            "focal_gamma": args.focal_gamma if args.loss_type == "focal" else None,
            "class_weight_boost": args.class_weight_boost,
            "early_stop_metric": args.early_stop_metric,
        },
        "train_history": train_history[-10:],
    }

    # FIX #8: model.save() already writes the sidecar JSON internally.
    # The previous model.save_meta() call was a duplicate write.
    model.save(model_path, meta=meta)

    logger.info(
        "Saved %s model → %s  (val_acc=%.3f)",
        asset_key.upper(),
        model_path,
        best_val_acc,
    )

    if prev_meta is not None:
        print_champion_comparison(asset_key.upper(), prev_meta, meta)

    return {**meta, "saved": True, "model_path": str(model_path)}
