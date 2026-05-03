//! Signal pipeline — all 11 indicator layers and final signal aggregation.
//!
//! The layers are organised as follows:
//!
//! | Layer | Module | Type |
//! |-------|--------|------|
//! | L1 VWAP + L2 EMA + L3 SuperTrend + L4 Trend Speed + L9 AO + L10 Hurst + L11 Accel | [`engine`] | [`Indicators`] |
//! | L5 Liquidity Profile | [`liquidity`] | [`LiquidityProfile`] |
//! | L6 Confluence | [`confluence`] | [`ConfluenceEngine`] |
//! | L7 Market Structure + Fibonacci | [`structure`] | [`MarketStructure`] |
//! | L8 CVD | [`cvd`] | [`CVDTracker`] |
//! | Aggregator | [`aggregator`] | [`compute_signal`] · [`SignalStreak`] |
//! | Regime helpers | [`vol_regime`] | [`VolatilityPercentile`] · [`PercentileTracker`] |

pub mod aggregator;
pub mod confluence;
pub mod cvd;
pub mod engine;
pub mod liquidity;
pub mod structure;
pub mod vol_regime;

pub use aggregator::{SignalComponents, SignalIndicator, SignalStreak, compute_signal};
pub use confluence::{ConfluenceEngine, ConfluenceIndicator, ConfluenceParams};
pub use cvd::{CVDTracker, CvdIndicator, CvdParams};
pub use engine::{EngineIndicator, Indicators};
pub use liquidity::{LiquidityIndicator, LiquidityParams, LiquidityProfile};
pub use structure::{MarketStructure, StructureIndicator, StructureParams};
pub use vol_regime::{
    MarketRegimeTracker, PercentileTracker, VolatilityPercentile, VolumeRegime, VolumeRegimeParams,
};

use crate::registry::IndicatorRegistry;

pub fn register_all(reg: &IndicatorRegistry) {
    reg.register("confluence", confluence::factory);
    reg.register("cvd", cvd::factory);
    reg.register("engine", engine::factory);
    reg.register("liquidity", liquidity::factory);
    reg.register("signal", aggregator::factory);
    reg.register("structure", structure::factory);
    reg.register("vol_regime", vol_regime::factory);
}
