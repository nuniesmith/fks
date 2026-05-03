"""
Base estimator class for all models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import pandas as pd

from model.base.model import BaseModel

if TYPE_CHECKING:
    import numpy as np


class Estimator(BaseModel, ABC):
    """
    Base class for all estimator models.

    Estimators are models that can fit to data and make predictions.
    This class provides a common interface for all estimator models.
    """

    def __init__(self, name: str, params: dict[str, Any] | None = None):
        """
        Initialize the estimator with a name and parameters.

        Args:
            name: The name of the estimator.
            params: Optional parameters for the estimator.
        """
        super().__init__()
        self.name = name
        self.params = params or {}
        self._model = None
        self._is_fitted = False

    @abstractmethod
    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray | None = None) -> Estimator:  # type: ignore[override]
        """
        Fit the estimator to the data.

        Args:
            X: Features or time series data.
            y: Target values (optional, for supervised learning).

        Returns:
            Self for method chaining.
        """

    @abstractmethod
    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray | pd.Series:  # type: ignore[override]
        """
        Make predictions using the fitted estimator.

        Args:
            X: Features or time series data.

        Returns:
            Predicted values.
        """

    def transform(self, X: pd.DataFrame | np.ndarray) -> np.ndarray | pd.DataFrame:
        """
        Transform the input data (for transformers and some estimators).

        Args:
            X: Features or time series data.

        Returns:
            Transformed data.
        """
        # Default implementation returns predictions
        result = self.predict(X)
        if isinstance(result, pd.Series):
            return result.to_frame()
        return result

    @property
    def is_fitted(self) -> bool:
        """
        Check if the estimator has been fitted.

        Returns:
            True if the estimator has been fitted, False otherwise.
        """
        return self._is_fitted

    def reset(self) -> None:
        """
        Reset the estimator to its initial state.
        """
        self._model = None
        self._is_fitted = False

    def save(self, path: str) -> None:
        """
        Save the estimator to a file.

        Args:
            path: Path to save the estimator to.
        """
        raise NotImplementedError("Saving not implemented for this estimator")

    def load(self, path: str) -> Estimator:
        """
        Load the estimator from a file.

        Args:
            path: Path to load the estimator from.

        Returns:
            Self for method chaining.
        """
        raise NotImplementedError("Loading not implemented for this estimator")

    def train(
        self,
        data: Any = None,
        target: Any = None,
        X_train: Any = None,
        y_train: Any = None,
        **kwargs,
    ) -> Estimator:
        """Default train implementation — delegates to fit().

        Accepts either ``(data, target)`` where *data* is a DataFrame and
        *target* is a column name, or ``(X_train, y_train)`` pre-split arrays.
        """
        if X_train is not None:
            return self.fit(X_train, y_train, **kwargs)  # type: ignore[arg-type]
        if data is not None and target is not None:
            if isinstance(data, pd.DataFrame) and isinstance(target, str):
                y = data[target]
                X = data.drop(columns=[target])
                return self.fit(X, y, **kwargs)  # type: ignore[arg-type]
            return self.fit(data, target, **kwargs)  # type: ignore[arg-type]
        raise ValueError("Provide either (X_train, y_train) or (data, target).")

    def generate_samples(self, n_samples: int = 10, **kwargs) -> pd.DataFrame:
        """Default implementation — returns an empty DataFrame.

        Subclasses that support sample generation should override this.
        """
        return pd.DataFrame()

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the estimator to a dictionary.

        Returns:
            Dictionary representation of the estimator.
        """
        return {
            "name": self.name,
            "params": self.params,
            "is_fitted": self._is_fitted,
        }
