//! [`DiscordNotifier`] — POSTs simple text messages to a Discord webhook URL.

use async_trait::async_trait;
use reqwest::Client;
use serde::Serialize;
use std::time::Duration;

use crate::notifier::{Notifier, NotifyError};

/// Posts plain `content` strings to a Discord webhook.
///
/// Discord webhooks accept JSON of the shape `{"content": "..."}`, optionally
/// with `username` and `embeds`. This notifier uses just `content` for the
/// MVP — rich embeds can land later as a separate notifier or method.
///
/// # Errors
///
/// Returns [`NotifyError::Config`] from [`Self::new`] if the URL is empty.
/// `notify` returns [`NotifyError::Transport`] on network failures and
/// [`NotifyError::Remote`] when Discord returns a non-2xx status.
pub struct DiscordNotifier {
    webhook_url: String,
    client: Client,
    username: Option<String>,
}

#[derive(Serialize)]
struct DiscordPayload<'a> {
    content: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    username: Option<&'a str>,
}

impl DiscordNotifier {
    /// Build a notifier from a webhook URL.
    ///
    /// # Errors
    ///
    /// Returns [`NotifyError::Config`] if `webhook_url` is empty.
    pub fn new(webhook_url: impl Into<String>) -> Result<Self, NotifyError> {
        let webhook_url = webhook_url.into();
        if webhook_url.trim().is_empty() {
            return Err(NotifyError::Config("webhook_url is empty".into()));
        }

        let client = Client::builder()
            .timeout(Duration::from_secs(10))
            .build()
            .map_err(|e| NotifyError::Transport(e.to_string()))?;

        Ok(Self {
            webhook_url,
            client,
            username: None,
        })
    }

    /// Build a notifier from a webhook URL or `Err` if the URL is empty.
    /// Convenience wrapper around [`Self::new`].
    pub fn from_env(env_var: &str) -> Result<Self, NotifyError> {
        let url = std::env::var(env_var)
            .map_err(|_| NotifyError::Config(format!("environment variable {env_var} not set")))?;
        Self::new(url)
    }

    /// Builder: override the bot username displayed in Discord.
    pub fn with_username(mut self, username: impl Into<String>) -> Self {
        self.username = Some(username.into());
        self
    }
}

#[async_trait]
impl Notifier for DiscordNotifier {
    async fn notify(&self, msg: &str) -> Result<(), NotifyError> {
        let payload = DiscordPayload {
            content: msg,
            username: self.username.as_deref(),
        };

        let resp = self
            .client
            .post(&self.webhook_url)
            .json(&payload)
            .send()
            .await
            .map_err(|e| NotifyError::Transport(e.to_string()))?;

        let status = resp.status();
        if !status.is_success() {
            // Drain the body BEFORE logging so the macro's temporaries
            // don't span an await point (would make the future !Send).
            let body = resp.text().await.unwrap_or_default();
            tracing::warn!(
                status = status.as_u16(),
                body   = %body,
                "discord webhook returned non-success status"
            );
            return Err(NotifyError::Remote(status.as_u16()));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_url_is_rejected() {
        assert!(matches!(
            DiscordNotifier::new(""),
            Err(NotifyError::Config(_))
        ));
        assert!(matches!(
            DiscordNotifier::new("   "),
            Err(NotifyError::Config(_))
        ));
    }

    #[test]
    fn from_env_missing_var_is_rejected() {
        // SAFETY: the var is guaranteed not set in the test process.
        assert!(matches!(
            DiscordNotifier::from_env("RUSTRADE_NOTIFY_TEST_DEFINITELY_UNSET"),
            Err(NotifyError::Config(_))
        ));
    }

    #[test]
    fn well_formed_url_constructs_ok() {
        let n = DiscordNotifier::new("https://discord.com/api/webhooks/123/abc").unwrap();
        assert!(n.username.is_none());
        let n = n.with_username("rustrade-bot");
        assert_eq!(n.username.as_deref(), Some("rustrade-bot"));
    }
}
