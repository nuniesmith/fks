//! The [`Notifier`] trait + an in-memory test impl.

use std::sync::Mutex;

use async_trait::async_trait;
use thiserror::Error;

/// Errors a [`Notifier`] can return.
#[derive(Debug, Error)]
pub enum NotifyError {
    /// The transport (HTTP, etc.) failed.
    #[error("transport error: {0}")]
    Transport(String),

    /// The remote service returned a non-success status.
    #[error("remote responded with status {0}")]
    Remote(u16),

    /// The notifier was misconfigured at construction time
    /// (empty webhook URL, malformed config, etc.).
    #[error("configuration error: {0}")]
    Config(String),
}

/// A target that can receive a single string message.
///
/// Implementations are typically `Arc<dyn Notifier>` and shared across
/// services. The trait is intentionally narrow: one method, one string,
/// one outcome. Higher-level abstractions (rich embeds, structured
/// events) belong in adapter code that converts to a string before
/// calling [`Self::notify`].
#[async_trait]
pub trait Notifier: Send + Sync + 'static {
    /// Post `msg` to the underlying transport.
    async fn notify(&self, msg: &str) -> Result<(), NotifyError>;
}

/// Test-only [`Notifier`] that records every message it sees.
///
/// Cheap to clone — internally an `Arc<Mutex<Vec<String>>>`.
#[derive(Debug, Default, Clone)]
pub struct InMemoryNotifier {
    inner: std::sync::Arc<Mutex<Vec<String>>>,
}

impl InMemoryNotifier {
    /// Build an empty notifier.
    pub fn new() -> Self {
        Self::default()
    }

    /// Snapshot every message recorded so far.
    pub fn messages(&self) -> Vec<String> {
        self.inner.lock().unwrap().clone()
    }

    /// Number of messages recorded.
    pub fn len(&self) -> usize {
        self.inner.lock().unwrap().len()
    }

    /// `true` when no messages have been recorded.
    pub fn is_empty(&self) -> bool {
        self.inner.lock().unwrap().is_empty()
    }
}

#[async_trait]
impl Notifier for InMemoryNotifier {
    async fn notify(&self, msg: &str) -> Result<(), NotifyError> {
        self.inner.lock().unwrap().push(msg.to_string());
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn in_memory_notifier_records_messages() {
        let n = InMemoryNotifier::new();
        n.notify("hello").await.unwrap();
        n.notify("world").await.unwrap();
        assert_eq!(n.len(), 2);
        assert_eq!(n.messages(), vec!["hello", "world"]);
    }

    #[tokio::test]
    async fn in_memory_notifier_is_send_and_sync() {
        // Compile-time check that we can store as Arc<dyn Notifier>.
        let n: std::sync::Arc<dyn Notifier> = std::sync::Arc::new(InMemoryNotifier::new());
        n.notify("test").await.unwrap();
    }
}
