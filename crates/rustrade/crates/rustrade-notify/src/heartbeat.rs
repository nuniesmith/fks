//! [`WebhookHeartbeatService`] — a [`TradingService`] that posts a
//! periodic heartbeat through any [`Notifier`].
//!
//! The supervisor restarts it on failure and cancels it on graceful
//! shutdown. The first heartbeat fires after one full interval (not
//! immediately) so you don't double-post around bot startup if the
//! bot binary also sends a "started" message.

use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use rustrade_supervisor::{RestartPolicy, TradingService};
use tokio_util::sync::CancellationToken;

use crate::notifier::Notifier;

/// Periodic heartbeat poster.
///
/// One instance per webhook target. Failures from the underlying
/// [`Notifier`] are logged and swallowed — a transient Discord outage
/// shouldn't tear down the whole supervisor tree. Repeated long failures
/// will simply produce repeated warning logs.
pub struct WebhookHeartbeatService {
    name: String,
    notifier: Arc<dyn Notifier>,
    interval: Duration,
    message: String,
}

impl WebhookHeartbeatService {
    /// Build a heartbeat service.
    ///
    /// `name` is the supervisor-side identifier used in lifecycle logs and
    /// metrics (e.g. `"kucoin-v2-heartbeat"`). `interval` is the tick
    /// period; reasonable values are 1–5 minutes for active monitoring,
    /// 15+ for "yes the bot is still up" sanity checks.
    pub fn new(
        name: impl Into<String>,
        notifier: Arc<dyn Notifier>,
        interval: Duration,
        message: impl Into<String>,
    ) -> Self {
        Self {
            name: name.into(),
            notifier,
            interval,
            message: message.into(),
        }
    }
}

#[async_trait]
impl TradingService for WebhookHeartbeatService {
    fn name(&self) -> &str {
        &self.name
    }

    fn restart_policy(&self) -> RestartPolicy {
        // Heartbeat is best-effort — the run loop already swallows
        // notify errors, so the supervisor only sees an Err when something
        // genuinely went wrong (panic, channel closed). On-failure restart
        // with backoff is the right policy.
        RestartPolicy::OnFailure
    }

    async fn run(&self, cancel: CancellationToken) -> anyhow::Result<()> {
        tracing::info!(
            name = %self.name,
            interval_secs = self.interval.as_secs(),
            "heartbeat service started"
        );

        let mut ticker = tokio::time::interval(self.interval);
        // Skip the immediate first tick so the first heartbeat fires after
        // a full interval, not at startup.
        ticker.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
        ticker.tick().await;

        loop {
            tokio::select! {
                _ = cancel.cancelled() => {
                    tracing::info!(name = %self.name, "heartbeat service stopping");
                    return Ok(());
                }
                _ = ticker.tick() => {
                    if let Err(e) = self.notifier.notify(&self.message).await {
                        tracing::warn!(
                            name = %self.name,
                            error = %e,
                            "heartbeat notify failed; will retry next tick"
                        );
                    }
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::notifier::InMemoryNotifier;

    #[tokio::test]
    async fn heartbeat_posts_on_each_tick_until_cancelled() {
        let notifier = Arc::new(InMemoryNotifier::new());
        let svc = WebhookHeartbeatService::new(
            "test-heartbeat",
            notifier.clone() as Arc<dyn Notifier>,
            Duration::from_millis(40),
            "ping".to_string(),
        );

        let cancel = CancellationToken::new();
        let cancel_clone = cancel.clone();
        let handle = tokio::spawn(async move { svc.run(cancel_clone).await });

        // Wait long enough for ~3 ticks past the initial skipped tick.
        tokio::time::sleep(Duration::from_millis(180)).await;
        cancel.cancel();
        handle.await.unwrap().unwrap();

        let n = notifier.len();
        assert!(
            (2..=6).contains(&n),
            "expected 2-6 heartbeats in 180ms with 40ms interval, got {n}"
        );
    }

    #[tokio::test]
    async fn heartbeat_exits_promptly_on_cancellation() {
        let notifier = Arc::new(InMemoryNotifier::new());
        let svc = WebhookHeartbeatService::new(
            "test",
            notifier as Arc<dyn Notifier>,
            Duration::from_secs(3600),
            "hello".to_string(),
        );

        let cancel = CancellationToken::new();
        let cancel_clone = cancel.clone();
        let handle = tokio::spawn(async move { svc.run(cancel_clone).await });

        tokio::time::sleep(Duration::from_millis(20)).await;
        let start = std::time::Instant::now();
        cancel.cancel();
        handle.await.unwrap().unwrap();
        let elapsed = start.elapsed();

        assert!(
            elapsed < Duration::from_millis(100),
            "cancellation took too long: {elapsed:?}"
        );
    }
}
