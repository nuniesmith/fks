"""
Simple training/inference pipeline for HMMTransformer.
Provides utilities to prepare windows, fit HMM on returns, and train the Transformer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, List

import numpy as np
import torch
from torch import nn

from services.transformer.models.hmm_transformer import (
    HMMTransformer,
    HMMConfig,
    TransformerConfig,
    train_step,
)


@dataclass
class DataWindow:
    X: np.ndarray  # [N, S, F]
    OBS: np.ndarray  # [N, S, D]
    Y: np.ndarray  # [N, S, O]


def make_windows(series: np.ndarray, window: int = 64, horizon: int = 1) -> DataWindow:
    """
    Create rolling windows from a 1D price series for quick prototyping.
    Returns features X (returns), OBS (returns for HMM), and Y (future returns).
    """
    # compute log returns
    ret = np.diff(np.log(series))
    S = window
    xs: List[np.ndarray] = []
    ys: List[np.ndarray] = []
    for i in range(len(ret) - S - horizon + 1):
        xwin = ret[i : i + S]
        ywin = ret[i + horizon : i + S + horizon]
        xs.append(xwin)
        ys.append(ywin)
    X = np.stack(xs, axis=0)  # [N, S]
    Y = np.stack(ys, axis=0)  # [N, S]

    # features: return and rolling volatility
    vol = np.sqrt(
        np.convolve((ret - ret.mean()) ** 2, np.ones(S) / S, mode="valid")
    )[: X.shape[0] + S - 1]
    vol = vol[: X.shape[0] + S - 1]
    # align vol windows to X
    vol_windows = []
    for i in range(X.shape[0]):
        vol_windows.append(vol[i : i + S])
    VOL = np.stack(vol_windows, axis=0)

    X_feat = np.stack([X, VOL], axis=-1)  # [N, S, F=2]
    OBS = X[..., None]  # [N, S, 1]
    Y = Y[..., None]  # [N, S, 1]
    return DataWindow(X=X_feat.astype(np.float32), OBS=OBS.astype(np.float32), Y=Y.astype(np.float32))


def train_quick(
    series: np.ndarray,
    hmm_states: int = 3,
    epochs: int = 2,
    window: int = 64,
    horizon: int = 1,
) -> Tuple[HMMTransformer, float]:
    """Quick training on a single series for smoke testing."""
    data = make_windows(series, window=window, horizon=horizon)
    model = HMMTransformer(in_features=data.X.shape[-1], hmm_cfg=HMMConfig(n_states=hmm_states))

    # Fit HMM on concatenated observations
    model.fit_hmm(data.OBS.reshape(-1, data.OBS.shape[-1]))

    optim = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    X_t = torch.from_numpy(data.X)
    OBS_t = torch.from_numpy(data.OBS)
    Y_t = torch.from_numpy(data.Y)

    total_loss = 0.0
    for ep in range(epochs):
        loss, mae = train_step(model, X_t, OBS_t, Y_t, optim, loss_fn)
        total_loss = loss
    return model, total_loss
