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

#[derive(Debug, Serialize)]
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

#[derive(Debug, Serialize, Clone)]
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

#[derive(Debug, Serialize)]
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
        Self { error: error.into(), detail: None }
    }
    pub fn with_detail(error: impl Into<String>, detail: impl Into<String>) -> Self {
        Self { error: error.into(), detail: Some(detail.into()) }
    }
}
