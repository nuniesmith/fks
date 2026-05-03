"""
ml/inference.py — CPU inference wrapper for the live futures bot.

Loads pre-trained PerAssetCNN and MasterCNN models from disk and exposes
a simple synchronous API that can be called from inside the async trading
loop without blocking (inference on a small CPU model is <1 ms).

Design
------
- Models are loaded once at worker startup and cached in memory.
- Inference is fully synchronous — no async/await needed.
- If no model file exists for an asset the inference object degrades
  gracefully: predict() returns a neutral result with confidence=0.0
  so the existing EMA + book signal logic takes over unchanged.
- MasterCNN inference is optional; if the master model is absent the
  portfolio risk score defaults to 0.0 (no restriction).

Typical usage in AssetWorker
-----------------------------
    # At startup (inside run(), after exchange is ready)
    from ml.inference import CNNInference
    self._cnn = CNNInference.load(
        asset_key=self.asset_key,
        models_dir=self.config.ml.models_dir,
    )

    # Inside _trading_loop, before _place_order()
    result = self._cnn.predict(
        candles=candles,
        imbalance=imbalance,
        vol_pct=vol_pct,
        wave_ratio=self.wave_state.wave_ratio,
        fast_ema=fast_ema,
        slow_ema=slow_ema,
    )

    if not result.enabled:
        pass  # no model — fall through to normal signal logic

    elif result.confidence < cfg.ml.min_confidence:
        continue  # CNN not convinced — skip entry

    elif result.signal != raw_signal:
        continue  # CNN disagrees with EMA crossover — skip entry

    else:
        # Scale position size by CNN conviction
        size = int(size * result.size_multiplier)

Portfolio risk check (in supervisor loop or per-worker gate)
-------------------------------------------------------------
    from ml.inference import MasterInference
    master = MasterInference.load(models_dir=cfg.ml.models_dir, n_assets=5)
    risk = master.portfolio_risk(asset_feature_tensors)
    # risk is a float in [0, 1]; halt new entries when > cfg.ml.master_risk_threshold
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .features import DEFAULT_WINDOW, N_FEATURES, extract_features
from .model import (
    LABEL_FLAT,
    LABEL_LONG,
    LABEL_NAMES,
    LABEL_SHORT,
    LABEL_LOSS,
    MasterCNN,
    PerAssetCNN,
)

logger = logging.getLogger(__name__)

# ── File naming convention ────────────────────────────────────────────────────
# Per-asset :  models/cnn_{asset_key}.pt          e.g. models/cnn_btc.pt
# Master    :  models/cnn_master.pt

_PER_ASSET_FILENAME = "cnn_{asset}.pt"
_MASTER_FILENAME = "cnn_master.pt"


# ── Result dataclasses ────────────────────────────────────────────────────────


@dataclass
class InferenceResult:
    """Result of a single per-asset CNN inference call.

    Attributes
    ----------
    enabled : bool
        False when no model is loaded for this asset.  When False the
        caller should ignore all other fields and fall back to the
        existing rule-based signal.
    signal : str
        Predicted class: "flat", "long", or "short".
    confidence : float
        Softmax probability of the predicted class [0, 1].
    probs : dict[str, float]
        Full class probability distribution {"flat": …, "long": …, "short": …}.
    size_multiplier : float
        Suggested position-size scaling factor derived from confidence.
        = confidence when confidence >= min_confidence, else 0.0.
        Callers multiply their computed ``lots`` by this value.
    latency_ms : float
        Wall-clock time taken for inference in milliseconds.
    """

    enabled: bool = False
    signal: str = "flat"
    confidence: float = 0.0
    probs: dict[str, float] = field(
        default_factory=lambda: {"flat": 1.0, "long": 0.0, "short": 0.0, "loss": 0.0}
    )
    size_multiplier: float = 0.0
    latency_ms: float = 0.0

    @property
    def is_long(self) -> bool:
        return self.signal == "long"

    @property
    def is_short(self) -> bool:
        return self.signal == "short"

    @property
    def is_flat(self) -> bool:
        return self.signal == "flat"

    @property
    def is_loss(self) -> bool:
        return self.signal == "loss"

    def agrees_with(self, bot_signal: str) -> bool:
        """Return True if the CNN signal matches the bot's EMA crossover signal.

        A flat CNN result never agrees (returns False) so the caller skips the entry.
        """
        if self.signal == "flat":
            return False
        return self.signal == bot_signal

    def __repr__(self) -> str:
        return (
            f"InferenceResult(signal={self.signal!r} conf={self.confidence:.3f} "
            f"mult={self.size_multiplier:.3f} enabled={self.enabled})"
        )


@dataclass
class PortfolioRiskResult:
    """Result of a MasterCNN portfolio risk inference call.

    Attributes
    ----------
    enabled : bool
        False when no master model is loaded.
    risk_score : float
        Portfolio risk score in [0, 1].  A score above the configured
        threshold (e.g. 0.65) should block new entries.
    should_halt : bool
        Convenience flag: True when risk_score >= threshold.
    latency_ms : float
        Wall-clock inference time in milliseconds.
    """

    enabled: bool = False
    risk_score: float = 0.0
    should_halt: bool = False
    latency_ms: float = 0.0

    def __repr__(self) -> str:
        return (
            f"PortfolioRiskResult(risk={self.risk_score:.3f} "
            f"halt={self.should_halt} enabled={self.enabled})"
        )


# ── CNNInference — per-asset wrapper ─────────────────────────────────────────


class CNNInference:
    """Per-asset CNN inference wrapper.

    Loads a PerAssetCNN from disk (if available) and provides a simple
    ``predict()`` method that takes the same inputs available in the
    AssetWorker trading loop.

    Parameters
    ----------
    model : PerAssetCNN or None
        Loaded model.  None means no model available — all predict() calls
        return a disabled InferenceResult.
    asset_key : str
        Short asset name used for logging (e.g. "btc").
    min_confidence : float
        Confidence threshold below which size_multiplier is set to 0.0.
        The caller is still responsible for checking this; the multiplier
        is a convenience for callers that want automatic scaling.
    meta : dict
        Model metadata loaded from the JSON sidecar (accuracy, training
        date, etc.).
    """

    def __init__(
        self,
        model: PerAssetCNN | None,
        asset_key: str,
        min_confidence: float = 0.60,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self._model = model
        self._asset_key = asset_key
        self._min_confidence = min_confidence
        self._meta = meta or {}

        # ── 21.8: Adjust threshold based on model confidence ──────────────
        self._model_confidence = self._meta.get("model_confidence", "high")
        confidence_multipliers = {"high": 1.0, "medium": 1.1, "low": 1.3}
        multiplier = confidence_multipliers.get(self._model_confidence, 1.0)
        if multiplier != 1.0:
            original = self._min_confidence
            self._min_confidence = min(self._min_confidence * multiplier, 0.95)
            logger.info(
                "[%s] Model confidence=%s → threshold adjusted %.2f → %.2f",
                asset_key.upper(),
                self._model_confidence,
                original,
                self._min_confidence,
            )

        # ── 21.11: Temperature scaling for confidence calibration ─────────
        self._temperature = float(self._meta.get("temperature", 1.0))
        if self._temperature != 1.0:
            logger.info(
                "[%s] Confidence calibration: temperature=%.4f  ECE %.4f → %.4f",
                asset_key.upper(),
                self._temperature,
                self._meta.get("ece_before", 0.0),
                self._meta.get("ece_after", 0.0),
            )

        # ── Directional gating ────────────────────────────────────────────
        # If training detected very low recall for one direction, the model
        # metadata will contain directional_gate = "long_only" / "short_only"
        # / "flat_only".  We override blind-direction predictions to "flat"
        # at inference time so the model only signals in directions it can
        # actually detect.
        self._directional_gate = self._meta.get("directional_gate", "both")
        if self._directional_gate != "both":
            logger.warning(
                "[%s] Directional gate active: %s — blind directions will be overridden to flat",
                asset_key.upper(),
                self._directional_gate,
            )

        if model is not None:
            model.eval()
            gate_suffix = (
                f"  gate={self._directional_gate}" if self._directional_gate != "both" else ""
            )
            logger.info(
                "[%s] CNN loaded — params=%d  window=%d  accuracy=%.1f%%  confidence=%s  temp=%.3f  trained=%s%s",
                asset_key.upper(),
                model.param_count(),
                model.window,
                self._meta.get("val_accuracy", 0.0) * 100,
                self._model_confidence,
                self._temperature,
                self._meta.get("trained_at", "unknown"),
                gate_suffix,
            )
        else:
            logger.info(
                "[%s] No CNN model found — inference disabled (rule-based signals only)",
                asset_key.upper(),
            )

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def load(
        cls,
        asset_key: str,
        models_dir: str | Path = "models",
        min_confidence: float = 0.60,
    ) -> CNNInference:
        """Load a PerAssetCNN from disk.

        Looks for ``{models_dir}/cnn_{asset_key}.pt``.
        If the file is missing or corrupt, returns a disabled CNNInference.
        """
        models_dir = Path(models_dir)
        model_path = models_dir / _PER_ASSET_FILENAME.format(asset=asset_key.lower())

        if not model_path.exists():
            logger.debug(
                "[%s] Model file not found at %s — running without CNN",
                asset_key.upper(),
                model_path,
            )
            return cls(model=None, asset_key=asset_key, min_confidence=min_confidence)

        try:
            model = PerAssetCNN.load(model_path, map_location="cpu")
            meta = PerAssetCNN.load_meta(model_path)
            return cls(
                model=model,
                asset_key=asset_key,
                min_confidence=min_confidence,
                meta=meta,
            )
        except Exception as exc:
            logger.warning(
                "[%s] Failed to load CNN from %s: %s — running without CNN",
                asset_key.upper(),
                model_path,
                exc,
            )
            return cls(model=None, asset_key=asset_key, min_confidence=min_confidence)

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict(
        self,
        candles,  # pd.DataFrame — typed loosely to avoid import at module level
        imbalance: float = 1.0,
        vol_pct: float = 0.5,
        wave_ratio: float = 0.0,
        fast_ema: float | None = None,
        slow_ema: float | None = None,
        fast_period: int = 8,
        slow_period: int = 21,
    ) -> InferenceResult:
        """Run inference on the current market state.

        Parameters
        ----------
        candles : pd.DataFrame
            Current candle DataFrame from ``build_candles()``.
        imbalance : float
            Current order-book bid/ask volume ratio from the live feed.
        vol_pct : float
            Volatility percentile [0, 1] from ``compute_vol_pct()``.
        wave_ratio : float
            ``WaveState.wave_ratio`` from the current loop iteration.
        fast_ema, slow_ema : float or None
            Pre-computed scalar EMA values.  If None, re-computed from candles.
        fast_period, slow_period : int
            EMA periods matching ``best_params["fast"]`` / ``["slow"]``.

        Returns
        -------
        InferenceResult
            When ``enabled=False`` the caller should skip CNN gating and
            use the existing rule-based signal as-is.
        """
        if self._model is None:
            return InferenceResult(enabled=False)

        t0 = time.perf_counter()

        # Extract features
        features = extract_features(
            candles=candles,
            imbalance=imbalance,
            vol_pct=vol_pct,
            wave_ratio=wave_ratio,
            window=self._model.window,
        )

        if features is None:
            # Not enough data yet — return disabled so caller falls through
            return InferenceResult(enabled=False)

        # Build batch tensor: (1, N_FEATURES, window)
        x = torch.from_numpy(features).unsqueeze(0)  # (1, 17, window)

        with torch.no_grad():
            logits = self._model(x)  # (1, 3) raw logits
            scaled = logits / self._temperature  # apply temperature
            probs_tensor = torch.softmax(scaled, dim=-1)  # (1, 3)

        probs_np = probs_tensor[0].cpu().numpy()  # (3,) float32

        # Map to class names
        probs_dict = {
            LABEL_NAMES[LABEL_FLAT]: float(probs_np[LABEL_FLAT]),
            LABEL_NAMES[LABEL_LONG]: float(probs_np[LABEL_LONG]),
            LABEL_NAMES[LABEL_SHORT]: float(probs_np[LABEL_SHORT]),
            LABEL_NAMES[LABEL_LOSS]: float(probs_np[LABEL_LOSS]),
        }

        # Predicted class = argmax
        pred_idx = int(np.argmax(probs_np))

        # Treat loss class as flat — the model learned to avoid this pattern,
        # so we honour that by producing no trade signal.
        if pred_idx == LABEL_LOSS:
            pred_idx = LABEL_FLAT

        signal = LABEL_NAMES[pred_idx]
        confidence = float(probs_np[pred_idx])

        # ── Directional gating: override blind-direction predictions ──────
        # If the model was flagged as blind in one direction during training,
        # force that direction's predictions to "flat" so the bot falls back
        # to rule-based signals instead of trusting a near-random prediction.
        if self._directional_gate == "long_only" and signal == "short":
            logger.debug(
                "[%s] Directional gate: overriding short → flat (model is short-blind)",
                self._asset_key.upper(),
            )
            signal = "flat"
            confidence = float(probs_np[LABEL_FLAT])
        elif self._directional_gate == "short_only" and signal == "long":
            logger.debug(
                "[%s] Directional gate: overriding long → flat (model is long-blind)",
                self._asset_key.upper(),
            )
            signal = "flat"
            confidence = float(probs_np[LABEL_FLAT])
        elif self._directional_gate == "flat_only" and signal != "flat":
            logger.debug(
                "[%s] Directional gate: overriding %s → flat (model is direction-blind)",
                self._asset_key.upper(),
                signal,
            )
            signal = "flat"
            confidence = float(probs_np[LABEL_FLAT])

        # Size multiplier: full confidence when above threshold, else 0
        size_multiplier = confidence if confidence >= self._min_confidence else 0.0

        latency_ms = (time.perf_counter() - t0) * 1000.0

        result = InferenceResult(
            enabled=True,
            signal=signal,
            confidence=confidence,
            probs=probs_dict,
            size_multiplier=size_multiplier,
            latency_ms=latency_ms,
        )

        logger.debug(
            "[%s] CNN predict → %s (conf=%.3f mult=%.3f lat=%.2fms)",
            self._asset_key.upper(),
            signal,
            confidence,
            size_multiplier,
            latency_ms,
        )

        return result

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._model is not None

    @property
    def meta(self) -> dict[str, Any]:
        return dict(self._meta)

    @property
    def window(self) -> int:
        return self._model.window if self._model is not None else DEFAULT_WINDOW

    def __repr__(self) -> str:
        status = f"loaded (window={self.window})" if self.enabled else "disabled"
        return f"CNNInference(asset={self._asset_key!r} status={status})"


# ── MasterInference — portfolio risk wrapper ──────────────────────────────────


class MasterInference:
    """Portfolio-level CNN inference wrapper.

    Loads a MasterCNN from disk (if available) and computes a portfolio
    risk score from all tracked assets' current feature windows.

    Designed to be used in the supervisor loop in main.py, alongside
    the existing unrealised-PnL circuit breaker.

    Parameters
    ----------
    model : MasterCNN or None
    n_assets : int
        Number of asset slots the model was trained with.
    risk_threshold : float
        Score above which ``PortfolioRiskResult.should_halt`` is True.
    meta : dict
    """

    def __init__(
        self,
        model: MasterCNN | None,
        n_assets: int = 5,
        risk_threshold: float = 0.65,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self._model = model
        self._n_assets = n_assets
        self._risk_threshold = risk_threshold
        self._meta = meta or {}

        if model is not None:
            model.eval()
            logger.info(
                "MasterCNN loaded — n_assets=%d  params=%d  accuracy=%.1f%%  trained=%s",
                n_assets,
                model.param_count(),
                self._meta.get("val_accuracy", 0.0) * 100,
                self._meta.get("trained_at", "unknown"),
            )
        else:
            logger.info("No MasterCNN found — portfolio risk scoring disabled")

    @classmethod
    def load(
        cls,
        models_dir: str | Path = "models",
        n_assets: int = 5,
        risk_threshold: float = 0.65,
    ) -> MasterInference:
        """Load a MasterCNN from disk.

        Looks for ``{models_dir}/cnn_master.pt``.
        Returns a disabled MasterInference if the file is absent.

        Note: ``n_assets`` from the saved checkpoint is always used in preference
        to the caller-supplied value so that the forward-pass tensor shape is
        guaranteed to match the model weights.  If the live bot runs with fewer
        active workers than the model was trained on, the missing asset slots are
        zero-padded inside ``portfolio_risk()`` — this is safe and by design.
        """
        models_dir = Path(models_dir)
        model_path = models_dir / _MASTER_FILENAME

        if not model_path.exists():
            logger.debug("MasterCNN not found at %s", model_path)
            return cls(model=None, n_assets=n_assets, risk_threshold=risk_threshold)

        try:
            model = MasterCNN.load(model_path, map_location="cpu")
            # Use the n_assets baked into the checkpoint so the input tensor shape
            # always matches the model's first Linear layer, regardless of how many
            # workers are currently active.  Active workers fill their slots with
            # real features; inactive slots are zero-padded in portfolio_risk().
            checkpoint_n_assets = model.n_assets
            if checkpoint_n_assets != n_assets:
                logger.info(
                    "MasterCNN checkpoint has n_assets=%d; caller supplied %d — "
                    "using checkpoint value (inactive slots will be zero-padded)",
                    checkpoint_n_assets,
                    n_assets,
                )
            meta_path = model_path.with_suffix(".json")
            meta: dict[str, Any] = {}
            if meta_path.exists():
                import json

                meta = json.loads(meta_path.read_text())
            return cls(
                model=model,
                n_assets=checkpoint_n_assets,
                risk_threshold=risk_threshold,
                meta=meta,
            )
        except Exception as exc:
            logger.warning("Failed to load MasterCNN from %s: %s", model_path, exc)
            return cls(model=None, n_assets=n_assets, risk_threshold=risk_threshold)

    def portfolio_risk(
        self,
        asset_features: list[np.ndarray | None],
    ) -> PortfolioRiskResult:
        """Compute the portfolio risk score from all assets' feature arrays.

        Parameters
        ----------
        asset_features : list of np.ndarray or None
            One entry per asset, in the same order the model was trained on.
            Each entry is a (N_FEATURES, window) float32 array from
            ``extract_features()``, or None if the asset has no live data
            (its slot will be filled with zeros).

        Returns
        -------
        PortfolioRiskResult
            When ``enabled=False`` the caller should use the existing
            margin-cap circuit breaker instead.
        """
        if self._model is None:
            return PortfolioRiskResult(enabled=False)

        t0 = time.perf_counter()

        window = self._model.window
        tensors: list[torch.Tensor] = []

        for i in range(self._n_assets):
            if i < len(asset_features) and asset_features[i] is not None:
                arr = asset_features[i]
                # Ensure the window dimension matches what the model expects
                if arr.shape != (N_FEATURES, window):
                    arr = np.zeros((N_FEATURES, window), dtype=np.float32)
            else:
                arr = np.zeros((N_FEATURES, window), dtype=np.float32)

            tensors.append(torch.from_numpy(arr.astype(np.float32)))

        # Stack to (n_assets, N_FEATURES, window) then add batch dim
        x = torch.stack(tensors, dim=0).unsqueeze(0)  # (1, n_assets, N_FEATURES, window)

        with torch.no_grad():
            logits = self._model(x)  # (1, 1) — raw logits
            risk_tensor = torch.sigmoid(logits)

        risk_score = float(risk_tensor.squeeze().item())
        should_halt = risk_score >= self._risk_threshold
        latency_ms = (time.perf_counter() - t0) * 1000.0

        result = PortfolioRiskResult(
            enabled=True,
            risk_score=risk_score,
            should_halt=should_halt,
            latency_ms=latency_ms,
        )

        logger.debug(
            "MasterCNN risk=%.3f halt=%s lat=%.2fms",
            risk_score,
            should_halt,
            latency_ms,
        )

        return result

    @property
    def enabled(self) -> bool:
        return self._model is not None

    def __repr__(self) -> str:
        status = "loaded" if self.enabled else "disabled"
        return f"MasterInference(n_assets={self._n_assets} status={status})"
