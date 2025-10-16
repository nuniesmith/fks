"""Simple stacking ensemble.

Lightweight implementation used only for local tests right now.  We purposely
avoid pulling in heavier framework dependencies so this module can be executed
stand‑alone inside the minimal worker container / CI.

Design constraints:
* Base models must expose ``predict_proba`` returning shape (n_samples, 2)
* ``meta_model_factory`` returns an object implementing ``fit`` + ``predict_proba``
* We only construct meta features from the positive‑class probability column
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import logging

log = logging.getLogger(__name__)


class EnsembleError(Exception):
    """Raised when stacking ensemble operations fail."""
    pass


@dataclass
class StackingResult:
    meta_model: Any
    base_models: Dict[str, Any]
    params: Dict[str, Any]


class SimpleStackingEnsemble:
    def __init__(self, meta_model_factory, base_models: Dict[str, Any]):  # factories or fitted
        self.meta_model_factory = meta_model_factory
        self.base_models = base_models
        self.meta_model: Any | None = None

    def fit(self, X, y):  # X unused directly; we build meta features from base model probs
        import numpy as np  # type: ignore
        try:  # pragma: no branch - straight line happy path
            prob_cols: List[Any] = []
            for name, mdl in self.base_models.items():
                if not hasattr(mdl, "predict_proba"):
                    raise EnsembleError(f"Base model '{name}' lacks predict_proba")
                probs = mdl.predict_proba(X)
                if probs is None or len(probs.shape) != 2 or probs.shape[1] < 2:  # type: ignore[attr-defined]
                    raise EnsembleError(f"Base model '{name}' returned invalid probability matrix")
                prob_cols.append(probs)
            if not prob_cols:
                raise EnsembleError("No base model probabilities collected")
            meta_X = np.hstack([p[:, 1].reshape(-1, 1) for p in prob_cols])  # positive class prob as single feature per model
            self.meta_model = self.meta_model_factory()
            if not hasattr(self.meta_model, "fit") or not hasattr(self.meta_model, "predict_proba"):
                raise EnsembleError("Meta model must implement fit & predict_proba")
            self.meta_model.fit(meta_X, y)
            return StackingResult(meta_model=self.meta_model, base_models=self.base_models, params={})
        except Exception as e:  # pragma: no cover - surfaced as EnsembleError
            if not isinstance(e, EnsembleError):
                raise EnsembleError(f"Stacking fit failed: {e}") from e
            raise

    def predict_proba(self, X):
        import numpy as np  # type: ignore
        if self.meta_model is None:
            raise EnsembleError("Meta model not fitted")
        prob_cols: List[Any] = []
        for name, mdl in self.base_models.items():
            probs = mdl.predict_proba(X)
            if probs is None or len(probs.shape) != 2 or probs.shape[1] < 2:  # type: ignore[attr-defined]
                raise EnsembleError(f"Base model '{name}' returned invalid probability matrix at predict time")
            prob_cols.append(probs)
        if not prob_cols:
            raise EnsembleError("No base model probabilities for prediction")
        meta_X = np.hstack([p[:, 1].reshape(-1, 1) for p in prob_cols])
        return self.meta_model.predict_proba(meta_X)