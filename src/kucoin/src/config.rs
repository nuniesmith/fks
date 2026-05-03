//! `RuntimeConfig` — infrastructure settings for the live bot.
//!
//! Strategy / indicator parameters live in `indicators::BotSettings`.
//! This module only covers what the bot needs to *run*:
//! credentials, Redis, Discord, and environment routing.

use exchange_apiws::KucoinEnv;

/// Infrastructure configuration loaded from environment variables or `.env`.
#[derive(Debug, Clone)]
#[allow(clippy::struct_excessive_bools)]
pub struct RuntimeConfig {
    // ── Exchange ──────────────────────────────────────────────────────────────
    /// `LiveFutures` by default; override with `KUCOIN_ENV=spot`.
    pub env: KucoinEnv,

    // ── Redis ─────────────────────────────────────────────────────────────────
    pub redis_url: String,

    // ── Discord ───────────────────────────────────────────────────────────────
    pub discord_webhook: Option<String>,
    pub discord_enabled: bool,
    pub discord_notify_signal: bool,
    pub discord_notify_fill: bool,
    pub discord_notify_error: bool,
}

impl RuntimeConfig {
    /// Load from environment / `.env` file.
    pub fn from_env() -> anyhow::Result<Self> {
        dotenvy::dotenv().ok();

        let env = match std::env::var("KUCOIN_ENV").as_deref() {
            Ok("spot") => KucoinEnv::LiveSpot,
            Ok("unified") => KucoinEnv::Unified,
            _ => KucoinEnv::LiveFutures,
        };

        let discord_webhook = std::env::var("DISCORD_WEBHOOK").ok();
        let discord_enabled = discord_webhook.is_some()
            && std::env::var("DISCORD_ENABLED")
                .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
                .unwrap_or(true);

        // Read boolean env flags — default true (backwards-compatible).
        // Operators can silence individual notification types without a code
        // change by setting the corresponding env var to "false" or "0":
        //   DISCORD_NOTIFY_SIGNAL=false  → suppress new-signal embeds
        //   DISCORD_NOTIFY_FILL=false    → suppress fill-confirmed embeds
        //   DISCORD_NOTIFY_ERROR=false   → suppress error embeds
        let bool_flag = |key: &str| {
            std::env::var(key)
                .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
                .unwrap_or(true)
        };

        Ok(Self {
            env,
            redis_url: std::env::var("REDIS_URL")
                .unwrap_or_else(|_| "redis://127.0.0.1:6379".into()),
            discord_webhook,
            discord_enabled,
            discord_notify_signal: bool_flag("DISCORD_NOTIFY_SIGNAL"),
            discord_notify_fill:   bool_flag("DISCORD_NOTIFY_FILL"),
            discord_notify_error:  bool_flag("DISCORD_NOTIFY_ERROR"),
        })
    }
}
