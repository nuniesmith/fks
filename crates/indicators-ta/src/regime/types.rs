//! Thin re-export of crate-level types used by regime detector internals.
//!
//! Detector modules (detector, ensemble, hmm, primitives) use `super::types::`
//! to reference these types. This file satisfies that path without requiring
//! each file to be updated when the module is reorganised.

pub use crate::types::{
    MarketRegime, RecommendedStrategy, RegimeConfidence, RegimeConfig, TrendDirection,
};
