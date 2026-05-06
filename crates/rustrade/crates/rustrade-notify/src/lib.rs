//! # rustrade-notify
//!
//! Webhook-style notifications as supervised [`TradingService`]s.
//!
//! [`TradingService`]: rustrade_supervisor::TradingService
//!
//! # Why a separate crate?
//!
//! Trading bots want lifecycle telemetry — "bot started", periodic
//! heartbeats, "circuit breaker tripped" — in a place humans actually
//! see (Discord, Slack, PagerDuty). This crate provides:
//!
//! - The narrow [`Notifier`] trait — `async fn notify(&self, msg: &str)`.
//! - A built-in [`DiscordNotifier`] (feature `discord`, default-on).
//! - A [`WebhookHeartbeatService`] — a [`TradingService`] that posts
//!   a periodic heartbeat through any [`Notifier`].
//! - A test-only [`InMemoryNotifier`] for assertions in unit tests.
//!
//! It deliberately does **not** wire itself into [`rustrade::ExecutionService`].
//! Notification policy (which events to send, what content) is bot-specific;
//! this crate ships the pipes, not the editorial choices.
//!
//! # Quick start (Discord)
//!
//! ```ignore
//! use std::sync::Arc;
//! use std::time::Duration;
//! use rustrade_notify::{DiscordNotifier, WebhookHeartbeatService};
//! use rustrade::Bot;
//!
//! let notifier = Arc::new(DiscordNotifier::new(
//!     std::env::var("KC_DISCORD_WEBHOOK").unwrap(),
//! ));
//!
//! let heartbeat = WebhookHeartbeatService::new(
//!     "kucoin-v2-heartbeat",
//!     notifier,
//!     Duration::from_secs(300),
//!     "kucoin-v2 heartbeat: still alive".to_string(),
//! );
//!
//! bot.supervisor().spawn_service(Box::new(heartbeat));
//! ```

#![warn(missing_docs)]

mod heartbeat;
mod notifier;

#[cfg(feature = "discord")]
mod discord;

pub use heartbeat::WebhookHeartbeatService;
pub use notifier::{InMemoryNotifier, NotifyError, Notifier};

#[cfg(feature = "discord")]
pub use discord::DiscordNotifier;
