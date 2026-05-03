"""
Breakout CNN — Dataset and image transforms.

Contains ``BreakoutDataset`` (PyTorch Dataset for breakout chart images +
tabular features), image transforms for training and inference, and the
``skip_invalid_collate`` helper.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd

from analysis.ml.breakout_constants import (
    _TORCH_AVAILABLE,
    IMAGE_SIZE,
    IMAGENET_MEAN,
    IMAGENET_STD,
    NUM_TABULAR,
    SESSION_ORDINAL,
    logger,
)
from analysis.ml.breakout_features import (
    get_asset_class_id,
    get_asset_volatility_class,
    get_breakout_type_ordinal,
)
from analysis.ml.breakout_model import (
    get_asset_class_idx,
    get_asset_idx,
)

# Re-import torch & friends conditionally
if _TORCH_AVAILABLE:
    import torch
    import torchvision.transforms as T
    from PIL import Image
    from torch.utils.data import Dataset


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------


def get_inference_transform():
    """Standard image transform for inference (resize + normalise)."""
    if not _TORCH_AVAILABLE:
        return None
    return T.Compose(
        [
            T.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            T.ToTensor(),
            T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


def get_training_transform():
    """Image transform for training with moderate augmentation.

    Augmentations are moderate — we want the CNN to learn from the chart
    structure (candlestick bodies, ORB box, overlays) while building
    robustness against minor visual variations to reduce overfitting.

    Augmentation strategy:
      - Random crop (±32 px): simulates chart zoom variation
      - No horizontal flip: chart direction (left→right time) must be preserved
      - Brightness/contrast jitter (±12%): handles monitor calibration
        differences and theme variations (dark vs light dashboard)
      - Saturation jitter (±8%): Kraken/crypto pairs use different
        colour palettes from futures charts
      - Random rotation (±2.0°): simulates slight chart panel tilt in screenshots
      - Random erasing (p=0.15, max 15% area): simulates UI overlays
        or partial occlusions on the dashboard
    """
    if not _TORCH_AVAILABLE:
        return None
    return T.Compose(
        [
            T.Resize((IMAGE_SIZE + 32, IMAGE_SIZE + 32)),
            T.RandomCrop((IMAGE_SIZE, IMAGE_SIZE)),
            T.RandomHorizontalFlip(p=0.0),  # disabled — chart direction matters
            T.RandomRotation(degrees=2.0, fill=0),
            T.ColorJitter(brightness=0.12, contrast=0.12, saturation=0.08, hue=0.0),
            T.ToTensor(),
            T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            T.RandomErasing(p=0.15, scale=(0.02, 0.15), ratio=(0.3, 3.3), value=0),
        ]
    )


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

if _TORCH_AVAILABLE:

    class BreakoutDataset(Dataset[Any]):  # type: ignore[no-redef]
        """PyTorch Dataset for breakout chart images + tabular features.

        Expects a CSV with columns:
          - image_path: path to the PNG chart snapshot
          - label: one of the 11 label values produced by rb_simulator:
              excellent_long, excellent_short  — hit TP2/TP3 (R ≥ 2.0)
              good_long, good_short            — hit TP1 only (1.0 ≤ R < 2.0)
              marginal_long, marginal_short    — timed out in profit (0 < R < 1.0)
              bad_long, bad_short              — SL hit or timed out at a loss
              choppy_long, choppy_short        — SL hit within 15 bars (fast reversal)
              no_setup                         — no valid breakout formed
          - quality_pct, volume_ratio, atr_pct, cvd_delta, nr7_flag, direction
            (the tabular features)

        3-class target mapping (RETRAIN-I1):
          - 2: excellent_* or good_*  (hit TP1+, R ≥ 1.0)
          - 1: marginal_*             (timed out in profit, 0 < R < 1.0)
          - 0: bad_*, choppy_*, no_setup, no_trade  (don't trade)
        """

        def __init__(
            self,
            csv_path: str,
            transform=None,
            image_root: str | None = None,
        ):
            self.df = pd.read_csv(csv_path)
            self.transform = transform or get_inference_transform()
            self.image_root = image_root

            if "label" not in self.df.columns:
                raise ValueError("CSV must have a 'label' column")

            # --- Pre-validate: aggressively remove rows without usable images ---
            initial_count = len(self.df)

            # 1. Drop rows where image_path is NaN or empty string
            self.df = self.df.dropna(subset=["image_path"])
            self.df = self.df[self.df["image_path"].astype(str).str.strip().ne("")]
            dropped_empty = initial_count - len(self.df)

            # 2. Verify image files actually exist on disk
            exists_mask = self.df["image_path"].apply(lambda p: os.path.isfile(self._resolve_image_path(str(p))))  # type: ignore[union-attr]
            dropped_missing = int((~exists_mask).sum())  # type: ignore[arg-type]
            self.df = self.df[exists_mask]

            # 3. Integrity check — verify images can actually be opened.
            #    Corrupt files (truncated writes, zero-byte, partial PNGs)
            #    cause repeated warnings every epoch in __getitem__.  We
            #    catch them here, delete them from disk, and drop the rows.
            dropped_corrupt = 0
            if len(self.df) > 0:

                def _is_readable(p: str) -> bool:
                    resolved = self._resolve_image_path(str(p))
                    if not os.path.isfile(resolved):
                        return False
                    try:
                        with Image.open(resolved) as img:
                            img.verify()
                        return True
                    except Exception:
                        return False

                readable_mask = self.df["image_path"].apply(_is_readable)  # type: ignore[union-attr]
                corrupt_mask = ~readable_mask
                dropped_corrupt = int(corrupt_mask.sum())

                if dropped_corrupt > 0:
                    # Delete corrupt files from disk so they don't pollute future runs
                    for bad_path in self.df.loc[corrupt_mask, "image_path"]:
                        resolved = self._resolve_image_path(str(bad_path))
                        if os.path.isfile(resolved):
                            try:
                                os.remove(resolved)
                                logger.info("Deleted corrupt image: %s", resolved)
                            except OSError as rm_err:
                                logger.warning("Could not delete corrupt image %s: %s", resolved, rm_err)
                    self.df = self.df[readable_mask]

            # 4. Reset index so iloc is contiguous
            self.df = self.df.reset_index(drop=True)  # type: ignore[union-attr]

            if dropped_empty > 0 or dropped_missing > 0 or dropped_corrupt > 0:
                logger.warning(
                    "BreakoutDataset: dropped %d empty-path + %d missing-file + %d corrupt-image rows from %s (kept %d / %d)",
                    dropped_empty,
                    dropped_missing,
                    dropped_corrupt,
                    csv_path,
                    len(self.df),
                    initial_count,
                )

            logger.info("BreakoutDataset loaded: %d samples from %s", len(self.df), csv_path)

        def _resolve_image_path(self, p: str) -> str:
            """Resolve an image path from CSV to an on-disk location.

            Handles every path variant the pipeline can produce:
              1. Absolute Docker path: /app/dataset/images/X.png
                 → works inside container as-is; also try stripping /app/
              2. Validator-stripped relative: dataset/images/X.png
                 → would double-nest with image_root; extract basename
              3. Bare filename: X.png
                 → join with image_root
              4. Absolute non-Docker path: /some/other/X.png
                 → use as-is
            """
            p = str(p).strip()

            # Fast path: the path already exists (absolute Docker path inside
            # the container, or any other valid absolute/relative path).
            if os.path.isfile(p):
                return p

            # Strip Docker /app/ prefix if present (common when CSV is
            # written inside a container but read on the host or after the
            # pre-training validator has already stripped it partially).
            _DOCKER_PREFIX = "/app/"
            bare = p
            if bare.startswith(_DOCKER_PREFIX):
                bare = bare[len(_DOCKER_PREFIX) :]

            # If image_root is set, try multiple resolution strategies:
            if self.image_root:
                # Strategy A: join image_root + bare path as-is
                candidate = os.path.join(self.image_root, bare)
                if os.path.isfile(candidate):
                    return candidate

                # Strategy B: use only the filename (basename) to avoid
                # double-nesting like /app/dataset/images/dataset/images/X.png
                basename = os.path.basename(bare)
                candidate = os.path.join(self.image_root, basename)
                if os.path.isfile(candidate):
                    return candidate

            # Fallback: return the best-effort path (may not exist — caller
            # will handle the missing-file case).
            if self.image_root and not os.path.isabs(bare):
                return os.path.join(self.image_root, os.path.basename(bare))
            return p

        def __len__(self) -> int:
            return len(self.df)

        def __getitem__(self, idx: int):
            row = self.df.iloc[idx]  # type: ignore[union-attr]

            # --- Image ---
            img_path = self._resolve_image_path(str(row["image_path"]))

            valid = True  # tracks whether this sample should be used
            try:
                img = Image.open(img_path).convert("RGB")

                # Detect degenerate / near-blank images: if the image has
                # essentially zero variance it contains no chart information
                # (e.g. a solid-colour fallback from a render failure).
                img_arr = np.asarray(img)
                if img_arr.std() < 2.0:
                    logger.warning(
                        "Near-blank image detected (std=%.2f): %s — marking invalid",
                        img_arr.std(),
                        img_path,
                    )
                    valid = False
            except Exception as exc:
                logger.warning("Failed to load image %s: %s — marking invalid", img_path, exc)
                # Create a dummy image so tensor pipeline doesn't crash;
                # the valid=False flag tells the collate_fn to drop this sample.
                img = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), color=(0, 0, 0))
                valid = False

            if self.transform:
                img = self.transform(img)

            # ── Tabular features v8 — 37 features matching feature_contract v8 ──
            #
            # Raw values are normalised here using the same transforms as
            # the original normalisation logic so that
            # Python training and inference are byte-for-byte identical.

            # [0] quality_pct_norm — quality / 100, clamp [0, 1]
            _qual = max(0.0, min(1.0, float(row.get("quality_pct", 50)) / 100.0))

            # [1] volume_ratio — log-scale: min(log1p(raw) / log1p(10), 1.0)
            _vol_raw = max(float(row.get("volume_ratio", 1.0)), 0.01)
            _vol_norm = min(np.log1p(_vol_raw) / np.log1p(10.0), 1.0)

            # [2] atr_pct — ×100 then clamp [0, 1]
            _atr_norm = min(float(row.get("atr_pct", 0.0)) * 100.0, 1.0)

            # [3] cvd_delta — clamp [-1, 1]
            _cvd_norm = max(-1.0, min(1.0, float(row.get("cvd_delta", 0.0))))

            # [4] nr7_flag — passthrough 0 or 1
            _nr7 = float(row.get("nr7_flag", 0))

            # [5] direction_flag — 1=LONG 0=SHORT
            _dir = 1.0 if str(row.get("direction", "")).upper().startswith("L") else 0.0

            # [6] session_ordinal — Globex day position [0, 1]; infer from breakout_time
            _hour = 10  # default to US open hour
            _session_ord = SESSION_ORDINAL["us"]
            try:
                _bt = str(row.get("breakout_time", ""))
                if _bt and " " in _bt:
                    _hour = int(_bt.split(" ")[1].split(":")[0])
                    if _hour < 3:
                        _session_ord = SESSION_ORDINAL["shanghai"]
                    elif _hour < 8:
                        _session_ord = SESSION_ORDINAL["london"]
                    elif _hour < 9:
                        _session_ord = SESSION_ORDINAL["london_ny"]
                    else:
                        _session_ord = SESSION_ORDINAL["us"]
            except Exception:
                pass

            # [7] london_overlap_flag — 08:00–09:00 ET
            _london_overlap = 1.0 if 8 <= _hour <= 9 else 0.0

            # [8] or_range_atr_ratio — ORB range / ATR; clamp(raw, 0, 3) / 3
            _orb_range = float(row.get("range_size", row.get("or_range", 0.0)))
            _atr_val = float(row.get("atr_value", 0.0))
            if _atr_val <= 0:
                # Derive atr_value from atr_pct × a proxy price (1.0 → atr_pct already fractional)
                _atr_val = float(row.get("atr_pct", 0.0))
            _or_range_atr = min(max(_orb_range / _atr_val, 0.0), 3.0) / 3.0 if _atr_val > 0 else 0.0

            # [9] premarket_range_ratio — premarket range / ORB range; clamp(raw, 0, 5) / 5
            _pm_range = float(row.get("premarket_range", 0.0))
            _pm_ratio = min(max(_pm_range / _orb_range, 0.0), 5.0) / 5.0 if _orb_range > 0 else 0.0

            # [10] bar_of_day — minutes since Globex open (18:00 ET) / 1380; clamp [0, 1]
            _bar_min = int(row.get("bar_of_day_minutes", -1))
            if _bar_min < 0:
                # Derive from _hour: minutes since 18:00 ET
                _bar_min = (_hour + 6) * 60 if _hour < 18 else (_hour - 18) * 60
            _bar_of_day = max(0.0, min(1.0, _bar_min / 1380.0))

            # [11] day_of_week — Mon=0..Fri=4 / 4; already normalised in CSV or default 0.5
            _dow = float(row.get("day_of_week_norm", 0.5))

            # [12] vwap_distance — (price − vwap) / ATR; clamp(raw, -3, 3) / 3
            _vwap_dist_raw = float(row.get("vwap_distance", 0.0))
            _vwap_dist = max(-3.0, min(3.0, _vwap_dist_raw)) / 3.0

            # [13] asset_class_id — ordinal / 4 matching asset class normalisation
            _ticker = str(row.get("ticker", row.get("symbol", ""))).upper().strip()
            _asset_cls = get_asset_class_id(_ticker)

            # ── v6 additions ──────────────────────────────────────────────

            # [14] breakout_type_ord — BreakoutType ordinal / 12 → [0, 1]
            _bt_ord_val = 0.0
            try:
                _bt_raw = str(row.get("breakout_type", row.get("breakout_type_ord", "ORB")))
                # Try numeric ordinal first (from CSV)
                try:
                    _bt_ord_val = max(0.0, min(1.0, float(row.get("breakout_type_ord", -1))))
                    if _bt_ord_val < 0:
                        raise ValueError
                except (ValueError, TypeError):
                    _bt_ord_val = get_breakout_type_ordinal(_bt_raw)
            except Exception:
                _bt_ord_val = 0.0

            # [15] asset_volatility_class — low=0.0, med=0.5, high=1.0
            _vol_cls = get_asset_volatility_class(_ticker)

            # [16] hour_of_day — ET hour / 23 → [0, 1]
            _hour_of_day = max(0.0, min(1.0, _hour / 23.0))

            # [17] tp3_atr_mult_norm — TP3 multiplier / 5.0 → [0, 1]
            _tp3_mult = 0.0
            try:
                _tp3_raw = float(row.get("tp3_atr_mult", 0.0))
                _tp3_mult = max(0.0, min(1.0, _tp3_raw / 5.0))
            except (ValueError, TypeError):
                pass

            # ── v7 features (slots 18–23) — read from CSV or default ─────
            _daily_bias_dir = max(0.0, min(1.0, float(row.get("daily_bias_direction", 0.5))))
            _daily_bias_conf = max(0.0, min(1.0, float(row.get("daily_bias_confidence", 0.0))))
            _prior_day_pat = max(0.0, min(1.0, float(row.get("prior_day_pattern", 1.0))))
            _weekly_range_pos = max(0.0, min(1.0, float(row.get("weekly_range_position", 0.5))))
            _monthly_trend = max(0.0, min(1.0, float(row.get("monthly_trend_score", 0.5))))
            _crypto_mom = max(0.0, min(1.0, float(row.get("crypto_momentum_score", 0.5))))

            # ── v7.1 sub-features (slots 24–27) — read from CSV or default
            _bt_category = max(0.0, min(1.0, float(row.get("breakout_type_category", 0.5))))
            _session_overlap = max(0.0, min(1.0, float(row.get("session_overlap_flag", 0.0))))
            _atr_trend = max(0.0, min(1.0, float(row.get("atr_trend", 0.5))))
            _vol_trend = max(0.0, min(1.0, float(row.get("volume_trend", 0.5))))

            # ── v8-B cross-asset correlation features (slots 28–30) ──────
            _primary_peer_corr = max(0.0, min(1.0, float(row.get("primary_peer_corr", 0.5))))
            _cross_class_corr = max(0.0, min(1.0, float(row.get("cross_class_corr", 0.5))))
            _correlation_regime = max(0.0, min(1.0, float(row.get("correlation_regime", 0.5))))

            # ── v8-C asset fingerprint features (slots 31–36) ────────────
            _typical_daily_range_norm = max(0.0, min(1.0, float(row.get("typical_daily_range_norm", 0.5))))
            _session_concentration = max(0.0, min(1.0, float(row.get("session_concentration", 0.5))))
            _breakout_follow_through = max(0.0, min(1.0, float(row.get("breakout_follow_through", 0.5))))
            _hurst_exponent = max(0.0, min(1.0, float(row.get("hurst_exponent", 0.5))))
            _overnight_gap_tendency = max(0.0, min(1.0, float(row.get("overnight_gap_tendency", 0.5))))
            _volume_profile_shape = max(0.0, min(1.0, float(row.get("volume_profile_shape", 0.5))))

            tabular = torch.tensor(
                [
                    _qual,  # [0]  quality_pct_norm
                    _vol_norm,  # [1]  volume_ratio (log-scaled)
                    _atr_norm,  # [2]  atr_pct (×100, clamped)
                    _cvd_norm,  # [3]  cvd_delta
                    _nr7,  # [4]  nr7_flag
                    _dir,  # [5]  direction_flag
                    _session_ord,  # [6]  session_ordinal
                    _london_overlap,  # [7]  london_overlap_flag
                    _or_range_atr,  # [8]  or_range_atr_ratio
                    _pm_ratio,  # [9]  premarket_range_ratio
                    _bar_of_day,  # [10] bar_of_day
                    _dow,  # [11] day_of_week
                    _vwap_dist,  # [12] vwap_distance
                    _asset_cls,  # [13] asset_class_id
                    _bt_ord_val,  # [14] breakout_type_ord
                    _vol_cls,  # [15] asset_volatility_class
                    _hour_of_day,  # [16] hour_of_day
                    _tp3_mult,  # [17] tp3_atr_mult_norm
                    # ── v7 ────────────────────────────────────────────────
                    _daily_bias_dir,  # [18] daily_bias_direction
                    _daily_bias_conf,  # [19] daily_bias_confidence
                    _prior_day_pat,  # [20] prior_day_pattern
                    _weekly_range_pos,  # [21] weekly_range_position
                    _monthly_trend,  # [22] monthly_trend_score
                    _crypto_mom,  # [23] crypto_momentum_score
                    # ── v7.1 ──────────────────────────────────────────────
                    _bt_category,  # [24] breakout_type_category
                    _session_overlap,  # [25] session_overlap_flag
                    _atr_trend,  # [26] atr_trend
                    _vol_trend,  # [27] volume_trend
                    # ── v8-B cross-asset ──────────────────────────────────
                    _primary_peer_corr,  # [28] primary_peer_corr
                    _cross_class_corr,  # [29] cross_class_corr
                    _correlation_regime,  # [30] correlation_regime
                    # ── v8-C fingerprint ──────────────────────────────────
                    _typical_daily_range_norm,  # [31] typical_daily_range_norm
                    _session_concentration,  # [32] session_concentration
                    _breakout_follow_through,  # [33] breakout_follow_through
                    _hurst_exponent,  # [34] hurst_exponent
                    _overnight_gap_tendency,  # [35] overnight_gap_tendency
                    _volume_profile_shape,  # [36] volume_profile_shape
                ],
                dtype=torch.float32,
            )

            # Guard against NaN / Inf from corrupt data
            if torch.isnan(tabular).any() or torch.isinf(tabular).any():
                logger.warning("NaN/Inf in tabular features at row %d — zeroing", idx)
                tabular = torch.zeros(NUM_TABULAR, dtype=torch.float32)

            # ── v8-A: Embedding IDs (integer, NOT in the float tabular vector) ──
            _asset_class_idx = get_asset_class_idx(_ticker)
            _asset_idx = get_asset_idx(_ticker)

            # --- Label (3-class mapping, RETRAIN-I1 / RETRAIN-I4) ---
            # Class 0: bad / choppy / no_setup  — do not trade
            # Class 1: marginal                 — timed out in profit (0 < R < 1.0)
            # Class 2: good / excellent         — hit TP1+ (R ≥ 1.0)
            label_str = str(row.get("label", "bad"))
            if label_str.startswith("excellent") or label_str.startswith("good"):
                target = 2
            elif label_str.startswith("marginal"):
                target = 1
            else:
                # bad_*, choppy_*, no_setup, no_trade → class 0 (don't trade)
                target = 0

            return (
                img,
                tabular,
                torch.tensor(target, dtype=torch.long),
                torch.tensor(valid, dtype=torch.bool),
                torch.tensor(_asset_class_idx, dtype=torch.long),
                torch.tensor(_asset_idx, dtype=torch.long),
            )

        @staticmethod
        def skip_invalid_collate(batch):
            """Custom collate_fn that drops samples flagged as invalid.

            Each sample is a tuple:
              ``(img, tabular, target, valid_flag, asset_class_idx, asset_idx)``
            Only samples where ``valid_flag`` is True are kept.  If the entire
            batch is invalid we return ``None`` — the training loop must check
            for this and skip the batch.
            """
            # batch is a list of 6-tuples
            filtered = [s for s in batch if s[3].item()]
            if not filtered:
                return None  # entire batch was invalid — caller must skip

            imgs = torch.stack([s[0] for s in filtered])
            tabs = torch.stack([s[1] for s in filtered])
            targets = torch.stack([s[2] for s in filtered])
            asset_class_ids = torch.stack([s[4] for s in filtered])
            asset_ids = torch.stack([s[5] for s in filtered])
            return imgs, tabs, targets, asset_class_ids, asset_ids


else:
    # Stub when torch is not available
    class BreakoutDataset:  # type: ignore[no-redef,misc]
        """Stub for environments without PyTorch."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("PyTorch is not installed — cannot create BreakoutDataset")

        def __len__(self) -> int:
            return 0

        def __getitem__(self, idx: int) -> Any:
            raise RuntimeError("PyTorch is not installed")

        @staticmethod
        def skip_invalid_collate(batch: Any) -> Any:
            """Stub — PyTorch is not installed."""
            raise RuntimeError("PyTorch is not installed")
