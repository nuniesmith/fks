"""
Breakout CNN — Feature contract, model info, and CLI entry point.

Contains ``generate_feature_contract``, ``get_type_embedding_weights``,
``model_info``, ``_cli``, and the ``__main__`` block.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from analysis.ml.breakout_constants import (
    _TORCH_AVAILABLE,
    ASSET_CLASS_ORDINALS,
    ASSET_VOLATILITY_CLASS,
    BREAKOUT_TYPE_ORDINALS,
    DEFAULT_MODEL_DIR,
    DEFAULT_THRESHOLD,
    FEATURE_CONTRACT_VERSION,
    IMAGE_SIZE,
    IMAGENET_MEAN,
    IMAGENET_STD,
    NUM_OUTPUT_CLASSES,
    NUM_TABULAR,
    SESSION_ORDINAL,
    SESSION_THRESHOLDS,
    TABULAR_FEATURES,
    logger,
)
from analysis.ml.breakout_loading import (
    _find_best_model,
    _find_latest_model,
)
from analysis.ml.breakout_model import (
    ASSET_CLASS_EMBED_DIM,
    ASSET_CLASS_IDX_LOOKUP,
    ASSET_ID_EMBED_DIM,
    ASSET_ID_LOOKUP,
    NUM_ASSET_CLASSES,
    NUM_ASSETS,
    get_device,
)

# Re-import torch conditionally
if _TORCH_AVAILABLE:
    import torch


# ---------------------------------------------------------------------------
# Feature contract generation
# ---------------------------------------------------------------------------


def generate_feature_contract(output_path: str | None = None) -> dict[str, Any]:
    """Generate and optionally write the ``feature_contract.json`` v8 file.

    The contract encodes every parameter needed by consumers (engine,
    inference pipeline, rb trainer) to correctly prepare the tabular feature
    vector and interpret model outputs.

    v8 additions over v7.1:
      - ``asset_class_lookup`` / ``asset_id_lookup`` for embedding indices
      - Cross-asset correlation feature descriptions (v8-B)
      - Asset fingerprint feature descriptions (v8-C)
      - Architecture metadata (embedding dims, wider head)

    Args:
        output_path: If given, write the JSON to this path (creates parent
            directories as needed).  If ``None``, only return the dict.

    Returns:
        The contract as a Python dict (always returned regardless of
        ``output_path``).
    """
    import json as _json
    from datetime import datetime as _dt

    # Import breakout type helpers for the full contract
    try:
        from core.breakout_types import to_feature_contract_dict as _bt_dict

        _breakout_types_section = _bt_dict()
    except ImportError:
        _breakout_types_section = {}

    contract: dict[str, Any] = {
        "version": FEATURE_CONTRACT_VERSION,
        "num_tabular": NUM_TABULAR,
        "tabular_features": TABULAR_FEATURES,
        "default_threshold": DEFAULT_THRESHOLD,
        "image_size": IMAGE_SIZE,
        "imagenet_mean": IMAGENET_MEAN,
        "imagenet_std": IMAGENET_STD,
        # Per-session CNN thresholds — must match session threshold config
        "session_thresholds": SESSION_THRESHOLDS,
        # Per-session ordinals — must match session ordinal config
        "session_ordinals": SESSION_ORDINAL,
        # Asset class map — must match asset class normalisation
        "asset_class_map": ASSET_CLASS_ORDINALS,
        # v6: breakout type ordinals — must match BreakoutType enum
        "breakout_type_ordinals": BREAKOUT_TYPE_ORDINALS,
        # v6: asset volatility classes — must match volatility class config
        "asset_volatility_classes": ASSET_VOLATILITY_CLASS,
        # v6: full breakout type configs (ordinals, bracket params, box styles)
        "breakout_types": _breakout_types_section,
        # v7: daily strategy layer feature descriptions
        "v7_feature_descriptions": {
            "daily_bias_direction": "Daily bias from bias_analyzer: SHORT=0.0, NEUTRAL=0.5, LONG=1.0",
            "daily_bias_confidence": "Confidence of daily bias analysis, 0.0-1.0 scalar",
            "prior_day_pattern": (
                "Yesterday's candle pattern ordinal / 9: inside=0, doji=1, "
                "engulfing_bull=2, engulfing_bear=3, hammer=4, shooting_star=5, "
                "strong_close_up=6, strong_close_down=7, outside_day=8, neutral=9"
            ),
            "weekly_range_position": "Price position within prior week's H/L range: 0.0=at low, 1.0=at high",
            "monthly_trend_score": "Normalised slope of 20-day EMA on daily bars: [-1,+1] mapped to [0,1]",
            "crypto_momentum_score": "Crypto momentum leading indicator: [-1,+1] mapped to [0,1], 0.5=neutral",
        },
        # v7.1: Phase 4B sub-feature decomposition descriptions
        "v71_sub_feature_descriptions": {
            "breakout_type_category": (
                "Coarse grouping of breakout_type_ord: time-based=0.0 (ORB, Asian, IB), "
                "range-based=0.5 (PDR, Weekly, Monthly, VA, Inside, Gap, Pivot, Fib), "
                "squeeze-based=1.0 (Consolidation, BollingerSqueeze)"
            ),
            "session_overlap_flag": (
                "1.0 if the bar is in the London+NY overlap window (08:00-12:00 ET), "
                "0.0 otherwise. Captures the highest-volume intraday window."
            ),
            "atr_trend": (
                "ATR direction over last 10 bars: 1.0=expanding (volatility increasing), "
                "0.0=contracting (volatility decreasing), 0.5=flat. "
                "Enriches atr_pct with trend context."
            ),
            "volume_trend": (
                "5-bar volume slope normalised to [0,1]: 1.0=rising sharply, "
                "0.5=flat, 0.0=declining sharply. Enriches volume_ratio with "
                "trend context - rising volume into breakout is bullish for continuation."
            ),
        },
        # v7.1: breakout type category mapping
        "breakout_type_categories": {
            "time_based": ["ORB", "Asian", "InitialBalance"],
            "range_based": [
                "PrevDay",
                "Weekly",
                "Monthly",
                "ValueArea",
                "InsideDay",
                "GapRejection",
                "PivotPoints",
                "Fibonacci",
            ],
            "squeeze_based": ["Consolidation", "BollingerSqueeze"],
        },
        # ── v8-A: Hierarchical asset embedding lookup tables ──────────────
        "asset_class_lookup": ASSET_CLASS_IDX_LOOKUP,
        "asset_id_lookup": ASSET_ID_LOOKUP,
        "num_asset_classes": NUM_ASSET_CLASSES,
        "num_assets": NUM_ASSETS,
        "asset_class_embed_dim": ASSET_CLASS_EMBED_DIM,
        "asset_id_embed_dim": ASSET_ID_EMBED_DIM,
        # ── v8-B: Cross-asset correlation feature descriptions ────────────
        "v8_cross_asset_descriptions": {
            "primary_peer_corr": (
                "Pearson correlation with primary peer asset over 30-bar window, "
                "mapped from [-1,1] to [0,1]. 0.5 = uncorrelated."
            ),
            "cross_class_corr": (
                "Strongest cross-class correlation magnitude over 30-bar window, "
                "mapped from [-1,1] to [0,1]. Reveals risk-on/off regime."
            ),
            "correlation_regime": (
                "Correlation structure state: 0.0 = broken/inverted (decorrelated), "
                "0.5 = normal, 1.0 = elevated (herding). Detected by comparing "
                "30-bar vs 200-bar baseline correlation z-score."
            ),
        },
        # ── v8-C: Asset fingerprint feature descriptions ──────────────────
        "v8_fingerprint_descriptions": {
            "typical_daily_range_norm": (
                "Median daily range / ATR(14), clamped [0.5, 2.5] then normalised to [0,1]. "
                "High = very active asset, low = quiet."
            ),
            "session_concentration": (
                "Fraction of daily range captured in the dominant session [0,1]. "
                "High = concentrated activity, low = distributed."
            ),
            "breakout_follow_through": (
                "Trailing 20-day breakout win rate for this asset [0,1]. "
                "1.0 = every breakout continues, 0.0 = every one fades."
            ),
            "hurst_exponent": (
                "Rolling Hurst exponent normalised to [0,1]. "
                "<0.4 = mean-reverting (choppy), >0.6 = trending (momentum), 0.5 = random walk."
            ),
            "overnight_gap_tendency": (
                "Median overnight gap size / ATR, clamped and normalised to [0,1]. "
                "High = gap-prone, low = smooth transitions."
            ),
            "volume_profile_shape": (
                "Intraday volume distribution regularity score [0,1]. "
                "0.9 = U-shaped (predictable), 0.4 = flat (unpredictable)."
            ),
        },
        # ── v9: 3-class output head metadata (RETRAIN-I1) ────────────────
        "num_output_classes": NUM_OUTPUT_CLASSES,
        "output_class_labels": {
            "0": "bad/choppy/no_setup",
            "1": "marginal",
            "2": "good/excellent",
        },
        "label_scheme": {
            "version": "v9",
            "labels": [
                "excellent_long",
                "excellent_short",
                "good_long",
                "good_short",
                "marginal_long",
                "marginal_short",
                "bad_long",
                "bad_short",
                "choppy_long",
                "choppy_short",
                "no_setup",
            ],
            "target_mapping": {
                "excellent_long": 2,
                "excellent_short": 2,
                "good_long": 2,
                "good_short": 2,
                "marginal_long": 1,
                "marginal_short": 1,
                "bad_long": 0,
                "bad_short": 0,
                "choppy_long": 0,
                "choppy_short": 0,
                "no_setup": 0,
            },
            "inference_class": 2,
            "inference_description": "P(good/excellent) = softmax(logits)[:, 2]",
        },
        "generated_at": _dt.now(tz=__import__("datetime").timezone.utc).isoformat(),
    }

    if output_path:
        import os as _os

        _os.makedirs(_os.path.dirname(_os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            _json.dump(contract, fh, indent=2)

    return contract


# ---------------------------------------------------------------------------
# Type embedding inspection (legacy)
# ---------------------------------------------------------------------------


def get_type_embedding_weights(model_path: str | None = None) -> dict[str, Any] | None:
    """Return the learned BreakoutType embedding matrix from a checkpoint.

    Returns None for v4 models (no type embedding) or if torch is unavailable.
    Kept for backward compatibility with callers that checked for embeddings
    in older v6 checkpoints.
    """
    if not _TORCH_AVAILABLE:
        return None

    mp = model_path or _find_best_model()
    if not mp or not os.path.isfile(mp):
        return None

    try:
        try:
            sd = torch.load(mp, map_location="cpu", weights_only=True)
        except TypeError:
            sd = torch.load(mp, map_location="cpu")  # type: ignore[call-overload]

        if "type_embedding.weight" not in sd:
            # v4 models have no type embedding — this is expected
            return None

        emb_weight = sd["type_embedding.weight"].numpy()
        _ordinal_to_name = {int(round(v * 12)): k for k, v in BREAKOUT_TYPE_ORDINALS.items()}
        result: dict[str, Any] = {}
        for i, vec in enumerate(emb_weight):
            name = _ordinal_to_name.get(i, f"type_{i}")
            result[name] = vec.tolist()
        return result
    except Exception as exc:
        logger.warning("Failed to extract type embedding weights: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Model info / diagnostics
# ---------------------------------------------------------------------------


def model_info(model_path: str | None = None) -> dict[str, Any]:
    """Return diagnostic information about the current or specified model.

    Useful for the dashboard / health checks.
    """
    if not _TORCH_AVAILABLE:
        return {"available": False, "error": "PyTorch not installed"}

    path = model_path or _find_latest_model()
    if path is None:
        return {"available": False, "error": "No trained model found"}

    try:
        file_stat = os.stat(path)
        size_mb = file_stat.st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
    except OSError:
        size_mb = 0.0
        modified = ""

    info = {
        "available": True,
        "model_path": path,
        "size_mb": round(size_mb, 1),
        "modified": modified,
        "device": get_device(),
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "image_size": IMAGE_SIZE,
        "num_tabular_features": NUM_TABULAR,
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "tabular_features": TABULAR_FEATURES,
        "default_threshold": DEFAULT_THRESHOLD,
    }

    if torch.cuda.is_available():
        info["cuda_device"] = torch.cuda.get_device_name(0)
        info["cuda_memory_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)

    return info


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _cli():
    """Simple CLI for training and inference."""
    import argparse

    parser = argparse.ArgumentParser(description="Breakout CNN — Train or Predict")
    sub = parser.add_subparsers(dest="command")

    # Train
    train_parser = sub.add_parser("train", help="Train the CNN model")
    train_parser.add_argument("--csv", required=True, help="Path to training CSV")
    train_parser.add_argument("--val-csv", default=None, help="Path to validation CSV")
    train_parser.add_argument("--epochs", type=int, default=8)
    train_parser.add_argument("--batch-size", type=int, default=32)
    train_parser.add_argument("--lr", type=float, default=3e-4)
    train_parser.add_argument("--freeze-epochs", type=int, default=2)
    train_parser.add_argument("--model-dir", default=DEFAULT_MODEL_DIR)
    train_parser.add_argument("--image-root", default=None)
    train_parser.add_argument(
        "--type-embedding",
        action="store_true",
        default=False,
        help="Legacy flag — ignored for v6 models (no type embedding used).",
    )
    train_parser.add_argument("--workers", type=int, default=4)

    # Predict
    pred_parser = sub.add_parser("predict", help="Predict on a single image")
    pred_parser.add_argument("--image", required=True, help="Path to chart PNG")
    pred_parser.add_argument(
        "--features",
        nargs=NUM_TABULAR,
        type=float,
        required=True,
        help=f"Tabular features: {', '.join(TABULAR_FEATURES)}",
    )
    pred_parser.add_argument("--model", default=None, help="Model path (default: latest)")
    pred_parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)

    # Info
    sub.add_parser("info", help="Show model info")

    # Embedding inspection
    sub.add_parser(
        "embedding",
        help="Print learned BreakoutType embedding weights from the current champion model",
    )

    # Contract
    contract_parser = sub.add_parser("contract", help="Generate feature_contract.json v6 (18 features)")
    contract_parser.add_argument(
        "--output",
        default="feature_contract.json",
        help="Output path for feature_contract.json (default: ./feature_contract.json)",
    )
    contract_parser.add_argument(
        "--print",
        action="store_true",
        dest="print_only",
        help="Print the contract to stdout without writing a file",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    if args.command == "train":
        from analysis.ml.breakout_training import train_model

        result = train_model(
            data_csv=args.csv,
            val_csv=args.val_csv,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            freeze_epochs=args.freeze_epochs,
            model_dir=args.model_dir,
            image_root=args.image_root,
            num_workers=args.workers,
        )
        if result:
            print(f"\nModel saved to: {result.model_path}")
            print(f"Best epoch: {result.best_epoch}  |  Epochs trained: {result.epochs_trained}")
        else:
            print("\nTraining failed")
            exit(1)

    elif args.command == "predict":
        from analysis.ml.breakout_inference import predict_breakout

        result = predict_breakout(
            image_path=args.image,
            tabular_features=args.features,
            model_path=args.model,
            threshold=args.threshold,
        )
        if result:
            signal_str = "SIGNAL" if result["signal"] else "NO SIGNAL"
            print(
                f"\n{signal_str} — P(good breakout) = {result['prob']:.4f} "
                f"(threshold={result['threshold']}, confidence={result['confidence']})"
            )
        else:
            print("\nPrediction failed")
            exit(1)

    elif args.command == "embedding":
        weights = get_type_embedding_weights()
        if weights is None:
            print("No type embedding found in checkpoint (model not trained with --type-embedding).")
        else:
            import json as _json

            print(_json.dumps(weights, indent=2))

    elif args.command == "info":
        info = model_info()
        for k, v in info.items():
            print(f"  {k}: {v}")

    elif args.command == "contract":
        import json as _json

        if args.print_only:
            contract = generate_feature_contract(output_path=None)
            print(_json.dumps(contract, indent=2))
        else:
            contract = generate_feature_contract(output_path=args.output)
            print(f"\u2705 feature_contract.json v{contract['version']} written to: {args.output}")
            print(f"   tabular features : {contract['num_tabular']}")
            print(f"   breakout types   : {len(contract.get('breakout_types', {}))}")
            print(f"   sessions         : {len(contract.get('session_thresholds', {}))}")

    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
