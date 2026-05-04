//! Tracing subscriber initialization helpers.
//!
//! Most bots want exactly one of two configurations:
//!
//! - **Development**: human-friendly compact output to stdout, level from `RUST_LOG`.
//! - **Production**: structured JSON to stdout (so `docker logs` captures it
//!   and Promtail / Vector can ingest it cleanly).
//!
//! [`init`] picks the dev preset; [`init_json`] picks the production preset.
//! Both honour the `RUST_LOG` environment variable for filtering, defaulting
//! to `info` if unset.

use tracing_subscriber::EnvFilter;

/// Initialize a development-friendly tracing subscriber.
///
/// Compact human-readable output to stdout. Filtered by `RUST_LOG` (default
/// `info`). Idempotent — safe to call multiple times.
pub fn init() {
    let _ = tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .with_target(true)
        .compact()
        .try_init();
}

/// Initialize a production-flavoured JSON tracing subscriber.
///
/// One JSON object per log line on stdout. Filtered by `RUST_LOG` (default
/// `info`). Idempotent — safe to call multiple times.
pub fn init_json() {
    let _ = tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .with_target(true)
        .json()
        .try_init();
}
