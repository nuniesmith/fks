"""
ML package for the futures trading bot.

Provides a lightweight CNN-based signal gating and portfolio risk
scoring layer that sits on top of the existing EMA + order-book
signal pipeline.

Sub-modules
-----------
features   — extract a normalised feature tensor from live candle/book state
model      — PerAssetCNN and MasterCNN PyTorch architectures
labeler    — walk historical klines and simulate TP/SL to generate labels
dataset    — PyTorch Dataset wrapping labelled sliding windows
inference  — thin CPU inference wrapper used by the live bot
train      — standalone offline training script (run once, saves .pt files)

Typical live-bot usage
----------------------
    from ml.inference import CNNInference

    # At worker startup
    cnn = CNNInference.load(asset_key="btc", models_dir="/app/models")

    # Inside _trading_loop, before placing an order
    result = cnn.predict(candles, imbalance=imbalance, vol_pct=vol_pct)
    if result.confidence < cfg.ml.min_confidence:
        continue          # skip — CNN not convinced
    if result.signal != raw_signal:
        continue          # CNN disagrees with EMA crossover
    size *= result.confidence   # scale size by conviction
"""

from .inference import CNNInference, InferenceResult
from .model import MasterCNN, PerAssetCNN

__all__ = [
    "CNNInference",
    "InferenceResult",
    "MasterCNN",
    "PerAssetCNN",
]
