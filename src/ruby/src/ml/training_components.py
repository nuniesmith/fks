"""
ml/training_components.py — Reusable building blocks for CNN training.

Exported:
  FocalLoss              - class-imbalanced focal loss with optional label smoothing
  EarlyStopping          - patience-based early stopping (min or max mode)
  warmup_cosine_lr       - LR multiplier: linear warmup then cosine decay
  calibrate_temperature  - find optimal softmax temperature on a val DataLoader
"""

from __future__ import annotations

import math
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from ml.model import N_CLASSES

# ── Focal loss ────────────────────────────────────────────────────────────────


class FocalLoss(nn.Module):
    """Focal loss for class-imbalanced multi-class classification.

    Down-weights well-classified (easy) examples so the model focuses on
    hard-to-classify minority-class samples.

    Parameters
    ----------
    weight : Tensor | None
        Per-class weights (same semantics as ``nn.CrossEntropyLoss``).
    gamma : float
        Focusing parameter.  γ=0 → standard weighted CE.  γ=2 is a good
        default for moderate imbalance; raise toward 3-4 for extreme skew.
    label_smoothing : float
        Optional label smoothing ε (0–1).
    """

    def __init__(
        self,
        weight: torch.Tensor | None = None,
        gamma: float = 2.0,
        label_smoothing: float = 0.0,
    ) -> None:
        super().__init__()
        self.register_buffer("weight", weight)
        self.gamma = gamma
        self.label_smoothing = label_smoothing

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = F.cross_entropy(
            logits,
            targets,
            weight=self.weight,
            label_smoothing=self.label_smoothing,
            reduction="none",
        )
        pt = torch.exp(-ce)  # probability of the true class
        focal = ((1.0 - pt) ** self.gamma) * ce
        return focal.mean()


# ── Early stopping ────────────────────────────────────────────────────────────


class EarlyStopping:
    """Stop training when a monitored metric stops improving.

    Parameters
    ----------
    patience : int
        Epochs to wait after the last improvement before triggering.
    min_delta : float
        Minimum change to qualify as an improvement.
    mode : str
        ``'min'`` for metrics to minimise (e.g. val_loss),
        ``'max'`` for metrics to maximise (e.g. macro_f1, val_acc).

    Usage
    -----
    ::

        es = EarlyStopping(patience=10, mode="max")
        for epoch in range(max_epochs):
            ...
            if es(val_f1):
                break
    """

    def __init__(
        self,
        patience: int = 12,
        min_delta: float = 1e-4,
        mode: str = "min",
    ) -> None:
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self._best: float | None = None
        self._counter: int = 0
        self.triggered: bool = False

    def _is_improvement(self, current: float) -> bool:
        if self._best is None:
            return True
        if self.mode == "max":
            return current > self._best + self.min_delta
        return current < self._best - self.min_delta

    def __call__(self, metric: float) -> bool:
        if self._is_improvement(metric):
            self._best = metric
            self._counter = 0
        else:
            self._counter += 1
            if self._counter >= self.patience:
                self.triggered = True
        return self.triggered


# ── LR schedule ───────────────────────────────────────────────────────────────


def warmup_cosine_lr(
    epoch: int,
    warmup_epochs: int,
    total_epochs: int,
    min_frac: float = 0.05,
) -> float:
    """LR multiplier: linear warmup for the first ``warmup_epochs`` epochs,
    then cosine decay from 1.0 down to ``min_frac``.

    Designed for use with ``torch.optim.lr_scheduler.LambdaLR``::

        scheduler = LambdaLR(
            optimizer,
            lr_lambda=lambda ep: warmup_cosine_lr(ep, warmup_epochs, total_epochs),
        )
    """
    if warmup_epochs > 0 and epoch < warmup_epochs:
        return float(epoch + 1) / float(warmup_epochs)
    progress = (epoch - warmup_epochs) / max(total_epochs - warmup_epochs, 1)
    cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
    return min_frac + (1.0 - min_frac) * cosine


# ── Temperature calibration ───────────────────────────────────────────────────


def calibrate_temperature(
    model: nn.Module,
    val_dl: Any,
    device: torch.device,
    n_classes: int = N_CLASSES,
) -> tuple[float, float, float]:
    """Find the optimal softmax temperature *T* on *val_dl*.

    Minimises negative log-likelihood by scaling logits as ``logits / T``
    before softmax, producing well-calibrated confidence scores:
    P(correct | confidence = p) ≈ p.

    The search is performed on the *already-collected* logits so the val
    DataLoader is iterated exactly once regardless of the number of scalar
    candidates tried by the optimiser.

    Parameters
    ----------
    model : nn.Module
        Model in eval mode.  Must be on *device* already.
    val_dl : DataLoader
        Validation DataLoader.  Must be re-iterable (standard
        ``torch.utils.data.DataLoader`` with ``num_workers=0`` is fine).
    device : torch.device
    n_classes : int

    Returns
    -------
    temperature : float   Optimal temperature (typically 1.0-3.0).
    ece_before  : float   Expected Calibration Error at T=1.
    ece_after   : float   Expected Calibration Error at optimal T.
    """
    from scipy.optimize import minimize_scalar

    model.eval()

    all_logits: list[torch.Tensor] = []
    all_labels: list[torch.Tensor] = []

    with torch.no_grad():
        for x_batch, y_batch in val_dl:
            logits = model(x_batch.to(device))
            all_logits.append(logits.cpu())
            all_labels.append(y_batch.cpu())

    logits_cat = torch.cat(all_logits, dim=0)  # (N, n_classes)
    labels_cat = torch.cat(all_labels, dim=0)  # (N,)

    def _ece(probs: torch.Tensor, labels: torch.Tensor, n_bins: int = 15) -> float:
        confidences, predictions = probs.max(dim=-1)
        accuracies = predictions.eq(labels).float()
        ece = 0.0
        for i in range(n_bins):
            lo, hi = i / n_bins, (i + 1) / n_bins
            mask = (confidences > lo) & (confidences <= hi)
            if mask.sum() > 0:
                ece += mask.float().mean().item() * abs(
                    accuracies[mask].mean().item() - confidences[mask].mean().item()
                )
        return ece

    ece_before = _ece(torch.softmax(logits_cat, dim=-1), labels_cat)

    def _nll(T: float) -> float:
        log_probs = torch.log_softmax(logits_cat / max(T, 0.01), dim=-1)
        return F.nll_loss(log_probs, labels_cat.long()).item()

    result = minimize_scalar(_nll, bounds=(0.1, 10.0), method="bounded")
    best_T = float(result.x) if result.success else 1.0
    ece_after = _ece(torch.softmax(logits_cat / best_T, dim=-1), labels_cat)

    return round(best_T, 4), round(ece_before, 4), round(ece_after, 4)
