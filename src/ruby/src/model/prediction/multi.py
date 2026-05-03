import os
from datetime import datetime, timedelta
from typing import Any

from model._shims import logger

# Import AssetPricePredictor from the single-asset predictor module
try:
    from model.prediction.single import AssetPricePredictor
except ImportError as e:
    raise ImportError(
        "Failed to import AssetPricePredictor from model.prediction.single. "
        "Ensure the single-asset predictor module is available."
    ) from e

# ---------------------------------------------------------------------------
# AssetDataManager stub
# ---------------------------------------------------------------------------
# AssetDataManager does not exist in this project yet.
# Provide a minimal stub so the rest of the module remains functional
# until a real implementation is added under lib.model.data.manager.
try:
    from model.data.manager import AssetDataManager  # type: ignore[import-untyped]
except ImportError:

    class AssetDataManager:  # type: ignore[no-redef]
        """STUB — AssetDataManager is not yet implemented.

        .. warning:: **@experimental / not-yet-built** — This is a non-functional
           placeholder.  It exists solely so that ``MultiAssetPredictor`` can be
           *imported* without crashing.  Every data method returns ``None`` and
           logs a warning; no real data is fetched.

        To implement: create ``lib.model.data.manager.AssetDataManager``
        that fetches bar data from the DataSyncService / Redis bar cache.
        Until then, do NOT call ``MultiAssetPredictor`` from live engine code.
        """

        #: Class-level flag so we only emit the "stub" warning once per process.
        _warned: bool = False

        #: Identifies this class as the unimplemented stub so callers can
        #: detect it at runtime (e.g. ``isinstance`` checks or duck-typing).
        IS_STUB: bool = True

        def download_data(self, asset: str, **kwargs: Any) -> None:
            """Return ``None`` — no real data source is wired up.

            Parameters
            ----------
            asset:
                Asset identifier (e.g. ``"gold"``, ``"bitcoin"``).
            **kwargs:
                Ignored.  A real implementation would accept ``start_date``,
                ``end_date``, ``interval``, etc.
            """
            if not AssetDataManager._warned:
                logger.warning(
                    "AssetDataManager is a stub — not yet implemented. "
                    "Create lib.model.data.manager.AssetDataManager to enable "
                    "real data fetching. Returning None for all calls."
                )
                AssetDataManager._warned = True
            logger.warning(
                "AssetDataManager.download_data() called for asset '%s' but no "
                "real implementation exists — returning None.",
                asset,
            )
            return None

        def prepare_features(self, raw_data: Any, **kwargs: Any) -> None:
            """Return ``None`` — no feature preparation without real data.

            A real implementation would transform raw OHLCV data into the
            feature DataFrame expected by ``AssetPricePredictor``.
            """
            logger.warning(
                "AssetDataManager.prepare_features() called on stub — returning None (no real data to prepare)."
            )
            return None

        def __repr__(self) -> str:
            return "<AssetDataManager (stub — not yet implemented)>"


def _is_stub_data_manager(dm: Any) -> bool:
    """Return ``True`` if *dm* is the unimplemented stub ``AssetDataManager``."""
    return getattr(dm, "IS_STUB", False) is True


# ---------------------------------------------------------------------------
# Unavailable-prediction sentinel helpers
# ---------------------------------------------------------------------------

_UNAVAILABLE_SENTINEL: dict[str, Any] = {
    "prediction_source": "unavailable",
    "error": "multi_asset_not_implemented",
    "direction": None,
    "confidence": 0.0,
    "message": (
        "MultiAssetPredictor is not yet production-ready.  "
        "The AssetDataManager stub does not fetch real data.  "
        "Do not surface this result in the UI."
    ),
}


def _make_unavailable_prediction(asset: str, *, reason: str | None = None) -> dict[str, Any]:
    """Build an unavailable sentinel dict for a single asset."""
    sentinel = dict(_UNAVAILABLE_SENTINEL)
    sentinel["asset"] = asset
    if reason:
        sentinel["error"] = reason
    return sentinel


# ---------------------------------------------------------------------------
# MultiAssetPredictor
# ---------------------------------------------------------------------------


class MultiAssetPredictor:
    """Combined predictor for multiple asset types.

    .. warning:: **@experimental / not-yet-built** — This class depends on
       ``AssetDataManager`` which is currently a non-functional stub.  All
       public methods that would produce predictions return safe
       ``{"prediction_source": "unavailable", ...}`` sentinels instead of
       crashing or — worse — returning fake numbers.

       **Do NOT register this predictor with the live engine** until
       ``AssetDataManager`` has a real implementation.
    """

    #: Guard flag — checked by the engine before using predictions.
    #: Will be ``True`` only once a real ``AssetDataManager`` is available.
    is_operational: bool = False

    def __init__(self, assets: list[str] | None = None):
        """
        Initialize the multi-asset predictor.

        Args:
            assets (list, optional): List of asset types to predict
        """
        self.assets = assets or ["gold", "bitcoin", "ethereum"]
        self.predictors: dict[str, AssetPricePredictor] = {}

        # Create a shared data manager instance
        self.data_manager = AssetDataManager()  # type: ignore[misc]

        # Determine whether we have a real data manager
        self._using_stub = _is_stub_data_manager(self.data_manager)
        if self._using_stub:
            logger.warning(
                "MultiAssetPredictor initialised with STUB AssetDataManager. "
                "All predictions will return unavailable sentinels. "
                "Implement lib.model.data.manager.AssetDataManager to enable "
                "real multi-asset predictions."
            )
            self.is_operational = False
        else:
            self.is_operational = True

        for asset in self.assets:
            predictor = AssetPricePredictor(asset_type=asset)  # type: ignore[misc]
            # Assign the shared data manager to each predictor
            predictor.data_manager = self.data_manager
            self.predictors[asset] = predictor

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train_all_models(
        self, save_dir: str = "models", hyperparameter_tuning: bool = False
    ) -> dict[str, dict[str, Any]]:
        """
        Train models for all assets.

        If the data manager is a stub, returns unavailable sentinels for every
        asset instead of attempting (and failing) to train.

        Args:
            save_dir (str): Directory to save trained models
            hyperparameter_tuning (bool): Whether to perform hyperparameter tuning

        Returns:
            dict: Training results for each asset
        """
        if self._using_stub:
            logger.error(
                "train_all_models() called but AssetDataManager is a stub — "
                "cannot train without real data.  Returning unavailable sentinels."
            )
            return {
                asset: _make_unavailable_prediction(asset, reason="training_unavailable_no_data_manager")
                for asset in self.assets
            }

        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        results: dict[str, dict[str, Any]] = {}

        for asset, predictor in self.predictors.items():
            logger.info(f"Training model for {asset}...")

            try:
                model_result = predictor.train_model(
                    save_path=os.path.join(save_dir, f"{asset}_model.pkl"),
                    hyperparameter_tuning=hyperparameter_tuning,
                )
                results[asset] = model_result
            except Exception as e:
                logger.error(f"Error training model for {asset}: {e}")
                results[asset] = _make_unavailable_prediction(asset, reason=f"training_error: {e}")

        return results

    # ------------------------------------------------------------------
    # Predictions
    # ------------------------------------------------------------------

    def predict_all(self, prediction_horizon: str = "market_open") -> dict[str, dict[str, Any]]:
        """
        Make predictions for all assets.

        If the data manager is a stub, every asset receives an unavailable
        sentinel — no fake predictions are ever returned.

        Args:
            prediction_horizon (str): 'market_open', '24h', or '1h'

        Returns:
            dict: Predictions for each asset.  Each value is either a real
            prediction dict or an unavailable sentinel with
            ``"prediction_source": "unavailable"``.
        """
        if self._using_stub:
            logger.warning(
                "predict_all() called but AssetDataManager is a stub — "
                "returning unavailable sentinels for all %d assets.",
                len(self.assets),
            )
            return {asset: _make_unavailable_prediction(asset) for asset in self.assets}

        predictions: dict[str, dict[str, Any]] = {}

        for asset, predictor in self.predictors.items():
            if predictor.model is None:
                logger.warning(f"No trained model available for {asset}. Attempting to load...")

                # Try to load from default path
                model_path = f"models/{asset}_model.pkl"
                if os.path.exists(model_path):
                    if predictor._load_model(model_path):
                        logger.info(f"Loaded model for {asset} from {model_path}")
                    else:
                        predictions[asset] = _make_unavailable_prediction(asset, reason="failed_to_load_model")
                        continue
                else:
                    logger.error(f"No model file found for {asset}")
                    predictions[asset] = _make_unavailable_prediction(asset, reason="no_trained_model")
                    continue

            # Make prediction — the single-asset predictor already returns
            # its own unavailable sentinel when data is missing, so we get
            # safe results either way.
            logger.info(f"Making predictions for {asset} with horizon {prediction_horizon}...")
            try:
                result = predictor.predict_next_movement(
                    prediction_horizon=prediction_horizon,
                )
                # Tag multi-asset origin so the UI can trace provenance
                if isinstance(result, dict):
                    result.setdefault("asset", asset)
                predictions[asset] = result
            except Exception as e:
                logger.error(f"Error predicting {asset} movements: {e}")
                predictions[asset] = _make_unavailable_prediction(asset, reason=str(e))

        return predictions

    # ------------------------------------------------------------------
    # Latest prices
    # ------------------------------------------------------------------

    def get_latest_prices(self) -> dict[str, dict[str, Any]]:
        """
        Get the latest prices for all assets.

        Returns ``{"prediction_source": "unavailable", ...}`` for every asset
        if the data manager is a stub.

        Returns:
            dict: Latest prices and basic statistics
        """
        if self._using_stub:
            logger.warning(
                "get_latest_prices() called but AssetDataManager is a stub — returning unavailable sentinels."
            )
            return {
                asset: _make_unavailable_prediction(asset, reason="price_data_unavailable") for asset in self.assets
            }

        results: dict[str, dict[str, Any]] = {}

        for asset in self.assets:
            try:
                # Get today's data
                today = datetime.now().date()
                yesterday = today - timedelta(days=1)

                data = self.data_manager.download_data(
                    asset,
                    start_date=yesterday.strftime("%Y-%m-%d"),
                    end_date=today.strftime("%Y-%m-%d"),
                    interval="1h",
                )

                if data is None or (hasattr(data, "empty") and data.empty):
                    results[asset] = _make_unavailable_prediction(asset, reason="no_recent_price_data")
                    continue

                latest = data.iloc[-1]

                # Calculate daily change
                if len(data) > 1:
                    first_price = data.iloc[0]["Close"]
                    latest_price = latest["Close"]
                    daily_change_pct = ((latest_price - first_price) / first_price) * 100
                else:
                    daily_change_pct = 0

                results[asset] = {
                    "latest_price": latest["Close"],
                    "daily_change_pct": daily_change_pct,
                    "prediction_source": "live",
                }
            except Exception as e:
                logger.error(f"Error fetching latest prices for {asset}: {e}")
                results[asset] = _make_unavailable_prediction(asset, reason=str(e))

        return results
