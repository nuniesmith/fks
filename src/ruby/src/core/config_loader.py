"""
Configuration loader for the multi-asset futures trading bot.

Loads ``infrastructure/config/futures.yaml``, expands ``${ENV_VAR:-default}`` placeholders
from the environment (and ``.env`` if present), and exposes every section
through a typed :class:`FuturesConfig` dataclass.

Usage::

    from services.config_loader import load_config, get_config

    config = load_config()  # first call — parses YAML
    config = get_config()  # subsequent — returns cached singleton

    for key, asset in config.enabled_assets.items():
        print(asset.symbol, asset.leverage)
"""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:  # python-dotenv is optional at import time
    _load_dotenv = None  # type: ignore[assignment]

from utils.logging_config import get_logger

logger = get_logger("config_loader")

# ---------------------------------------------------------------------------
# Regex for ${VAR}, ${VAR:-default}, ${VAR-default}
# ---------------------------------------------------------------------------
_ENV_RE = re.compile(r"\$\{(?P<var>[A-Za-z_][A-Za-z0-9_]*)(?:(?P<sep>:-?|-)(?P<default>[^}]*))?\}")

# Resolve project root (two levels up from this file → futures/)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG_PATH = str(_PROJECT_ROOT / "infrastructure" / "config" / "trading" / "futures.yaml")


# ═══════════════════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class AssetConfig:
    """Per-asset configuration."""

    key: str  # short name used as dict key, e.g. "btc"
    symbol: str = ""
    base: str = ""
    leverage: int = 20
    max_leverage: int = 125
    margin_pct: float = 0.10
    min_order_usdt: float = 0.50
    enabled: bool = True
    sl_pct: float | None = None  # per-asset override; None → use strategy default

    def __repr__(self) -> str:
        state = "ON" if self.enabled else "OFF"
        sl = f", sl={self.sl_pct}" if self.sl_pct is not None else ""
        return (
            f"AssetConfig({self.key} {self.symbol} lev={self.leverage} "
            f"margin={self.margin_pct:.0%} {state}{sl})"
        )


@dataclass
class ExchangeCredentials:
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""


@dataclass
class ExchangeConfig:
    id: str = "kucoinfutures"
    margin_mode: str = "isolated"
    position_mode: str = "one_way"
    credentials: ExchangeCredentials = field(default_factory=ExchangeCredentials)
    session_recycle_sec: int = 21600  # recycle exchange session every 6 hours


@dataclass
class CapitalConfig:
    balance_usdt: float = 0.0
    risk_per_add_pct: float = 0.01
    max_stack: int = 3
    min_order_usdt: float = 0.50


@dataclass
class CorrelationGuardConfig:
    enabled: bool = False
    window: int = 50
    max_correlated_positions: int = 3
    correlation_threshold: float = 0.7


@dataclass
class RiskConfig:
    max_daily_loss_pct: float = 0.05
    max_asset_daily_loss_pct: float = 0.02
    max_consecutive_losses: int = 4
    max_open_trades: int = 3
    cooldown_after_loss_sec: int = 30
    daily_trade_limit: int = 200
    asset_trade_limit: int = 50
    portfolio_max_unrealized_loss_pct: float = 0.03
    max_portfolio_margin_pct: float = 0.80  # halt new entries if total margin > 80% of balance
    consecutive_loss_cooldown_sec: int = 900  # 15 min cooldown after breaker trips
    correlation_guard: CorrelationGuardConfig = field(default_factory=CorrelationGuardConfig)


@dataclass
class MlConfig:
    """Configuration for the CNN signal-gating and portfolio risk layer.

    When ``enabled=False`` (or no model file exists for an asset) the bot
    falls back to the existing rule-based EMA + order-book signal pipeline
    unchanged, so you can deploy before training is complete.
    """

    enabled: bool = True
    models_dir: str = "/app/models"
    min_confidence: float = 0.60  # minimum CNN softmax confidence to act on a signal
    size_scale_by_confidence: bool = True  # multiply lot size by CNN confidence score
    master_risk_threshold: float = 0.65  # MasterCNN score above this halts new entries
    master_check_interval_sec: int = 30  # how often to run the portfolio risk check (seconds)
    adaptive_threshold: bool = True  # enable adaptive confidence threshold
    threshold_learning_rate: float = 0.02  # adjustment per outcome
    threshold_max_adjustment: float = 0.25  # max deviation from base (fraction)
    target_win_rate: float = 0.55  # target win rate for threshold adaptation


@dataclass
class AdlConfig:
    """Auto-Deleveraging protection — monitors KuCoin's ADL ranking and
    automatically reduces leverage when the position is at high ADL risk,
    then restores it once the risk subsides."""

    check_interval_sec: int = 60  # poll KuCoin for ADL this often (only when position open)
    reduce_at_level: int = 4  # reduce leverage when ADL bars >= this (scale 1-5)
    restore_at_level: int = 2  # restore leverage when ADL bars <= this
    leverage_reduce_factor: float = 0.75  # each reduction step: new_lev = int(current * factor)
    min_leverage: int = 2  # never go below this regardless of ADL level


@dataclass
class StrategyConfig:
    fast_ema: int = 8
    slow_ema: int = 21
    tp_pct_base: float = 0.004
    tp_pct_floor: float = 0.002
    sl_pct: float = 0.0035
    imbalance_thresh: float = 1.42
    add_threshold_base: float = 0.002

    # ── Fee-aware trade management ────────────────────────────────
    # Minimum raw price move (as fraction) before a signal-reversal
    # close is allowed.  Must exceed round-trip fees to avoid
    # guaranteed-loss churn.
    # Default 0.15% ≈ 2×(taker 0.06% + slippage 0.01%) + buffer.
    min_profit_close_pct: float = 0.0015

    # Minimum seconds a position must be held before a signal-
    # reversal close is permitted.  TP/SL exits are unaffected.
    min_hold_sec: float = 120.0

    # ── Multi-TP/SL with trailing stop tightening ─────────────────
    multi_tp_enabled: bool = False  # start disabled for backward compat
    multi_tp_levels: list = field(
        default_factory=lambda: [
            {"r_multiple": 1.0, "close_pct": 0.25, "trail_atr": 1.5},
            {"r_multiple": 2.0, "close_pct": 0.50, "trail_atr": 1.0},
            {"r_multiple": 3.0, "close_pct": 0.75, "trail_atr": 0.75},
            {"r_multiple": 5.0, "close_pct": 1.00, "trail_atr": 0.50},
        ]
    )


@dataclass
class WaveConfig:
    ema_period: int = 20
    rma_alpha: float = 0.1
    lookback_waves: int = 200
    quality_min: float = 50.0
    wave_pct_gate: float = 0.40


@dataclass
class AwesomeOscillatorConfig:
    fast: int = 5
    slow: int = 34


@dataclass
class RegimeConfig:
    sma_period: int = 200
    slope_lookback: int = 20
    slope_trending_threshold: float = 1.0
    vol_volatile_threshold: float = 1.5
    vol_ranging_threshold: float = 0.8


@dataclass
class _TPMultiplier:
    base: float = 1.0
    vol_scale: float = 0.3


@dataclass
class VolatilityConfig:
    atr_period: int = 14
    percentile_lookback: int = 200
    tp_multipliers: dict[str, _TPMultiplier] = field(default_factory=dict)
    position_multipliers: dict[str, float] = field(default_factory=dict)
    regime_position_multipliers: dict[str, float] = field(
        default_factory=lambda: {"trending": 1.2, "volatile": 0.5, "ranging": 0.8, "neutral": 1.0}
    )
    entry_filter_min_percentile: float = 0.10
    entry_filter_max_percentile: float = 0.95


@dataclass
class QualityConfig:
    weights: dict[str, int] = field(default_factory=dict)
    vol_mult_high: float = 1.8
    vol_mult_mid: float = 1.2
    vol_mult_low: float = 0.8
    neutral_regime_credit: int = 10


@dataclass
class CandlePatternsConfig:
    enabled: bool = False
    body_ratio_threshold: float = 0.3
    wick_multiplier: float = 2.0
    engulfing_enabled: bool = True
    pin_bar_wick_pct: float = 0.6


@dataclass
class OptunaConfig:
    n_trials: int = 70
    timeout_sec: int = 14
    direction: str = "maximize"
    intervals: dict[str, int] = field(default_factory=dict)
    fast_assets: list[str] = field(default_factory=list)
    slow_assets: list[str] = field(default_factory=list)
    search_space: dict[str, Any] = field(default_factory=dict)
    fees: dict[str, float] = field(default_factory=dict)


@dataclass
class CandlesConfig:
    interval: str = "5s"
    min_ticks: int = 60
    tick_buffer: int = 15000


@dataclass
class StreamsConfig:
    orderbook_depth: int = 20
    orderbook_display: int = 10
    reconnect_delay_sec: int = 2
    reconnect_max_delay_sec: int = 30
    reconnect_backoff_factor: float = 2.0


@dataclass
class RedisConfig:
    url: str = "redis://futures-redis:6379/0"
    password: str = ""
    key_prefix: str = "futures:"
    ttl: dict[str, int] = field(default_factory=dict)
    max_order_history: int = 1000


@dataclass
class SimulationConfig:
    fill_model: str = "last_price"
    slippage_pct: float = 0.0002
    discord_alerts: bool = True
    log_prefix: str = "[SIM]"


@dataclass
class MonitoringConfig:
    heartbeat_interval_sec: int = 300
    loop_sleep_sec: int = 2
    worker_timeout_sec: int = 120
    summary_interval_sec: int = 900


@dataclass
class DiscordConfig:
    webhook_url: str = ""
    enabled: bool = True
    timeout_sec: int = 5
    rate_limit_per_min: int = 25
    colors: dict[str, int] = field(default_factory=dict)
    alerts: dict[str, bool] = field(default_factory=dict)


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file: str | None = None


@dataclass
class DeployConfig:
    platform: str = "linux/arm64"
    restart_policy: str = "unless-stopped"
    log_max_size: str = "10m"
    log_max_files: int = 3


# ═══════════════════════════════════════════════════════════════════════════
# Main config container
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class FuturesConfig:
    """Top-level configuration object for the futures trading bot."""

    mode: str = "sim"
    timezone: str = "America/New_York"

    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    assets: dict[str, AssetConfig] = field(default_factory=dict)
    capital: CapitalConfig = field(default_factory=CapitalConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    adl: AdlConfig = field(default_factory=AdlConfig)
    ml: MlConfig = field(default_factory=MlConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    wave: WaveConfig = field(default_factory=WaveConfig)
    awesome_oscillator: AwesomeOscillatorConfig = field(default_factory=AwesomeOscillatorConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    volatility: VolatilityConfig = field(default_factory=VolatilityConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    candle_patterns: CandlePatternsConfig = field(default_factory=CandlePatternsConfig)
    optuna: OptunaConfig = field(default_factory=OptunaConfig)
    candles: CandlesConfig = field(default_factory=CandlesConfig)
    streams: StreamsConfig = field(default_factory=StreamsConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    deploy: DeployConfig = field(default_factory=DeployConfig)

    # ── Convenience properties ────────────────────────────────────────

    @property
    def enabled_assets(self) -> dict[str, AssetConfig]:
        """Return only assets where ``enabled`` is ``True``."""
        return {k: v for k, v in self.assets.items() if v.enabled}

    @property
    def redis_url(self) -> str:
        return self.redis.url

    @property
    def redis_password(self) -> str:
        return self.redis.password

    @property
    def is_sim(self) -> bool:
        return self.mode == "sim"

    @property
    def is_live(self) -> bool:
        return self.mode == "live"


# ═══════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════


def _expand_env_vars(value: str) -> str:
    """Replace ``${VAR:-default}`` patterns with environment values."""

    def _replacer(match: re.Match) -> str:
        var = match.group("var")
        sep = match.group("sep")
        default = match.group("default")

        env_val = os.environ.get(var)

        # ${VAR:-default} → use default if VAR is unset *or* empty
        # ${VAR-default}  → use default only if VAR is unset
        if sep == ":-":
            if env_val is None or env_val == "":
                return default if default is not None else ""
            return env_val
        elif sep == "-":
            if env_val is None:
                return default if default is not None else ""
            return env_val
        else:
            # No separator — just ${VAR}
            if env_val is not None:
                return env_val
            logger.warning("env var %s is not set and has no default", var)
            return ""

    return _ENV_RE.sub(_replacer, value)


def _walk_and_expand(obj: Any) -> Any:
    """Recursively expand env vars in all string values of a nested structure."""
    if isinstance(obj, str):
        return _expand_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _walk_and_expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_and_expand(item) for item in obj]
    return obj


def _safe_get(d: dict, key: str, default: Any = None) -> Any:
    """Get from dict, returning *default* if d is None or key missing."""
    if d is None:
        return default
    return d.get(key, default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return default


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


# ═══════════════════════════════════════════════════════════════════════════
# Section builders
# ═══════════════════════════════════════════════════════════════════════════


def _build_asset(key: str, raw: dict) -> AssetConfig:
    if raw is None:
        raw = {}
    sl_raw = raw.get("sl_pct")
    sl_pct: float | None = None
    if sl_raw is not None:
        try:
            sl_pct = float(sl_raw)
        except (TypeError, ValueError):
            pass
    return AssetConfig(
        key=key,
        symbol=_safe_str(raw.get("symbol"), key.upper() + "USDTM"),
        base=_safe_str(raw.get("base"), key.upper()),
        leverage=_safe_int(raw.get("leverage"), 20),
        max_leverage=_safe_int(raw.get("max_leverage"), 125),
        margin_pct=_safe_float(raw.get("margin_pct"), 0.10),
        min_order_usdt=_safe_float(raw.get("min_order_usdt"), 0.50),
        enabled=_safe_bool(raw.get("enabled"), True),
        sl_pct=sl_pct,
    )


def _build_exchange(raw: dict | None) -> ExchangeConfig:
    if raw is None:
        return ExchangeConfig()
    creds_raw = raw.get("credentials") or {}
    creds = ExchangeCredentials(
        api_key=_safe_str(creds_raw.get("api_key")),
        api_secret=_safe_str(creds_raw.get("api_secret")),
        passphrase=_safe_str(creds_raw.get("passphrase")),
    )
    return ExchangeConfig(
        id=_safe_str(raw.get("id"), "kucoinfutures"),
        margin_mode=_safe_str(raw.get("margin_mode"), "isolated"),
        position_mode=_safe_str(raw.get("position_mode"), "one_way"),
        credentials=creds,
        session_recycle_sec=_safe_int(raw.get("session_recycle_sec"), 21600),
    )


def _build_capital(raw: dict | None) -> CapitalConfig:
    if raw is None:
        return CapitalConfig()
    return CapitalConfig(
        balance_usdt=_safe_float(raw.get("balance_usdt"), 0.0),
        risk_per_add_pct=_safe_float(raw.get("risk_per_add_pct"), 0.01),
        max_stack=_safe_int(raw.get("max_stack"), 3),
        min_order_usdt=_safe_float(raw.get("min_order_usdt"), 0.50),
    )


def _build_risk(raw: dict | None) -> RiskConfig:
    if raw is None:
        return RiskConfig()
    cg_raw = _safe_get(raw, "correlation_guard") or {}
    return RiskConfig(
        max_daily_loss_pct=_safe_float(raw.get("max_daily_loss_pct"), 0.05),
        max_asset_daily_loss_pct=_safe_float(raw.get("max_asset_daily_loss_pct"), 0.02),
        max_consecutive_losses=_safe_int(raw.get("max_consecutive_losses"), 4),
        max_open_trades=_safe_int(raw.get("max_open_trades"), 3),
        cooldown_after_loss_sec=_safe_int(raw.get("cooldown_after_loss_sec"), 30),
        daily_trade_limit=_safe_int(raw.get("daily_trade_limit"), 200),
        asset_trade_limit=_safe_int(raw.get("asset_trade_limit"), 50),
        portfolio_max_unrealized_loss_pct=_safe_float(
            raw.get("portfolio_max_unrealized_loss_pct"), 0.03
        ),
        max_portfolio_margin_pct=_safe_float(raw.get("max_portfolio_margin_pct"), 0.80),
        consecutive_loss_cooldown_sec=_safe_int(raw.get("consecutive_loss_cooldown_sec"), 900),
        correlation_guard=CorrelationGuardConfig(
            enabled=_safe_bool(cg_raw.get("enabled"), False),
            window=_safe_int(cg_raw.get("window"), 50),
            max_correlated_positions=_safe_int(cg_raw.get("max_correlated_positions"), 3),
            correlation_threshold=_safe_float(cg_raw.get("correlation_threshold"), 0.7),
        ),
    )


def _build_ml(raw: dict | None) -> MlConfig:
    if raw is None:
        return MlConfig()
    return MlConfig(
        enabled=_safe_bool(raw.get("enabled"), True),
        models_dir=_safe_str(raw.get("models_dir"), "/app/models"),
        min_confidence=_safe_float(raw.get("min_confidence"), 0.60),
        size_scale_by_confidence=_safe_bool(raw.get("size_scale_by_confidence"), True),
        master_risk_threshold=_safe_float(raw.get("master_risk_threshold"), 0.65),
        master_check_interval_sec=_safe_int(raw.get("master_check_interval_sec"), 30),
        adaptive_threshold=_safe_bool(raw.get("adaptive_threshold"), True),
        threshold_learning_rate=_safe_float(raw.get("threshold_learning_rate"), 0.02),
        threshold_max_adjustment=_safe_float(raw.get("threshold_max_adjustment"), 0.25),
        target_win_rate=_safe_float(raw.get("target_win_rate"), 0.55),
    )


def _build_adl(raw: dict | None) -> AdlConfig:
    if raw is None:
        return AdlConfig()
    return AdlConfig(
        check_interval_sec=_safe_int(raw.get("check_interval_sec"), 60),
        reduce_at_level=_safe_int(raw.get("reduce_at_level"), 4),
        restore_at_level=_safe_int(raw.get("restore_at_level"), 2),
        leverage_reduce_factor=_safe_float(raw.get("leverage_reduce_factor"), 0.75),
        min_leverage=_safe_int(raw.get("min_leverage"), 2),
    )


def _build_strategy(raw: dict | None) -> StrategyConfig:
    if raw is None:
        return StrategyConfig()

    # Parse multi_tp block — supports nested dict or flat keys
    multi_tp_raw = raw.get("multi_tp", {})
    if isinstance(multi_tp_raw, dict):
        multi_tp_enabled = _safe_bool(multi_tp_raw.get("enabled"), False)
        multi_tp_levels = multi_tp_raw.get("levels", [])
    else:
        multi_tp_enabled = _safe_bool(raw.get("multi_tp_enabled"), False)
        multi_tp_levels = []

    return StrategyConfig(
        fast_ema=_safe_int(raw.get("fast_ema"), 8),
        slow_ema=_safe_int(raw.get("slow_ema"), 21),
        tp_pct_base=_safe_float(raw.get("tp_pct_base"), 0.004),
        sl_pct=_safe_float(raw.get("sl_pct"), 0.0035),
        imbalance_thresh=_safe_float(raw.get("imbalance_thresh"), 1.42),
        add_threshold_base=_safe_float(raw.get("add_threshold_base"), 0.002),
        tp_pct_floor=_safe_float(raw.get("tp_pct_floor"), 0.002),
        min_profit_close_pct=_safe_float(raw.get("min_profit_close_pct"), 0.0015),
        min_hold_sec=_safe_float(raw.get("min_hold_sec"), 120.0),
        multi_tp_enabled=multi_tp_enabled,
        multi_tp_levels=multi_tp_levels
        if multi_tp_levels
        else StrategyConfig.__dataclass_fields__["multi_tp_levels"].default_factory(),
    )


def _build_wave(raw: dict | None) -> WaveConfig:
    if raw is None:
        return WaveConfig()
    return WaveConfig(
        ema_period=_safe_int(raw.get("ema_period"), 20),
        rma_alpha=_safe_float(raw.get("rma_alpha"), 0.1),
        lookback_waves=_safe_int(raw.get("lookback_waves"), 200),
        quality_min=_safe_float(raw.get("quality_min"), 50.0),
        wave_pct_gate=_safe_float(raw.get("wave_pct_gate"), 0.40),
    )


def _build_ao(raw: dict | None) -> AwesomeOscillatorConfig:
    if raw is None:
        return AwesomeOscillatorConfig()
    return AwesomeOscillatorConfig(
        fast=_safe_int(raw.get("fast"), 5),
        slow=_safe_int(raw.get("slow"), 34),
    )


def _build_regime(raw: dict | None) -> RegimeConfig:
    if raw is None:
        return RegimeConfig()
    return RegimeConfig(
        sma_period=_safe_int(raw.get("sma_period"), 200),
        slope_lookback=_safe_int(raw.get("slope_lookback"), 20),
        slope_trending_threshold=_safe_float(raw.get("slope_trending_threshold"), 1.0),
        vol_volatile_threshold=_safe_float(raw.get("vol_volatile_threshold"), 1.5),
        vol_ranging_threshold=_safe_float(raw.get("vol_ranging_threshold"), 0.8),
    )


def _build_volatility(raw: dict | None) -> VolatilityConfig:
    if raw is None:
        return VolatilityConfig()

    # tp_multipliers
    tp_raw = raw.get("tp_multipliers") or {}
    tp_mults: dict[str, _TPMultiplier] = {}
    for regime_name, vals in tp_raw.items():
        if isinstance(vals, dict):
            tp_mults[regime_name] = _TPMultiplier(
                base=_safe_float(vals.get("base"), 1.0),
                vol_scale=_safe_float(vals.get("vol_scale"), 0.3),
            )

    pos_raw = raw.get("position_multipliers") or {}
    pos_mults = {k: _safe_float(v, 1.0) for k, v in pos_raw.items()}

    regime_pos_raw = raw.get("regime_position_multipliers") or {}
    regime_pos_mults = {k.lower(): _safe_float(v, 1.0) for k, v in regime_pos_raw.items()}

    ef = raw.get("entry_filter") or {}
    return VolatilityConfig(
        atr_period=_safe_int(raw.get("atr_period"), 14),
        percentile_lookback=_safe_int(raw.get("percentile_lookback"), 200),
        tp_multipliers=tp_mults,
        position_multipliers=pos_mults,
        regime_position_multipliers=regime_pos_mults
        if regime_pos_mults
        else {"trending": 1.2, "volatile": 0.5, "ranging": 0.8, "neutral": 1.0},
        entry_filter_min_percentile=_safe_float(ef.get("min_percentile"), 0.10),
        entry_filter_max_percentile=_safe_float(ef.get("max_percentile"), 0.95),
    )


def _build_quality(raw: dict | None) -> QualityConfig:
    if raw is None:
        return QualityConfig()
    weights_raw = raw.get("weights") or {}
    weights = {k: _safe_int(v, 0) for k, v in weights_raw.items()}
    return QualityConfig(
        weights=weights,
        vol_mult_high=_safe_float(raw.get("vol_mult_high"), 1.8),
        vol_mult_mid=_safe_float(raw.get("vol_mult_mid"), 1.2),
        vol_mult_low=_safe_float(raw.get("vol_mult_low"), 0.8),
        neutral_regime_credit=_safe_int(raw.get("neutral_regime_credit"), 10),
    )


def _build_candle_patterns(raw: dict | None) -> CandlePatternsConfig:
    if raw is None:
        return CandlePatternsConfig()
    return CandlePatternsConfig(
        enabled=_safe_bool(raw.get("enabled"), False),
        body_ratio_threshold=_safe_float(raw.get("body_ratio_threshold"), 0.3),
        wick_multiplier=_safe_float(raw.get("wick_multiplier"), 2.0),
        engulfing_enabled=_safe_bool(raw.get("engulfing_enabled"), True),
        pin_bar_wick_pct=_safe_float(raw.get("pin_bar_wick_pct"), 0.6),
    )


def _build_optuna(raw: dict | None) -> OptunaConfig:
    if raw is None:
        return OptunaConfig()
    intervals_raw = raw.get("intervals") or {}
    intervals = {k: _safe_int(v, 1200) for k, v in intervals_raw.items()}
    fast_assets = raw.get("fast_assets") or []
    slow_assets = raw.get("slow_assets") or []
    search_space = raw.get("search_space") or {}
    fees = raw.get("fees") or {}
    fees_typed = {k: _safe_float(v, 0.0) for k, v in fees.items()}
    return OptunaConfig(
        n_trials=_safe_int(raw.get("n_trials"), 70),
        timeout_sec=_safe_int(raw.get("timeout_sec"), 14),
        direction=_safe_str(raw.get("direction"), "maximize"),
        intervals=intervals,
        fast_assets=list(fast_assets),
        slow_assets=list(slow_assets),
        search_space=dict(search_space),
        fees=fees_typed,
    )


def _build_candles(raw: dict | None) -> CandlesConfig:
    if raw is None:
        return CandlesConfig()
    return CandlesConfig(
        interval=_safe_str(raw.get("interval"), "5s"),
        min_ticks=_safe_int(raw.get("min_ticks"), 60),
        tick_buffer=_safe_int(raw.get("tick_buffer"), 15000),
    )


def _build_streams(raw: dict | None) -> StreamsConfig:
    if raw is None:
        return StreamsConfig()
    return StreamsConfig(
        orderbook_depth=_safe_int(raw.get("orderbook_depth"), 20),
        orderbook_display=_safe_int(raw.get("orderbook_display"), 10),
        reconnect_delay_sec=_safe_int(raw.get("reconnect_delay_sec"), 2),
        reconnect_max_delay_sec=_safe_int(raw.get("reconnect_max_delay_sec"), 30),
        reconnect_backoff_factor=_safe_float(raw.get("reconnect_backoff_factor"), 2.0),
    )


def _build_redis(raw: dict | None) -> RedisConfig:
    if raw is None:
        return RedisConfig()
    ttl_raw = raw.get("ttl") or {}
    ttl = {k: _safe_int(v, 0) for k, v in ttl_raw.items()}
    return RedisConfig(
        url=_safe_str(raw.get("url"), "redis://futures-redis:6379/0"),
        password=_safe_str(raw.get("password")),
        key_prefix=_safe_str(raw.get("key_prefix"), "futures:"),
        ttl=ttl,
        max_order_history=_safe_int(raw.get("max_order_history"), 1000),
    )


def _build_simulation(raw: dict | None) -> SimulationConfig:
    if raw is None:
        return SimulationConfig()
    return SimulationConfig(
        fill_model=_safe_str(raw.get("fill_model"), "last_price"),
        slippage_pct=_safe_float(raw.get("slippage_pct"), 0.0002),
        discord_alerts=_safe_bool(raw.get("discord_alerts"), True),
        log_prefix=_safe_str(raw.get("log_prefix"), "[SIM]"),
    )


def _build_monitoring(raw: dict | None) -> MonitoringConfig:
    if raw is None:
        return MonitoringConfig()
    return MonitoringConfig(
        heartbeat_interval_sec=_safe_int(raw.get("heartbeat_interval_sec"), 300),
        loop_sleep_sec=_safe_int(raw.get("loop_sleep_sec"), 2),
        worker_timeout_sec=_safe_int(raw.get("worker_timeout_sec"), 120),
        summary_interval_sec=_safe_int(raw.get("summary_interval_sec"), 900),
    )


def _build_discord(raw: dict | None) -> DiscordConfig:
    if raw is None:
        return DiscordConfig()
    colors_raw = raw.get("colors") or {}
    colors: dict[str, int] = {}
    for name, val in colors_raw.items():
        if isinstance(val, int):
            colors[name] = val
        elif isinstance(val, str):
            try:
                colors[name] = int(val, 0)
            except ValueError:
                colors[name] = 0
    alerts_raw = raw.get("alerts") or {}
    alerts = {k: _safe_bool(v, True) for k, v in alerts_raw.items()}
    return DiscordConfig(
        webhook_url=_safe_str(raw.get("webhook_url")),
        enabled=_safe_bool(raw.get("enabled"), True),
        timeout_sec=_safe_int(raw.get("timeout_sec"), 5),
        rate_limit_per_min=_safe_int(raw.get("rate_limit_per_min"), 25),
        colors=colors,
        alerts=alerts,
    )


def _build_logging_cfg(raw: dict | None) -> LoggingConfig:
    if raw is None:
        return LoggingConfig()
    file_val = raw.get("file")
    return LoggingConfig(
        level=_safe_str(raw.get("level"), "INFO").upper(),
        format=_safe_str(
            raw.get("format"),
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        ),
        file=file_val if isinstance(file_val, str) else None,
    )


def _build_deploy(raw: dict | None) -> DeployConfig:
    if raw is None:
        return DeployConfig()
    return DeployConfig(
        platform=_safe_str(raw.get("platform"), "linux/arm64"),
        restart_policy=_safe_str(raw.get("restart_policy"), "unless-stopped"),
        log_max_size=_safe_str(raw.get("log_max_size"), "10m"),
        log_max_files=_safe_int(raw.get("log_max_files"), 3),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

_singleton: FuturesConfig | None = None
_lock = threading.Lock()


def load_config(path: str | None = None) -> FuturesConfig:
    """Parse *path* (default ``infrastructure/config/futures.yaml``) and return a
    :class:`FuturesConfig` instance.

    Environment variables referenced as ``${VAR:-default}`` are expanded
    from ``os.environ`` (and ``.env`` if *python-dotenv* is installed).

    Each call re-reads the file and updates the singleton cache so that
    ``get_config()`` returns the latest version.
    """
    global _singleton

    # Load .env if python-dotenv is available
    if _load_dotenv is not None:
        env_path = _PROJECT_ROOT / ".env"
        if env_path.is_file():
            _load_dotenv(dotenv_path=str(env_path), override=False)
            logger.debug("loaded .env from %s", env_path)

    config_path = path or _DEFAULT_CONFIG_PATH
    logger.info("loading config from %s", config_path)

    try:
        with open(config_path, encoding="utf-8") as fh:
            raw_text = fh.read()
    except FileNotFoundError:
        logger.error("config file not found: %s — using all defaults", config_path)
        cfg = FuturesConfig()
        with _lock:
            _singleton = cfg
        return cfg
    except OSError as exc:
        logger.error("cannot read config file %s: %s — using all defaults", config_path, exc)
        cfg = FuturesConfig()
        with _lock:
            _singleton = cfg
        return cfg

    # Expand env vars in the raw YAML text before parsing
    expanded_text = _walk_and_expand(raw_text)

    try:
        data: dict = yaml.safe_load(expanded_text) or {}
    except yaml.YAMLError as exc:
        logger.error("YAML parse error in %s: %s — using all defaults", config_path, exc)
        cfg = FuturesConfig()
        with _lock:
            _singleton = cfg
        return cfg

    if not isinstance(data, dict):
        logger.error("config root is not a mapping — using all defaults")
        data = {}

    # Build assets dict
    assets_raw = data.get("assets") or {}
    assets: dict[str, AssetConfig] = {}
    for key, adict in assets_raw.items():
        assets[key] = _build_asset(key, adict or {})

    mode_raw = _safe_str(data.get("mode"), "sim").strip().lower()
    if mode_raw not in ("sim", "live"):
        logger.warning("unknown mode '%s' — defaulting to 'sim'", mode_raw)
        mode_raw = "sim"

    cfg = FuturesConfig(
        mode=mode_raw,
        timezone=_safe_str(data.get("timezone"), "America/New_York"),
        exchange=_build_exchange(data.get("exchange")),
        assets=assets,
        capital=_build_capital(data.get("capital")),
        risk=_build_risk(data.get("risk")),
        adl=_build_adl(data.get("adl")),
        ml=_build_ml(data.get("ml")),
        strategy=_build_strategy(data.get("strategy")),
        wave=_build_wave(data.get("wave")),
        awesome_oscillator=_build_ao(data.get("awesome_oscillator")),
        regime=_build_regime(data.get("regime")),
        volatility=_build_volatility(data.get("volatility")),
        quality=_build_quality(data.get("quality")),
        candle_patterns=_build_candle_patterns(data.get("candle_patterns")),
        optuna=_build_optuna(data.get("optuna")),
        candles=_build_candles(data.get("candles")),
        streams=_build_streams(data.get("streams")),
        redis=_build_redis(data.get("redis")),
        simulation=_build_simulation(data.get("simulation")),
        monitoring=_build_monitoring(data.get("monitoring")),
        discord=_build_discord(data.get("discord")),
        logging=_build_logging_cfg(data.get("logging")),
        deploy=_build_deploy(data.get("deploy")),
    )

    with _lock:
        _singleton = cfg

    n_enabled = len(cfg.enabled_assets)
    n_total = len(cfg.assets)
    capital_str = "live (from KuCoin)" if cfg.mode == "live" else f"${cfg.capital.balance_usdt:.2f}"
    logger.info(
        "config loaded — mode=%s, %d/%d assets enabled, capital=%s",
        cfg.mode,
        n_enabled,
        n_total,
        capital_str,
    )

    return cfg


def get_config() -> FuturesConfig:
    """Return the cached :class:`FuturesConfig` singleton.

    If ``load_config()`` has not been called yet, it is invoked with the
    default path automatically.
    """
    global _singleton
    if _singleton is not None:
        return _singleton
    with _lock:
        # Double-check after acquiring the lock
        if _singleton is not None:
            return _singleton
        return load_config()
