"""
Breakout CNN — Model architecture and embedding constants.

Contains the ``HybridBreakoutCNN`` model class (real when torch is available,
stub otherwise), hierarchical asset embedding lookup tables, and device
detection helpers.
"""

from __future__ import annotations

from typing import Any

from analysis.ml.breakout_constants import (
    _TORCH_AVAILABLE,
    NUM_TABULAR,
    logger,
)

# Re-import torch & friends conditionally — the guard already ran in
# breakout_constants so _TORCH_AVAILABLE is authoritative.
if _TORCH_AVAILABLE:
    import torch
    import torch.nn as nn
    import torchvision.models as models


# ---------------------------------------------------------------------------
# Model constants
# ---------------------------------------------------------------------------

# Number of distinct breakout types — used to size the embedding table.
# Mirrors len(BreakoutType) in lib.core.breakout_types.
NUM_BREAKOUT_TYPES = 13

# Learned embedding dimension for breakout type.
# Replaces the single scalar ``breakout_type_ord`` feature with a richer
# NUM_BREAKOUT_TYPES × BREAKOUT_EMBED_DIM lookup table that the model
# trains end-to-end.  The tabular vector's ``breakout_type_ord`` slot [14]
# is still consumed (so the input dimension stays at NUM_TABULAR = 18) but
# when ``use_type_embedding=True`` that slot is ignored and the embedding
# replaces it in the combined representation.
BREAKOUT_EMBED_DIM = 8

# ---------------------------------------------------------------------------
# v8-A: Hierarchical Asset Embedding constants
# ---------------------------------------------------------------------------
# 5 asset classes: equity_index=0, fx=1, metals_energy=2, bonds_ags=3, crypto=4
NUM_ASSET_CLASSES = 5
ASSET_CLASS_EMBED_DIM = 4

# Per-symbol asset ID — one per tradeable symbol.  The embedding learns
# each asset's "personality" from breakout outcomes end-to-end.
ASSET_ID_LOOKUP: dict[str, int] = {
    # Equity index (0–3)
    "MES": 0,
    "MNQ": 1,
    "M2K": 2,
    "MYM": 3,
    # FX (4–9)
    "6E": 4,
    "6B": 5,
    "6J": 6,
    "6A": 7,
    "6C": 8,
    "6S": 9,
    "M6E": 4,
    "M6B": 5,  # micros → same embedding as full
    # Metals / Energy (10–14)
    "MGC": 10,
    "SIL": 11,
    "MHG": 12,
    "MCL": 13,
    "MNG": 14,
    # Treasuries / Ags (15–19)
    "ZN": 15,
    "ZB": 16,
    "ZC": 17,
    "ZS": 18,
    "ZW": 19,
    # Crypto (20–24)
    "MBT": 20,
    "MET": 21,
    "BTC": 20,
    "ETH": 21,  # short aliases → same embedding
    "SOL": 22,
    "LINK": 22,
    "AVAX": 22,  # alt-coins share an embedding
    "DOT": 23,
    "ADA": 23,
    "POL": 23,
    "XRP": 23,
    # Kraken tickers → same as their short aliases
    "KRAKEN:XBTUSD": 20,
    "KRAKEN:ETHUSD": 21,
    "KRAKEN:SOLUSD": 22,
    "KRAKEN:LINKUSD": 22,
    "KRAKEN:AVAXUSD": 22,
    "KRAKEN:DOTUSD": 23,
    "KRAKEN:ADAUSD": 23,
    "KRAKEN:POLUSD": 23,
    "KRAKEN:XRPUSD": 23,
}
NUM_ASSETS = 25  # unique asset IDs (0–24)
ASSET_ID_EMBED_DIM = 8

# Integer asset class index (not normalised) for embedding lookup.
# Maps the same tickers as ASSET_CLASS_ORDINALS but returns 0–4 int.
ASSET_CLASS_IDX_LOOKUP: dict[str, int] = {
    # Equity index → 0
    "MES": 0,
    "MNQ": 0,
    "M2K": 0,
    "MYM": 0,
    # FX → 1
    "6E": 1,
    "6B": 1,
    "6J": 1,
    "6A": 1,
    "6C": 1,
    "6S": 1,
    "M6E": 1,
    "M6B": 1,
    # Metals / Energy → 2
    "MGC": 2,
    "SIL": 2,
    "MHG": 2,
    "MCL": 2,
    "MNG": 2,
    # Treasuries / Ags → 3
    "ZN": 3,
    "ZB": 3,
    "ZC": 3,
    "ZS": 3,
    "ZW": 3,
    # Crypto → 4
    "MBT": 4,
    "MET": 4,
    "BTC": 4,
    "ETH": 4,
    "SOL": 4,
    "LINK": 4,
    "AVAX": 4,
    "DOT": 4,
    "ADA": 4,
    "POL": 4,
    "XRP": 4,
    "KRAKEN:XBTUSD": 4,
    "KRAKEN:ETHUSD": 4,
    "KRAKEN:SOLUSD": 4,
    "KRAKEN:LINKUSD": 4,
    "KRAKEN:AVAXUSD": 4,
    "KRAKEN:DOTUSD": 4,
    "KRAKEN:ADAUSD": 4,
    "KRAKEN:POLUSD": 4,
    "KRAKEN:XRPUSD": 4,
}


# ---------------------------------------------------------------------------
# Embedding ID helpers
# ---------------------------------------------------------------------------


def get_asset_class_idx(ticker: str) -> int:
    """Return the integer asset class index (0–4) for embedding lookup."""
    return ASSET_CLASS_IDX_LOOKUP.get(str(ticker).upper().strip(), 0)


def get_asset_idx(ticker: str) -> int:
    """Return the integer asset ID (0–24) for embedding lookup."""
    return ASSET_ID_LOOKUP.get(str(ticker).upper().strip(), 0)


# ---------------------------------------------------------------------------
# Device helper
# ---------------------------------------------------------------------------


def get_device() -> str:
    """Return the best available device string ('cuda', 'mps', or 'cpu')."""
    if not _TORCH_AVAILABLE:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

if _TORCH_AVAILABLE:

    class HybridBreakoutCNN(nn.Module):  # type: ignore[no-redef]
        """Hybrid image + tabular model for breakout classification (v9 contract).

        Architecture (v9):
          Image branch:     EfficientNetV2-S (pre-trained ImageNet) → 1280-dim
          Asset embeddings: nn.Embedding(5, 4) + nn.Embedding(25, 8) → 12-dim
          Tabular branch:   Linear(N→256) → BN → GELU → Dropout(0.3) →
                            Linear(256→128) → BN → GELU → Linear(128→64)
          Classifier:       Linear(1280+64+12→512) → BN → GELU → Dropout →
                            Linear(512→128) → GELU → Dropout → Linear(128→3)

        NUM_TABULAR = 37 (v8 contract: v7.1 28 features + 3 cross-asset + 6 fingerprint).
        Embedding IDs (asset_class_idx, asset_idx) are passed separately from
        the float tabular vector.

        The model outputs raw logits for 3 classes (RETRAIN-I1 expansion):
          - Class 0: bad/choppy/no_setup (SL hit, fast reversal, no valid setup)
          - Class 1: marginal (timed out in profit, 0 < R < 1.0)
          - Class 2: good/excellent (hit TP1+, R ≥ 1.0)

        Apply ``torch.softmax(output, dim=1)[:, 2]`` to get P(good/excellent breakout).
        For a binary signal threshold, use class-2 probability vs session threshold.
        """

        def __init__(
            self,
            num_tabular: int = NUM_TABULAR,
            dropout: float = 0.5,
            pretrained: bool = True,
            use_type_embedding: bool = False,  # kept for backward compat (ignored in v8)
            use_asset_embeddings: bool = True,
        ):
            super().__init__()
            self.num_tabular = num_tabular
            self.use_asset_embeddings = use_asset_embeddings

            # --- Image backbone: EfficientNetV2-S ---
            weights = models.EfficientNet_V2_S_Weights.DEFAULT if pretrained else None
            backbone = models.efficientnet_v2_s(weights=weights)
            backbone.classifier = nn.Identity()  # type: ignore[assignment]
            self.cnn = backbone
            self._cnn_out_dim = 1280

            # --- v8-A: Hierarchical Asset Embeddings ---
            # These replace the flat asset_class_id [13] and asset_volatility_class [15]
            # with learned representations.  The flat features are still in the tabular
            # vector for backward compat, but the embeddings provide richer signal.
            self._embed_dim = 0
            if use_asset_embeddings:
                self.asset_class_embedding = nn.Embedding(NUM_ASSET_CLASSES, ASSET_CLASS_EMBED_DIM)
                self.asset_id_embedding = nn.Embedding(NUM_ASSETS, ASSET_ID_EMBED_DIM)
                self._embed_dim = ASSET_CLASS_EMBED_DIM + ASSET_ID_EMBED_DIM  # 4 + 8 = 12

            # --- v8-D: Wider tabular head with GELU (capacity for 37 features) ---
            self.tabular_head = nn.Sequential(
                nn.Linear(num_tabular, 256),
                nn.BatchNorm1d(256),
                nn.GELU(),
                nn.Dropout(0.4),  # was 0.3
                nn.Linear(256, 128),
                nn.BatchNorm1d(128),
                nn.GELU(),
                nn.Linear(128, 64),
            )

            # --- Classifier (v9: 3-class output) ---
            combined_dim = self._cnn_out_dim + 64 + self._embed_dim
            self.classifier = nn.Sequential(
                nn.Linear(combined_dim, 512),
                nn.BatchNorm1d(512),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(512, 128),
                nn.GELU(),
                nn.Dropout(dropout * 0.75),
                nn.Linear(128, 3),  # 0=bad/choppy/no_setup, 1=marginal, 2=good/excellent
            )

        def forward(
            self,
            image: torch.Tensor,
            tabular: torch.Tensor,
            type_ids: torch.Tensor | None = None,  # kept for API compat
            asset_class_ids: torch.Tensor | None = None,
            asset_ids: torch.Tensor | None = None,
        ) -> torch.Tensor:
            """Forward pass.

            Args:
                image:           (B, 3, 224, 224) normalised image tensor.
                tabular:         (B, NUM_TABULAR) float tensor — v8 37-feature vector.
                type_ids:        ignored (kept for backward API compatibility).
                asset_class_ids: (B,) int tensor — asset class indices (0–4).
                asset_ids:       (B,) int tensor — per-symbol asset indices (0–24).

            Returns:
                (B, 3) logits tensor — classes: 0=bad/choppy/no_setup, 1=marginal, 2=good/excellent.
            """
            img_features = self.cnn(image)  # (B, 1280)
            tab_features = self.tabular_head(tabular)  # (B, 64)

            # Asset embeddings — concatenate if available
            if self.use_asset_embeddings and asset_class_ids is not None and asset_ids is not None:
                class_emb = self.asset_class_embedding(asset_class_ids)  # (B, 4)
                asset_emb = self.asset_id_embedding(asset_ids)  # (B, 8)
                combined = torch.cat([img_features, tab_features, class_emb, asset_emb], dim=1)
            else:
                combined = torch.cat([img_features, tab_features], dim=1)
                # Pad to expected classifier input dim if embeddings are in the architecture
                if self._embed_dim > 0:
                    pad = torch.zeros(combined.size(0), self._embed_dim, device=combined.device)
                    combined = torch.cat([combined, pad], dim=1)

            return self.classifier(combined)  # (B, 2)

        def freeze_backbone(self) -> None:
            """Freeze the CNN backbone (first N epochs of fine-tuning)."""
            for param in self.cnn.parameters():
                param.requires_grad = False
            logger.info("CNN backbone frozen")

        def unfreeze_backbone(self) -> None:
            """Unfreeze the CNN backbone for full fine-tuning."""
            for param in self.cnn.parameters():
                param.requires_grad = True
            logger.info("CNN backbone unfrozen")

else:

    class HybridBreakoutCNN:  # type: ignore[no-redef,misc]
        """Stub for environments without PyTorch."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("PyTorch is not installed — cannot create HybridBreakoutCNN")

        def freeze_backbone(self) -> None:
            raise RuntimeError("PyTorch is not installed")

        def unfreeze_backbone(self) -> None:
            raise RuntimeError("PyTorch is not installed")

        @property
        def use_asset_embeddings(self) -> bool:
            return False
