"""
Breakout CNN — Inference functions.

Contains ``_normalise_tabular_for_inference``, ``predict_breakout``, and
``predict_breakout_batch`` — everything needed to run the trained model
against new chart snapshots at inference time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from analysis.ml.breakout_constants import (
    _TORCH_AVAILABLE,
    NUM_TABULAR,
    TABULAR_FEATURES,
    get_session_threshold,
    logger,
)
from analysis.ml.breakout_dataset import get_inference_transform
from analysis.ml.breakout_loading import (
    _load_model,
    _model_cache,
    _resolve_model_name,
)
from analysis.ml.breakout_model import (
    get_asset_class_idx,
    get_asset_idx,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# Re-import torch & friends conditionally
if _TORCH_AVAILABLE:
    import torch
    from PIL import Image


# ---------------------------------------------------------------------------
# Tabular normalisation for inference
# ---------------------------------------------------------------------------


def _normalise_tabular_for_inference(raw_features: Sequence[float]) -> list[float]:
    """Normalise a raw tabular feature vector for inference.

    Applies the same transforms as the original normalisation logic
    so that Python inference is identical to the canonical contract.

    v8 input order (37 features — must match TABULAR_FEATURES exactly):
        [0]  quality_pct_norm      — quality / 100, already in [0, 1]
        [1]  volume_ratio          — raw ratio (log-normalised here)
        [2]  atr_pct               — ATR / price fraction (×100 here)
        [3]  cvd_delta             — signed vol ratio, clamped [-1, 1]
        [4]  nr7_flag              — 0 or 1 passthrough
        [5]  direction_flag        — 1=LONG 0=SHORT passthrough
        [6]  session_ordinal       — Globex day position [0, 1] passthrough
        [7]  london_overlap_flag   — 0 or 1 passthrough
        [8]  or_range_atr_ratio    — raw ORB/ATR  (clamp(0,3)/3 applied here)
        [9]  premarket_range_ratio — raw PM/ORB  (clamp(0,5)/5 applied here)
        [10] bar_of_day            — already normalised [0, 1] passthrough
        [11] day_of_week           — already normalised [0, 1] passthrough
        [12] vwap_distance         — raw (price-vwap)/ATR (clamp(-3,3)/3 here)
        [13] asset_class_id        — ordinal/4 already [0, 1] passthrough
        [14] breakout_type_ord     — BreakoutType ordinal/12 [0, 1] passthrough
        [15] asset_volatility_class — low=0/med=0.5/high=1.0 passthrough
        [16] hour_of_day           — ET hour/23 [0, 1] passthrough
        [17] tp3_atr_mult_norm     — TP3 mult/5.0 [0, 1] passthrough
        [18] daily_bias_direction  — SHORT=0, NEUTRAL=0.5, LONG=1.0 passthrough
        [19] daily_bias_confidence — [0, 1] passthrough
        [20] prior_day_pattern     — ordinal/9 [0, 1] passthrough
        [21] weekly_range_position — [0, 1] passthrough
        [22] monthly_trend_score   — [0, 1] passthrough
        [23] crypto_momentum_score — [0, 1] passthrough
        [24] breakout_type_category — {0, 0.5, 1.0} passthrough
        [25] session_overlap_flag  — 0 or 1 passthrough
        [26] atr_trend             — [0, 1] passthrough
        [27] volume_trend          — [0, 1] passthrough
        [28] primary_peer_corr     — [0, 1] passthrough
        [29] cross_class_corr      — [0, 1] passthrough
        [30] correlation_regime    — [0, 1] passthrough
        [31] typical_daily_range_norm — [0, 1] passthrough
        [32] session_concentration — [0, 1] passthrough
        [33] breakout_follow_through — [0, 1] passthrough
        [34] hurst_exponent        — [0, 1] passthrough
        [35] overnight_gap_tendency — [0, 1] passthrough
        [36] volume_profile_shape  — [0, 1] passthrough

    For backward compat, 8-feature (v5), 14-feature (v4), 18-feature (v6),
    24-feature (v7), and 28-feature (v7.1) vectors are zero-padded to 37
    with sensible defaults before normalisation.

    Returns a list of NUM_TABULAR floats ready for the model tabular input tensor.
    """
    f = list(raw_features)

    # v8 neutral defaults for slots [28..36] (cross-asset + fingerprint)
    _V8_NEUTRAL_DEFAULTS = [
        0.5,
        0.5,
        0.5,  # [28..30] cross-asset: peer_corr, cross_class, regime
        0.5,
        0.5,
        0.5,
        0.5,
        0.5,
        0.5,  # [31..36] fingerprint: range, session, follow_through, hurst, gap, vol_shape
    ]

    # Backward compat padding — extend shorter vectors with neutral defaults
    if len(f) == 8:
        # v5 (8 features) → pad to 37
        f.extend(
            [
                1.0,
                0.0,
                0.5,
                0.5,
                0.0,
                0.0,  # [8..13]
                0.0,
                0.5,
                0.5,
                0.0,  # [14..17]
                0.5,
                0.0,
                1.0,
                0.5,
                0.5,
                0.5,  # [18..23] v7 neutral defaults
                0.5,
                0.0,
                0.5,
                0.5,  # [24..27] v7.1 neutral defaults
            ]
            + _V8_NEUTRAL_DEFAULTS  # [28..36] v8 neutral defaults
        )
    elif len(f) == 14:
        # v4 (14 features) → pad [14..36]
        f.extend(
            [
                0.0,
                0.5,
                0.5,
                0.0,  # [14..17] v6 defaults
                0.5,
                0.0,
                1.0,
                0.5,
                0.5,
                0.5,  # [18..23] v7 neutral defaults
                0.5,
                0.0,
                0.5,
                0.5,  # [24..27] v7.1 neutral defaults
            ]
            + _V8_NEUTRAL_DEFAULTS  # [28..36] v8 neutral defaults
        )
    elif len(f) == 18:
        # v6 (18 features) → pad [18..36]
        f.extend(
            [
                0.5,
                0.0,
                1.0,
                0.5,
                0.5,
                0.5,  # [18..23] v7 neutral defaults
                0.5,
                0.0,
                0.5,
                0.5,  # [24..27] v7.1 neutral defaults
            ]
            + _V8_NEUTRAL_DEFAULTS  # [28..36] v8 neutral defaults
        )
    elif len(f) == 24:
        # v7 (24 features) → pad [24..36]
        f.extend(
            [0.5, 0.0, 0.5, 0.5]  # [24..27] v7.1 neutral defaults
            + _V8_NEUTRAL_DEFAULTS  # [28..36] v8 neutral defaults
        )
    elif len(f) == 28:
        # v7.1 (28 features) → pad [28..36] with v8 neutral defaults
        f.extend(_V8_NEUTRAL_DEFAULTS)

    if len(f) != NUM_TABULAR:
        raise ValueError(
            f"Expected {NUM_TABULAR} tabular features (v8), 28 (v7.1 compat), "
            f"24 (v7 compat), 18 (v6 compat), 14 (v4 compat), or 8 (v5 compat); "
            f"got {len(f)}. Required order: {TABULAR_FEATURES}"
        )

    # [0] quality_pct_norm — clamp [0, 1]
    quality_norm = max(0.0, min(1.0, f[0]))

    # [1] volume_ratio — log-scale: min(log1p(raw) / log1p(10), 1.0)
    vol_raw = max(f[1], 0.01)
    vol_norm = min(float(np.log1p(vol_raw) / np.log1p(10.0)), 1.0)

    # [2] atr_pct — ×100 then clamp [0, 1]
    atr_norm = max(0.0, min(1.0, f[2] * 100.0))

    # [3] cvd_delta — clamp [-1, 1]
    cvd_norm = max(-1.0, min(1.0, f[3]))

    # [4] nr7_flag       — passthrough
    # [5] direction_flag — passthrough
    # [6] session_ord    — passthrough [0, 1]
    # [7] london_overlap — passthrough

    # [8] or_range_atr_ratio — clamp(raw, 0, 3) / 3
    or_range_atr = max(0.0, min(3.0, f[8])) / 3.0

    # [9] premarket_range_ratio — clamp(raw, 0, 5) / 5
    pm_ratio = max(0.0, min(5.0, f[9])) / 5.0

    # [10] bar_of_day  — already [0, 1], passthrough with clamp
    bar_of_day = max(0.0, min(1.0, f[10]))

    # [11] day_of_week — already [0, 1], passthrough with clamp
    dow = max(0.0, min(1.0, f[11]))

    # [12] vwap_distance — clamp(raw, -3, 3) / 3  → [-1, 1]
    vwap_dist = max(-3.0, min(3.0, f[12])) / 3.0

    # [13] asset_class_id — already [0, 1], passthrough with clamp
    asset_cls = max(0.0, min(1.0, f[13]))

    # [14] breakout_type_ord — already [0, 1], passthrough with clamp
    bt_ord = max(0.0, min(1.0, f[14]))

    # [15] asset_volatility_class — already [0, 1], passthrough with clamp
    vol_class = max(0.0, min(1.0, f[15]))

    # [16] hour_of_day — already [0, 1], passthrough with clamp
    hour_of_day = max(0.0, min(1.0, f[16]))

    # [17] tp3_atr_mult_norm — already [0, 1], passthrough with clamp
    tp3_norm = max(0.0, min(1.0, f[17]))

    return [
        quality_norm,  # [0]
        vol_norm,  # [1]
        atr_norm,  # [2]
        cvd_norm,  # [3]
        f[4],  # [4] nr7_flag
        f[5],  # [5] direction_flag
        f[6],  # [6] session_ordinal
        f[7],  # [7] london_overlap_flag
        or_range_atr,  # [8]
        pm_ratio,  # [9]
        bar_of_day,  # [10]
        dow,  # [11]
        vwap_dist,  # [12]
        asset_cls,  # [13]
        bt_ord,  # [14] breakout_type_ord
        vol_class,  # [15] asset_volatility_class
        hour_of_day,  # [16] hour_of_day
        tp3_norm,  # [17] tp3_atr_mult_norm
        # ── v7 features (slots 18–23) — passthrough with clamp [0, 1] ────
        max(0.0, min(1.0, f[18])),  # [18] daily_bias_direction
        max(0.0, min(1.0, f[19])),  # [19] daily_bias_confidence
        max(0.0, min(1.0, f[20])),  # [20] prior_day_pattern
        max(0.0, min(1.0, f[21])),  # [21] weekly_range_position
        max(0.0, min(1.0, f[22])),  # [22] monthly_trend_score
        max(0.0, min(1.0, f[23])),  # [23] crypto_momentum_score
        # ── v7.1 sub-features (slots 24–27) — passthrough with clamp ─────
        max(0.0, min(1.0, f[24])),  # [24] breakout_type_category
        max(0.0, min(1.0, f[25])),  # [25] session_overlap_flag
        max(0.0, min(1.0, f[26])),  # [26] atr_trend
        max(0.0, min(1.0, f[27])),  # [27] volume_trend
        # ── v8-B cross-asset features (slots 28–30) — passthrough clamp ──
        max(0.0, min(1.0, f[28])),  # [28] primary_peer_corr
        max(0.0, min(1.0, f[29])),  # [29] cross_class_corr
        max(0.0, min(1.0, f[30])),  # [30] correlation_regime
        # ── v8-C fingerprint features (slots 31–36) — passthrough clamp ──
        max(0.0, min(1.0, f[31])),  # [31] typical_daily_range_norm
        max(0.0, min(1.0, f[32])),  # [32] session_concentration
        max(0.0, min(1.0, f[33])),  # [33] breakout_follow_through
        max(0.0, min(1.0, f[34])),  # [34] hurst_exponent
        max(0.0, min(1.0, f[35])),  # [35] overnight_gap_tendency
        max(0.0, min(1.0, f[36])),  # [36] volume_profile_shape
    ]


# ---------------------------------------------------------------------------
# Single-image inference
# ---------------------------------------------------------------------------


def predict_breakout(
    image_path: str,
    tabular_features: Sequence[float],
    model_path: str | None = None,
    threshold: float | None = None,
    session_key: str | None = None,
    ticker: str | None = None,
) -> dict[str, Any] | None:
    """Predict whether a chart snapshot shows a high-quality breakout.

    Args:
        image_path: Path to the PNG chart snapshot.
        tabular_features: List/tuple of floats in TABULAR_FEATURES order.
            Accepts 8 (v5), 14 (v4), 18 (v6), 24 (v7), 28 (v7.1), or
            37 (v8) features — shorter vectors are zero-padded automatically.

        model_path: Explicit model path (default: latest in models/).
        threshold: Probability threshold for "signal" verdict.
                   When None (default), the per-session threshold from
                   ``SESSION_THRESHOLDS`` is used via ``session_key``.
                   Passing an explicit float overrides the session default.
        session_key: ORBSession.key (e.g. "london", "tokyo", "us").
                     Used to look up the per-session threshold and for
                     logging.  Ignored if *threshold* is explicitly set.
        ticker: Symbol ticker (e.g. "MGC", "MNQ") for v8 asset embedding
                lookup **and** per-asset / per-group model selection.
                If None, embedding IDs default to 0 and the combined
                champion model is used.

    Returns:
        Dict with:
          - prob: float (0.0–1.0) — probability of clean breakout
          - signal: bool — True if prob >= threshold
          - confidence: str — "high", "medium", or "low"
          - threshold: float — the threshold that was applied
          - session_key: str — which session threshold was used
          - model_path: str — which model was used
        Or None if inference failed.
    """
    if not _TORCH_AVAILABLE:
        logger.warning("PyTorch not available — cannot run inference")
        return None

    # Resolve per-asset / per-group model when no explicit path is given.
    effective_model_path = model_path
    if effective_model_path is None:
        effective_model_path = _resolve_model_name(ticker)

    model = _load_model(effective_model_path)
    if model is None:
        return None

    # Resolve the effective threshold — explicit arg wins, then per-session,
    # then global default.
    effective_threshold = threshold if threshold is not None else get_session_threshold(session_key)

    device = next(model.parameters()).device
    transform = get_inference_transform()

    try:
        # Load and transform image
        img = Image.open(image_path).convert("RGB")
        assert transform is not None, "Transform must not be None"
        img_tensor = transform(img).unsqueeze(0).to(device)  # type: ignore[union-attr]  # (1, 3, 224, 224)

        # Normalise tabular features (same transforms as training dataset)
        # Handle model expecting fewer features than v8 (backward compat)
        tab_list = _normalise_tabular_for_inference(tabular_features)
        # If the loaded model expects fewer features (e.g. v7.1 28-feature model),
        # truncate to match its num_tabular
        model_num_tab = getattr(model, "num_tabular", NUM_TABULAR)
        if len(tab_list) > model_num_tab:
            tab_list = tab_list[:model_num_tab]
        elif len(tab_list) < model_num_tab:
            # Pad with neutral 0.5 for any missing features
            tab_list.extend([0.5] * (model_num_tab - len(tab_list)))

        tab_tensor = torch.tensor([tab_list], dtype=torch.float32).to(device)

        # v8-A: Asset embedding IDs
        _asset_class_idx = get_asset_class_idx(ticker) if ticker else 0
        _asset_idx = get_asset_idx(ticker) if ticker else 0
        asset_class_ids = torch.tensor([_asset_class_idx], dtype=torch.long).to(device)
        asset_ids = torch.tensor([_asset_idx], dtype=torch.long).to(device)

        # Inference
        with torch.no_grad():
            if model.use_asset_embeddings:
                logits = model(img_tensor, tab_tensor, asset_class_ids=asset_class_ids, asset_ids=asset_ids)
            else:
                logits = model(img_tensor, tab_tensor)
            probs = torch.softmax(logits, dim=1)
            # Class 2 = good/excellent (RETRAIN-I1: 3-class model)
            # Fall back to class 1 for legacy 2-class checkpoints
            num_classes = probs.shape[1]
            prob_good = float(probs[0, 2].item()) if num_classes >= 3 else float(probs[0, 1].item())

        # Confidence bucketing — relative to the effective threshold so that
        # a "high" confidence call means the same quality bar regardless of
        # which session we're in.
        if prob_good >= effective_threshold + 0.08:
            confidence = "high"
        elif prob_good >= effective_threshold - 0.04:
            confidence = "medium"
        else:
            confidence = "low"

        # Determine the actual model path used for reporting.
        used_model_path = effective_model_path or ""
        if not used_model_path:
            for path, (cached_m, _dev) in _model_cache.items():
                if cached_m is model:
                    used_model_path = path
                    break

        return {
            "prob": round(prob_good, 4),
            "signal": prob_good >= effective_threshold,
            "confidence": confidence,
            "threshold": effective_threshold,
            "session_key": session_key or "",
            "model_path": used_model_path,
        }

    except Exception as exc:
        logger.error("Inference failed for %s: %s", image_path, exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Batch inference
# ---------------------------------------------------------------------------


def predict_breakout_batch(
    image_paths: Sequence[str],
    tabular_features_batch: Sequence[Sequence[float]],
    model_path: str | None = None,
    threshold: float | None = None,
    session_key: str | None = None,
    batch_size: int = 16,
    tickers: Sequence[str] | None = None,
) -> list[dict[str, Any] | None]:
    """Batch inference for multiple chart snapshots.

    More efficient than calling ``predict_breakout`` in a loop because it
    batches the GPU forward passes.

    When *model_path* is ``None`` and all items in *tickers* resolve to the
    same per-asset or per-group model, that specialised model is used for
    the whole batch.  If tickers map to different models (or a mix of
    specific and combined), the function falls back to the combined champion
    model so the batch can be processed in a single forward pass.

    Args:
        image_paths: List of PNG paths.
        tabular_features_batch: List of tabular feature vectors (one per image).
        model_path: Explicit model path (default: latest).  When ``None``,
                    per-asset / per-group model resolution is attempted via
                    *tickers* (see above).
        threshold: Signal threshold.  When None (default), the per-session
                   threshold from ``SESSION_THRESHOLDS`` is used via
                   ``session_key``.  Passing an explicit float overrides it.
        session_key: ORBSession.key (e.g. "london", "tokyo", "us") used to
                     look up the per-session threshold.  Ignored if
                     *threshold* is explicitly set.
        batch_size: Max images per GPU forward pass.
        tickers: Optional list of symbol tickers (one per image) for v8
                 asset embedding lookup **and** per-asset / per-group model
                 selection.  If None, all default to ID 0 and the combined
                 champion model is used.

    Returns:
        List of result dicts (same format as predict_breakout), or None entries
        for images that failed to load.
    """
    if not _TORCH_AVAILABLE:
        return [None] * len(image_paths)

    if len(image_paths) != len(tabular_features_batch):
        logger.error("Mismatched lengths: %d images vs %d tabular", len(image_paths), len(tabular_features_batch))
        return [None] * len(image_paths)

    # Resolve per-asset / per-group model for the batch when no explicit
    # path is given.  If all tickers resolve to the same specialised model,
    # use it; otherwise fall back to the combined champion.
    effective_model_path = model_path
    if effective_model_path is None and tickers:
        resolved_paths = {_resolve_model_name(t) for t in tickers}
        # Remove None (combined fallback) — if only one non-None path remains
        # and *every* ticker resolved to it, use the specific model.
        resolved_paths.discard(None)
        if len(resolved_paths) == 1 and all(_resolve_model_name(t) is not None for t in tickers):
            effective_model_path = resolved_paths.pop()

    model = _load_model(effective_model_path)
    if model is None:
        return [None] * len(image_paths)

    # Resolve the effective threshold once for the whole batch.
    effective_threshold = threshold if threshold is not None else get_session_threshold(session_key)

    device = next(model.parameters()).device
    transform = get_inference_transform()
    model_num_tab = getattr(model, "num_tabular", NUM_TABULAR)
    results: list[dict[str, Any] | None] = [None] * len(image_paths)

    # Process in batches
    for batch_start in range(0, len(image_paths), batch_size):
        batch_end = min(batch_start + batch_size, len(image_paths))
        batch_indices = list(range(batch_start, batch_end))

        img_tensors = []
        tab_tensors = []
        acls_tensors = []
        aid_tensors = []
        valid_indices = []

        for i in batch_indices:
            try:
                img = Image.open(image_paths[i]).convert("RGB")
                assert transform is not None
                img_t = transform(img)
                tab_list = _normalise_tabular_for_inference(tabular_features_batch[i])
                # Match model's expected tabular dimension
                if len(tab_list) > model_num_tab:
                    tab_list = tab_list[:model_num_tab]
                elif len(tab_list) < model_num_tab:
                    tab_list.extend([0.5] * (model_num_tab - len(tab_list)))
                tab_t = torch.tensor(tab_list, dtype=torch.float32)

                # v8-A embedding IDs
                _tkr = tickers[i] if tickers and i < len(tickers) else None
                acls_t = torch.tensor(get_asset_class_idx(_tkr) if _tkr else 0, dtype=torch.long)
                aid_t = torch.tensor(get_asset_idx(_tkr) if _tkr else 0, dtype=torch.long)

                img_tensors.append(img_t)
                tab_tensors.append(tab_t)
                acls_tensors.append(acls_t)
                aid_tensors.append(aid_t)
                valid_indices.append(i)
            except Exception as exc:
                logger.debug("Failed to load image %s: %s", image_paths[i], exc)

        if not valid_indices:
            continue

        img_batch = torch.stack(img_tensors).to(device)
        tab_batch = torch.stack(tab_tensors).to(device)
        acls_batch = torch.stack(acls_tensors).to(device)
        aid_batch = torch.stack(aid_tensors).to(device)

        with torch.no_grad():
            if model.use_asset_embeddings:
                logits = model(img_batch, tab_batch, asset_class_ids=acls_batch, asset_ids=aid_batch)
            else:
                logits = model(img_batch, tab_batch)
            # Class 2 = good/excellent (RETRAIN-I1: 3-class model)
            # Fall back to class 1 for legacy 2-class checkpoints
            num_classes = logits.shape[1]
            probs = torch.softmax(logits, dim=1)[:, 2 if num_classes >= 3 else 1]  # (B,)

        for j, global_idx in enumerate(valid_indices):
            prob_good = float(probs[j].item())
            # Relative confidence bucketing — mirrors predict_breakout so
            # "high"/"medium"/"low" mean the same quality bar across sessions.
            if prob_good >= effective_threshold + 0.08:
                confidence = "high"
            elif prob_good >= effective_threshold - 0.04:
                confidence = "medium"
            else:
                confidence = "low"

            # Determine the actual model path used for reporting.
            used_model_path = effective_model_path or ""
            if not used_model_path:
                for _cached_path, (_cached_m, _cached_dev) in _model_cache.items():
                    if _cached_m is model:
                        used_model_path = _cached_path
                        break

            results[global_idx] = {
                "prob": round(prob_good, 4),
                "signal": prob_good >= effective_threshold,
                "confidence": confidence,
                "threshold": effective_threshold,
                "session_key": session_key or "",
                "model_path": used_model_path,
            }

    return results
