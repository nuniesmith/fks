// =============================================================================
// models.rs — FKS Bot Spawner request/response types
// =============================================================================

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ─────────────────────────────────────────────────────────────────────────────
// Spawn request
// ─────────────────────────────────────────────────────────────────────────────

/// Request body for POST /spawn
#[derive(Debug, Deserialize)]
pub struct SpawnRequest {
    /// Docker image to run. Must start with ALLOWED_IMAGE_PREFIX.
    pub image: String,

    /// Human-readable bot name / identifier (used as container name suffix).
    /// If omitted a UUID is generated.
    pub bot_id: Option<String>,

    /// Execution mode label — informational, stored as container label.
    #[serde(default = "default_mode")]
    pub mode: String,

    /// Environment variables injected into the container.
    #[serde(default)]
    pub env: HashMap<String, String>,

    /// Extra labels applied to the container (merged with mandatory fks.* labels).
    #[serde(default)]
    pub labels: HashMap<String, String>,

    /// CPU limit in fractional cores. Overrides the server default.
    pub cpu_limit: Option<f64>,

    /// Memory limit in megabytes. Overrides the server default.
    pub memory_limit_mb: Option<i64>,

    /// Optional command override (replaces the image's CMD).
    pub cmd: Option<Vec<String>>,

    /// Optional entrypoint override.
    pub entrypoint: Option<Vec<String>>,
}

fn default_mode() -> String {
    "paper".to_string()
}

// ─────────────────────────────────────────────────────────────────────────────
// Spawn response
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize)]
pub struct SpawnResponse {
    pub container_id: String,
    pub container_name: String,
    pub bot_id: String,
    pub image: String,
    pub mode: String,
    pub started_at: DateTime<Utc>,
}

// ─────────────────────────────────────────────────────────────────────────────
// Container info (returned by GET /containers and GET /container/:id)
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ContainerInfo {
    /// Short container ID (12 chars).
    pub id: String,
    /// Full 64-char container ID.
    pub id_full: String,
    pub name: String,
    pub image: String,
    pub status: String,
    pub state: String,
    pub bot_id: String,
    pub mode: String,
    pub created_at: Option<DateTime<Utc>>,
    pub started_at: Option<DateTime<Utc>>,
    pub finished_at: Option<DateTime<Utc>>,
    pub labels: HashMap<String, String>,
    /// CPU usage percent (0–100 per core), if available.
    pub cpu_percent: Option<f64>,
    /// Memory usage in bytes, if available.
    pub memory_bytes: Option<i64>,
}

// ─────────────────────────────────────────────────────────────────────────────
// Action responses
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize)]
pub struct ActionResponse {
    pub ok: bool,
    pub container_id: String,
    pub action: String,
    pub message: String,
}

impl ActionResponse {
    pub fn ok(container_id: impl Into<String>, action: impl Into<String>) -> Self {
        let action = action.into();
        Self {
            ok: true,
            message: format!("{} completed", action),
            container_id: container_id.into(),
            action,
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Health
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: &'static str,
    pub service: &'static str,
    pub version: &'static str,
    pub running_bots: usize,
    pub max_bots: usize,
}

// ─────────────────────────────────────────────────────────────────────────────
// Error response (serialised as JSON for 4xx/5xx)
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: String,
    pub detail: Option<String>,
}

impl ErrorResponse {
    pub fn new(error: impl Into<String>) -> Self {
        Self {
            error: error.into(),
            detail: None,
        }
    }
    #[allow(dead_code)] // public surface for richer error responses
    pub fn with_detail(error: impl Into<String>, detail: impl Into<String>) -> Self {
        Self {
            error: error.into(),
            detail: Some(detail.into()),
        }
    }
}

// ───────────────────────────────────────────────────────────────────────────
// Tests
// ───────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn spawn_request_minimal_deserializes_with_defaults() {
        let raw = r#"{"image": "fks-bot-arbitrage:latest"}"#;
        let req: SpawnRequest = serde_json::from_str(raw).expect("valid JSON");
        assert_eq!(req.image, "fks-bot-arbitrage:latest");
        assert!(req.bot_id.is_none());
        assert_eq!(req.mode, "paper", "default mode should be 'paper'");
        assert!(req.env.is_empty());
        assert!(req.labels.is_empty());
        assert!(req.cmd.is_none());
    }

    #[test]
    fn spawn_request_full_deserializes() {
        let raw = r#"{
            "image": "fks-bot-eth:v1",
            "bot_id": "my-bot",
            "mode": "live",
            "env": {"KEY": "value"},
            "labels": {"team": "trading"},
            "cpu_limit": 0.5,
            "memory_limit_mb": 256,
            "cmd": ["/bin/bot", "--flag"],
            "entrypoint": ["/sbin/init"]
        }"#;
        let req: SpawnRequest = serde_json::from_str(raw).expect("valid JSON");
        assert_eq!(req.bot_id.as_deref(), Some("my-bot"));
        assert_eq!(req.mode, "live");
        assert_eq!(req.env.get("KEY").map(String::as_str), Some("value"));
        assert_eq!(req.labels.get("team").map(String::as_str), Some("trading"));
        assert_eq!(req.cpu_limit, Some(0.5));
        assert_eq!(req.memory_limit_mb, Some(256));
        assert_eq!(
            req.cmd.as_deref().map(|v| v.len()),
            Some(2),
            "cmd vec should have 2 entries"
        );
        assert!(req.entrypoint.is_some());
    }

    #[test]
    fn action_response_ok_builds_expected_payload() {
        let r = ActionResponse::ok("abc123", "stop");
        assert!(r.ok);
        assert_eq!(r.container_id, "abc123");
        assert_eq!(r.action, "stop");
        assert_eq!(r.message, "stop completed");
    }

    #[test]
    fn error_response_with_detail_serializes_both_fields() {
        let e = ErrorResponse::with_detail("InvalidImage", "prefix mismatch");
        let v = serde_json::to_value(&e).unwrap();
        assert_eq!(v["error"], "InvalidImage");
        assert_eq!(v["detail"], "prefix mismatch");
    }

    #[test]
    fn error_response_new_omits_detail_field_or_serializes_null() {
        // detail is Option<String>; serde_json serializes None as null by default.
        let e = ErrorResponse::new("NotFound");
        let v = serde_json::to_value(&e).unwrap();
        assert_eq!(v["error"], "NotFound");
        assert!(v["detail"].is_null());
    }
}
