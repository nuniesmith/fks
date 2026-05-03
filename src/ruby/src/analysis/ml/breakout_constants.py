"""
Breakout CNN — Constants, lookup tables, and configuration.

All shared constants used across the breakout CNN sub-modules live here.
This module intentionally has NO dependency on torch/torchvision so it can
always be imported safely.
"""

from __future__ import annotations

import contextlib

import numpy as np  # noqa: F401 — re-exported for convenience

from core.logging_config import get_logger

logger = get_logger("analysis.breakout_cnn")

# ---------------------------------------------------------------------------
# Guard torch imports — allow the module to be imported without GPU/torch
# ---------------------------------------------------------------------------

try:
    import torch  # noqa: F401
    import torch.nn as nn  # noqa: F401
    import torchvision.models as models  # noqa: F401
    import torchvision.transforms as T  # noqa: F401
    from PIL import Image  # noqa: F401
    from torch.utils.data import DataLoader, Dataset  # noqa: F401

    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    logger.warning(
        "PyTorch / torchvision not installed — CNN features disabled.  "
        "Install with: pip install torch torchvision Pillow"
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Ordered list of tabular feature names expected by the model.
# The dataset and inference code must provide them in exactly this order.
#
# v8 contract (37 features) — extends v7.1's 28 features with 9 new slots
# from cross-asset correlation and asset fingerprint.
# Slots [13] asset_class_id and [15] asset_volatility_class are still present
# in the tabular vector for backward compat, but v8 models also receive
# asset_class_idx and asset_idx as separate integer IDs routed to nn.Embedding
# layers.
#
# Aligns with the Ruby breakout engine's tabular preparation and
# original normalisation logic.
# This is the canonical contract for Python training and inference.
#
# Index  Feature                  Raw source / notes
# ─────  ───────────────────────  ──────────────────────────────────────────
#  [0]   quality_pct_norm        quality_pct / 100  →  [0, 1]
#  [1]   volume_ratio            breakout bar vol / rolling avg vol
#  [2]   atr_pct                 ATR / close price  (fraction, not %)
#  [3]   cvd_delta               cumulative signed vol / total vol  [-1, 1]
#  [4]   nr7_flag                1 if session range is narrowest of 7
#  [5]   direction_flag          1 = LONG, 0 = SHORT
#  [6]   session_ordinal         Globex day cycle ordinal  [0, 1]
#  [7]   london_overlap_flag     1 if bar hour 08:00–09:00 ET
#  [8]   or_range_atr_ratio      ORB range / ATR  (raw, normalised later)
#  [9]   premarket_range_ratio   premarket range / ORB range  (raw)
#  [10]  bar_of_day              minutes since Globex open / 1380  [0, 1]
#  [11]  day_of_week             weekday Mon=0..Fri=4  / 4  →  [0, 1]
#  [12]  vwap_distance           (price − vwap) / ATR  (raw, normalised later)
#  [13]  asset_class_id          asset class ordinal / 4  →  [0, 1]
#  ── v6 additions (slots 14–17) ──────────────────────────────────────────
#  [14]  breakout_type_ord       BreakoutType.value / 12  →  [0, 1]
#  [15]  asset_volatility_class  low=0.0 / med=0.5 / high=1.0
#  [16]  hour_of_day             ET hour / 23  →  [0, 1]
#  [17]  tp3_atr_mult_norm       TP3 ATR multiplier / 5.0  →  [0, 1]
#  ── v7 additions (slots 18–23) — Daily Strategy layer features ──────────
#  [18]  daily_bias_direction    from bias_analyzer: -1→0, 0→0.5, +1→1.0
#  [19]  daily_bias_confidence   0.0–1.0 scalar from bias analyzer
#  [20]  prior_day_pattern       ordinal of yesterday's candle pattern / 9
#  [21]  weekly_range_position   price position in prior week H/L  [0, 1]
#  [22]  monthly_trend_score     20-day EMA slope [-1,+1] → [0, 1]
#  [23]  crypto_momentum_score   from crypto_momentum: [-1,+1] → [0, 1]
#  ── v7.1 additions (slots 24–27) — sub-feature decomposition ──
#  [24]  breakout_type_category  time-based=0, range-based=0.5, squeeze=1.0
#  [25]  session_overlap_flag    1.0 if London+NY overlap window, else 0.0
#  [26]  atr_trend               ATR expanding=1.0, contracting=0.0 (10-bar)
#  [27]  volume_trend            5-bar volume slope, normalised [0, 1]
#  ── v8-B additions (slots 28–30) — Cross-Asset Correlation features ─────
#  [28]  primary_peer_corr       Pearson r with primary peer, [-1,1] → [0,1]
#  [29]  cross_class_corr        strongest cross-class corr mag, [-1,1] → [0,1]
#  [30]  correlation_regime      0.0=broken, 0.5=normal, 1.0=elevated
#  ── v8-C additions (slots 31–36) — Asset Fingerprint features ───────────
#  [31]  typical_daily_range_norm  median daily range / ATR, clamped [0, 1]
#  [32]  session_concentration   dominant session fraction [0, 1]
#  [33]  breakout_follow_through trailing 20-day breakout win rate [0, 1]
#  [34]  hurst_exponent          mean-reversion tendency [0, 1]
#  [35]  overnight_gap_tendency  median overnight gap / ATR, clamped [0, 1]
#  [36]  volume_profile_shape    volume regularity score [0, 1]
TABULAR_FEATURES: list[str] = [
    "quality_pct_norm",  # [0]  quality / 100
    "volume_ratio",  # [1]  breakout bar vol / avg vol
    "atr_pct",  # [2]  ATR / price
    "cvd_delta",  # [3]  CVD signed ratio [-1, 1]
    "nr7_flag",  # [4]  1 if NR7 session
    "direction_flag",  # [5]  1=LONG 0=SHORT
    "session_ordinal",  # [6]  Globex day position [0, 1]
    "london_overlap_flag",  # [7]  1 if 08:00–09:00 ET overlap
    "or_range_atr_ratio",  # [8]  ORB range / ATR
    "premarket_range_ratio",  # [9]  premarket range / ORB range
    "bar_of_day",  # [10] minutes-since-open / 1380
    "day_of_week",  # [11] Mon=0..Fri=4  / 4
    "vwap_distance",  # [12] (price-vwap) / ATR
    "asset_class_id",  # [13] asset class ordinal / 4
    # ── v6 additions ─────────────────────────────────────────────────────
    "breakout_type_ord",  # [14] BreakoutType ordinal / 12
    "asset_volatility_class",  # [15] low=0 / med=0.5 / high=1
    "hour_of_day",  # [16] ET hour / 23
    "tp3_atr_mult_norm",  # [17] TP3 multiplier / 5
    # ── v7 additions — Daily Strategy layer ──────────────────────────────
    "daily_bias_direction",  # [18] -1→0, 0→0.5, +1→1.0
    "daily_bias_confidence",  # [19] 0.0–1.0 from bias analyzer
    "prior_day_pattern",  # [20] candle pattern ordinal / 9
    "weekly_range_position",  # [21] price in week range [0, 1]
    "monthly_trend_score",  # [22] EMA slope [-1,+1] → [0, 1]
    "crypto_momentum_score",  # [23] crypto lead [-1,+1] → [0, 1]
    # ── v7.1 additions — sub-feature decomposition ──────────────
    "breakout_type_category",  # [24] time=0, range=0.5, squeeze=1.0
    "session_overlap_flag",  # [25] 1.0 if London+NY overlap
    "atr_trend",  # [26] expanding=1.0, contracting=0.0
    "volume_trend",  # [27] 5-bar vol slope [0, 1]
    # ── v8-B additions — Cross-Asset Correlation features ────────────────
    "primary_peer_corr",  # [28] peer correlation [0, 1]
    "cross_class_corr",  # [29] cross-class correlation [0, 1]
    "correlation_regime",  # [30] regime: broken/normal/elevated
    # ── v8-C additions — Asset Fingerprint features ──────────────────────
    "typical_daily_range_norm",  # [31] daily range / ATR [0, 1]
    "session_concentration",  # [32] dominant session frac [0, 1]
    "breakout_follow_through",  # [33] trailing win rate [0, 1]
    "hurst_exponent",  # [34] mean-reversion [0, 1]
    "overnight_gap_tendency",  # [35] gap / ATR [0, 1]
    "volume_profile_shape",  # [36] volume regularity [0, 1]
]

NUM_TABULAR = len(TABULAR_FEATURES)

# Feature contract version — must match the Ruby breakout engine.
# v9 adds:
#   - 3-class output head (0=bad/choppy/no_setup, 1=marginal, 2=good/excellent)
#   - 11-label training scheme (excellent/good/marginal/bad/choppy/no_setup)
#   - RETRAIN-I1 + RETRAIN-I4 label expansion
# v8: hierarchical asset embeddings, 3 cross-asset correlation features,
#     6 asset fingerprint features, architecture upgrades.
FEATURE_CONTRACT_VERSION = 8

# Number of output classes for the 3-class head (RETRAIN-I1).
#   0 = bad / choppy / no_setup  (do not trade)
#   1 = marginal                 (timed out in profit, 0 < R < 1.0)
#   2 = good / excellent         (hit TP1+, R >= 1.0)
NUM_OUTPUT_CLASSES = 3

# Asset class ordinal map — mirrors asset class normalisation logic.
# 0=equity_index, 1=fx, 2=metals_energy, 3=treasuries_ags, 4=crypto
# Normalised as ordinal / 4.0 so the value sits in [0, 1].
ASSET_CLASS_ORDINALS: dict[str, float] = {
    # Equity index micros
    "MES": 0.0 / 4,
    "MNQ": 0.0 / 4,
    "M2K": 0.0 / 4,
    "MYM": 0.0 / 4,
    # FX
    "6E": 1.0 / 4,
    "6B": 1.0 / 4,
    "6J": 1.0 / 4,
    "6A": 1.0 / 4,
    "6C": 1.0 / 4,
    "6S": 1.0 / 4,
    "M6E": 1.0 / 4,
    "M6B": 1.0 / 4,
    # Metals / Energy
    "MGC": 2.0 / 4,
    "SIL": 2.0 / 4,
    "MHG": 2.0 / 4,
    "MCL": 2.0 / 4,
    "MNG": 2.0 / 4,
    # Treasuries / Ags
    "ZN": 3.0 / 4,
    "ZB": 3.0 / 4,
    "ZC": 3.0 / 4,
    "ZS": 3.0 / 4,
    "ZW": 3.0 / 4,
    # Crypto (CME futures)
    "MBT": 4.0 / 4,
    "MET": 4.0 / 4,
    # Crypto (short aliases — used in training symbol lists)
    "BTC": 4.0 / 4,
    "ETH": 4.0 / 4,
    "SOL": 4.0 / 4,
    "LINK": 4.0 / 4,
    "AVAX": 4.0 / 4,
    "DOT": 4.0 / 4,
    "ADA": 4.0 / 4,
    "POL": 4.0 / 4,
    "XRP": 4.0 / 4,
    # Crypto (Kraken internal tickers — KRAKEN: prefix)
    "KRAKEN:XBTUSD": 4.0 / 4,
    "KRAKEN:ETHUSD": 4.0 / 4,
    "KRAKEN:SOLUSD": 4.0 / 4,
    "KRAKEN:LINKUSD": 4.0 / 4,
    "KRAKEN:AVAXUSD": 4.0 / 4,
    "KRAKEN:DOTUSD": 4.0 / 4,
    "KRAKEN:ADAUSD": 4.0 / 4,
    "KRAKEN:POLUSD": 4.0 / 4,
    "KRAKEN:XRPUSD": 4.0 / 4,
}

# Keep BREAKOUT_TYPE_ORDINALS for generate_feature_contract / model_info consumers
# that still reference it by name.  These are not used in the v4 tabular vector.
BREAKOUT_TYPE_ORDINALS: dict[str, float] = {
    "ORB": 0.0 / 12,
    "PDR": 1.0 / 12,
    "IB": 2.0 / 12,
    "CONS": 3.0 / 12,
    "WEEKLY": 4.0 / 12,
    "MONTHLY": 5.0 / 12,
    "ASIAN": 6.0 / 12,
    "BBSQUEEZE": 7.0 / 12,
    "VA": 8.0 / 12,
    "INSIDE": 9.0 / 12,
    "GAP": 10.0 / 12,
    "PIVOT": 11.0 / 12,
    "FIB": 12.0 / 12,
}

# Keep ASSET_VOLATILITY_CLASS for any callers that still reference it by name.
# Not used in the v4 tabular vector (replaced by asset_class_id).
ASSET_VOLATILITY_CLASS: dict[str, float] = {
    "ZN": 0.0,
    "M6B": 0.0,
    "M6E": 0.0,
    "MES": 0.5,
    "MYM": 0.5,
    "MGC": 0.5,
    "MCL": 0.5,
    "SIL": 0.5,
    "M2K": 0.5,
    "MNQ": 1.0,
    "MBT": 1.0,
    "MHG": 1.0,
    # Crypto short aliases
    "BTC": 1.0,
    "ETH": 1.0,
    "SOL": 1.0,
    "LINK": 1.0,
    "AVAX": 1.0,
    "DOT": 1.0,
    "ADA": 1.0,
    "POL": 1.0,
    "XRP": 1.0,
    # Crypto Kraken internal tickers
    "KRAKEN:XBTUSD": 1.0,
    "KRAKEN:ETHUSD": 1.0,
    "KRAKEN:SOLUSD": 1.0,
    "KRAKEN:LINKUSD": 1.0,
    "KRAKEN:AVAXUSD": 1.0,
    "KRAKEN:DOTUSD": 1.0,
    "KRAKEN:ADAUSD": 1.0,
    "KRAKEN:POLUSD": 1.0,
    "KRAKEN:XRPUSD": 1.0,
}

# Image pre-processing — matches ImageNet stats used by EfficientNetV2
IMAGE_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# Inference threshold — probability above this → "send signal"
DEFAULT_THRESHOLD = 0.82

# Per-session inference thresholds.
#
# Rationale: overnight sessions (CME open, Sydney, Tokyo, Shanghai) have
# thinner markets and noisier price action than the primary London / US
# sessions, so we require lower confidence to avoid over-filtering the
# smaller signal pool while still maintaining signal quality.  Daytime
# sessions (London, London-NY, US, CME Settlement) keep the
# full 0.82 bar.
#
# These are *starting* values — tune after 2 weeks of paper-trade data
# by comparing CNN probability distributions per session in Grafana and
# adjusting to match the 58-65% win-rate target.
#
# Keys match ORBSession.key values in orb.py / SESSION_BY_KEY.
SESSION_THRESHOLDS: dict[str, float] = {
    # ── Overnight sessions (18:00–03:00 ET, thin markets) ──────────────
    "cme": 0.75,  # CME Globex re-open 18:00 ET — first bars, wide spread
    "sydney": 0.72,  # Sydney/ASX 18:30 ET — thinnest session
    "tokyo": 0.74,  # Tokyo/TSE 19:00 ET — narrow range, metals/JPY
    "shanghai": 0.74,  # Shanghai/HK 21:00 ET — copper/gold driver
    # ── Primary daytime sessions ────────────────────────────────────────
    "london": 0.82,  # London Open 03:00 ET — PRIMARY, highest conviction
    "london_ny": 0.82,  # London-NY Crossover 08:00 ET — highest volume
    "us": 0.82,  # US Equity Open 09:30 ET — classic ORB session
    "cme_settle": 0.78,  # CME Settlement 14:00 ET — metals/energy only
}


def get_session_threshold(session_key: str | None) -> float:
    """Return the CNN inference threshold for *session_key*.

    Falls back to ``DEFAULT_THRESHOLD`` (0.82) for unknown or None keys.
    This is the single authoritative lookup used by both
    ``predict_breakout()`` and ``predict_breakout_batch()``.

    Args:
        session_key: ORBSession.key string (e.g. "london", "tokyo", "us").
                     None or empty string returns DEFAULT_THRESHOLD.

    Returns:
        Float probability threshold in [0, 1].

    Example::

        >>> get_session_threshold("tokyo")
        0.74
        >>> get_session_threshold("london")
        0.82
        >>> get_session_threshold(None)
        0.82
    """
    if not session_key:
        return DEFAULT_THRESHOLD
    return SESSION_THRESHOLDS.get(session_key.lower().strip(), DEFAULT_THRESHOLD)


# Ordinal session encoding — maps ORBSession.key → float in [0, 1].
# Encodes the session's position in the 24-hour Globex day cycle so the
# tabular head can learn time-of-day patterns.  Used by BreakoutDataset
# and _normalise_tabular_for_inference in place of the old binary
# session_flag (1.0 = US, 0.0 = London).
#
# Ordered chronologically within the Globex day (18:00 ET start):
#   cme(18:00) → sydney(18:30) → tokyo(19:00) → shanghai(21:00) →
#   london(03:00) → london_ny(08:00) →
#   us(09:30) → cme_settle(14:00)
SESSION_ORDINAL: dict[str, float] = {
    "cme": 0.0 / 7,  # 18:00 ET — position 0
    "sydney": 1.0 / 7,  # 18:30 ET — position 1
    "tokyo": 2.0 / 7,  # 19:00 ET — position 2
    "shanghai": 3.0 / 7,  # 21:00 ET — position 3
    "london": 4.0 / 7,  # 03:00 ET — position 4
    "london_ny": 5.0 / 7,  # 08:00 ET — position 5
    "us": 6.0 / 7,  # 09:30 ET — position 6
    "cme_settle": 7.0 / 7,  # 14:00 ET — position 7
}

# Backward-compat aliases so old callers that pass session_flag=1.0 (US)
# or session_flag=0.0 (London) still get sensible ordinal values.
_SESSION_FLAG_COMPAT = {1.0: SESSION_ORDINAL["us"], 0.0: SESSION_ORDINAL["london"]}


def get_session_ordinal(session_key: str | None) -> float:
    """Return the ordinal encoding [0, 1] for *session_key*.

    Falls back to the US session ordinal (0.875) for unknown keys.
    Accepts the legacy float values ``1.0`` (US) and ``0.0`` (London)
    for backward compatibility with old callers.

    Args:
        session_key: ORBSession.key string, or None.

    Returns:
        Float in [0.0, 1.0] representing session position in the Globex day.
    """
    if session_key is None:
        return SESSION_ORDINAL["us"]
    # Legacy float-as-string passthrough (e.g. "1.0", "0.0")
    with contextlib.suppress(ValueError):
        fval = float(session_key)
        if fval in _SESSION_FLAG_COMPAT:
            return _SESSION_FLAG_COMPAT[fval]
    return SESSION_ORDINAL.get(str(session_key).lower().strip(), SESSION_ORDINAL["us"])


# Model output directory
DEFAULT_MODEL_DIR = "models"
MODEL_PREFIX = "breakout_cnn_"

# Asset groups for per-group model selection.
# When a per-asset model (breakout_cnn_best_{SYMBOL}.pt) doesn't exist,
# _resolve_model_name() falls back to a per-group model
# (breakout_cnn_best_{group}.pt) before using the combined champion.
ASSET_GROUPS: dict[str, str] = {
    "MGC": "metals",
    "SIL": "metals",
    "MES": "equity_micros",
    "MNQ": "equity_micros",
    "M2K": "equity_micros",
    "MYM": "equity_micros",
    "ZN": "treasuries",
    "ZB": "treasuries",
    "ZW": "agriculture",
}

# Breakout type → category mapping.
# Categories capture *how* the range is formed:
#   time-based (0.0):    range defined by a fixed time window
#   range-based (0.5):   range defined by prior price levels / structures
#   squeeze-based (1.0): range detected algorithmically via compression
_BREAKOUT_TYPE_CATEGORY: dict[str, float] = {
    # Time-based — fixed session/time windows define the range
    "ORB": 0.0,
    "ASIAN": 0.0,
    "IB": 0.0,
    # Range-based — prior price levels / structures define the range
    "PDR": 0.5,
    "WEEKLY": 0.5,
    "MONTHLY": 0.5,
    "VA": 0.5,
    "INSIDE": 0.5,
    "GAP": 0.5,
    "PIVOT": 0.5,
    "FIB": 0.5,
    # Squeeze-based — algorithmically detected compression
    "CONS": 1.0,
    "BBSQUEEZE": 1.0,
}
