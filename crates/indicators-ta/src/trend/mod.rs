//! Trend indicators: moving averages, ATR, MACD, and linear regression.

pub mod atr;
pub mod ema;
pub mod linear_regression;
pub mod macd;
pub mod parabolic_sar;
pub mod sma;
pub mod wma;

pub use atr::Atr;
pub use ema::Ema;
pub use linear_regression::LinearRegression;
pub use macd::Macd;
pub use parabolic_sar::ParabolicSar;
pub use sma::Sma;
pub use wma::Wma;

use crate::registry::IndicatorRegistry;

/// Register all trend indicators with the given registry.
pub fn register_all(reg: &IndicatorRegistry) {
    reg.register("atr", atr::factory);
    reg.register("ema", ema::factory);
    reg.register("linearregression", linear_regression::factory);
    reg.register("macd", macd::factory);
    reg.register("parabolicsar", parabolic_sar::factory);
    reg.register("sma", sma::factory);
    reg.register("wma", wma::factory);
}
