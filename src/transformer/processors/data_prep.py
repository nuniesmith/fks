"""
Utility functions for time series preprocessing: scaling, windowing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
from sklearn.preprocessing import StandardScaler


@dataclass
class ScaleWindowResult:
    X: np.ndarray
    y: np.ndarray
    scaler: StandardScaler


def scale_and_window(
    series: np.ndarray, window: int = 64, horizon: int = 1
) -> ScaleWindowResult:
    """
    Standardize a 1D series and build supervised windows for forecasting the
    next horizon-step return.
    """
    series = np.asarray(series, dtype=np.float32)
    returns = np.diff(np.log(series))
    scaler = StandardScaler()
    ret_scaled = scaler.fit_transform(returns.reshape(-1, 1)).flatten()

    Xs, ys = [], []
    for i in range(len(ret_scaled) - window - horizon + 1):
        Xs.append(ret_scaled[i : i + window])
        ys.append(ret_scaled[i + horizon : i + window + horizon])
    X = np.stack(Xs, axis=0).astype(np.float32)
    y = np.stack(ys, axis=0).astype(np.float32)
    X = X[..., None]  # [N, S, 1]
    y = y[..., None]  # [N, S, 1]
    return ScaleWindowResult(X=X, y=y, scaler=scaler)
