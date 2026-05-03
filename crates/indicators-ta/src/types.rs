//! Core domain types: `Candle`, market regime classification, regime config.

use serde::{Deserialize, Serialize};
use std::fmt;

use crate::error::IndicatorError;

// ── MACD
pub type TripleVec = (Vec<f64>, Vec<f64>, Vec<f64>);
pub type MacdResult = Result<TripleVec, IndicatorError>;

// ── Candle ────────────────────────────────────────────────────────────────────

/// One OHLCV bar.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Candle {
    /// Open time in milliseconds (Unix epoch).
    pub time: i64,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: f64,
}

impl Candle {
    /// Parse from a raw 6-element array `[timestamp_ms, open, high, low, close, volume]`
    /// where every element is a JSON string.
    pub fn from_raw(row: &[serde_json::Value]) -> Option<Self> {
        Some(Self {
            time: row.first()?.as_str()?.parse().ok()?,
            open: row.get(1)?.as_str()?.parse().ok()?,
            high: row.get(2)?.as_str()?.parse().ok()?,
            low: row.get(3)?.as_str()?.parse().ok()?,
            close: row.get(4)?.as_str()?.parse().ok()?,
            volume: row.get(5)?.as_str()?.parse().ok()?,
        })
    }

    /// Typical price `(H+L+C)/3`.
    pub fn typical_price(&self) -> f64 {
        (self.high + self.low + self.close) / 3.0
    }

    /// Mid-price `(H+L)/2`.
    pub fn hl2(&self) -> f64 {
        (self.high + self.low) / 2.0
    }

    /// True range against an optional previous close.
    pub fn true_range(&self, prev_close: Option<f64>) -> f64 {
        let hl = self.high - self.low;
        match prev_close {
            Some(pc) => hl.max((self.high - pc).abs()).max((self.low - pc).abs()),
            None => hl,
        }
    }
}

// ── MarketRegime ──────────────────────────────────────────────────────────────

/// Regime classification used by the statistical regime detectors.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum MarketRegime {
    /// Strong directional move — use trend-following.
    Trending(TrendDirection),
    /// Price oscillating around a mean — use mean reversion.
    MeanReverting,
    /// High volatility, no clear direction — reduce exposure.
    Volatile,
    /// Insufficient data or unclear signals.
    #[default]
    Uncertain,
}

impl MarketRegime {
    pub fn is_tradeable(&self) -> bool {
        matches!(
            self,
            MarketRegime::Trending(_) | MarketRegime::MeanReverting
        )
    }

    pub fn size_multiplier(&self) -> f64 {
        match self {
            MarketRegime::Trending(_) => 1.0,
            MarketRegime::MeanReverting => 0.8,
            MarketRegime::Volatile => 0.3,
            MarketRegime::Uncertain => 0.0,
        }
    }

    pub fn recommended_strategy(&self) -> RecommendedStrategy {
        RecommendedStrategy::from(self)
    }
}

impl fmt::Display for MarketRegime {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            MarketRegime::Trending(TrendDirection::Bullish) => write!(f, "Trending (Bullish)"),
            MarketRegime::Trending(TrendDirection::Bearish) => write!(f, "Trending (Bearish)"),
            MarketRegime::MeanReverting => write!(f, "Mean-Reverting"),
            MarketRegime::Volatile => write!(f, "Volatile/Choppy"),
            MarketRegime::Uncertain => write!(f, "Uncertain"),
        }
    }
}

// ── TrendDirection ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum TrendDirection {
    Bullish,
    Bearish,
}

impl fmt::Display for TrendDirection {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            TrendDirection::Bullish => write!(f, "Bullish"),
            TrendDirection::Bearish => write!(f, "Bearish"),
        }
    }
}

// ── RegimeConfidence ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct RegimeConfidence {
    pub regime: MarketRegime,
    pub confidence: f64,
    pub adx_value: f64,
    pub bb_width_percentile: f64,
    pub trend_strength: f64,
}

impl RegimeConfidence {
    pub fn new(regime: MarketRegime, confidence: f64) -> Self {
        Self {
            regime,
            confidence: confidence.clamp(0.0, 1.0),
            adx_value: 0.0,
            bb_width_percentile: 0.0,
            trend_strength: 0.0,
        }
    }

    pub fn with_metrics(
        regime: MarketRegime,
        confidence: f64,
        adx: f64,
        bb_width: f64,
        trend_strength: f64,
    ) -> Self {
        Self {
            regime,
            confidence: confidence.clamp(0.0, 1.0),
            adx_value: adx,
            bb_width_percentile: bb_width,
            trend_strength,
        }
    }

    pub fn is_actionable(&self) -> bool {
        self.confidence >= 0.6
    }
    pub fn is_strong(&self) -> bool {
        self.confidence >= 0.75
    }
}

impl Default for RegimeConfidence {
    fn default() -> Self {
        Self::new(MarketRegime::Uncertain, 0.0)
    }
}

impl fmt::Display for RegimeConfidence {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{} (conf: {:.0}%, ADX: {:.1}, BB%: {:.0}, trend: {:.2})",
            self.regime,
            self.confidence * 100.0,
            self.adx_value,
            self.bb_width_percentile,
            self.trend_strength,
        )
    }
}

// ── RecommendedStrategy ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum RecommendedStrategy {
    TrendFollowing,
    MeanReversion,
    ReducedExposure,
    StayCash,
}

impl From<&MarketRegime> for RecommendedStrategy {
    fn from(regime: &MarketRegime) -> Self {
        match regime {
            MarketRegime::Trending(_) => RecommendedStrategy::TrendFollowing,
            MarketRegime::MeanReverting => RecommendedStrategy::MeanReversion,
            MarketRegime::Volatile => RecommendedStrategy::ReducedExposure,
            MarketRegime::Uncertain => RecommendedStrategy::StayCash,
        }
    }
}

impl fmt::Display for RecommendedStrategy {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            RecommendedStrategy::TrendFollowing => write!(f, "Trend Following"),
            RecommendedStrategy::MeanReversion => write!(f, "Mean Reversion"),
            RecommendedStrategy::ReducedExposure => write!(f, "Reduced Exposure"),
            RecommendedStrategy::StayCash => write!(f, "Stay Cash"),
        }
    }
}

// ── RegimeConfig ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegimeConfig {
    pub adx_period: usize,
    pub adx_trending_threshold: f64,
    pub adx_ranging_threshold: f64,
    pub bb_period: usize,
    pub bb_std_dev: f64,
    pub bb_width_volatility_threshold: f64,
    pub ema_short_period: usize,
    pub ema_long_period: usize,
    pub atr_period: usize,
    pub atr_expansion_threshold: f64,
    pub regime_stability_bars: usize,
    pub min_regime_duration: usize,
}

impl Default for RegimeConfig {
    fn default() -> Self {
        Self {
            adx_period: 14,
            adx_trending_threshold: 25.0,
            adx_ranging_threshold: 20.0,
            bb_period: 20,
            bb_std_dev: 2.0,
            bb_width_volatility_threshold: 75.0,
            ema_short_period: 50,
            ema_long_period: 200,
            atr_period: 14,
            atr_expansion_threshold: 1.5,
            regime_stability_bars: 3,
            min_regime_duration: 5,
        }
    }
}

impl RegimeConfig {
    pub fn crypto_optimized() -> Self {
        Self {
            adx_trending_threshold: 20.0,
            adx_ranging_threshold: 15.0,
            bb_width_volatility_threshold: 70.0,
            ema_short_period: 21,
            ema_long_period: 50,
            atr_expansion_threshold: 1.3,
            regime_stability_bars: 2,
            min_regime_duration: 3,
            ..Default::default()
        }
    }

    pub fn conservative() -> Self {
        Self {
            adx_trending_threshold: 30.0,
            adx_ranging_threshold: 18.0,
            bb_width_volatility_threshold: 80.0,
            atr_expansion_threshold: 2.0,
            regime_stability_bars: 5,
            min_regime_duration: 10,
            ..Default::default()
        }
    }
}
