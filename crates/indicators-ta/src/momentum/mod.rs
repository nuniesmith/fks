//! Momentum indicators: RSI, stochastics, Williams %R, and Schaff Trend Cycle.

pub mod rsi;
pub mod schaff_trend_cycle;
pub mod stochastic;
pub mod stochastic_rsi;
pub mod williams_r;

pub use rsi::Rsi;
pub use schaff_trend_cycle::SchaffTrendCycle;
pub use stochastic::Stochastic;
pub use stochastic_rsi::StochasticRsi;
pub use williams_r::WilliamsR;

use crate::registry::IndicatorRegistry;

/// Register all momentum indicators with the given registry.
pub fn register_all(reg: &IndicatorRegistry) {
    reg.register("rsi", rsi::factory);
    reg.register("schafftrendcycle", schaff_trend_cycle::factory);
    reg.register("stochastic", stochastic::factory);
    reg.register("stochasticrsi", stochastic_rsi::factory);
    reg.register("williamsr", williams_r::factory);
}
