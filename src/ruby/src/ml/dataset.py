"""
ml/dataset.py — PyTorch Dataset for CNN training.

Wraps a labelled klines DataFrame into sliding windows of feature
tensors that can be fed directly into PerAssetCNN or MasterCNN.

Two Dataset classes
-------------------
AssetDataset
    Single-asset sliding-window dataset.  Each sample is a
    (N_FEATURES, window) float32 tensor paired with an int64 label.
    Used for per-asset CNN training.

PortfolioDataset
    Multi-asset dataset for MasterCNN training.  Each sample stacks
    one feature window per asset into a (n_assets, N_FEATURES, window)
    tensor.  The label is binary: 1 = portfolio entered a drawdown
    period in the next K bars, 0 = portfolio remained healthy.

Usage
-----
    from ml.dataset import AssetDataset, build_dataloaders

    ds = AssetDataset(df, labels, window=60)
    train_dl, val_dl = build_dataloaders(ds, batch_size=64, val_split=0.2)

    for x, y in train_dl:
        # x: (batch, 20, 60)
        # y: (batch,)  int64 in {0, 1, 2}
        ...
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from .features import DEFAULT_WINDOW, N_FEATURES, extract_features, precompute_all_features
from .labeler import LABEL_FLAT, LABEL_LONG, LABEL_SHORT, LABEL_LOSS, class_weights

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AssetDataset
# ---------------------------------------------------------------------------


class AssetDataset(Dataset):
    """Sliding-window dataset for a single asset.

    Each item is a tuple ``(x, y)`` where:
        x : float32 tensor of shape (N_FEATURES, window)
        y : int64 scalar label  {0=flat, 1=long, 2=short}

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV klines with lowercase columns: open, high, low, close, volume.
        Should be the *full* historical DataFrame; the Dataset handles all
        the windowing internally.
    labels : np.ndarray of int64
        Per-bar labels produced by ``labeler.generate_labels()``.
        Must have the same length as ``df``.
    window : int
        Number of candle bars in each sample (time dimension).
    fast_period, slow_period : int
        EMA periods — must match the values used during label generation.
    min_warmup : int
        Number of leading bars to skip before yielding samples.
        Defaults to ``window + 34`` (enough for AO slow SMA warmup).
    """

    def __init__(
        self,
        df: pd.DataFrame,
        labels: np.ndarray,
        window: int = DEFAULT_WINDOW,
        fast_period: int = 8,
        slow_period: int = 21,
        min_warmup: int | None = None,
    ) -> None:
        assert len(df) == len(labels), (
            f"df ({len(df)}) and labels ({len(labels)}) must have the same length"
        )

        self.df = df.reset_index(drop=True)
        self.labels = labels.astype(np.int64)
        self.window = window
        self.fast_period = fast_period
        self.slow_period = slow_period

        # First bar index from which a full window is available
        self._warmup = min_warmup if min_warmup is not None else window + 34

        # Pre-compute all valid sample indices (bars where we have a full
        # window behind us AND a non-NaN label)
        self._indices: list[int] = []
        for i in range(self._warmup, len(self.df)):
            self._indices.append(i)

        # ── Precompute all features once over full DataFrame ──────────────
        t0 = __import__("time").time()
        self._features = precompute_all_features(
            candles=self.df,
            window=self.window,
            training=True,
        )
        if self._features is None:
            raise ValueError(
                f"Feature precomputation failed for {len(self.df)} bars — "
                f"not enough data for indicator warmup"
            )
        precompute_elapsed = __import__("time").time() - t0

        logger.info(
            "AssetDataset: %d total bars → %d samples  (window=%d, warmup=%d)  features precomputed in %.1fs",
            len(df),
            len(self._indices),
            window,
            self._warmup,
            precompute_elapsed,
        )

    # ── Dataset interface ─────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._indices)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        bar_idx = self._indices[idx]

        # Slice the precomputed feature array — window ending at bar_idx (inclusive)
        start = bar_idx - self.window + 1
        x = torch.from_numpy(self._features[:, start : bar_idx + 1].copy())
        y = torch.tensor(int(self.labels[bar_idx]), dtype=torch.int64)
        return x, y

    # ── Helpers ───────────────────────────────────────────────────────────────

    def label_array(self) -> np.ndarray:
        """Return labels for all valid sample indices (useful for samplers)."""
        return np.array([self.labels[i] for i in self._indices], dtype=np.int64)

    def class_weights(self) -> list[float]:
        """Inverse-frequency class weights for the valid samples."""
        return class_weights(self.label_array())

    def class_counts(self) -> dict[str, int]:
        arr = self.label_array()
        return {
            "flat": int((arr == LABEL_FLAT).sum()),
            "long": int((arr == LABEL_LONG).sum()),
            "short": int((arr == LABEL_SHORT).sum()),
            "loss": int((arr == LABEL_LOSS).sum()),
        }


# ---------------------------------------------------------------------------
# PortfolioDataset
# ---------------------------------------------------------------------------


class PortfolioDataset(Dataset):
    """Multi-asset dataset for MasterCNN training.

    Each sample stacks one feature window per asset into a tensor of shape
    ``(n_assets, N_FEATURES, window)`` and pairs it with a binary label
    indicating whether the portfolio entered a drawdown in the next
    ``forward_bars`` bars.

    Labeling uses a **consensus-based** approach: for each sample, every
    asset is checked for an ATR-relative drawdown in the forward window.
    A sample is labelled "risky" (1.0) only when **at least
    ``min_assets_in_drawdown``** assets simultaneously show a drawdown
    exceeding ``drawdown_pct × ATR-14``.  This requires a broad market
    selloff rather than a single volatile asset moving — dramatically
    reducing false-positive risky labels compared to the old "any single
    asset" rule.

    Using ATR-relative thresholds instead of fixed percentages accounts
    for different volatility levels across assets (e.g., FARTCOIN moves
    far more than BTC in percentage terms, but both have meaningful
    ATR-relative drops).

    Parameters
    ----------
    asset_dfs : list of pd.DataFrame
        One OHLCV DataFrame per asset, aligned on time index.
        All DataFrames must have the same length and the same time index.
    window : int
        Candle bars per asset window (time dimension of each CNN input).
    forward_bars : int
        Bars to look forward when computing the portfolio drawdown label.
    drawdown_pct : float
        ATR multiplier for drawdown detection (default 2.0 = 2× ATR).
        A drop of more than drawdown_pct × ATR-14 in a single asset
        counts that asset as "in drawdown" for the sample.  The sample
        is labelled risky only when enough assets meet this threshold
        (see ``min_assets_in_drawdown``).
    min_assets_in_drawdown : int
        Minimum number of assets that must independently exceed the
        ATR-relative drawdown threshold before a sample is labelled
        risky.  Default 3 — requires a broad market selloff rather
        than idiosyncratic single-asset moves.
    fast_period, slow_period : int
        EMA periods for feature extraction.
    """

    def __init__(
        self,
        asset_dfs: list[pd.DataFrame],
        window: int = DEFAULT_WINDOW,
        forward_bars: int = 30,
        drawdown_pct: float = 2.0,  # now ATR multiplier: 2.0 = 2× ATR
        min_assets_in_drawdown: int = 3,
        fast_period: int = 8,
        slow_period: int = 21,
    ) -> None:
        assert len(asset_dfs) > 0, "Need at least one asset DataFrame"
        n = len(asset_dfs[0])
        for i, df in enumerate(asset_dfs):
            assert len(df) == n, (
                f"All asset DataFrames must have the same length. "
                f"asset[0]={n}, asset[{i}]={len(df)}"
            )

        self.asset_dfs = [df.reset_index(drop=True) for df in asset_dfs]
        self.n_assets = len(asset_dfs)
        self.window = window
        self.forward_bars = forward_bars
        self.drawdown_pct = drawdown_pct
        self.min_assets_in_drawdown = min_assets_in_drawdown
        self.fast_period = fast_period
        self.slow_period = slow_period

        # Precompute features for each asset
        t0 = __import__("time").time()
        self._asset_features: list[np.ndarray] = []
        for i, df in enumerate(self.asset_dfs):
            feats = precompute_all_features(candles=df, window=window, training=True)
            if feats is None:
                raise ValueError(f"Feature precomputation failed for asset {i}")
            self._asset_features.append(feats)
        precompute_elapsed = __import__("time").time() - t0

        # Precompute ATR for each asset (for ATR-relative drawdown labels)
        self._asset_atrs: list[np.ndarray] = []
        for df in self.asset_dfs:
            hi = df["high"].astype(np.float32).to_numpy()
            lo = df["low"].astype(np.float32).to_numpy()
            cl = df["close"].astype(np.float32).to_numpy()
            # Simple ATR-14 computation
            tr = np.maximum(
                hi - lo, np.maximum(np.abs(hi - np.roll(cl, 1)), np.abs(lo - np.roll(cl, 1)))
            )
            tr[0] = hi[0] - lo[0]
            atr = pd.Series(tr).ewm(span=14, adjust=False).mean().to_numpy().astype(np.float32)
            self._asset_atrs.append(atr)

        warmup = window + 34
        # Valid range: enough history AND enough future for the label
        self._indices = list(range(warmup, n - forward_bars))

        # Pre-compute portfolio drawdown labels
        self._labels = self._compute_portfolio_labels()

        n_risky = int(self._labels.sum())
        n_total = max(len(self._indices), 1)
        risky_pct = n_risky / n_total * 100
        logger.info(
            "PortfolioDataset: %d assets x %d bars → %d samples  "
            "(risky=%d %.1f%%, min_assets_in_drawdown=%d)  features precomputed in %.1fs",
            self.n_assets,
            n,
            len(self._indices),
            n_risky,
            risky_pct,
            self.min_assets_in_drawdown,
            precompute_elapsed,
        )

        # Warn if label distribution is severely imbalanced
        if risky_pct > 70.0:
            logger.warning(
                "PortfolioDataset: risky ratio %.1f%% is very high (>70%%). "
                "Consider increasing min_assets_in_drawdown (currently %d) "
                "or increasing drawdown_pct (currently %.1f) to reduce false positives.",
                risky_pct,
                self.min_assets_in_drawdown,
                self.drawdown_pct,
            )
        elif risky_pct < 10.0:
            logger.warning(
                "PortfolioDataset: risky ratio %.1f%% is very low (<10%%). "
                "Consider decreasing min_assets_in_drawdown (currently %d) "
                "or decreasing drawdown_pct (currently %.1f) to capture more risk events.",
                risky_pct,
                self.min_assets_in_drawdown,
                self.drawdown_pct,
            )

    def _compute_portfolio_labels(self) -> np.ndarray:
        """Binary label: 1 if >= min_assets_in_drawdown assets drop > drawdown_pct × ATR.

        Uses a consensus-based approach: each asset is independently checked
        for an ATR-relative drawdown in the forward window, and the sample is
        labelled risky only when enough assets are simultaneously in drawdown.
        This requires a broad market selloff rather than a single volatile
        asset moving.

        Uses ATR-relative thresholds instead of fixed percentages to account
        for different volatility levels across assets.
        """
        labels = np.zeros(len(self._indices), dtype=np.float32)

        for sample_idx, bar_idx in enumerate(self._indices):
            assets_in_drawdown = 0

            for asset_idx, df in enumerate(self.asset_dfs):
                entry_close = float(df["close"].iloc[bar_idx])
                if entry_close <= 0:
                    continue

                atr_val = float(self._asset_atrs[asset_idx][bar_idx])
                if atr_val <= 0:
                    continue

                # ATR-relative threshold: drawdown_pct is treated as an ATR multiplier
                threshold = atr_val * self.drawdown_pct

                future = df["close"].iloc[bar_idx + 1 : bar_idx + self.forward_bars + 1]
                if future.empty:
                    continue
                min_close = float(future.min())
                if (entry_close - min_close) > threshold:
                    assets_in_drawdown += 1

            # Require consensus: broad market selloff, not a single asset move
            if assets_in_drawdown >= self.min_assets_in_drawdown:
                labels[sample_idx] = 1.0

        return labels

    # ── Dataset interface ─────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._indices)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        bar_idx = self._indices[idx]
        start = bar_idx - self.window + 1

        windows: list[torch.Tensor] = []
        for feats in self._asset_features:
            window_slice = feats[:, start : bar_idx + 1]
            if window_slice.shape[1] != self.window:
                window_slice = np.zeros((N_FEATURES, self.window), dtype=np.float32)
            windows.append(torch.from_numpy(window_slice.copy()))

        x = torch.stack(windows, dim=0)  # (n_assets, N_FEATURES, window)
        y = torch.tensor(float(self._labels[idx]), dtype=torch.float32)
        return x, y

    def label_array(self) -> np.ndarray:
        return self._labels.copy()


# ---------------------------------------------------------------------------
# DataLoader helpers
# ---------------------------------------------------------------------------


def build_dataloaders(
    dataset: AssetDataset,
    batch_size: int = 64,
    val_split: float = 0.15,
    num_workers: int = 0,
    use_weighted_sampler: bool = True,
) -> tuple[DataLoader, DataLoader]:
    """Split an AssetDataset into train/val DataLoaders.

    Parameters
    ----------
    dataset : AssetDataset
    batch_size : int
    val_split : float
        Fraction of samples to use for validation (default 0.15).
        The split is chronological — the last ``val_split`` fraction of
        samples becomes the validation set.  This avoids leaking future
        data into training (unlike a random split).
    num_workers : int
        DataLoader worker processes.  0 = main process (safe on all platforms).
    use_weighted_sampler : bool
        If True, use a WeightedRandomSampler on the training set so each
        class is sampled roughly equally, compensating for the heavy
        class imbalance (most bars are flat=0).

    Returns
    -------
    train_dl, val_dl : DataLoader, DataLoader
    """
    n = len(dataset)
    val_size = max(1, int(n * val_split))
    train_size = n - val_size

    # Chronological split — no random shuffling to avoid leakage
    train_indices = list(range(train_size))
    val_indices = list(range(train_size, n))

    # Build subsets using simple index wrappers
    train_subset = _IndexSubset(dataset, train_indices)
    val_subset = _IndexSubset(dataset, val_indices)

    # Weighted sampler for training to balance classes
    train_sampler = None
    if use_weighted_sampler and isinstance(dataset, AssetDataset):
        all_labels = dataset.label_array()
        train_labels = all_labels[: len(train_indices)]
        weights = _sample_weights(train_labels)
        train_sampler = WeightedRandomSampler(
            weights=torch.from_numpy(weights).float(),
            num_samples=len(train_indices),
            replacement=True,
        )

    train_dl = DataLoader(
        train_subset,
        batch_size=batch_size,
        sampler=train_sampler,
        shuffle=(train_sampler is None),
        num_workers=num_workers,
        pin_memory=False,
        drop_last=True,
    )

    val_dl = DataLoader(
        val_subset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=False,
        drop_last=False,
    )

    logger.info(
        "DataLoaders: train=%d samples (%d batches)  val=%d samples (%d batches)  batch_size=%d",
        len(train_subset),
        len(train_dl),
        len(val_subset),
        len(val_dl),
        batch_size,
    )

    return train_dl, val_dl


def build_portfolio_dataloaders(
    dataset: PortfolioDataset,
    batch_size: int = 32,
    val_split: float = 0.15,
    num_workers: int = 0,
    use_weighted_sampler: bool = True,
) -> tuple[DataLoader, DataLoader]:
    """Build train/val DataLoaders for a PortfolioDataset.

    Uses weighted sampling on the training set to balance the binary
    label distribution (risky vs safe).
    """
    n = len(dataset)
    val_size = max(1, int(n * val_split))
    train_size = n - val_size

    train_subset = _IndexSubset(dataset, list(range(train_size)))
    val_subset = _IndexSubset(dataset, list(range(train_size, n)))

    train_sampler = None
    if use_weighted_sampler:
        labels = dataset.label_array()
        train_labels = labels[:train_size]
        # Binary: compute weight per class
        n_risky = float(train_labels.sum())
        n_safe = float(len(train_labels) - n_risky)
        if n_risky > 0 and n_safe > 0:
            w_safe = len(train_labels) / (2.0 * n_safe)
            w_risky = len(train_labels) / (2.0 * n_risky)
            weights = np.where(train_labels > 0.5, w_risky, w_safe).astype(np.float64)
            train_sampler = WeightedRandomSampler(
                weights=torch.from_numpy(weights).float(),
                num_samples=train_size,
                replacement=True,
            )

    train_dl = DataLoader(
        train_subset,
        batch_size=batch_size,
        sampler=train_sampler,
        shuffle=(train_sampler is None),
        num_workers=num_workers,
        drop_last=True,
    )
    val_dl = DataLoader(
        val_subset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        drop_last=False,
    )

    return train_dl, val_dl


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


class _IndexSubset(Dataset):
    """Minimal index-based subset wrapper (avoids importing torch.utils.data.Subset)."""

    def __init__(self, dataset: Dataset, indices: Sequence[int]) -> None:
        self.dataset = dataset
        self.indices = indices

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, idx: int):
        return self.dataset[self.indices[idx]]


def _sample_weights(labels: np.ndarray) -> np.ndarray:
    """Return a per-sample weight array for WeightedRandomSampler."""
    classes, counts = np.unique(labels, return_counts=True)
    class_weight_map = {int(c): float(len(labels)) / float(cnt) for c, cnt in zip(classes, counts)}
    weights = np.array([class_weight_map.get(int(lbl), 1.0) for lbl in labels], dtype=np.float64)
    return weights
