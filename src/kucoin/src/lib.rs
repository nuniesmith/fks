//! `kucoin` — Bot runtime: strategy orchestration, order execution, notifications.
//!
//! All math lives in `indicators-ta`  → `use indicators::*`
//! All exchange I/O lives in `exchange-apiws` → `use exchange_apiws::*`
//! This crate wires them together into a live trading runtime.
//!
//! # Module layout
//! ```text
//! kucoin
//! ├── bot/
//! │   ├── state          — BotState: live position + candle window
//! │   ├── candle_poller  — REST seed + live tick→candle stitching
//! │   ├── sizing         — contract count from balance + risk params
//! │   ├── pnl            — realized P&L bookkeeping
//! │   ├── execute        — place / close orders via exchange_apiws
//! │   └── circuit_breaker — consecutive-loss cutoff
//! ├── config   — RuntimeConfig: Redis URL, Discord webhook, env routing
//! ├── error    — BotError
//! ├── notify/
//! │   ├── discord        — Discord webhook notifications
//! │   └── redis_store    — state persistence
//! └── types    — BotPosition, BotFill, Position(i32) runtime shims
//! ```

pub mod bot;
pub mod config;
pub mod error;
pub mod notify;
pub mod settings;
pub mod types;

// ── Re-exports from published crates ─────────────────────────────────────────
pub use error::BotError;
pub use exchange_apiws::{Credentials, KuCoinClient, KucoinEnv};
pub use settings::BotSettings;
