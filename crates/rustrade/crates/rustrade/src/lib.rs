//! # rustrade
//!
//! The facade crate of the rustrade trading bot framework. Brings together
//! [`rustrade-core`], [`rustrade-supervisor`], and [`rustrade-risk`] into a
//! single `Bot` type that you instantiate with an exchange adapter and one or
//! more brains.
//!
//! # Quick start
//!
//! ```ignore
//! use std::sync::Arc;
//! use rustrade::{Bot, BotConfig, Brain, ExchangeClient};
//!
//! #[tokio::main]
//! async fn main() -> anyhow::Result<()> {
//!     rustrade::logging::init();
//!
//!     let exchange: Arc<dyn ExchangeClient> = Arc::new(MyKucoinAdapter::new(creds));
//!     let brains: Vec<Arc<dyn Brain>>      = vec![Arc::new(MySarBrain::new(cfg))];
//!
//!     let config = BotConfig::new("my-bot")
//!         .with_close_positions_on_shutdown(true);
//!
//!     Bot::new(config, exchange, brains)
//!         .run_until_shutdown()
//!         .await
//! }
//! ```
//!
//! # What `Bot` does for you
//!
//! - Builds a `Supervisor`, spawns one [`ExecutionService`](execution::ExecutionService)
//!   per brain.
//! - Each execution service subscribes to a [`MarketDataBus`], invokes
//!   `brain.on_event()`, and translates the resulting [`Decision`] into a
//!   call on your `ExchangeClient` — gated by `PositionSizer`,
//!   `CircuitBreaker`, and `SessionPnl` from [`rustrade-risk`].
//! - On Ctrl-C / SIGTERM, runs graceful shutdown and (optionally) closes
//!   open positions before exiting.

pub mod bot;
pub mod execution;
pub mod logging;

pub use bot::{Bot, BotConfig};
pub use execution::ExecutionService;

// Re-export the building blocks so downstream code can `use rustrade::*`.
pub use rustrade_core::{
    Brain, BrainHealth, Candle, Decision, Error, Exchange, ExchangeClient, Fill, MarketDataBus,
    MarketDataEvent, MarketSource, Order, OrderKind, OrderStatus, Position, Price, Result, Side,
    Signal, SignalBus, SignalType, SizeHint, Symbol, Tick, Volume,
};
pub use rustrade_supervisor::{
    BackoffAction, BackoffConfig, BackoffState, MetricsSnapshot, RestartPolicy, ServiceLifecycle,
    ServiceLifecycleSnapshot, ServicePhase, SpawnOptions, Supervisor, SupervisorConfig,
    SupervisorMetrics, TerminationReason, TradingService, TransitionError,
};
pub use rustrade_risk::{
    CircuitBreaker, CircuitBreakerConfig, PositionSizer, SessionPnl, SessionPnlConfig,
    SizingConfig,
};
