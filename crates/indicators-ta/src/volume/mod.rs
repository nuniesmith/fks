//! Volume indicators: VWAP, ADL, CVD, Chaikin Money Flow, and VZO.

pub mod adl;
pub mod chaikin_money_flow;
pub mod vwap;
pub mod vzo;

pub use adl::Adl;
pub use chaikin_money_flow::ChaikinMoneyFlow;
pub use vwap::Vwap;
pub use vzo::VolumeZoneOscillator;

use crate::registry::IndicatorRegistry;

/// Register all volume indicators with the given registry.
pub fn register_all(reg: &IndicatorRegistry) {
    reg.register("adl", adl::factory);
    reg.register("chaikinmoneyflow", chaikin_money_flow::factory);
    reg.register("vwap", vwap::factory);
    reg.register("vzo", vzo::factory);
}
