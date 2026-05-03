"""
ml/model.py — CNN architectures for the futures trading bot.

Two models
----------
PerAssetCNN
    1-D convolutional network trained independently for each asset.
    Input  : (batch, N_FEATURES=20, window=60)  — channels-first
    Output : (batch, 3) logits → [flat, long, short]

    At inference the caller takes softmax → confidence of the predicted
    class.  Only acts on a signal when confidence > cfg.ml.min_confidence.

MasterCNN
    Portfolio-level risk aggregator.  Takes one feature window per tracked
    asset, encodes each through a shared PerAssetCNN backbone (weights
    NOT shared with the per-asset classifiers — separate model), then
    combines the embeddings to produce a single portfolio risk score.

    Input  : (batch, n_assets, N_FEATURES, window)
    Output : (batch, 1)  sigmoid → risk score [0, 1]
             0.0 = all clear, take new entries
             1.0 = portfolio saturated, skip new entries

Design notes
------------
- Residual skip connections in each conv block help gradient flow on
  small datasets (typical crypto training sets are 50k–500k samples).
- BatchNorm before activation keeps activations well-scaled even when
  input features have very different magnitudes.
- Dropout (p=0.4) on the MasterCNN FC layers; p=0.3 (configurable) on encoder.
- Global average pooling instead of flatten removes sensitivity to the
  exact window length so the same architecture works at window=30 or 90.
- ~130k parameters for PerAssetCNN → fast CPU inference (<0.5 ms).
- ~150k parameters for MasterCNN with 10 assets (reduced capacity for better generalization).

Label convention (PerAssetCNN)
------------------------------
    0  flat   — no signal / skip this bar
    1  long   — go long (buy signal confirmed)
    2  short  — go short (sell signal confirmed)
    3  loss   — go long/short but signal is weak / ambiguous
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

# ── Constants ────────────────────────────────────────────────────────────────

N_FEATURES: int = 20  # must match ml/features.py
N_CLASSES: int = 4  # flat / long / short / loss
DEFAULT_WINDOW: int = 60

# Class index constants — import these so callers never hard-code integers
LABEL_FLAT: int = 0
LABEL_LONG: int = 1
LABEL_SHORT: int = 2
LABEL_LOSS: int = 3

LABEL_NAMES: dict[int, str] = {
    LABEL_FLAT: "flat",
    LABEL_LONG: "long",
    LABEL_SHORT: "short",
    LABEL_LOSS: "loss",
}


# ── Building blocks ──────────────────────────────────────────────────────────


class _ConvBlock(nn.Module):
    """Conv1d → BatchNorm → ReLU with an optional residual skip.

    When ``use_residual=True`` and in_channels != out_channels a 1×1 conv
    is used to project the skip connection to the right channel count.
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        dilation: int = 1,
        use_residual: bool = True,
    ) -> None:
        super().__init__()
        padding = dilation * (kernel_size - 1) // 2  # 'same' padding

        self.conv = nn.Conv1d(
            in_channels,
            out_channels,
            kernel_size=kernel_size,
            padding=padding,
            dilation=dilation,
            bias=False,
        )
        self.bn = nn.BatchNorm1d(out_channels)

        self.use_residual = use_residual
        self.skip: nn.Module | None = None
        if use_residual and in_channels != out_channels:
            self.skip = nn.Conv1d(in_channels, out_channels, kernel_size=1, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.bn(self.conv(x))  # ← no ReLU here anymore
        if self.use_residual:
            identity = x if self.skip is None else self.skip(x)
            out = out + identity
        return F.relu(out, inplace=True)  # single ReLU after residual add


class _SEBlock(nn.Module):
    """Squeeze-and-Excitation channel attention.

    Learns per-channel importance weights, helping the model focus on
    features most relevant for the current prediction (e.g., volume spike
    features for breakout detection vs range features for flat prediction).
    """

    def __init__(self, channels: int, reduction: int = 4) -> None:
        super().__init__()
        mid = max(channels // reduction, 8)
        self.squeeze = nn.AdaptiveAvgPool1d(1)
        self.excite = nn.Sequential(
            nn.Linear(channels, mid, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(mid, channels, bias=False),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, channels, time)
        b, c, _ = x.shape
        w = self.squeeze(x).view(b, c)  # (batch, channels)
        w = self.excite(w).view(b, c, 1)  # (batch, channels, 1)
        return x * w


class _AssetEncoder(nn.Module):
    """Shared convolutional backbone — produces a fixed-size embedding vector.

    Three conv blocks with progressively larger receptive fields:
      Block 1 — kernel 3, dilation 1 → local patterns  (1–3 bars)
      Block 2 — kernel 3, dilation 2 → medium context  (1–5 bars)
      Block 3 — kernel 3, dilation 4 → broad context   (1–9 bars)
      Block 4 — kernel 3, dilation 8 → very broad context (1–17 bars)

    Followed by global average pooling → embedding_dim vector.
    """

    def __init__(
        self,
        n_features: int = N_FEATURES,
        embedding_dim: int = 64,
        encoder_dropout: float = 0.15,
    ) -> None:
        super().__init__()

        self.block1 = _ConvBlock(n_features, 64, kernel_size=3, dilation=1)
        self.se1 = _SEBlock(64)
        self.drop1 = nn.Dropout1d(encoder_dropout)
        self.block2 = _ConvBlock(64, 128, kernel_size=3, dilation=2)
        self.se2 = _SEBlock(128)
        self.drop2 = nn.Dropout1d(encoder_dropout)
        self.block3 = _ConvBlock(128, embedding_dim, kernel_size=3, dilation=4)
        self.se3 = _SEBlock(embedding_dim)
        self.drop3 = nn.Dropout1d(encoder_dropout)
        self.block4 = _ConvBlock(embedding_dim, embedding_dim, kernel_size=3, dilation=8)
        self.se4 = _SEBlock(embedding_dim)
        self.drop4 = nn.Dropout1d(encoder_dropout)
        # Global avg + max pooling concatenated — doubles embedding expressiveness
        # without adding parameters. Final embedding_dim stays the same via a 1×1 proj.
        self.pool_avg = nn.AdaptiveAvgPool1d(1)
        self.pool_max = nn.AdaptiveMaxPool1d(1)
        self.pool_proj = nn.Sequential(
            nn.Linear(embedding_dim * 2, embedding_dim, bias=False),
            nn.ReLU(inplace=True),
        )
        self.embedding_dim = embedding_dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.drop1(self.se1(self.block1(x)))
        x = self.drop2(self.se2(self.block2(x)))
        x = self.drop3(self.se3(self.block3(x)))
        x = self.drop4(self.se4(self.block4(x)))
        avg = self.pool_avg(x).squeeze(-1)  # (batch, embedding_dim)
        mx = self.pool_max(x).squeeze(-1)  # (batch, embedding_dim)
        x = self.pool_proj(torch.cat([avg, mx], dim=-1))  # → (batch, embedding_dim)
        return x


# ── PerAssetCNN ──────────────────────────────────────────────────────────────


class PerAssetCNN(nn.Module):
    """Per-asset 1-D CNN for entry/exit signal classification.

    Trained independently for each asset so each model can specialise in
    that coin's typical volatility structure, liquidity patterns, and
    breakout behaviour.

    Parameters
    ----------
    n_features:
        Number of input feature channels (default 15, matches features.py).
    window:
        Number of candle bars in the input sequence (default 60).
    n_classes:
        Output classes — 4 by default (flat / long / short / loss).
    embedding_dim:
        Width of the shared encoder's output embedding (default 64).
    dropout:
        Dropout probability applied before the classification head.
    """

    def __init__(
        self,
        n_features: int = N_FEATURES,
        window: int = DEFAULT_WINDOW,
        n_classes: int = N_CLASSES,
        embedding_dim: int = 64,
        dropout: float = 0.4,
    ) -> None:
        super().__init__()

        self.n_features = n_features
        self.window = window
        self.n_classes = n_classes
        self.embedding_dim = embedding_dim

        self.encoder = _AssetEncoder(n_features, embedding_dim)

        self.head = nn.Sequential(
            nn.Dropout(p=dropout),
            nn.Linear(embedding_dim, 32),
            nn.ReLU(inplace=True),
            nn.Linear(32, n_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Parameters
        ----------
        x : (batch, n_features, window)

        Returns
        -------
        logits : (batch, n_classes) — use softmax for probabilities
        """
        emb = self.encoder(x)  # (batch, embedding_dim)
        return self.head(emb)  # (batch, n_classes)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Return softmax class probabilities without gradient tracking."""
        with torch.no_grad():
            logits = self(x)
            return F.softmax(logits, dim=-1)

    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    # ── Serialisation ────────────────────────────────────────────────────────

    def save(self, path: str | Path, meta: dict[str, Any] | None = None) -> None:
        """Save model weights + constructor args to a single .pt file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {
            "model_state": self.state_dict(),
            "constructor": {
                "n_features": self.n_features,
                "window": self.window,
                "n_classes": self.n_classes,
                "embedding_dim": self.embedding_dim,
            },
            "meta": meta or {},
        }
        torch.save(payload, path)

    @classmethod
    def load(cls, path: str | Path, map_location: str = "cpu") -> PerAssetCNN:
        """Load a saved PerAssetCNN from a .pt file."""
        payload = torch.load(path, map_location=map_location, weights_only=False)
        model = cls(**payload["constructor"])
        model.load_state_dict(payload["model_state"])
        model.eval()
        return model

    def save_meta(self, path: str | Path, meta: dict[str, Any]) -> None:
        """Write a human-readable JSON sidecar alongside the .pt file."""
        p = Path(path)
        sidecar = p.with_suffix(".json")
        sidecar.write_text(json.dumps(meta, indent=2, default=str))

    @staticmethod
    def load_meta(path: str | Path) -> dict[str, Any]:
        p = Path(path)
        sidecar = p.with_suffix(".json")
        if sidecar.exists():
            return json.loads(sidecar.read_text())
        return {}


# ── Cross-asset attention ────────────────────────────────────────────────────


class _CrossAssetAttention(nn.Module):
    """Multi-head self-attention over asset embeddings.

    Lets the model learn inter-asset correlations — e.g., BTC crashing
    while ETH is in a breakout signals high portfolio risk.
    """

    def __init__(self, embedding_dim: int = 64, n_heads: int = 4, dropout: float = 0.1) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(embedding_dim)
        self.attn = nn.MultiheadAttention(
            embed_dim=embedding_dim,
            num_heads=n_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.ffn = nn.Sequential(
            nn.Linear(embedding_dim, embedding_dim * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(embedding_dim * 2, embedding_dim),
            nn.Dropout(dropout),
        )
        self.norm2 = nn.LayerNorm(embedding_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (batch, n_assets, embedding_dim)
        Returns: (batch, n_assets, embedding_dim) — attended embeddings
        """
        # Self-attention with residual
        normed = self.norm(x)
        attn_out, _ = self.attn(normed, normed, normed)
        x = x + attn_out
        # FFN with residual
        x = x + self.ffn(self.norm2(x))
        return x


# ── MasterCNN ────────────────────────────────────────────────────────────────


class MasterCNN(nn.Module):
    """Portfolio-level risk aggregator.

    Watches all currently-tracked assets simultaneously and outputs a
    single portfolio risk score in [0, 1].  A high score means the
    portfolio is already heavily loaded (multiple open positions, high
    unrealised exposure) and new entries should be skipped.

    This model trains on *portfolio-level* outcomes rather than per-trade
    outcomes, so it learns which combinations of simultaneous open
    positions historically lead to drawdown.

    Architecture
    ------------
    1. A private shared encoder (PerAssetCNN backbone, separate weights
       from the per-asset classifiers) encodes each asset's feature window
       into an ``embedding_dim``-dimensional vector.
    2. The asset embeddings are concatenated → (n_assets × embedding_dim).
    3. Two FC layers reduce to a scalar risk score via sigmoid.

    The encoder has shared weights across assets — it learns a
    universal "market state" representation.  The FC head then learns
    how dangerous each combination of market states is at the
    portfolio level.

    Parameters
    ----------
    n_assets:
        Number of tracked assets (default 5: BTC ETH SOL DOGE PEPE).
        At inference time, pass zeros for slots of inactive assets.
    n_features:
        Feature channels per asset window (default 15).
    window:
        Candle bars per asset window (default 60).
    embedding_dim:
        Width of each asset's embedding from the shared encoder (default 48).
    dropout:
        Dropout on the FC layers (default 0.4).
    encoder_dropout:
        Dropout in the shared encoder conv blocks (default 0.25).
    """

    def __init__(
        self,
        n_assets: int = 5,
        n_features: int = N_FEATURES,
        window: int = DEFAULT_WINDOW,
        embedding_dim: int = 64,
        dropout: float = 0.4,
        encoder_dropout: float = 0.25,
    ) -> None:
        super().__init__()

        self.n_assets = n_assets
        self.n_features = n_features
        self.window = window
        self.embedding_dim = embedding_dim
        self.encoder_dropout = encoder_dropout

        # Shared encoder — encodes one asset's window into embedding_dim floats.
        # Separate from the PerAssetCNN instances used for signal classification.
        self.encoder = _AssetEncoder(n_features, embedding_dim, encoder_dropout=encoder_dropout)

        # Cross-asset attention — lets asset embeddings attend to each other
        self.cross_attn = _CrossAssetAttention(embedding_dim)

        combined_dim = n_assets * embedding_dim

        # Reduced-capacity risk head — sized proportionally to embedding_dim.
        # With 10 assets × 48 embedding = 480 input dims, 96→24→1 keeps the
        # head small enough to avoid overfitting on typical dataset sizes.
        self.risk_head = nn.Sequential(
            nn.Dropout(p=dropout),
            nn.Linear(combined_dim, 96),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout),
            nn.Linear(96, 24),
            nn.ReLU(inplace=True),
            nn.Linear(24, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Parameters
        ----------
        x : (batch, n_assets, n_features, window)
            Stack each asset's feature tensor along dim=1.
            For inactive assets (no position, no live data) fill with zeros.

        Returns
        -------
        logits : (batch, 1)  — raw logits (unbounded).
            ``predict_risk()`` applies sigmoid for inference.
        """
        batch_size = x.shape[0]

        # Encode each asset slice independently with the shared encoder
        embeddings: list[torch.Tensor] = []
        for i in range(self.n_assets):
            asset_slice = x[:, i]  # (batch, n_features, window)
            emb = self.encoder(asset_slice)  # (batch, embedding_dim)
            embeddings.append(emb)

        # Stack → (batch, n_assets, embedding_dim) for attention
        stacked = torch.stack(embeddings, dim=1)

        # Cross-asset attention — lets assets attend to each other
        attended = self.cross_attn(stacked)

        # Flatten → (batch, n_assets * embedding_dim)
        combined = attended.reshape(batch_size, -1)

        logits = self.risk_head(combined)  # (batch, 1) — raw logits
        return logits

    def predict_risk(self, x: torch.Tensor) -> float:
        """Return the scalar risk score for a single portfolio snapshot."""
        with torch.no_grad():
            if x.dim() == 3:
                # (n_assets, n_features, window) → add batch dim
                x = x.unsqueeze(0)
            logits = self(x)
            return float(torch.sigmoid(logits).squeeze())

    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    # ── Serialisation ────────────────────────────────────────────────────────

    def save(self, path: str | Path, meta: dict[str, Any] | None = None) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {
            "model_state": self.state_dict(),
            "constructor": {
                "n_assets": self.n_assets,
                "n_features": self.n_features,
                "window": self.window,
                "embedding_dim": self.embedding_dim,
                "encoder_dropout": self.encoder_dropout,
            },
            "meta": meta or {},
        }
        torch.save(payload, path)

    @classmethod
    def load(cls, path: str | Path, map_location: str = "cpu") -> MasterCNN:
        payload = torch.load(path, map_location=map_location, weights_only=False)
        model = cls(**payload["constructor"])
        model.load_state_dict(payload["model_state"])
        model.eval()
        return model

    def save_meta(self, path: str | Path, meta: dict[str, Any]) -> None:
        p = Path(path)
        sidecar = p.with_suffix(".json")
        sidecar.write_text(json.dumps(meta, indent=2, default=str))


# ── Utility ──────────────────────────────────────────────────────────────────


def build_per_asset_cnn(
    n_features: int = N_FEATURES,
    window: int = DEFAULT_WINDOW,
    embedding_dim: int = 64,
    dropout: float = 0.3,
) -> PerAssetCNN:
    """Factory helper — returns an untrained PerAssetCNN ready for training."""
    return PerAssetCNN(
        n_features=n_features,
        window=window,
        n_classes=N_CLASSES,
        embedding_dim=embedding_dim,
        dropout=dropout,
    )


def build_master_cnn(
    n_assets: int = 5,
    n_features: int = N_FEATURES,
    window: int = DEFAULT_WINDOW,
    embedding_dim: int = 64,
    dropout: float = 0.4,
    encoder_dropout: float = 0.25,
) -> MasterCNN:
    """Factory helper — returns an untrained MasterCNN ready for training."""
    return MasterCNN(
        n_assets=n_assets,
        n_features=n_features,
        window=window,
        embedding_dim=embedding_dim,
        dropout=dropout,
        encoder_dropout=encoder_dropout,
    )


if __name__ == "__main__":
    # Quick smoke test — run with: python -m ml.model
    print("=== PerAssetCNN smoke test ===")
    model = build_per_asset_cnn()
    model.eval()
    dummy = torch.randn(4, N_FEATURES, DEFAULT_WINDOW)
    logits = model(dummy)
    probs = F.softmax(logits, dim=-1)
    print(f"  Input  : {tuple(dummy.shape)}")
    print(f"  Logits : {tuple(logits.shape)}")
    print(f"  Probs  : {probs[0].tolist()}")
    print(f"  Params : {model.param_count():,}")

    print("\n=== MasterCNN smoke test ===")
    master = build_master_cnn(n_assets=5)
    master.eval()
    portfolio = torch.randn(2, 5, N_FEATURES, DEFAULT_WINDOW)
    risk = master(portfolio)
    print(f"  Input  : {tuple(portfolio.shape)}")
    print(f"  Risk   : {risk.squeeze().tolist()}")
    print(f"  Params : {master.param_count():,}")
