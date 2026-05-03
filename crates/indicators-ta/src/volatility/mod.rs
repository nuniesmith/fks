//! Volatility indicators: Bollinger Bands, Keltner Channels, choppiness, Elder Ray, market cycle.

pub mod bollinger;
pub mod choppiness_index;
pub mod elder_ray_index;
pub mod keltner_channels;
pub mod market_cycle;

pub use bollinger::BollingerBands;
pub use choppiness_index::ChoppinessIndex;
pub use elder_ray_index::ElderRayIndex;
pub use keltner_channels::KeltnerChannels;
pub use market_cycle::MarketCycle;

use crate::registry::IndicatorRegistry;

/// Register all volatility indicators with the given registry.
pub fn register_all(reg: &IndicatorRegistry) {
    reg.register("bollingerbands", bollinger::factory);
    reg.register("choppinessindex", choppiness_index::factory);
    reg.register("elderrayindex", elder_ray_index::factory);
    reg.register("keltnerchannels", keltner_channels::factory);
    reg.register("marketcycle", market_cycle::factory);
}
