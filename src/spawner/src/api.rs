// =============================================================================
// api.rs — Axum HTTP router + handlers for FKS Bot Spawner
//
// Routes:
//   GET    /health                    → HealthResponse (JSON)
//   GET    /metrics                   → Prometheus text
//   GET    /containers                → Vec<ContainerInfo> (JSON)
//   GET    /container/:id             → ContainerInfo (JSON)
//   POST   /spawn                     → SpawnResponse (JSON)
//   DELETE /container/:id             → ActionResponse (JSON)
//   POST   /container/:id/stop        → ActionResponse (JSON)
//   POST   /container/:id/restart     → ActionResponse (JSON)
//   GET    /container/:id/logs        → SSE stream (text/event-stream)
// =============================================================================

use std::{convert::Infallible, sync::Arc, time::Instant};

use axum::{
    Router,
    extract::{Path, Query, State},
    http::StatusCode,
    response::{
        sse::{Event, KeepAlive, Sse},
        Json,
    },
    routing::{delete, get, post},
};
use futures_util::StreamExt;
use serde::Deserialize;
use tokio_stream::wrappers::ReceiverStream;
use tracing::{info, warn};

use crate::{
    config::Config,
    docker_client::DockerClient,
    error::SpawnerError,
    metrics,
    models::{ActionResponse, HealthResponse, SpawnRequest, SpawnResponse},
    prometheus_sd,
};

// ─────────────────────────────────────────────────────────────────────────────
// Shared state
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Clone)]
pub struct AppState {
    pub docker: DockerClient,
    pub config: Arc<Config>,
}

// ─────────────────────────────────────────────────────────────────────────────
// Router
// ─────────────────────────────────────────────────────────────────────────────

pub fn build_router(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health_handler))
        .route("/metrics", get(metrics_handler))
        .route("/spawn", post(spawn_handler))
        .route("/containers", get(list_containers_handler))
        .route("/container/:id", get(inspect_handler))
        .route("/container/:id", delete(remove_handler))
        .route("/container/:id/stop", post(stop_handler))
        .route("/container/:id/restart", post(restart_handler))
        .route("/container/:id/logs", get(logs_sse_handler))
        .with_state(state)
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /health
// ─────────────────────────────────────────────────────────────────────────────

async fn health_handler(
    State(state): State<AppState>,
) -> Result<Json<HealthResponse>, SpawnerError> {
    let bots = state.docker.list_bots().await?;
    let running = bots.iter().filter(|b| b.state == "running").count();

    metrics::RUNNING_BOTS.set(running as f64);

    Ok(Json(HealthResponse {
        status: "ok",
        service: "fks-bot-spawner",
        version: env!("CARGO_PKG_VERSION"),
        running_bots: running,
        max_bots: state.config.max_concurrent_bots,
    }))
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /metrics
// ─────────────────────────────────────────────────────────────────────────────

async fn metrics_handler() -> (StatusCode, String) {
    (StatusCode::OK, metrics::render())
}

// ─────────────────────────────────────────────────────────────────────────────
// POST /spawn
// ─────────────────────────────────────────────────────────────────────────────

async fn spawn_handler(
    State(state): State<AppState>,
    Json(req): Json<SpawnRequest>,
) -> Result<(StatusCode, Json<SpawnResponse>), SpawnerError> {
    let t = Instant::now();
    let image_prefix = req
        .image
        .split(':')
        .next()
        .unwrap_or(&req.image)
        .to_string();

    let resp = state.docker.spawn(req).await.map_err(|e| {
        metrics::SPAWN_ERRORS_TOTAL.inc();
        warn!(error = %e, "spawn failed");
        e
    })?;

    metrics::SPAWNS_TOTAL.inc();
    metrics::SPAWN_DURATION
        .with_label_values(&[&image_prefix])
        .observe(t.elapsed().as_secs_f64());

    info!(
        container_id = %resp.container_id,
        bot_id = %resp.bot_id,
        image = %resp.image,
        "bot spawned successfully"
    );

    // Update Prometheus SD file asynchronously — don't block the response.
    let docker = state.docker.clone();
    let config = state.config.clone();
    tokio::spawn(async move {
        prometheus_sd::update_sd_file(&docker, &config).await;
    });

    Ok((StatusCode::CREATED, Json(resp)))
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /containers
// ─────────────────────────────────────────────────────────────────────────────

async fn list_containers_handler(
    State(state): State<AppState>,
) -> Result<Json<serde_json::Value>, SpawnerError> {
    let bots = state.docker.list_bots().await?;
    let running = bots.iter().filter(|b| b.state == "running").count();
    metrics::RUNNING_BOTS.set(running as f64);
    Ok(Json(serde_json::json!({
        "containers": bots,
        "total": bots.len(),
        "running": running,
    })))
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /container/:id
// ─────────────────────────────────────────────────────────────────────────────

async fn inspect_handler(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, SpawnerError> {
    let info = state.docker.inspect(&id).await?;
    Ok(Json(serde_json::to_value(info)?))
}

// ─────────────────────────────────────────────────────────────────────────────
// DELETE /container/:id
// ─────────────────────────────────────────────────────────────────────────────

async fn remove_handler(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<ActionResponse>, SpawnerError> {
    state.docker.remove(&id).await?;
    metrics::REMOVES_TOTAL.inc();

    let docker = state.docker.clone();
    let config = state.config.clone();
    tokio::spawn(async move {
        prometheus_sd::update_sd_file(&docker, &config).await;
    });

    Ok(Json(ActionResponse::ok(&id, "remove")))
}

// ─────────────────────────────────────────────────────────────────────────────
// POST /container/:id/stop
// ─────────────────────────────────────────────────────────────────────────────

async fn stop_handler(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<ActionResponse>, SpawnerError> {
    state.docker.stop(&id).await?;
    metrics::STOPS_TOTAL.inc();

    let docker = state.docker.clone();
    let config = state.config.clone();
    tokio::spawn(async move {
        prometheus_sd::update_sd_file(&docker, &config).await;
    });

    Ok(Json(ActionResponse::ok(&id, "stop")))
}

// ─────────────────────────────────────────────────────────────────────────────
// POST /container/:id/restart
// ─────────────────────────────────────────────────────────────────────────────

async fn restart_handler(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<ActionResponse>, SpawnerError> {
    state.docker.restart(&id).await?;
    Ok(Json(ActionResponse::ok(&id, "restart")))
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /container/:id/logs  → SSE
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct LogsQuery {
    /// Number of tail lines to return before following. Default: 100.
    tail: Option<String>,
}

async fn logs_sse_handler(
    State(state): State<AppState>,
    Path(id): Path<String>,
    Query(params): Query<LogsQuery>,
) -> Sse<impl futures_util::Stream<Item = Result<Event, Infallible>>> {
    let log_stream = state.docker.stream_logs(&id, params.tail);

    let sse_stream = log_stream.map(|line| {
        Ok::<_, Infallible>(
            Event::default()
                .event("log")
                .data(line.trim_end().to_string()),
        )
    });

    Sse::new(sse_stream).keep_alive(
        KeepAlive::new()
            .interval(std::time::Duration::from_secs(15))
            .text("keep-alive"),
    )
}
