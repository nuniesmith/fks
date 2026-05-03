//! # indicators — Technical Indicators + Market Regime Detection

// ── Core types & traits ───────────────────────────────────────────────────────
pub mod error;
pub mod functions;
pub mod indicator;
pub mod indicator_config;
pub mod registry;
pub mod types;

// ── Indicator categories ──────────────────────────────────────────────────────
pub mod momentum;
pub mod trend;
pub mod volatility;
pub mod volume;

// ── Signal pipeline ───────────────────────────────────────────────────────────
pub mod signal;

// ── Regime detection ─────────────────────────────────────────────────────────
pub mod regime;

// ── Re-exports: core ─────────────────────────────────────────────────────────
pub use functions::{ATR, EMA, IndicatorCalculator, StrategyIndicators};
pub use functions::{atr, ema, macd, rsi, sma, true_range};
pub use indicator::{Indicator, IndicatorOutput, PriceColumn};
pub use indicator_config::IndicatorConfig;
// IndexMap backs IndicatorOutput::into_inner(); re-exported so callers don't
// need a direct `indexmap` dependency in their Cargo.toml.
pub use indexmap::IndexMap;
pub use registry::IndicatorRegistry;
pub use types::{
    Candle, MarketRegime, RecommendedStrategy, RegimeConfidence, RegimeConfig, TrendDirection,
};

// ── Re-exports: momentum ─────────────────────────────────────────────────────
pub use momentum::{Rsi, Stochastic, StochasticRsi};

// ── Re-exports: signal pipeline ──────────────────────────────────────────────
pub use signal::CVDTracker;
pub use signal::ConfluenceEngine;
pub use signal::Indicators;
pub use signal::LiquidityProfile;
pub use signal::MarketStructure;
pub use signal::{MarketRegimeTracker, PercentileTracker, VolatilityPercentile};
pub use signal::{SignalComponents, SignalStreak, compute_signal};
// Indicator wrappers for the signal pipeline
pub use signal::EngineIndicator;
pub use signal::SignalIndicator;
pub use signal::{ConfluenceIndicator, ConfluenceParams};
pub use signal::{CvdIndicator, CvdParams};
pub use signal::{LiquidityIndicator, LiquidityParams};
pub use signal::{StructureIndicator, StructureParams};
pub use signal::{VolumeRegime, VolumeRegimeParams};

// ── Re-exports: regime detection ─────────────────────────────────────────────
pub use regime::RegimeDetector;
/// Internal Bollinger Bands used by the regime detector (incremental, not batch).
/// For the batch `Indicator` impl see [`volatility::BollingerBands`].
pub use regime::{ADX, BollingerBands, BollingerBandsValues, RSI};
pub use regime::{
    ActiveStrategy, AssetSummary, DetectionMethod, EnhancedRouter, EnhancedRouterConfig,
    RoutedSignal,
};
pub use regime::{EnsembleConfig, EnsembleRegimeDetector, EnsembleResult, EnsembleStatus};
pub use regime::{HMMConfig, HMMRegimeDetector};
// Indicator wrappers for regime detection
pub use regime::DetectorIndicator;
pub use regime::EnsembleIndicator;
pub use regime::HmmIndicator;
pub use regime::RouterIndicator;
pub use regime::{
    AdxIndicator, AtrPrimIndicator, BbPrimIndicator, EmaPrimIndicator, RsiPrimIndicator,
};
