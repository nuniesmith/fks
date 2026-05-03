"""
Backward-compatible facade — implementation split into sub-modules.

Modules:
  breakout_constants  – lookup tables, thresholds, feature lists
  breakout_features   – feature-engineering helper functions
  breakout_dataset    – BreakoutDataset, transforms, collate
  breakout_model      – HybridBreakoutCNN architecture
  breakout_training   – train_model, evaluate_model, compare_models
  breakout_loading    – model discovery, caching, loading
  breakout_inference  – predict_breakout, predict_breakout_batch
  breakout_contract   – feature contract, model_info, CLI
"""

from analysis.ml.breakout_constants import *  # noqa: F401,F403
from analysis.ml.breakout_constants import _TORCH_AVAILABLE  # noqa: F401  — underscore name excluded by wildcard
from analysis.ml.breakout_contract import *  # noqa: F401,F403
from analysis.ml.breakout_dataset import *  # noqa: F401,F403
from analysis.ml.breakout_features import *  # noqa: F401,F403
from analysis.ml.breakout_inference import *  # noqa: F401,F403
from analysis.ml.breakout_loading import *  # noqa: F401,F403
from analysis.ml.breakout_model import *  # noqa: F401,F403
from analysis.ml.breakout_training import *  # noqa: F401,F403
