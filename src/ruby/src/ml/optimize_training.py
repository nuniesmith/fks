"""
ml/optimize_training.py — end-to-end training pipeline with Optuna integration.

Pipeline stages
---------------
  0. Prefetch  — fetch all asset klines and warm the Redis cache in parallel
  1. LabelOpt  — per-asset Optuna label-parameter search (cached, skipped if fresh)
  2. HyperOpt  — training hyperparameter search averaged across proxy assets
  3. Tier-1    — train one PerAssetCNN per asset using best label + hyper params
  4. Tier-2    — train MasterCNN on aligned multi-asset data
  5. Promote   — compare new models vs saved champions; promote and git-tag if better

Changes vs original
-------------------
  A. promote_champions — degenerate label gate blocks promotion when flat_pct > 0.95,
     regardless of whether a champion already exists.  AVAX/DOT/SHIB-style near-flat
     models will never reach production.

  B. run_pipeline — a 10% chronological holdout is carved out before Stage 1 and
     Stage 2 so that Optuna never sees that data.  OOS label-quality scores are
     computed at the end and returned in the summary dict.

  C. optimize_hyperparams / run_pipeline — proxy_asset replaced by proxy_assets
     (list[str] | str).  The Optuna objective averages F1 across all proxy assets
     so that the chosen hyperparams are not over-fitted to BTC's volatility profile.
     Recommended default: proxy_assets=["btc", "pepe"].

Invoke from train.py main() via:
    if args.full_pipeline:
        run_pipeline(args, exchange, device, cache)
        return

Or run standalone:
    python -m src.ml.optimize_training --all --hyper-trials 50 --label-trials 100
"""

from __future__ import annotations

import copy
import json
import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import optuna

optuna.logging.set_verbosity(optuna.logging.WARNING)

logger = logging.getLogger("optimize_training")


# ── Dataclass for resolved best hyperparams ───────────────────────────────────


@dataclass
class HyperParams:
    """Best training hyperparameters found by Optuna (or sensible defaults)."""

    lr: float = 3e-4
    focal_gamma: float = 2.0
    label_smoothing: float = 0.15
    mixup_alpha: float = 0.2
    embedding_dim: int = 64
    dropout: float = 0.3
    weight_decay: float = 5e-4
    class_weight_boost: float = 1.0

    def apply_to(self, args: Any) -> Any:
        """Return a shallow copy of args with these hyperparams applied."""
        a = copy.copy(args)
        a.lr = self.lr
        a.focal_gamma = self.focal_gamma
        a.label_smoothing = self.label_smoothing
        a.mixup_alpha = self.mixup_alpha
        a.embedding_dim = self.embedding_dim  # train_asset reads via getattr
        a.dropout = self.dropout  # train_asset reads via getattr
        a.weight_decay = self.weight_decay
        a.class_weight_boost = self.class_weight_boost
        return a


# ─────────────────────────────────────────────────────────────────────────────
# Stage 0 — Data prefetch
# ─────────────────────────────────────────────────────────────────────────────


def prefetch_all_assets(
    asset_keys: list[str],
    exchange: Any,
    args: Any,
    cache: Any,
    *,
    max_workers: int = 4,
) -> dict[str, Any]:
    """
    Fetch klines for every asset in parallel and warm the Redis cache.

    Returns a dict mapping asset_key → DataFrame (empty df means fetch failed).
    Workers are capped at max_workers to avoid hammering the exchange rate limit.
    """
    from ml.labeler import fetch_klines
    from ml.train import ASSET_SYMBOLS

    logger.info("━" * 60)
    logger.info("Stage 0 — Prefetching %d assets (workers=%d)", len(asset_keys), max_workers)

    results: dict[str, Any] = {}
    t0 = time.time()

    def _fetch(key: str):
        symbol = ASSET_SYMBOLS.get(key)
        if symbol is None:
            logger.warning("[prefetch] Unknown asset key: %s", key)
            return key, None
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
        cache_info = cache.stats_line() if cache is not None else "cache disabled"
        logger.info(
            "[prefetch] %-10s  %6d bars  [%s]",
            key.upper(),
            len(df),
            cache_info,
        )
        return key, df

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch, k): k for k in asset_keys}
        for fut in as_completed(futures):
            key, df = fut.result()
            results[key] = df

    ok = sum(1 for df in results.values() if df is not None and not df.empty)
    logger.info(
        "Stage 0 complete in %.1fs — %d/%d assets cached",
        time.time() - t0,
        ok,
        len(asset_keys),
    )
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Per-asset label optimisation
# ─────────────────────────────────────────────────────────────────────────────


def optimize_all_labels(
    asset_keys: list[str],
    asset_dfs: dict[str, Any],
    args: Any,
    *,
    n_trials: int = 100,
    force: bool = False,
) -> dict[str, dict]:
    """
    Run Optuna label-param search for each asset that has data.

    Skips assets whose cache file is fresher than _CACHE_TTL_DAYS days (and
    whose regime fingerprint matches) unless force=True.
    Returns a mapping of asset_key → best label param dict.
    """
    from ml.optimize_labels import optimize_label_params

    logger.info("━" * 60)
    logger.info("Stage 1 — Label optimisation  (trials=%d, force=%s)", n_trials, force)

    label_params: dict[str, dict] = {}
    models_dir = Path(args.models_dir)
    t0 = time.time()

    for key in asset_keys:
        df = asset_dfs.get(key)
        if df is None or df.empty:
            logger.warning("[label-opt] %s — no data, skipping", key.upper())
            continue

        logger.info("[label-opt] %s — starting %d-trial search ...", key.upper(), n_trials)
        t_asset = time.time()
        params = optimize_label_params(
            asset_key=key,
            df=df,
            n_trials=n_trials,
            models_dir=models_dir,
            force=force,
            verbose=False,
        )
        label_params[key] = params
        logger.info(
            "[label-opt] %s — done in %.1fs  consol_atr=%.2f  bars=%d  tp=%.2f  sl=%.2f",
            key.upper(),
            time.time() - t_asset,
            params["consolidation_atr_mult"],
            params["consolidation_bars"],
            params["tp_atr_mult"],
            params["sl_atr_mult"],
        )

    logger.info(
        "Stage 1 complete in %.1fs — optimised %d/%d assets",
        time.time() - t0,
        len(label_params),
        len(asset_keys),
    )
    return label_params


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Training hyperparameter optimisation
# ─────────────────────────────────────────────────────────────────────────────


def _make_proxy_train_fn(
    proxy_asset: str,
    asset_dfs: dict[str, Any],
    label_params: dict[str, dict],
    exchange: Any,
    base_args: Any,
    device: Any,
    cache: Any,
):
    """
    Return an Optuna objective that trains on a single proxy asset.

    Labels, dataset, and dataloaders are built ONCE here, before the study
    starts, and shared across every trial.  Only the model, loss, optimiser,
    and scheduler are rebuilt per trial — the only things that actually vary.

    Previously these were rebuilt inside every trial, causing ~274s of feature
    precomputation to repeat 50 times (~3.8 hours of pure waste on RTX 3080).
    """
    import contextlib

    import torch
    import torch.nn as nn
    from torch.optim import AdamW
    from torch.optim.lr_scheduler import LambdaLR

    from ml.dataset import AssetDataset, build_dataloaders
    from ml.features import N_FEATURES
    from ml.labeler import class_weights, generate_labels_breakout, label_summary
    from ml.model import N_CLASSES, build_per_asset_cnn
    from ml.training_components import EarlyStopping as _EarlyStopping
    from ml.training_components import FocalLoss
    from ml.training_components import warmup_cosine_lr as _warmup_cosine_lr

    proxy_df = asset_dfs.get(proxy_asset)

    # ── Precompute labels, dataset, and dataloaders ONCE ─────────────────────
    if proxy_df is None or proxy_df.empty:
        logger.error(
            "[hyper-opt] Proxy asset %s has no data — returning dummy objective",
            proxy_asset.upper(),
        )

        def _empty_objective(trial: optuna.Trial) -> float:
            return 0.0

        return _empty_objective

    lp = label_params.get(proxy_asset, {})
    if not lp:
        lp = dict(
            consolidation_bars=base_args.consolidation_bars,
            consolidation_atr_mult=base_args.consolidation_atr_mult,
            max_breakout_wait=base_args.max_breakout_wait,
            tp_atr_mult=base_args.tp_atr_mult,
            sl_atr_mult=base_args.sl_atr_mult,
            max_hold_bars=base_args.max_forward_bars,
        )

    logger.info(
        "[hyper-opt] Pre-computing %s labels + features (once, shared across all trials)...",
        proxy_asset.upper(),
    )
    t_pre = time.time()
    labels = generate_labels_breakout(proxy_df, **lp)
    summary = label_summary(labels)
    n_total = max(sum(summary.values()), 1)
    logger.info(
        "[hyper-opt] Labels: flat=%d (%.1f%%)  long=%d (%.1f%%)  short=%d (%.1f%%)  loss=%d (%.1f%%)",
        summary["flat"],
        summary["flat"] / n_total * 100,
        summary["long"],
        summary["long"] / n_total * 100,
        summary["short"],
        summary["short"] / n_total * 100,
        summary.get("loss", 0),
        summary.get("loss", 0) / n_total * 100,
    )

    shared_dataset = AssetDataset(df=proxy_df, labels=labels, window=base_args.window)
    shared_train_dl, shared_val_dl = build_dataloaders(
        dataset=shared_dataset,
        batch_size=base_args.batch_size,
        val_split=base_args.val_split,
        num_workers=0,
        use_weighted_sampler=True,
    )
    shared_cw = class_weights(labels)

    logger.info(
        "[hyper-opt] Dataset ready in %.1fs — %d samples  "
        "(%d train batches / %d val batches). Starting Optuna trials...",
        time.time() - t_pre,
        len(shared_dataset),
        len(shared_train_dl),
        len(shared_val_dl),
    )

    _insufficient = summary["long"] + summary["short"] < 100 or len(shared_dataset) < 200

    def objective(trial: optuna.Trial) -> float:
        if _insufficient:
            return 0.0

        # ── 1. Sample hyperparams — each trial gets its own args copy ─────
        trial_args = copy.copy(base_args)
        trial_args.lr = trial.suggest_float("lr", 1e-4, 1e-3, log=True)
        trial_args.focal_gamma = trial.suggest_float("focal_gamma", 1.0, 3.0)
        trial_args.label_smoothing = trial.suggest_float("label_smoothing", 0.05, 0.25)
        trial_args.mixup_alpha = trial.suggest_float("mixup_alpha", 0.0, 0.4)
        trial_args.weight_decay = trial.suggest_float("weight_decay", 1e-5, 1e-3, log=True)
        trial_args.class_weight_boost = trial.suggest_float("class_weight_boost", 1.0, 3.0)
        trial_args.embedding_dim = trial.suggest_categorical("embedding_dim", [48, 64, 96])
        trial_args.dropout = trial.suggest_float("dropout", 0.2, 0.5)
        # Shorter run for proxy speed — full epochs used in Tier-1 training
        trial_args.epochs = min(trial_args.epochs, 25)

        # ── 2. Build model (fresh each trial — this is what actually varies) ─
        model = build_per_asset_cnn(
            n_features=N_FEATURES,
            window=trial_args.window,
            embedding_dim=trial_args.embedding_dim,
            dropout=trial_args.dropout,
        ).to(device)

        # ── 3. Loss / optimiser / scheduler ──────────────────────────────
        cw = shared_cw.copy()
        if trial_args.class_weight_boost > 1.0:
            cw[1] *= trial_args.class_weight_boost
            cw[2] *= trial_args.class_weight_boost
            cw[3] *= trial_args.class_weight_boost
        weight_tensor = torch.tensor(cw, dtype=torch.float32).to(device)

        criterion = FocalLoss(
            weight=weight_tensor,
            gamma=trial_args.focal_gamma,
            label_smoothing=trial_args.label_smoothing,
        )
        optimizer = AdamW(
            model.parameters(),
            lr=trial_args.lr,
            weight_decay=trial_args.weight_decay,
        )
        scheduler = LambdaLR(
            optimizer,
            lr_lambda=lambda ep: _warmup_cosine_lr(ep, trial_args.warmup_epochs, trial_args.epochs),
        )

        use_amp = device.type == "cuda"
        scaler = torch.amp.GradScaler(device="cuda") if use_amp else None
        early_stop = _EarlyStopping(patience=8, mode="max")
        accum_steps = 4

        # ── 4. Training loop ──────────────────────────────────────────────
        best_macro_f1 = 0.0

        for epoch in range(1, trial_args.epochs + 1):
            model.train()
            optimizer.zero_grad()
            for step, (x_batch, y_batch) in enumerate(shared_train_dl):
                x_batch, y_batch = x_batch.to(device), y_batch.to(device)
                ctx = (
                    torch.amp.autocast(device_type="cuda") if use_amp else contextlib.nullcontext()
                )
                with ctx:
                    loss = criterion(model(x_batch), y_batch) / accum_steps
                if scaler:
                    scaler.scale(loss).backward()
                else:
                    loss.backward()
                if (step + 1) % accum_steps == 0 or (step + 1) == len(shared_train_dl):
                    if scaler:
                        scaler.unscale_(optimizer)
                        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                        scaler.step(optimizer)
                        scaler.update()
                    else:
                        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                        optimizer.step()
                    optimizer.zero_grad()
            scheduler.step()

            # Validation + macro F1
            model.eval()
            vp_all, vl_all = [], []
            with torch.no_grad():
                for x_batch, y_batch in shared_val_dl:
                    logits = model(x_batch.to(device))
                    vp_all.extend(logits.argmax(-1).cpu().tolist())
                    vl_all.extend(y_batch.tolist())

            _vp = np.array(vp_all, dtype=np.int64)
            _vl = np.array(vl_all, dtype=np.int64)
            f1s = []
            for ci in range(N_CLASSES):
                tp = int(((_vp == ci) & (_vl == ci)).sum())
                fp = int(((_vp == ci) & (_vl != ci)).sum())
                fn = int(((_vp != ci) & (_vl == ci)).sum())
                p = tp / max(tp + fp, 1)
                r = tp / max(tp + fn, 1)
                f1s.append(2 * p * r / max(p + r, 1e-8))
            macro_f1 = float(np.mean(f1s))

            if macro_f1 > best_macro_f1:
                best_macro_f1 = macro_f1

            trial.report(macro_f1, step=epoch)
            if trial.should_prune():
                raise optuna.TrialPruned()

            if early_stop(macro_f1):
                break

        return best_macro_f1

    return objective


def optimize_hyperparams(
    proxy_assets: list[str] | str,
    asset_dfs: dict[str, Any],
    label_params: dict[str, dict],
    exchange: Any,
    args: Any,
    device: Any,
    cache: Any,
    *,
    n_trials: int = 50,
    cache_path: Path | None = None,
) -> HyperParams:
    """
    Run Optuna hyperparameter search and return the best HyperParams.

    proxy_assets accepts a single asset key (str) or a list of keys.  When
    multiple proxies are given the Optuna objective averages F1 across all of
    them so that the chosen hyperparams are not overfit to a single asset's
    volatility profile.  Recommended: ["btc", "pepe"] for coverage of both a
    stable large-cap and a high-volatility meme coin.

    Results are written to {models_dir}/hyper_params.json so subsequent runs
    can skip this stage if the file is fresh (< 7 days) and --force-hyper-opt
    is not set.
    """
    if isinstance(proxy_assets, str):
        proxy_assets = [proxy_assets]

    if cache_path is None:
        cache_path = Path(args.models_dir) / "hyper_params.json"

    # Check for a fresh cached result
    if cache_path.exists() and not getattr(args, "force_hyper_opt", False):
        age_days = (time.time() - cache_path.stat().st_mtime) / 86400
        if age_days < 7:
            logger.info(
                "Stage 2 — Using cached hyper params (%.1f days old): %s",
                age_days,
                cache_path,
            )
            saved = json.loads(cache_path.read_text())
            return HyperParams(**saved)

    logger.info("━" * 60)
    logger.info(
        "Stage 2 — Hyperparameter optimisation  proxies=%s  trials=%d",
        [p.upper() for p in proxy_assets],
        n_trials,
    )
    t0 = time.time()

    # Build a pre-compute function per proxy (labels + dataloaders computed
    # once per proxy, shared across all trials for that proxy).
    proxy_fns = []
    for _pa in proxy_assets:
        _fn = _make_proxy_train_fn(
            proxy_asset=_pa,
            asset_dfs=asset_dfs,
            label_params=label_params,
            exchange=exchange,
            base_args=args,
            device=device,
            cache=cache,
        )
        proxy_fns.append(_fn)

    def _combined_objective(trial: optuna.Trial) -> float:
        """Average F1 across all proxy assets for this set of hyperparams."""
        scores = [fn(trial) for fn in proxy_fns]
        valid = [s for s in scores if s > 0]
        return float(np.mean(valid)) if valid else 0.0

    study = optuna.create_study(
        direction="maximize",
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=5),
        sampler=optuna.samplers.TPESampler(seed=getattr(args, "seed", 42)),
    )
    study.optimize(_combined_objective, n_trials=n_trials, show_progress_bar=False)

    best = study.best_params
    logger.info(
        "Stage 2 complete in %.1fs  best_f1=%.4f  params=%s",
        time.time() - t0,
        study.best_value,
        best,
    )

    hp = HyperParams(
        lr=best["lr"],
        focal_gamma=best["focal_gamma"],
        label_smoothing=best["label_smoothing"],
        mixup_alpha=best["mixup_alpha"],
        embedding_dim=best["embedding_dim"],
        dropout=best["dropout"],
        weight_decay=best["weight_decay"],
        class_weight_boost=best["class_weight_boost"],
    )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(hp.__dict__, indent=2))
    logger.info("Cached hyper params → %s", cache_path)

    return hp


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — Tier-1: per-asset training
# ─────────────────────────────────────────────────────────────────────────────


def train_all_assets(
    asset_keys: list[str],
    exchange: Any,
    args: Any,
    device: Any,
    cache: Any,
    *,
    hp: HyperParams,
    label_params: dict[str, dict],
) -> list[dict]:
    """
    Train one PerAssetCNN per asset using the best label and hyper params.

    Label params are injected into ASSET_LABEL_PARAMS so _resolve_label_params
    picks them up via priority-2 without needing --optimize-labels at this stage.
    Hyper params are applied to a per-asset copy of args.
    """
    from ml.train_asset import ASSET_LABEL_PARAMS, train_asset

    logger.info("━" * 60)
    logger.info("Stage 3 — Tier-1 training  (%d assets)", len(asset_keys))

    # Inject optimised label params so _resolve_label_params priority-2 fires
    ASSET_LABEL_PARAMS.update(label_params)

    # Apply best hyperparams to a shared args copy
    tier1_args = hp.apply_to(args)

    results = []
    for idx, key in enumerate(asset_keys, 1):
        logger.info("▶ [%d/%d] %s", idx, len(asset_keys), key.upper())
        t = time.time()
        result = train_asset(
            asset_key=key,
            exchange=exchange,
            args=tier1_args,
            device=device,
            cache=cache,
        )
        if result is not None:
            results.append(result)
            logger.info(
                "◀ [%d/%d] %s  %.1fs  f1=%.3f  saved=%s",
                idx,
                len(asset_keys),
                key.upper(),
                time.time() - t,
                result.get("val_macro_f1", 0.0),
                result.get("saved", False),
            )

    saved = sum(1 for r in results if r.get("saved"))
    logger.info("Stage 3 complete — %d/%d models saved", saved, len(asset_keys))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — Tier-2: master model training
# ─────────────────────────────────────────────────────────────────────────────


def train_master_model(
    asset_keys: list[str],
    exchange: Any,
    args: Any,
    device: Any,
    cache: Any,
    *,
    hp: HyperParams,
) -> dict | None:
    """
    Train the MasterCNN portfolio risk model using the best hyper params.

    The master model uses BCE (not focal), so focal_gamma is not applied,
    but lr / weight_decay / mixup_alpha carry over.
    """
    from ml.train_master import train_master

    logger.info("━" * 60)
    logger.info("Stage 4 — Tier-2 master model")

    master_args = hp.apply_to(args)
    t = time.time()
    result = train_master(
        asset_keys=asset_keys,
        exchange=exchange,
        args=master_args,
        device=device,
        cache=cache,
    )
    if result is not None:
        logger.info(
            "Stage 4 complete in %.1fs  val_f1=%.3f  saved=%s",
            time.time() - t,
            result.get("val_f1", 0.0),
            result.get("saved", False),
        )
    else:
        logger.warning("Stage 4 — master model training returned None")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5 — Champion promotion
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PromotionResult:
    asset: str
    promoted: bool
    reason: str
    old_f1: float | None = None
    new_f1: float | None = None
    delta: float | None = None


def _load_champion_meta(models_dir: Path, asset_key: str) -> dict | None:
    """Load the sidecar JSON for an existing champion model."""
    sidecar = models_dir / f"cnn_{asset_key.lower()}.json"
    if not sidecar.exists():
        return None
    try:
        return json.loads(sidecar.read_text())
    except Exception:
        return None


def _git_tag(tag: str, message: str, models_dir: Path) -> bool:
    """Create an annotated git tag in the repo containing models_dir."""
    try:
        repo_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=models_dir,
            text=True,
        ).strip()
        subprocess.run(
            ["git", "tag", "-a", tag, "-m", message],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        logger.info("Git tag created: %s", tag)
        return True
    except Exception as exc:
        logger.warning("Git tag failed: %s", exc)
        return False


def promote_champions(
    tier1_results: list[dict],
    master_result: dict | None,
    args: Any,
    *,
    min_delta_f1: float = 0.005,
    git_tag: bool = True,
) -> list[PromotionResult]:
    """
    Compare every newly trained model against its saved champion.
    Promote (keep the file, optionally git-tag) if the new model is better
    by at least min_delta_f1.  Rolls back (overwrites with previous best) if worse.

    Promotion criteria for Tier-1:
      - flat_pct <= 0.95 (degenerate label guard — checked first, blocks all others)
      - val_macro_f1 improved by >= min_delta_f1
      - model was actually saved (passed the quality gate in train_asset)
      - directional_gate is not 'flat_only'

    Promotion criteria for Tier-2 (master):
      - val_f1 improved by >= min_delta_f1
      - model was actually saved
      - neither 'safe' nor 'risky' per-class F1 is below 0.10
    """
    models_dir = Path(args.models_dir)
    promotions: list[PromotionResult] = []
    timestamp = time.strftime("%Y%m%d-%H%M")

    logger.info("━" * 60)
    logger.info("Stage 5 — Champion promotion  (min_delta_f1=%.3f)", min_delta_f1)

    # ── Tier-1 assets ─────────────────────────────────────────────────────────
    for result in tier1_results:
        key = result.get("asset", "unknown")

        if not result.get("saved", False):
            promotions.append(
                PromotionResult(
                    asset=key,
                    promoted=False,
                    reason=f"not saved: {result.get('reason', 'below threshold')}",
                )
            )
            continue

        if result.get("directional_gate") == "flat_only":
            promotions.append(
                PromotionResult(
                    asset=key,
                    promoted=False,
                    reason="directional_gate=flat_only — model is direction-blind",
                    new_f1=result.get("val_macro_f1"),
                )
            )
            logger.warning("[promote] %s skipped — direction-blind model", key.upper())
            continue

        new_f1 = result.get("val_macro_f1", 0.0)

        # ── Degenerate label guard ────────────────────────────────────────────
        # A model trained on >= 95% flat labels is effectively a flat-predictor.
        # Block promotion regardless of whether a champion already exists — the
        # "first champion" path is intentionally included in this gate so that
        # AVAX/DOT/SHIB-style assets never reach production on first run.
        flat_pct = result.get("flat_pct", 0.0)
        if flat_pct > 0.95:
            promotions.append(
                PromotionResult(
                    asset=key,
                    promoted=False,
                    reason=f"degenerate labels: flat_pct={flat_pct:.1%}",
                    new_f1=new_f1,
                )
            )
            logger.warning(
                "[promote] %s skipped — degenerate labels (flat_pct=%.1f%%)",
                key.upper(),
                flat_pct * 100,
            )
            continue

        champion = _load_champion_meta(models_dir, key)

        # No previous champion — first save always promotes
        if champion is None:
            promotions.append(
                PromotionResult(
                    asset=key,
                    promoted=True,
                    reason="first champion",
                    new_f1=new_f1,
                )
            )
            if git_tag:
                _git_tag(
                    f"champion/{key}/{timestamp}",
                    f"First champion for {key.upper()}  f1={new_f1:.4f}",
                    models_dir,
                )
            logger.info("[promote] %s ✅ first champion  f1=%.4f", key.upper(), new_f1)
            continue

        old_f1 = champion.get("val_macro_f1", 0.0)
        delta = new_f1 - old_f1

        if delta >= min_delta_f1:
            promotions.append(
                PromotionResult(
                    asset=key,
                    promoted=True,
                    reason=f"improved by {delta:+.4f}",
                    old_f1=old_f1,
                    new_f1=new_f1,
                    delta=delta,
                )
            )
            if git_tag:
                _git_tag(
                    f"champion/{key}/{timestamp}",
                    f"New champion {key.upper()}  f1={old_f1:.4f}→{new_f1:.4f} ({delta:+.4f})",
                    models_dir,
                )
            logger.info(
                "[promote] %s ✅ promoted  f1=%.4f→%.4f (%+.4f)",
                key.upper(),
                old_f1,
                new_f1,
                delta,
            )
        else:
            # New model didn't beat the champion — restore the champion .pt
            # The JSON sidecar already reflects the new run; restore .pt only.
            champ_pt = models_dir / f"cnn_{key.lower()}.pt"
            champ_backup = models_dir / f"cnn_{key.lower()}.pt.bak"
            if champ_backup.exists():
                champ_pt.write_bytes(champ_backup.read_bytes())
                logger.info(
                    "[promote] %s ⏪ rolled back to champion  "
                    "new_f1=%.4f  champ_f1=%.4f  delta=%+.4f",
                    key.upper(),
                    new_f1,
                    old_f1,
                    delta,
                )
            else:
                logger.warning(
                    "[promote] %s ⚠ no backup found — keeping new model despite "
                    "no improvement (delta=%+.4f)",
                    key.upper(),
                    delta,
                )
            promotions.append(
                PromotionResult(
                    asset=key,
                    promoted=False,
                    reason=f"no improvement: delta={delta:+.4f} < {min_delta_f1}",
                    old_f1=old_f1,
                    new_f1=new_f1,
                    delta=delta,
                )
            )

    # ── Tier-2 master ─────────────────────────────────────────────────────────
    if master_result is not None and master_result.get("saved", False):
        new_f1 = master_result.get("val_f1", 0.0)
        pc = master_result.get("per_class", {})
        safe_f1 = pc.get("safe", {}).get("f1", 0.0)
        risky_f1 = pc.get("risky", {}).get("f1", 0.0)

        if safe_f1 < 0.10 or risky_f1 < 0.10:
            promotions.append(
                PromotionResult(
                    asset="master",
                    promoted=False,
                    reason=f"weak class coverage: safe_f1={safe_f1:.3f}  risky_f1={risky_f1:.3f}",
                    new_f1=new_f1,
                )
            )
            logger.warning(
                "[promote] MASTER skipped — weak class coverage (safe=%.3f risky=%.3f)",
                safe_f1,
                risky_f1,
            )
        else:
            champion = _load_champion_meta(models_dir, "master")
            old_f1 = champion.get("val_f1", 0.0) if champion else None
            delta = (new_f1 - old_f1) if old_f1 is not None else None
            promoted = old_f1 is None or (delta is not None and delta >= min_delta_f1)

            promotions.append(
                PromotionResult(
                    asset="master",
                    promoted=promoted,
                    reason="first champion"
                    if old_f1 is None
                    else (
                        f"improved by {delta:+.4f}"
                        if promoted
                        else f"no improvement: delta={delta:+.4f}"
                    ),
                    old_f1=old_f1,
                    new_f1=new_f1,
                    delta=delta,
                )
            )
            if promoted and git_tag:
                _git_tag(
                    f"champion/master/{timestamp}",
                    f"New master champion  f1={old_f1 or 0:.4f}→{new_f1:.4f}",
                    models_dir,
                )
            status = "✅ promoted" if promoted else "⏪ not promoted"
            logger.info(
                "[promote] MASTER %s  f1=%.4f→%.4f",
                status,
                old_f1 or 0.0,
                new_f1,
            )

    # ── Summary ───────────────────────────────────────────────────────────────
    n_promoted = sum(1 for p in promotions if p.promoted)
    logger.info("Stage 5 complete — %d/%d promoted", n_promoted, len(promotions))
    for p in promotions:
        icon = "✅" if p.promoted else "⏭"
        delta_str = f"  Δf1={p.delta:+.4f}" if p.delta is not None else ""
        logger.info(
            "  %s %-10s  %s%s",
            icon,
            p.asset.upper(),
            p.reason,
            delta_str,
        )

    return promotions


# ─────────────────────────────────────────────────────────────────────────────
# Backup helper — call before training so rollback has something to restore
# ─────────────────────────────────────────────────────────────────────────────


def backup_existing_champions(asset_keys: list[str], models_dir: Path) -> None:
    """Copy existing .pt files to .pt.bak before the training run starts."""
    for key in asset_keys + ["master"]:
        src = models_dir / f"cnn_{key.lower()}.pt"
        if src.exists():
            dst = src.with_suffix(".pt.bak")
            dst.write_bytes(src.read_bytes())
            logger.debug("Backed up %s → %s", src.name, dst.name)


# ─────────────────────────────────────────────────────────────────────────────
# Top-level pipeline entry point
# ─────────────────────────────────────────────────────────────────────────────


def run_pipeline(
    args: Any,
    exchange: Any,
    device: Any,
    cache: Any,
    *,
    asset_keys: list[str] | None = None,
    proxy_assets: list[str] | str = "btc",
    label_trials: int = 100,
    hyper_trials: int = 50,
    min_delta_f1: float = 0.005,
    git_tag: bool = True,
) -> dict[str, Any]:
    """
    Run all five pipeline stages end-to-end and return a results summary.

    proxy_assets accepts a single asset key or a list.  Using multiple proxies
    (e.g. ["btc", "pepe"]) makes the Stage 2 hyperparameter search more robust
    across different volatility profiles without significant extra wall-clock
    time (datasets are already pre-fetched in Stage 0).

    A 10% chronological holdout is carved out before Stage 1 and Stage 2.
    OOS label-quality scores are computed at the end and included in the
    returned summary dict under "oos_label_scores".

    Designed to be called from train.py main() when --full-pipeline is passed:

        if args.full_pipeline:
            from ml.optimize_training import run_pipeline
            run_pipeline(args, exchange, device, cache, asset_keys=asset_keys)
            return
    """
    from ml.train import DEFAULT_ASSETS

    if asset_keys is None:
        asset_keys = list(DEFAULT_ASSETS)

    # Normalise proxy_assets to a list for the banner and Stage 2 call.
    if isinstance(proxy_assets, str):
        proxy_assets = [proxy_assets]

    models_dir = Path(args.models_dir)
    t_pipeline = time.time()

    _proxy_str = ", ".join(p.upper() for p in proxy_assets)
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║  Full Training Pipeline                                  ║")
    logger.info("║  Assets : %-46s║", ", ".join(asset_keys))
    logger.info("║  Proxy  : %-46s║", _proxy_str)
    logger.info("╚" + "═" * 58 + "╝")

    # Back up existing champions before any writes
    backup_existing_champions(asset_keys, models_dir)

    # Stage 0 — prefetch full history for all assets
    asset_dfs = prefetch_all_assets(asset_keys, exchange, args, cache, max_workers=4)

    # ── Chronological holdout ─────────────────────────────────────────────────
    # Reserve the last 10% of every asset's history as an OOS test set.
    # Label opt (Stage 1) and hyper opt (Stage 2) operate on the 90% train slice
    # only.  Tier-1 training (Stage 3) re-fetches internally and uses full data;
    # the holdout is used exclusively for the unbiased OOS evaluation at the end.
    # Nothing between here and the final OOS block may read from asset_dfs_holdout.
    _HOLDOUT_FRAC = 0.10
    asset_dfs_train: dict[str, Any] = {}
    asset_dfs_holdout: dict[str, Any] = {}
    for _k, _df in asset_dfs.items():
        if _df is not None and not _df.empty and len(_df) >= 1_000:
            _split = int(len(_df) * (1.0 - _HOLDOUT_FRAC))
            asset_dfs_train[_k] = _df.iloc[:_split].reset_index(drop=True)
            asset_dfs_holdout[_k] = _df.iloc[_split:].reset_index(drop=True)
            logger.info(
                "[holdout] %-10s  train=%d bars  holdout=%d bars",
                _k.upper(),
                _split,
                len(_df) - _split,
            )
        else:
            asset_dfs_train[_k] = _df
            asset_dfs_holdout[_k] = None

    # Stage 1 — label optimisation  (train slice only)
    label_params = optimize_all_labels(
        asset_keys,
        asset_dfs_train,  # ← train slice, not full history
        args,
        n_trials=label_trials,
        force=getattr(args, "force_label_opt", False),
    )

    # Stage 2 — hyperparameter optimisation  (train slice only)
    hp = optimize_hyperparams(
        proxy_assets=proxy_assets,
        asset_dfs=asset_dfs_train,  # ← train slice, not full history
        label_params=label_params,
        exchange=exchange,
        args=args,
        device=device,
        cache=cache,
        n_trials=hyper_trials,
    )

    # Stage 3 — Tier-1 per-asset training (train_asset re-fetches internally)
    tier1_results = train_all_assets(
        asset_keys,
        exchange,
        args,
        device,
        cache,
        hp=hp,
        label_params=label_params,
    )

    # Stage 4 — Tier-2 master model
    master_result = train_master_model(asset_keys, exchange, args, device, cache, hp=hp)

    # Stage 5 — champion promotion
    promotions = promote_champions(
        tier1_results,
        master_result,
        args,
        min_delta_f1=min_delta_f1,
        git_tag=git_tag,
    )

    elapsed = time.time() - t_pipeline
    n_promoted = sum(1 for p in promotions if p.promoted)

    # ── OOS evaluation on held-out slices ─────────────────────────────────────
    # Generate labels with the optimised params on each holdout slice and compute
    # the label-quality score.  This gives an unbiased signal on whether the label
    # params generalise beyond the optimisation period without requiring a full
    # model inference pass (no predict() API needed).
    from ml.labeler import generate_labels_breakout
    from ml.optimize_labels import detect_regimes, label_quality_score

    oos_scores: dict[str, float] = {}
    for _k, _holdout_df in asset_dfs_holdout.items():
        if _holdout_df is None or _holdout_df.empty:
            continue
        _lp = label_params.get(_k)
        if _lp is None:
            continue
        try:
            _oos_labels = generate_labels_breakout(_holdout_df, **_lp)
            try:
                _oos_regimes = detect_regimes(_holdout_df)
            except Exception:
                _oos_regimes = None
            _oos_score = label_quality_score(
                _oos_labels,
                _lp["tp_atr_mult"],
                _lp["sl_atr_mult"],
                _oos_regimes,
            )
            oos_scores[_k] = round(_oos_score, 4)
            logger.info(
                "[oos] %-10s  label_quality_score=%.4f",
                _k.upper(),
                _oos_score,
            )
        except Exception as _exc:
            logger.warning("[oos] %s — evaluation failed: %s", _k.upper(), _exc)

    logger.info(
        "Pipeline complete in %.1fs — %d/%d models promoted  OOS scores: %s",
        elapsed,
        n_promoted,
        len(promotions),
        {k: f"{v:.4f}" for k, v in oos_scores.items()},
    )

    return {
        "asset_dfs": {k: len(v) if v is not None else 0 for k, v in asset_dfs.items()},
        "label_params": label_params,
        "best_hyperparams": hp.__dict__,
        "tier1_results": tier1_results,
        "master_result": master_result,
        "promotions": [p.__dict__ for p in promotions],
        "elapsed_seconds": round(elapsed, 1),
        "oos_label_scores": oos_scores,
    }
