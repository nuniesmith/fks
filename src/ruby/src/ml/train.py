"""
ml/train.py — Standalone offline training script for the futures CNN models.

Trains PerAssetCNN (one per asset) and optionally MasterCNN (portfolio risk).
Fetches historical klines directly from KuCoin Futures via ccxt, generates
labels, builds DataLoaders, trains, evaluates, and saves .pt files to the
models/ directory.

Run from the project root
--------------------------
    # Train all enabled assets + master model
    python -m src.ml.train --all

    # Train a single asset
    python -m src.ml.train --asset btc

    # Train with custom settings
    python -m src.ml.train --asset eth --epochs 100 --bars 20000 --lr 3e-4

    # Train master model only (requires per-asset models to already exist)
    python -m src.ml.train --master-only

    # Dry-run: fetch + label data, print stats, skip training
    python -m src.ml.train --asset btc --dry-run

Module layout
-------------
    ml/train.py                 ← this file (entry point, constants, CLI)
    ml/train_asset.py           ← train_asset(), _resolve_label_params()
    ml/train_master.py          ← train_master(), _init_encoder_from_per_asset()
    ml/training_components.py   ← FocalLoss, EarlyStopping, warmup_cosine_lr,
                                   calibrate_temperature
    ml/reporting.py             ← colour codes, champion comparison, summary table

Changes from v1
---------------
    - KCS removed (limited history, consistently failed the macro_f1 threshold)
    - SWA removed from both train_asset() and train_master() — never beneficial
    - DEFAULT_CONSOLIDATION_ATR_MULT lowered 5.5 → 4.0 to tighten consolidation
    - DEFAULT_LABEL_SMOOTHING raised 0.10 → 0.15 for better calibration on
      high-volatility assets such as FARTCOIN
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

# ── Path setup ────────────────────────────────────────────────────────────────
_SRC = Path(__file__).resolve().parent.parent  # futures/src/
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ml.features import DEFAULT_WINDOW as _FEATURES_DEFAULT_WINDOW
from ml.kline_cache import KlineCache
from ml.reporting import (
    BOLD,
    DIM,
    GREEN,
    RED,
    RESET,
    YELLOW,
    print_cross_tier_summary,
)
from ml.train_asset import ASSET_SYMBOLS, train_asset
from ml.train_master import train_master

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("train")

# ── Default enabled assets ────────────────────────────────────────────────────
DEFAULT_ASSETS = [
    "btc",
    "eth",
    "sol",
    "xrp",
    "doge",
    "bnb",
    "ada",
    "dot",
    "link",
    "pepe",
    "trump",
    "bonk",
    "shib",
    "avax",
    "arb",
    "op",
    "ena",
    "hype",
    "renderjup",
    "tao",
    "sui",
    "wif",
    "fart",
    "gold",
    "silver",
    "copper",
    "platinum",
    "palladium",
    "oil",
    "tsla",
    "nvda",
    "mstr",
    "coin",
    "meta",
    "pltr",
    "hood",
    "intc",
]

# ── Training defaults ─────────────────────────────────────────────────────────
DEFAULT_EPOCHS = 60
DEFAULT_BATCH_SIZE = 64
DEFAULT_LR = 3e-4
DEFAULT_WEIGHT_DECAY = 5e-4
DEFAULT_BARS = 100_000
DEFAULT_MIN_BARS = 5_000
DEFAULT_TIMEFRAME = "1m"
DEFAULT_WINDOW = _FEATURES_DEFAULT_WINDOW
DEFAULT_MAX_FORWARD_BARS = 90
DEFAULT_VAL_SPLIT = 0.15
DEFAULT_MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"
DEFAULT_MIN_VAL_ACCURACY = 0.38

# Breakout labelling
DEFAULT_CONSOLIDATION_BARS = 20
DEFAULT_CONSOLIDATION_ATR_MULT = 4.0  # was 5.5
DEFAULT_MAX_BREAKOUT_WAIT = 40
DEFAULT_TP_ATR_MULT = 1.5
DEFAULT_SL_ATR_MULT = 1.0

# Training techniques
DEFAULT_WARMUP_EPOCHS = 5
DEFAULT_EARLY_STOP_PATIENCE = 20
DEFAULT_MIXUP_ALPHA = 0.2
DEFAULT_LABEL_SMOOTHING = 0.15  # was 0.10
DEFAULT_LOSS_TYPE = "focal"
DEFAULT_FOCAL_GAMMA = 2.0
DEFAULT_CLASS_WEIGHT_BOOST = 1.0
DEFAULT_EARLY_STOP_METRIC = "macro_f1"


# ── Device selection ──────────────────────────────────────────────────────────


def _get_device() -> torch.device:
    if torch.cuda.is_available():
        device = torch.device("cuda")
        logger.info("Using CUDA GPU: %s", torch.cuda.get_device_name(0))
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
        logger.info("Using Apple MPS GPU")
    else:
        device = torch.device("cpu")
        logger.info("Using CPU (no GPU available)")
    return device


# ── Exchange factory ──────────────────────────────────────────────────────────


def _make_exchange(api_key: str = "", api_secret: str = "", passphrase: str = "") -> Any:
    """Create a synchronous ``ccxt.kucoinfutures`` instance for data fetching."""
    import ccxt

    params: dict[str, Any] = {"enableRateLimit": True, "rateLimit": 200}
    if api_key:
        params["apiKey"] = api_key
        params["secret"] = api_secret
        params["password"] = passphrase

    exchange = ccxt.kucoinfutures(params)
    try:
        exchange.load_markets()
        logger.info("Exchange connected — %d markets loaded", len(exchange.markets))
    except Exception as exc:
        logger.warning("Exchange load_markets failed: %s — continuing anyway", exc)
    return exchange


# ── Redis / kline cache factory ───────────────────────────────────────────────


def _make_cache(redis_url: str, redis_password: str = "", no_cache: bool = False) -> KlineCache:
    """Connect to Redis and return a KlineCache.

    Falls back to a disabled (no-op) KlineCache when ``no_cache`` is True or
    Redis is unreachable.
    """
    if no_cache:
        logger.info("Kline cache disabled (--no-cache)")
        return KlineCache()
    return KlineCache.connect(redis_url, password=redis_password or None)


# ── Argument parser ───────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m src.ml.train",
        description="Train PerAssetCNN and/or MasterCNN for the futures bot",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    group = p.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="Train all default assets + MasterCNN")
    group.add_argument("--asset", type=str, metavar="KEY", help="Single asset (e.g. btc)")
    group.add_argument("--assets", nargs="+", metavar="KEY", help="Multiple specific assets")
    group.add_argument(
        "--master-only",
        action="store_true",
        dest="master_only",
        help="MasterCNN only (per-asset models must already exist)",
    )

    # Data
    p.add_argument("--bars", type=int, default=DEFAULT_BARS)
    p.add_argument("--timeframe", type=str, default=DEFAULT_TIMEFRAME)
    p.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    p.add_argument(
        "--max-forward-bars", type=int, default=DEFAULT_MAX_FORWARD_BARS, dest="max_forward_bars"
    )
    p.add_argument(
        "--min-bars",
        type=int,
        default=DEFAULT_MIN_BARS,
        dest="min_bars",
        help="Minimum bars required to train an asset (≈3.5 days of 1m bars)",
    )
    p.add_argument(
        "--consolidation-bars",
        type=int,
        default=DEFAULT_CONSOLIDATION_BARS,
        dest="consolidation_bars",
    )
    p.add_argument(
        "--consolidation-atr-mult",
        type=float,
        default=DEFAULT_CONSOLIDATION_ATR_MULT,
        dest="consolidation_atr_mult",
        help="Max range/ATR to qualify a window as consolidation (lower = tighter)",
    )
    p.add_argument(
        "--max-breakout-wait", type=int, default=DEFAULT_MAX_BREAKOUT_WAIT, dest="max_breakout_wait"
    )
    p.add_argument("--tp-atr-mult", type=float, default=DEFAULT_TP_ATR_MULT, dest="tp_atr_mult")
    p.add_argument("--sl-atr-mult", type=float, default=DEFAULT_SL_ATR_MULT, dest="sl_atr_mult")

    # Training
    p.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, dest="batch_size")
    p.add_argument("--lr", type=float, default=DEFAULT_LR)
    p.add_argument("--weight-decay", type=float, default=DEFAULT_WEIGHT_DECAY, dest="weight_decay")
    p.add_argument("--val-split", type=float, default=DEFAULT_VAL_SPLIT, dest="val_split")
    p.add_argument(
        "--min-val-accuracy", type=float, default=DEFAULT_MIN_VAL_ACCURACY, dest="min_val_accuracy"
    )
    p.add_argument("--warmup-epochs", type=int, default=DEFAULT_WARMUP_EPOCHS, dest="warmup_epochs")
    p.add_argument(
        "--early-stop-patience",
        type=int,
        default=DEFAULT_EARLY_STOP_PATIENCE,
        dest="early_stop_patience",
    )
    p.add_argument("--mixup-alpha", type=float, default=DEFAULT_MIXUP_ALPHA, dest="mixup_alpha")
    p.add_argument(
        "--label-smoothing", type=float, default=DEFAULT_LABEL_SMOOTHING, dest="label_smoothing"
    )
    p.add_argument(
        "--loss-type",
        type=str,
        default=DEFAULT_LOSS_TYPE,
        dest="loss_type",
        choices=["ce", "focal"],
    )
    p.add_argument("--focal-gamma", type=float, default=DEFAULT_FOCAL_GAMMA, dest="focal_gamma")
    p.add_argument(
        "--class-weight-boost",
        type=float,
        default=DEFAULT_CLASS_WEIGHT_BOOST,
        dest="class_weight_boost",
    )
    p.add_argument(
        "--early-stop-metric",
        type=str,
        default=DEFAULT_EARLY_STOP_METRIC,
        dest="early_stop_metric",
        choices=["val_loss", "macro_f1"],
    )

    # Master model
    p.add_argument("--master-embedding-dim", type=int, default=64, dest="master_embedding_dim")
    p.add_argument("--master-dropout", type=float, default=0.4, dest="master_dropout")
    p.add_argument(
        "--master-encoder-dropout", type=float, default=0.25, dest="master_encoder_dropout"
    )

    # Output
    p.add_argument("--models-dir", type=str, default=str(DEFAULT_MODELS_DIR), dest="models_dir")

    # API keys
    p.add_argument(
        "--api-key", type=str, default=os.environ.get("KUCOIN_API_KEY", ""), dest="api_key"
    )
    p.add_argument(
        "--api-secret", type=str, default=os.environ.get("KUCOIN_API_SECRET", ""), dest="api_secret"
    )
    p.add_argument(
        "--passphrase", type=str, default=os.environ.get("KUCOIN_PASSPHRASE", ""), dest="passphrase"
    )

    # Redis cache
    p.add_argument(
        "--redis-url",
        type=str,
        default=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        dest="redis_url",
    )
    p.add_argument(
        "--redis-password",
        type=str,
        default=os.environ.get("REDIS_PASSWORD", ""),
        dest="redis_password",
    )
    p.add_argument("--no-cache", action="store_true", dest="no_cache")

    # Misc
    p.add_argument(
        "--master", action="store_true", help="Also train MasterCNN after per-asset models"
    )
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    p.add_argument("--seed", type=int, default=42)

    # Label optimisation
    p.add_argument("--optimize-labels", action="store_true", dest="optimize_labels")
    p.add_argument("--label-opt-trials", type=int, default=50, dest="label_opt_trials")
    p.add_argument("--force-label-opt", action="store_true", dest="force_label_opt")

    # Full pipeline
    p.add_argument(
        "--full-pipeline",
        action="store_true",
        dest="full_pipeline",
        help="Run the full 5-stage pipeline: prefetch → label-opt → hyper-opt → tier-1 → master → promotion",
    )
    p.add_argument("--label-trials", type=int, default=100, dest="label_trials")
    p.add_argument("--hyper-trials", type=int, default=50, dest="hyper_trials")
    p.add_argument("--proxy-asset", type=str, default="btc", dest="proxy_asset")
    p.add_argument("--min-delta-f1", type=float, default=0.005, dest="min_delta_f1")
    p.add_argument("--no-git-tag", action="store_true", dest="no_git_tag")
    p.add_argument("--force-hyper-opt", action="store_true", dest="force_hyper_opt")

    return p


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    device = _get_device()

    if args.all:
        asset_keys = list(DEFAULT_ASSETS)
        train_master_model = True
    elif args.master_only:
        asset_keys = []
        train_master_model = True
    elif args.asset:
        asset_keys = [args.asset.lower()]
        train_master_model = getattr(args, "master", False)
    elif args.assets:
        asset_keys = [k.lower() for k in args.assets]
        train_master_model = getattr(args, "master", False)
    else:
        asset_keys = list(DEFAULT_ASSETS)
        train_master_model = True

    exchange = _make_exchange(
        api_key=args.api_key,
        api_secret=args.api_secret,
        passphrase=args.passphrase,
    )
    cache = _make_cache(
        redis_url=args.redis_url,
        redis_password=args.redis_password,
        no_cache=args.no_cache,
    )

    # ── Full pipeline ─────────────────────────────────────────────────────────
    if getattr(args, "full_pipeline", False):
        from ml.optimize_training import run_pipeline

        summary = run_pipeline(
            args=args,
            exchange=exchange,
            device=device,
            cache=cache,
            asset_keys=asset_keys,
            proxy_assets=getattr(args, "proxy_asset", "btc"),
            label_trials=getattr(args, "label_trials", 100),
            hyper_trials=getattr(args, "hyper_trials", 50),
            min_delta_f1=getattr(args, "min_delta_f1", 0.005),
            git_tag=not getattr(args, "no_git_tag", False),
        )
        n_promoted = sum(1 for p in summary["promotions"] if p["promoted"])
        logger.info(
            "Pipeline finished — %d/%d promoted in %.1fs",
            n_promoted,
            len(summary["promotions"]),
            summary["elapsed_seconds"],
        )
        if n_promoted == 0 and not args.dry_run:
            sys.exit(1)
        return

    # ── Header ────────────────────────────────────────────────────────────────
    logger.info("━" * 60)
    logger.info("  Futures CNN Training")
    logger.info("  Assets       : %s", asset_keys or "(none — master only)")
    logger.info("  Master model : %s", "yes" if train_master_model else "no")
    logger.info("  Bars/asset   : %d  (%s)", args.bars, args.timeframe)
    logger.info("  Kline cache  : %s", args.redis_url if cache.enabled else "disabled")
    logger.info("  Window       : %d bars", args.window)
    logger.info("  Epochs       : %d", args.epochs)
    logger.info("  Batch size   : %d", args.batch_size)
    logger.info("  LR           : %g", args.lr)
    logger.info(
        "  Consolidation: %d bars, ATR-mult=%.1f, breakout-wait=%d",
        args.consolidation_bars,
        args.consolidation_atr_mult,
        args.max_breakout_wait,
    )
    logger.info(
        "  Bracket      : TP=%.1f×ATR  SL=%.1f×ATR  max-hold=%d bars",
        args.tp_atr_mult,
        args.sl_atr_mult,
        args.max_forward_bars,
    )
    logger.info(
        "  Training     : warmup=%d ep, early-stop=%d (%s), mixup=%.2f, smooth=%.2f",
        args.warmup_epochs,
        args.early_stop_patience,
        args.early_stop_metric,
        args.mixup_alpha,
        args.label_smoothing,
    )
    logger.info(
        "  Loss         : %s  γ=%.1f  class-boost=%.1f×",
        args.loss_type,
        args.focal_gamma,
        args.class_weight_boost,
    )
    logger.info("  Models dir   : %s", args.models_dir)
    logger.info("  Device       : %s", device)
    logger.info("  Dry run      : %s", args.dry_run)
    logger.info("━" * 60)

    results: list[dict] = []

    for asset_idx, asset_key in enumerate(asset_keys, 1):
        logger.info("")
        logger.info("▶ Asset %d/%d: %s", asset_idx, len(asset_keys), asset_key.upper())
        t_asset = time.time()
        result = train_asset(
            asset_key=asset_key,
            exchange=exchange,
            args=args,
            device=device,
            cache=cache,
        )
        if result is not None:
            results.append(result)
            logger.info(
                "◀ Asset %d/%d: %s complete in %.1fs",
                asset_idx,
                len(asset_keys),
                asset_key.upper(),
                time.time() - t_asset,
            )

    if train_master_model:
        master_assets = asset_keys if asset_keys else list(DEFAULT_ASSETS)
        master_result = train_master(
            asset_keys=master_assets,
            exchange=exchange,
            args=args,
            device=device,
            cache=cache,
        )
        if master_result is not None:
            results.append({"type": "master", **master_result})

    # ── Final summary ─────────────────────────────────────────────────────────
    logger.info("━" * 60)
    logger.info("  Training complete — %d job(s) finished", len(results))

    saved = [r for r in results if r.get("saved")]
    # ── Final summary ─────────────────────────────────────────────────────────
    logger.info("━" * 60)
    logger.info("  Training complete — %d job(s) finished", len(results))

    saved   = [r for r in results if r.get("saved")]
    skipped = [r for r in results if not r.get("saved") and not r.get("dry_run")]

    for r in saved:
        asset = r.get("asset") or r.get("type", "?")
        metric = r.get("val_accuracy") or r.get("best_val_loss", "?")
        logger.info("  ✅ %-12s  metric=%-8s  → %s", asset, metric, r.get("model_path", "?"))

    for r in skipped:
        logger.info("  ⚠️  %-12s  skipped: %s", r.get("asset", "?"), r.get("reason", "unknown"))

    logger.info("━" * 60)

    if not args.dry_run and results:
        print_cross_tier_summary(results)

    if not saved and not args.dry_run:
        logger.warning("No models were saved — check data quality and thresholds")
        sys.exit(1)


if __name__ == "__main__":
    main()
