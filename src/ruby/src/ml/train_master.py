"""
ml/train_master.py — MasterCNN portfolio risk model training.

Public API
----------
    train_master(asset_keys, exchange, args, device, cache=None) -> dict | None

Fixes applied vs the original monolithic train.py
---------------------------------------------------
    #1  All imports are at module level (no deferred imports).
    #3  Gradient accumulation step boundary uses ``enumerate`` instead of
        ``tqdm.n`` (same off-by-one fix as in train_asset.py).
    #4  ``scheduler.step()`` is called before the early-stopping check so the
        LR schedule advances on the final (early-stop) epoch.
    #5  Per-class metrics are computed from a fresh inference pass after the
        best checkpoint is restored, not from the final epoch's cached preds.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import LambdaLR
from tqdm import tqdm

import pandas as pd

from ml.dataset import PortfolioDataset, build_portfolio_dataloaders
from ml.features import N_FEATURES
from ml.kline_cache import KlineCache
from ml.labeler import fetch_klines
from ml.model import N_CLASSES, build_master_cnn
from ml.reporting import load_existing_meta, print_champion_comparison
from ml.training_components import EarlyStopping, warmup_cosine_lr
from ml.train_asset import ASSET_SYMBOLS

logger = logging.getLogger("train.master")

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message=".*lr_scheduler.step.*before.*optimizer.step.*",
)


# ── Encoder warm-start ────────────────────────────────────────────────────────

def _init_encoder_from_per_asset(
    master_model: Any,
    models_dir: Path,
    asset_keys: list[str],
) -> int:
    """Average per-asset encoder weights and use them to warm-start the master.

    Loads all available per-asset CNN checkpoints from *models_dir*, averages
    their ``encoder.*`` state-dict entries, and copies the result into
    ``master_model.encoder``.

    Returns the number of per-asset models successfully loaded.
    """
    from ml.model import PerAssetCNN

    encoder_states: list[dict[str, torch.Tensor]] = []

    for key in asset_keys:
        pt_path = models_dir / f"cnn_{key.lower()}.pt"
        if not pt_path.exists():
            continue
        try:
            per_asset = PerAssetCNN.load(str(pt_path), map_location="cpu")
            enc_state = {
                k: v.clone()
                for k, v in per_asset.state_dict().items()
                if k.startswith("encoder.")
            }
            if enc_state:
                encoder_states.append(enc_state)
        except Exception as exc:
            logger.warning("Could not load encoder from %s: %s", pt_path, exc)

    if not encoder_states:
        logger.info("  No per-asset encoders available for warm-start")
        return 0

    avg_state: dict[str, torch.Tensor] = {
        k: torch.stack([s[k].float() for s in encoder_states]).mean(dim=0)
        for k in encoder_states[0].keys()
    }

    master_enc_state   = master_model.encoder.state_dict()
    compatible_state:  dict[str, torch.Tensor] = {}
    skipped_keys:      list[str] = []

    for k, v in avg_state.items():
        clean_key = k.replace("encoder.", "")
        if clean_key in master_enc_state and master_enc_state[clean_key].shape == v.shape:
            compatible_state[clean_key] = v
        else:
            skipped_keys.append(clean_key)

    if compatible_state:
        master_model.encoder.load_state_dict(compatible_state, strict=False)

    n_loaded = sum(v.numel() for v in compatible_state.values())
    n_total  = sum(v.numel() for v in avg_state.values())
    logger.info(
        "  Warm-started master encoder from %d per-asset models (%d/%d params loaded)",
        len(encoder_states), n_loaded, n_total,
    )
    if skipped_keys:
        logger.info(
            "  Skipped %d shape-mismatched encoder layers: %s",
            len(skipped_keys),
            ", ".join(skipped_keys[:5]) + ("..." if len(skipped_keys) > 5 else ""),
        )
    return len(encoder_states)


# ── Val inference helper ──────────────────────────────────────────────────────

def _run_val_inference(
    model: nn.Module,
    val_dl: Any,
    device: torch.device,
    use_amp: bool,
) -> tuple[list[int], list[int], list[float]]:
    """Return (hard_preds, hard_labels, probs) lists for the full val set.

    Called after the best checkpoint is restored so per-class metrics reflect
    the saved model rather than the final training epoch.  (Fix #5.)
    """
    preds_all:  list[int]   = []
    labels_all: list[int]   = []
    probs_all:  list[float] = []
    model.eval()
    with torch.no_grad():
        for x_batch, y_batch in val_dl:
            x_batch = x_batch.to(device)
            y_batch = y_batch.to(device).unsqueeze(-1)
            ctx = torch.amp.autocast(device_type="cuda") if use_amp else contextlib.nullcontext()
            with ctx:
                logits = model(x_batch)
            probs  = torch.sigmoid(logits)
            preds  = (logits >= 0.0).long().squeeze(-1)
            labels = (y_batch >= 0.5).long().squeeze(-1)
            preds_all.extend(preds.cpu().tolist())
            labels_all.extend(labels.cpu().tolist())
            probs_all.extend(probs.squeeze(-1).cpu().tolist())
    return preds_all, labels_all, probs_all


def _compute_binary_per_class(
    preds: list[int] | np.ndarray,
    labels: list[int] | np.ndarray,
) -> dict[str, dict[str, float]]:
    vp = np.asarray(preds,  dtype=np.int64)
    vl = np.asarray(labels, dtype=np.int64)
    per_class: dict[str, dict[str, float]] = {}
    for idx, name in [(0, "safe"), (1, "risky")]:
        tp = int(((vp == idx) & (vl == idx)).sum())
        fp = int(((vp == idx) & (vl != idx)).sum())
        fn = int(((vp != idx) & (vl == idx)).sum())
        precision = tp / max(tp + fp, 1)
        recall    = tp / max(tp + fn, 1)
        f1        = 2 * precision * recall / max(precision + recall, 1e-8)
        per_class[name] = {
            "precision": round(precision, 4),
            "recall":    round(recall,    4),
            "f1":        round(f1,        4),
            "support":   tp + fn,
        }
    return per_class


# ── Main training function ────────────────────────────────────────────────────

def train_master(
    asset_keys: list[str],
    exchange: Any,
    args: argparse.Namespace,
    device: torch.device,
    cache: KlineCache | None = None,
) -> dict[str, Any] | None:
    """Train a MasterCNN portfolio risk model.

    Fetches klines for all assets, aligns them on a common time index, and
    trains on portfolio-level drawdown labels.

    SWA note
    --------
    SWA has been removed.  In the previous run the master SWA model produced
    F1=0.422 vs the best checkpoint's F1=0.537 — worse by a large margin.
    """
    logger.info("=" * 60)
    logger.info("Training MasterCNN  (assets=%s)", asset_keys)
    logger.info("=" * 60)

    # ── 1. Fetch data for all assets ──────────────────────────────────────────
    asset_dfs:   list[Any] = []
    asset_names: list[str] = []

    for i, key in enumerate(asset_keys, 1):
        logger.info("  [MASTER] Fetching data %d/%d: %s", i, len(asset_keys), key)
        symbol = ASSET_SYMBOLS.get(key)
        if symbol is None:
            logger.warning("Unknown asset %s — skipping for master model", key)
            continue

        if cache is not None:
            cache.reset_stats()

        df = fetch_klines(
            exchange=exchange,
            symbol=symbol,
            timeframe=args.timeframe,
            limit=args.bars,
            cache=cache,
            min_bars=getattr(args, "min_bars", 5_000),
        )

        if df.empty or len(df) < 500:
            logger.warning("Insufficient data for %s — skipping for master model", key)
            continue

        if cache is not None:
            logger.info("  [master/%s] %s", key, cache.stats_line())

        asset_dfs.append(df)
        asset_names.append(key)

    if len(asset_dfs) < 2:
        logger.error("Need at least 2 assets for MasterCNN — aborting")
        return None

    # ── 2. Timestamp-based alignment ─────────────────────────────────────────
    has_timestamps = all("timestamp" in df.columns for df in asset_dfs)

    if has_timestamps:
        common_start = max(df["timestamp"].iloc[0]  for df in asset_dfs)
        common_end   = min(df["timestamp"].iloc[-1] for df in asset_dfs)
        aligned = [
            df[(df["timestamp"] >= common_start) & (df["timestamp"] <= common_end)]
            .reset_index(drop=True)
            for df in asset_dfs
        ]
        min_len = min(len(df) for df in aligned)
        aligned = [df.tail(min_len).reset_index(drop=True) for df in aligned]
        logger.info(
            "Timestamp-aligned %d assets to %d bars (range: %s → %s)",
            len(aligned), min_len,
            pd.Timestamp(common_start, unit="ms"),
            pd.Timestamp(common_end,   unit="ms"),
        )
    else:
        min_len = min(len(df) for df in asset_dfs)
        aligned = [df.tail(min_len).reset_index(drop=True) for df in asset_dfs]
        logger.info(
            "Aligned %d assets to %d bars (no timestamp column — using tail alignment)",
            len(aligned), min_len,
        )

    n_assets = len(aligned)

    if args.dry_run:
        logger.info("Dry-run: skipping MasterCNN training")
        return {"dry_run": True, "n_assets": n_assets, "bars": min_len}

    # ── 3. Build PortfolioDataset & DataLoaders ───────────────────────────────
    drawdown_atr_mult       = 3.0
    forward_bars            = min(args.max_forward_bars, 30)
    min_assets_in_drawdown  = max(2, (len(aligned) + 1) // 2)

    dataset = PortfolioDataset(
        asset_dfs=aligned,
        window=args.window,
        forward_bars=forward_bars,
        drawdown_pct=drawdown_atr_mult,
        min_assets_in_drawdown=min_assets_in_drawdown,
    )

    if len(dataset) < 100:
        logger.error("PortfolioDataset too small (%d) — aborting master training", len(dataset))
        return None

    labels_arr = dataset.label_array()
    n_risky = int(labels_arr.sum())
    n_safe  = len(labels_arr) - n_risky
    logger.info(
        "  Portfolio labels: safe=%d (%.1f%%)  risky=%d (%.1f%%)",
        n_safe,  n_safe  / max(len(labels_arr), 1) * 100,
        n_risky, n_risky / max(len(labels_arr), 1) * 100,
    )

    train_dl, val_dl = build_portfolio_dataloaders(
        dataset=dataset,
        batch_size=args.batch_size,
        val_split=args.val_split,
        num_workers=0,
        use_weighted_sampler=True,
    )

    # ── 4. Build model ────────────────────────────────────────────────────────
    master_embedding_dim   = getattr(args, "master_embedding_dim",   48)
    master_dropout         = getattr(args, "master_dropout",         0.4)
    master_encoder_dropout = getattr(args, "master_encoder_dropout", 0.25)

    model = build_master_cnn(
        n_assets=n_assets,
        n_features=N_FEATURES,
        window=args.window,
        embedding_dim=master_embedding_dim,
        dropout=master_dropout,
        encoder_dropout=master_encoder_dropout,
    ).to(device)

    logger.info("MasterCNN: %d parameters  n_assets=%d", model.param_count(), n_assets)

    models_dir = Path(args.models_dir)
    n_warmstart = _init_encoder_from_per_asset(model, models_dir, asset_names)

    # ── 5. Loss, optimiser, scheduler, AMP, early stopping ───────────────────
    accum_steps     = 4
    effective_batch = args.batch_size * accum_steps
    logger.info(
        "  Gradient accumulation: %d steps -> effective batch %d",
        accum_steps, effective_batch,
    )

    if n_risky > 0 and n_safe > 0:
        raw_pw    = n_safe / n_risky
        clamped_pw = max(0.1, min(10.0, raw_pw))
        if abs(raw_pw - clamped_pw) > 0.01:
            logger.warning(
                "  pos_weight clamped: raw=%.4f -> %.2f  (%d safe / %d risky)",
                raw_pw, clamped_pw, n_safe, n_risky,
            )
        pos_weight = torch.tensor([clamped_pw], dtype=torch.float32).to(device)
        logger.info("  BCE pos_weight: %.2f (safe/risky ratio)", pos_weight.item())
    else:
        pos_weight = torch.ones(1, dtype=torch.float32).to(device)
        logger.warning("  BCE pos_weight: 1.00 (one class is empty — labels are degenerate)")

    criterion  = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer  = AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler  = LambdaLR(
        optimizer,
        lr_lambda=lambda ep: warmup_cosine_lr(ep, args.warmup_epochs, args.epochs),
    )

    use_amp    = device.type == "cuda"
    scaler     = torch.amp.GradScaler(device="cuda") if use_amp else None
    early_stop = EarlyStopping(patience=args.early_stop_patience, mode="max")
    logger.info("  Early stopping: metric=val_f1, patience=%d", args.early_stop_patience)

    _es_ema:       float | None = None
    _es_ema_alpha: float        = 0.3

    # ── 6. Training loop ──────────────────────────────────────────────────────
    best_val_f1  = 0.0
    best_val_acc = 0.0
    best_val_loss = float("inf")
    best_epoch    = 0
    best_state:   dict | None = None
    train_history: list[dict] = []

    t_train = time.time()

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss    = 0.0
        train_correct = 0
        train_total   = 0

        train_bar = tqdm(
            train_dl,
            desc=f"  [MASTER] Epoch {epoch:2d}/{args.epochs} train",
            leave=False,
            bar_format="{desc} {bar} {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]  {postfix}",
        )
        optimizer.zero_grad()

        # FIX #3: enumerate instead of tqdm.n
        for batch_idx, (x_batch, y_batch) in enumerate(train_bar):
            x_batch = x_batch.to(device)
            y_batch = y_batch.to(device).unsqueeze(-1)  # (batch, 1)

            if args.mixup_alpha > 0:
                lam     = float(np.random.beta(args.mixup_alpha, args.mixup_alpha))
                lam     = max(lam, 1.0 - lam)
                idx     = torch.randperm(x_batch.size(0), device=device)
                x_batch = lam * x_batch + (1.0 - lam) * x_batch[idx]
                y_batch = lam * y_batch + (1.0 - lam) * y_batch[idx]

            ctx = torch.amp.autocast(device_type="cuda") if use_amp else contextlib.nullcontext()
            with ctx:
                logits = model(x_batch)
                loss   = criterion(logits, y_batch)

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
            preds   = (logits >= 0.0).float()
            hard_y  = (y_batch >= 0.5).float()
            train_correct += int((preds == hard_y).sum())
            train_total   += len(y_batch)

        avg_train_loss = train_loss / max(train_total, 1)
        train_acc      = train_correct / max(train_total, 1)

        # ── Validation ────────────────────────────────────────────────────────
        model.eval()
        val_loss_sum    = 0.0
        val_total       = 0
        val_preds_all:  list[int]   = []
        val_labels_all: list[int]   = []

        val_bar = tqdm(
            val_dl,
            desc=f"  [MASTER] Epoch {epoch:2d}/{args.epochs} val  ",
            leave=False,
            bar_format="{desc} {bar} {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        )
        with torch.no_grad():
            for x_batch, y_batch in val_bar:
                x_batch = x_batch.to(device)
                y_batch = y_batch.to(device).unsqueeze(-1)
                ctx = torch.amp.autocast(device_type="cuda") if use_amp else contextlib.nullcontext()
                with ctx:
                    logits = model(x_batch)
                    loss   = criterion(logits, y_batch)
                val_loss_sum += loss.item() * len(y_batch)
                val_total    += len(y_batch)
                preds  = (logits >= 0.0).long().squeeze(-1)
                labels = (y_batch >= 0.5).long().squeeze(-1)
                val_preds_all.extend(preds.cpu().tolist())
                val_labels_all.extend(labels.cpu().tolist())

        avg_val_loss = val_loss_sum / max(val_total, 1)
        _vp = np.array(val_preds_all,  dtype=np.int64)
        _vl = np.array(val_labels_all, dtype=np.int64)
        val_acc  = float((_vp == _vl).mean())
        _pc      = _compute_binary_per_class(val_preds_all, val_labels_all)
        macro_f1 = sum(c["f1"] for c in _pc.values()) / max(len(_pc), 1)

        if macro_f1 > best_val_f1:
            best_val_f1  = macro_f1
            best_val_acc = val_acc
            best_val_loss = avg_val_loss
            best_epoch   = epoch
            best_state   = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        train_history.append({
            "epoch":      epoch,
            "train_loss": round(avg_train_loss, 4),
            "train_acc":  round(train_acc,      4),
            "val_loss":   round(avg_val_loss,   4),
            "val_acc":    round(val_acc,         4),
            "val_f1":     round(macro_f1,        4),
        })

        tqdm.write(
            f"  [MASTER] Epoch {epoch:3d}/{args.epochs}  "
            f"train_loss={avg_train_loss:.4f}  val_loss={avg_val_loss:.4f}  "
            f"val_acc={val_acc:.3f}  F1={macro_f1:.3f}"
            + ("  ★ best" if epoch == best_epoch else "")
        )

        # FIX #4: scheduler advances before early-stop check
        scheduler.step()

        _es_ema = (
            macro_f1
            if _es_ema is None
            else _es_ema_alpha * macro_f1 + (1 - _es_ema_alpha) * _es_ema
        )
        if early_stop(_es_ema):
            logger.info(
                "  [MASTER] Early stopping at epoch %d (patience=%d, best_val_f1=%.4f)",
                epoch, args.early_stop_patience, early_stop._best,
            )
            break

    elapsed = time.time() - t_train
    logger.info(
        "MasterCNN training complete in %.1fs  best_val_f1=%.3f  val_acc=%.3f @ epoch %d",
        elapsed, best_val_f1, best_val_acc, best_epoch,
    )

    # ── Restore best checkpoint ───────────────────────────────────────────────
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()

    # FIX #5: re-run inference with best checkpoint
    val_preds_all, val_labels_all, _ = _run_val_inference(model, val_dl, device, use_amp)
    per_class = _compute_binary_per_class(val_preds_all, val_labels_all)

    logger.info("Validation per-class metrics (best checkpoint, Master):")
    for cls_name, m in per_class.items():
        logger.info(
            "  %-8s  P=%.3f  R=%.3f  F1=%.3f  support=%d",
            cls_name, m["precision"], m["recall"], m["f1"], m["support"],
        )

    # ── 7a. Model confidence ──────────────────────────────────────────────────
    final_train_acc = train_history[-1]["train_acc"] if train_history else 0.0
    degradation     = (final_train_acc - best_val_acc) / (abs(final_train_acc) + 1e-10)
    model_confidence = (
        "high"   if degradation < 0.2 else
        "medium" if degradation < 0.5 else
        "low"
    )
    logger.info(
        "  [MASTER] Model confidence: %s  (train_acc=%.3f -> val_acc=%.3f, degradation=%.2f)",
        model_confidence, final_train_acc, best_val_acc, degradation,
    )

    # ── 8. Quality gate ───────────────────────────────────────────────────────
    min_master_f1 = 0.35
    safe_f1       = per_class.get("safe",  {}).get("f1", 0.0)
    risky_f1      = per_class.get("risky", {}).get("f1", 0.0)
    min_class_f1  = min(safe_f1, risky_f1)

    _base = {
        "type":             "master",
        "val_accuracy":     round(best_val_acc,  4),
        "val_f1":           round(best_val_f1,   4),
        "best_val_loss":    round(best_val_loss, 4),
        "per_class":        per_class,
        "model_confidence": model_confidence,
    }

    if min_class_f1 < 0.05:
        logger.warning(
            "Master model is DEGENERATE — min per-class F1=%.3f (safe=%.3f risky=%.3f). "
            "Labels likely too skewed (safe=%.1f%% risky=%.1f%%). "
            "Try increasing min_assets_in_drawdown or drawdown_pct.",
            min_class_f1, safe_f1, risky_f1,
            n_safe  / max(n_safe + n_risky, 1) * 100,
            n_risky / max(n_safe + n_risky, 1) * 100,
        )
        return {
            **_base,
            "saved":  False,
            "reason": (
                f"degenerate model — min per-class F1={min_class_f1:.3f} "
                f"(safe={safe_f1:.3f} risky={risky_f1:.3f}), "
                f"labels: {n_safe} safe / {n_risky} risky"
            ),
            "model_confidence": "degenerate",
        }

    if best_val_f1 < min_master_f1:
        logger.warning(
            "Master val_f1=%.3f < threshold=%.3f — model NOT saved",
            best_val_f1, min_master_f1,
        )
        return {**_base, "saved": False, "reason": f"val_f1 {best_val_f1:.3f} below threshold {min_master_f1:.3f}"}

    if safe_f1 < 0.10 or risky_f1 < 0.10:
        logger.warning(
            "Master model has weak class coverage — safe F1=%.3f, risky F1=%.3f. "
            "Saved but may not provide reliable portfolio gating.",
            safe_f1, risky_f1,
        )

    # ── 9. Save ───────────────────────────────────────────────────────────────
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / "cnn_master.pt"
    prev_meta  = load_existing_meta(model_path)

    meta = {
        **_base,
        "assets":         asset_names,
        "n_assets":       n_assets,
        "trained_at":     datetime.now(UTC).isoformat(),
        "training_bars":  min_len,
        "timeframe":      args.timeframe,
        "window":         args.window,
        "epochs":         args.epochs,
        "best_epoch":     best_epoch,
        "degradation":    round(degradation, 4),
        "n_warmstart_models": n_warmstart,
        "label_distribution": {
            "safe":      n_safe,
            "risky":     n_risky,
            "risky_pct": round(n_risky / max(n_safe + n_risky, 1) * 100, 1),
        },
        "hyperparams": {
            "lr":                    args.lr,
            "batch_size":            args.batch_size,
            "effective_batch_size":  effective_batch,
            "weight_decay":          args.weight_decay,
            "drawdown_atr_mult":     drawdown_atr_mult,
            "forward_bars":          forward_bars,
            "warmup_epochs":         args.warmup_epochs,
            "mixup_alpha":           args.mixup_alpha,
            "early_stop_metric":     "val_f1",
            "early_stop_patience":   args.early_stop_patience,
            "accum_steps":           accum_steps,
            "master_embedding_dim":  master_embedding_dim,
            "master_dropout":        master_dropout,
            "master_encoder_dropout": master_encoder_dropout,
        },
        "train_history": train_history[-10:],
    }

    model.save(model_path, meta=meta)
    model_path.with_suffix(".json").write_text(json.dumps(meta, indent=2, default=str))

    logger.info(
        "Saved MasterCNN -> %s  (val_f1=%.3f  val_acc=%.3f)",
        model_path, best_val_f1, best_val_acc,
    )

    if prev_meta is not None:
        print_champion_comparison("MASTER", prev_meta, meta)

    return {**meta, "saved": True, "model_path": str(model_path)}
