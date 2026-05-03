"""
Breakout CNN — Model resolution, caching, and loading from checkpoints.

Contains ``_resolve_model_name``, ``_find_best_model``, ``_find_latest_model``,
``_build_model_from_checkpoint``, ``_load_model``, ``invalidate_model_cache``,
and the module-level ``_model_cache`` / ``_model_lock`` shared state.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from analysis.ml.breakout_constants import (
    _TORCH_AVAILABLE,
    ASSET_GROUPS,
    DEFAULT_MODEL_DIR,
    MODEL_PREFIX,
    NUM_TABULAR,
    logger,
)
from analysis.ml.breakout_model import (
    HybridBreakoutCNN,
    get_device,
)

# Re-import torch conditionally
if _TORCH_AVAILABLE:
    import torch


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------


def _resolve_model_name(symbol: str | None = None) -> str | None:
    """Resolve which model file to use for a given symbol.

    Priority:
      1. Per-asset model:  ``breakout_cnn_best_{symbol}.pt``
      2. Per-group model:  ``breakout_cnn_best_{group}.pt``
      3. Combined model:   ``breakout_cnn_best.pt`` (returned as ``None``
         to let the caller fall through to the default discovery logic).

    Args:
        symbol: Ticker string (e.g. ``"MGC"``, ``"MNQ"``).  ``None`` or
                empty string returns ``None`` immediately.

    Returns:
        Absolute-ish path to the specialised model file if one exists on
        disk, or ``None`` to signal "use the combined champion".
    """
    if not symbol:
        return None

    model_dir = os.getenv("MODELS_DIR", DEFAULT_MODEL_DIR)

    # 1. Check per-asset model
    asset_path = os.path.join(model_dir, f"breakout_cnn_best_{symbol}.pt")
    if os.path.isfile(asset_path):
        return asset_path

    # 2. Check per-group model
    group = ASSET_GROUPS.get(symbol.upper().strip())
    if group:
        group_path = os.path.join(model_dir, f"breakout_cnn_best_{group}.pt")
        if os.path.isfile(group_path):
            return group_path

    # 3. Fall back to combined model
    return None


# ---------------------------------------------------------------------------
# Thread lock and cache for model loading
# ---------------------------------------------------------------------------

# Thread lock for model loading
_model_lock = threading.Lock()
# Dict-based cache keyed by resolved model path so that per-asset,
# per-group, and combined models can coexist in memory simultaneously.
_model_cache: dict[str, tuple[Any, str]] = {}  # path -> (model, device_str)


def invalidate_model_cache() -> bool:
    """Invalidate all cached CNN models so the next inference reloads from disk.

    Thread-safe.  Returns True if any cached model was actually evicted,
    False if the cache was already empty.

    Called by the engine's hot-reload watcher when it detects that a
    model file has changed on disk (new ``st_mtime``).
    """
    global _model_cache
    with _model_lock:
        had_models = len(_model_cache) > 0
        _model_cache.clear()
    if had_models:
        logger.info("CNN model cache invalidated — next inference will reload from disk")
    return had_models


# ---------------------------------------------------------------------------
# Model discovery
# ---------------------------------------------------------------------------


def _find_best_model(model_dir: str = DEFAULT_MODEL_DIR) -> str | None:
    """Find the best available model in *model_dir*.

    Selection priority:
      1. ``breakout_cnn_best.pt`` (the promoted champion) — always preferred
         when it exists.
      2. The checkpoint with the highest ``val_accuracy`` recorded in its
         companion ``<stem>_meta.json`` sidecar file.
      3. The most recently modified ``.pt`` file (mtime fallback when no
         meta JSON is available for any checkpoint).

    Args:
        model_dir: Directory to search (default ``"models"``).

    Returns:
        Absolute path to the chosen model file, or ``None`` if no models
        are found.
    """
    model_path = Path(model_dir)
    if not model_path.is_dir():
        return None

    # 1. Prefer the promoted champion if it exists
    champion = model_path / "breakout_cnn_best.pt"
    if champion.is_file():
        logger.debug("Model selection: using champion %s", champion)
        return str(champion)

    # 2. Scan all breakout_cnn_*.pt checkpoints
    pt_files = list(model_path.glob(f"{MODEL_PREFIX}*.pt"))
    if not pt_files:
        return None

    # Try to rank by val_accuracy from companion meta JSON sidecars.
    # A meta JSON for checkpoint "breakout_cnn_20260101_020000_acc87.pt"
    # would be named "breakout_cnn_20260101_020000_acc87_meta.json".
    # Also check the global "breakout_cnn_best_meta.json" as a fallback.
    global_meta_path = model_path / "breakout_cnn_best_meta.json"

    def _val_accuracy(pt: Path) -> float:
        # Sidecar meta: same stem + _meta.json
        sidecar = pt.with_name(pt.stem + "_meta.json")
        for candidate in (sidecar, global_meta_path):
            if candidate.is_file():
                try:
                    import json as _json

                    meta = _json.loads(candidate.read_text())
                    return float(meta.get("val_accuracy", 0.0))
                except Exception:
                    pass
        # Try to parse accuracy from filename: "..._accNN.pt"
        import re as _re

        m = _re.search(r"_acc(\d+(?:\.\d+)?)", pt.stem)
        if m:
            return float(m.group(1))
        return 0.0

    scored = [(pt, _val_accuracy(pt)) for pt in pt_files]

    # Check if any checkpoint has a meaningful accuracy score
    if any(score > 0.0 for _, score in scored):
        scored.sort(key=lambda x: x[1], reverse=True)
        best = scored[0][0]
        logger.debug(
            "Model selection: chose %s (val_acc=%.1f%%) from %d checkpoints",
            best.name,
            scored[0][1],
            len(pt_files),
        )
        return str(best)

    # 3. Fallback: most recently modified file
    pt_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    logger.debug("Model selection: fallback to newest mtime %s", pt_files[0].name)
    return str(pt_files[0])


def _find_latest_model(model_dir: str = DEFAULT_MODEL_DIR) -> str | None:
    """Alias for :func:`_find_best_model` kept for backwards compatibility."""
    return _find_best_model(model_dir)


# ---------------------------------------------------------------------------
# Model construction from checkpoint
# ---------------------------------------------------------------------------


def _build_model_from_checkpoint(state_dict: dict) -> Any:
    """Instantiate a HybridBreakoutCNN whose architecture matches *state_dict*.

    Detects whether the checkpoint was trained with v8 asset embeddings by
    checking for the ``asset_class_embedding.weight`` key in the state dict.
    Falls back to v7.1/v6 mode if embedding weights are absent.

    Returns a model with weights loaded (eval mode, not moved to device yet).
    """
    if not _TORCH_AVAILABLE:
        return None

    use_asset_emb = "asset_class_embedding.weight" in state_dict

    # Infer num_tabular from first tabular_head Linear weight shape.
    # v8 wider head: tabular_head.0.weight has shape (256, num_tabular)
    # v7.1/v6 head:  tabular_head.0.weight has shape (128, num_tabular)
    num_tabular = NUM_TABULAR
    tab_key = "tabular_head.0.weight"
    if tab_key in state_dict:
        in_features = state_dict[tab_key].shape[1]
        num_tabular = in_features

    model = HybridBreakoutCNN(
        num_tabular=num_tabular,
        pretrained=False,  # weights come from checkpoint
        use_asset_embeddings=use_asset_emb,
    )
    model.load_state_dict(state_dict, strict=False)  # type: ignore[union-attr]
    model.eval()  # type: ignore[union-attr]
    return model


# ---------------------------------------------------------------------------
# Model loading (with caching)
# ---------------------------------------------------------------------------


def _load_model(
    model_path: str | None = None,
    device: str | None = None,
) -> Any | None:
    """Load a HybridBreakoutCNN model from disk.

    Uses the module-level ``_model_cache`` dict (keyed by resolved path) to
    avoid reloading on every inference call.  Multiple models (per-asset,
    per-group, combined) can coexist in the cache simultaneously.

    Thread-safe via ``_model_lock``.  Automatically detects v6/v7.1/v8
    architecture from the checkpoint weights.

    Args:
        model_path: Explicit path to a ``.pt`` file.  If ``None``, finds
                    the best/latest model via :func:`_find_best_model`.
        device: Device to load onto.  If ``None``, auto-detects.

    Returns:
        The loaded model in eval mode, or ``None`` if loading failed.
    """
    if not _TORCH_AVAILABLE:
        return None

    global _model_cache

    if model_path is None:
        model_path = _find_latest_model()

    if model_path is None:
        logger.warning("No trained model found in %s", DEFAULT_MODEL_DIR)
        return None

    with _model_lock:
        # Return cached model if we already loaded this exact path
        if model_path in _model_cache:
            return _model_cache[model_path][0]

        dev = torch.device(device or get_device())

        try:
            try:
                state_dict = torch.load(model_path, map_location=dev, weights_only=True)
            except TypeError:
                state_dict = torch.load(model_path, map_location=dev)  # type: ignore[call-overload]

            model = _build_model_from_checkpoint(state_dict)
            if model is None:
                return None
            model = model.to(dev)

            _model_cache[model_path] = (model, str(dev))

            logger.info(
                "Model loaded: %s → %s (tabular=%d, asset_emb=%s)",
                model_path,
                dev,
                model.num_tabular,
                model.use_asset_embeddings,
            )
            return model

        except Exception as exc:
            logger.error("Failed to load model %s: %s", model_path, exc)
            return None
