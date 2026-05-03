//! Bot runtime modules.
//!
//! Signal math → `indicators` crate.
//! Exchange I/O → `exchange_apiws` crate.
//! This module wires them: state, sizing, execution, breaker, P&L.

pub mod candle_poller;
pub mod circuit_breaker;
pub mod execute;
pub mod pnl;
pub mod rolling_indicators;
pub mod sizing;
pub mod state;
pub mod strategy;
