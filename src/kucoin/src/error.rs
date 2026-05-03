//! `BotError` — unified runtime error type.
//!
//! Exchange and JSON errors are re-wrapped from `exchange_apiws::ExchangeError`
//! rather than depending on `reqwest` or `tungstenite` directly — those are
//! implementation details of the published I/O crate.

use thiserror::Error;

#[derive(Debug, Error)]
pub enum BotError {
    #[error("Exchange error: {0}")]
    Exchange(#[from] exchange_apiws::ExchangeError),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Config error: {0}")]
    Config(String),

    #[error("Order error: {0}")]
    Order(String),

    #[error("Insufficient data: {0}")]
    InsufficientData(String),

    #[error("Redis error: {0}")]
    Redis(#[from] redis::RedisError),

    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),

    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

pub type Result<T> = std::result::Result<T, BotError>;
