//! # rustrade-backtest
//!
//! A replay engine for the rustrade framework.
//!
//! The headline guarantee is **brain portability**: any `Brain` that runs in
//! production via [`rustrade::Bot`] runs in a backtest with zero code changes.
//! The backtest engine consumes the same [`MarketDataEvent`]s, calls
//! `brain.on_event()` exactly the same way, and dispatches `Decision`s to a
//! [`SimExchange`] that implements the same [`ExchangeClient`] trait the live
//! adapter does.
//!
//! [`MarketDataEvent`]: rustrade_core::MarketDataEvent
//! [`ExchangeClient`]: rustrade_core::ExchangeClient
//!
//! # Quick start
//!
//! ```ignore
//! use rustrade_backtest::{BacktestEngine, BacktestConfig, SimExchange, SimExchangeConfig};
//!
//! let candles = load_candles_somehow();
//! let brain = Arc::new(MySarBrain::new(...));
//!
//! let metrics = BacktestEngine::new(
//!         BacktestConfig::default(),
//!         SimExchange::new(SimExchangeConfig::default()),
//!         brain,
//!     )
//!     .run("BTCUSDT", candles)
//!     .await?;
//!
//! println!("Sharpe = {:.2}, max drawdown = {:.2}%", metrics.sharpe, metrics.max_drawdown_pct);
//! ```
//!
//! # What's in this crate
//!
//! - [`BacktestEngine`] — replay loop: feeds candles into a brain, dispatches
//!   decisions to the sim exchange, accumulates metrics.
//! - [`SimExchange`] — in-memory [`ExchangeClient`] impl. Fills orders at the
//!   next bar's open with configurable slippage + commission. Tracks equity,
//!   open positions, and a fill log.
//! - [`BacktestMetrics`] — total return, win rate, max drawdown, profit factor,
//!   Sharpe, Sortino. Computed from the equity curve at the end of the run.
//!
//! # What's *not* in this crate
//!
//! - **Data loaders** (parquet, CSV) — write your own `Vec<Candle>` from
//!   whatever storage you use. A future feature-gated `loader` module can
//!   add polars-based parquet/CSV adapters.
//! - **Vectorized indicators** — `indicators-ta` already covers this if
//!   you need batch math.
//! - **Multi-asset / multi-strategy** orchestration — for now, one brain,
//!   one symbol, one stream. Run multiple engines in parallel for
//!   ensemble or parameter-sweep work.

pub mod engine;
pub mod metrics;
pub mod sim_exchange;

pub use engine::{BacktestConfig, BacktestEngine, BacktestError, BacktestRun};
pub use metrics::{BacktestMetrics, EquityPoint, TradeRecord};
pub use sim_exchange::{SimExchange, SimExchangeConfig, SimExchangeError};
