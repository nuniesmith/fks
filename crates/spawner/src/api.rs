// =============================================================================
// api.rs — Axum HTTP router + handlers for FKS Bot Spawner
//
// Routes:
//   GET    /health                    → HealthResponse (JSON)
//   GET    /metrics                   → Prometheus text
//   GET    /containers                → Vec<ContainerInfo> (JSON)
//   GET    /container/{id}             → ContainerInfo (JSON)
//   POST   /spawn                     → SpawnResponse (JSON)
//   DELETE /container/{id}             → ActionResponse (JSON)
//   POST   /container/{id}/stop        → ActionResponse (JSON)
//   POST   /container/{id}/restart     → ActionResponse (JSON)
//   GET    /container/{id}/logs        → SSE stream (text/event-stream)
// =============================================================================

use std::{
    convert::Infallible,
    sync::Arc,
    time::{Duration, Instant},
};

use axum::{
    Router,
    extract::{Path, Query, State},
    http::StatusCode,
    middleware,
    response::{
        Json,
        sse::{Event, KeepAlive, Sse},
    },
    routing::{delete, get, post},
};
use futures_util::StreamExt;
use serde::Deserialize;
use tracing::{info, warn};

use crate::{
    auth::require_internal_token,
    config::Config,
    docker_client::DockerOps,
    error::SpawnerError,
    metrics,
    models::{ActionResponse, HealthResponse, SpawnRequest, SpawnResponse},
    prometheus_sd,
};

#[cfg(feature = "db")]
use crate::db::{BotRunStore, RecordSpawn};
#[cfg(feature = "db")]
use crate::models::{ConfigRequest, SecretRequest};

// ─────────────────────────────────────────────────────────────────────────────
// Shared state
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Clone)]
pub struct AppState {
    /// Backend driver — production uses `DockerClient` (talks to a real
    /// Docker daemon); tests inject `MockDockerClient` for handler-level
    /// integration tests without a daemon.
    pub docker: Arc<dyn DockerOps>,
    pub config: Arc<Config>,
    /// Optional Postgres-backed bot_runs persistence. None = stateless mode.
    #[cfg(feature = "db")]
    pub store: Option<BotRunStore>,
}

// ─────────────────────────────────────────────────────────────────────────────
// Router
// ─────────────────────────────────────────────────────────────────────────────

/// Build the spawner's HTTP router.
///
/// Routes are split across two sub-routers:
///
/// - **Public** (`/health`, `/metrics`) — always reachable. Used by the
///   Docker healthcheck and by Prometheus scraping over the
///   `fks_network` Docker network.
/// - **Protected** (everything else) — wrapped in the
///   [`require_internal_token`] middleware. When
///   `Config.internal_token` is non-empty, requests must carry
///   `X-Internal-Token: <value>` (set by nginx). When empty, the
///   middleware is a no-op so direct local-dev requests still work.
pub fn build_router(state: AppState) -> Router {
    let public = Router::new()
        .route("/health", get(health_handler))
        .route("/metrics", get(metrics_handler))
        .with_state(state.clone());

    let protected = Router::new()
        .route("/spawn", post(spawn_handler))
        .route("/containers", get(list_containers_handler))
        .route("/container/{id}", get(inspect_handler))
        .route("/container/{id}", delete(remove_handler))
        .route("/container/{id}/stop", post(stop_handler))
        .route("/container/{id}/restart", post(restart_handler))
        .route("/container/{id}/logs", get(logs_sse_handler));

    #[cfg(feature = "db")]
    let protected = protected
        .route("/runs", get(runs_handler))
        .route("/secrets", post(secrets_handler))
        .route("/secrets/status", get(secrets_status_handler))
        .route("/secrets/{exchange}", delete(delete_secret_handler))
        .route(
            "/configs",
            get(list_configs_handler).post(save_config_handler),
        )
        .route("/configs/{name}", delete(delete_config_handler));

    let protected = protected
        .layer(middleware::from_fn_with_state(
            state.clone(),
            require_internal_token,
        ))
        .with_state(state);

    Router::new().merge(public).merge(protected)
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

    // ── Spawn-time secrets injection ────────────────────────────────────────
    // `secrets: ["kraken", …]` injects that exchange's stored credentials as
    // {EXCHANGE}_API_KEY / _API_SECRET (+ _API_PASSPHRASE when stored) — the
    // env names the crypto bots read. Fails the spawn loudly when the DB is
    // unavailable or an exchange has no stored credentials: a bot that asked
    // for keys must never silently start keyless. Explicit request `env`
    // entries win over injected ones (documented on SpawnRequest).
    #[cfg(not(feature = "db"))]
    if !req.secrets.is_empty() {
        return Err(SpawnerError::InvalidRequest(
            "secrets injection requires the db feature (stateless build)".to_string(),
        ));
    }
    #[cfg(feature = "db")]
    let req = {
        let mut req = req;
        if !req.secrets.is_empty() {
            if req.secrets.len() > 10 {
                return Err(SpawnerError::InvalidRequest(
                    "too many secrets requested (max 10 exchanges)".to_string(),
                ));
            }
            let Some(store) = state.store.as_ref() else {
                return Err(SpawnerError::InvalidRequest(
                    "secrets injection requires the spawner Postgres DB (not configured)"
                        .to_string(),
                ));
            };
            for exchange in &req.secrets {
                let ex = exchange.trim().to_lowercase();
                if ex.is_empty()
                    || ex.len() > 32
                    || !ex
                        .chars()
                        .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
                {
                    return Err(SpawnerError::InvalidRequest(format!(
                        "invalid exchange name in secrets: '{exchange}'"
                    )));
                }
                let Some(creds) = store.get_secret(&ex).await? else {
                    return Err(SpawnerError::InvalidRequest(format!(
                        "no stored credentials for exchange '{ex}' — submit them via \
                         POST /secrets first"
                    )));
                };
                let prefix = ex.to_uppercase().replace('-', "_");
                req.env
                    .entry(format!("{prefix}_API_KEY"))
                    .or_insert(creds.api_key);
                req.env
                    .entry(format!("{prefix}_API_SECRET"))
                    .or_insert(creds.api_secret);
                if let Some(passphrase) = creds.api_passphrase {
                    req.env
                        .entry(format!("{prefix}_API_PASSPHRASE"))
                        .or_insert(passphrase);
                }
                // Log only the exchange — never the credential values.
                info!(exchange = %ex, "injecting stored exchange credentials into spawn env");
            }
        }
        req
    };

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

    // Persist to bot_runs (best-effort — never block the response on DB).
    #[cfg(feature = "db")]
    if let Some(store) = state.store.clone() {
        let args = OwnedSpawnRecord::from(&resp);
        tokio::spawn(async move {
            if let Err(e) = store
                .record_spawn(RecordSpawn {
                    container_id: &args.container_id,
                    container_name: &args.container_name,
                    image: &args.image,
                    mode: &args.mode,
                    started_at: args.started_at,
                })
                .await
            {
                warn!(error = %e, container_id = %args.container_id, "record_spawn failed");
            }
        });
    }

    // Update Prometheus SD file asynchronously — don't block the response.
    let docker = state.docker.clone();
    let config = state.config.clone();
    tokio::spawn(async move {
        prometheus_sd::update_sd_file(docker.as_ref(), &config).await;
    });

    Ok((StatusCode::CREATED, Json(resp)))
}

/// Owned snapshot of a `SpawnResponse` for use inside `tokio::spawn` futures
/// (the borrowed `RecordSpawn` can't outlive the handler).
#[cfg(feature = "db")]
struct OwnedSpawnRecord {
    container_id: String,
    container_name: String,
    image: String,
    mode: String,
    started_at: chrono::DateTime<chrono::Utc>,
}

#[cfg(feature = "db")]
impl From<&SpawnResponse> for OwnedSpawnRecord {
    fn from(r: &SpawnResponse) -> Self {
        Self {
            container_id: r.container_id.clone(),
            container_name: r.container_name.clone(),
            image: r.image.clone(),
            mode: r.mode.clone(),
            started_at: r.started_at,
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /containers
// ─────────────────────────────────────────────────────────────────────────────

async fn list_containers_handler(
    State(state): State<AppState>,
) -> Result<Json<serde_json::Value>, SpawnerError> {
    let mut bots = state.docker.list_bots().await?;
    let running = bots.iter().filter(|b| b.state == "running").count();
    metrics::RUNNING_BOTS.set(running as f64);

    // Enrich running containers with live CPU/memory — best-effort and
    // concurrent, each bounded by a short timeout so a slow stat can't stall the
    // listing. Failures simply leave cpu_percent/memory_bytes as None.
    // (Only this listing pays for stats; /health stays a cheap label query.)
    let stats = futures_util::future::join_all(bots.iter().map(|b| {
        let docker = state.docker.clone();
        let id = b.id_full.clone();
        let is_running = b.state == "running";
        async move {
            if !is_running {
                return None;
            }
            match tokio::time::timeout(Duration::from_secs(3), docker.stats(&id)).await {
                Ok(Ok(s)) => Some(s),
                _ => None,
            }
        }
    }))
    .await;
    for (b, s) in bots.iter_mut().zip(stats) {
        if let Some(s) = s {
            b.cpu_percent = s.cpu_percent;
            b.memory_bytes = s.memory_bytes;
            b.memory_limit_bytes = s.memory_limit_bytes;
        }
    }

    Ok(Json(serde_json::json!({
        "containers": bots,
        "total": bots.len(),
        "running": running,
    })))
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /container/{id}
// ─────────────────────────────────────────────────────────────────────────────

async fn inspect_handler(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, SpawnerError> {
    let info = state.docker.inspect(&id).await?;
    Ok(Json(serde_json::to_value(info)?))
}

// ─────────────────────────────────────────────────────────────────────────────
// DELETE /container/{id}
// ─────────────────────────────────────────────────────────────────────────────

async fn remove_handler(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<ActionResponse>, SpawnerError> {
    state.docker.remove(&id).await?;
    metrics::REMOVES_TOTAL.inc();

    #[cfg(feature = "db")]
    if let Some(store) = state.store.clone() {
        let id_owned = id.clone();
        tokio::spawn(async move {
            if let Err(e) = store.record_remove(&id_owned).await {
                warn!(error = %e, container_id = %id_owned, "record_remove failed");
            }
        });
    }

    let docker = state.docker.clone();
    let config = state.config.clone();
    tokio::spawn(async move {
        prometheus_sd::update_sd_file(docker.as_ref(), &config).await;
    });

    Ok(Json(ActionResponse::ok(&id, "remove")))
}

// ─────────────────────────────────────────────────────────────────────────────
// POST /container/{id}/stop
// ─────────────────────────────────────────────────────────────────────────────

async fn stop_handler(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<ActionResponse>, SpawnerError> {
    state.docker.stop(&id).await?;
    metrics::STOPS_TOTAL.inc();

    #[cfg(feature = "db")]
    if let Some(store) = state.store.clone() {
        let id_owned = id.clone();
        tokio::spawn(async move {
            if let Err(e) = store.record_stop(&id_owned).await {
                warn!(error = %e, container_id = %id_owned, "record_stop failed");
            }
        });
    }

    let docker = state.docker.clone();
    let config = state.config.clone();
    tokio::spawn(async move {
        prometheus_sd::update_sd_file(docker.as_ref(), &config).await;
    });

    Ok(Json(ActionResponse::ok(&id, "stop")))
}

// ─────────────────────────────────────────────────────────────────────────────
// POST /container/{id}/restart
// ─────────────────────────────────────────────────────────────────────────────

async fn restart_handler(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<ActionResponse>, SpawnerError> {
    state.docker.restart(&id).await?;
    Ok(Json(ActionResponse::ok(&id, "restart")))
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /container/{id}/logs  → SSE
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct LogsQuery {
    /// Number of tail lines to return before following. Default: 100.
    tail: Option<String>,
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /runs  (db feature only) — recent bot_runs history
// ─────────────────────────────────────────────────────────────────────────────

#[cfg(feature = "db")]
#[derive(Deserialize)]
struct RunsQuery {
    /// Max rows to return (clamped to 1..=500). Default: 50.
    limit: Option<i64>,
}

#[cfg(feature = "db")]
async fn runs_handler(
    State(state): State<AppState>,
    Query(params): Query<RunsQuery>,
) -> Result<Json<serde_json::Value>, SpawnerError> {
    let Some(store) = state.store.as_ref() else {
        // DB not configured — return an empty list so the WebUI degrades gracefully.
        return Ok(Json(serde_json::json!({
            "runs": [],
            "total": 0,
            "db_enabled": false,
        })));
    };

    let rows = store.recent_runs(params.limit.unwrap_or(50)).await?;
    Ok(Json(serde_json::json!({
        "runs": rows,
        "total": rows.len(),
        "db_enabled": true,
    })))
}

// ─────────────────────────────────────────────────────────────────────────────
// Secrets  (db feature only) — exchange API credential storage
//
// SECURITY: the WebUI browser only ever SUBMITS credentials here; they are
// never returned. POST stores (UPSERT by exchange); GET /secrets/status reports
// only which exchanges are configured (never the key/secret material). With
// SPAWNER_SECRETS_KEY set, values are encrypted at rest (ChaCha20-Poly1305,
// see secrets_crypto.rs); unset falls back to the legacy plaintext storage.
// Every route here is additionally gated by X-Internal-Token.
// ─────────────────────────────────────────────────────────────────────────────

#[cfg(feature = "db")]
async fn secrets_handler(
    State(state): State<AppState>,
    Json(req): Json<SecretRequest>,
) -> Result<(StatusCode, Json<serde_json::Value>), SpawnerError> {
    let exchange = req.exchange.trim().to_lowercase();
    let api_key = req.api_key.trim();
    let api_secret = req.api_secret.trim();
    let api_passphrase = req
        .api_passphrase
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty());

    if exchange.is_empty() || api_key.is_empty() || api_secret.is_empty() {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({
                "ok": false,
                "error": "exchange, api_key and api_secret are required",
            })),
        ));
    }

    let Some(store) = state.store.as_ref() else {
        // No Postgres configured — can't persist. Tell the caller honestly
        // instead of pretending the credentials were saved.
        return Ok((
            StatusCode::SERVICE_UNAVAILABLE,
            Json(serde_json::json!({
                "ok": false,
                "db_enabled": false,
                "error": "secret storage requires the spawner Postgres DB",
            })),
        ));
    };

    // AWAIT the write — unlike bot_runs (fire-and-forget via tokio::spawn) we
    // confirm the credential persisted before reporting success to the operator.
    store
        .upsert_secret(&exchange, api_key, api_secret, api_passphrase)
        .await?;

    // Log only the exchange — never the key or secret.
    info!(exchange = %exchange, "stored exchange API credentials");

    Ok((
        StatusCode::OK,
        Json(serde_json::json!({ "ok": true, "exchange": exchange })),
    ))
}

#[cfg(feature = "db")]
async fn delete_secret_handler(
    State(state): State<AppState>,
    Path(exchange): Path<String>,
) -> Result<Json<serde_json::Value>, SpawnerError> {
    let exchange = exchange.trim().to_lowercase();
    let Some(store) = state.store.as_ref() else {
        return Ok(Json(
            serde_json::json!({ "ok": false, "db_enabled": false }),
        ));
    };

    let removed = store.delete_secret(&exchange).await?;
    // Log only the exchange — never credentials.
    info!(exchange = %exchange, removed, "deleted exchange API credentials");
    Ok(Json(
        serde_json::json!({ "ok": removed, "exchange": exchange }),
    ))
}

#[cfg(feature = "db")]
async fn secrets_status_handler(
    State(state): State<AppState>,
) -> Result<Json<serde_json::Value>, SpawnerError> {
    let Some(store) = state.store.as_ref() else {
        // DB not configured — empty list so the WebUI degrades gracefully.
        return Ok(Json(serde_json::json!({
            "exchanges": [],
            "total": 0,
            "db_enabled": false,
        })));
    };

    let rows = store.configured_exchanges().await?;
    Ok(Json(serde_json::json!({
        "exchanges": rows,
        "total": rows.len(),
        "db_enabled": true,
    })))
}

// ─────────────────────────────────────────────────────────────────────────────
// Saved spawn configs  (db feature only) — reusable named spawn templates
//
// Persisted in `bot_configs`. The browser saves the spawn form as a named
// config (POST), lists them (GET), and removes them (DELETE, soft). The actual
// image-prefix / concurrency guards still apply at /spawn time.
// ─────────────────────────────────────────────────────────────────────────────

#[cfg(feature = "db")]
async fn save_config_handler(
    State(state): State<AppState>,
    Json(req): Json<ConfigRequest>,
) -> Result<(StatusCode, Json<serde_json::Value>), SpawnerError> {
    if req.name.trim().is_empty() || req.image.trim().is_empty() {
        return Ok((
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({
                "ok": false,
                "error": "name and image are required",
            })),
        ));
    }

    let Some(store) = state.store.as_ref() else {
        return Ok((
            StatusCode::SERVICE_UNAVAILABLE,
            Json(serde_json::json!({
                "ok": false,
                "db_enabled": false,
                "error": "config storage requires the spawner Postgres DB",
            })),
        ));
    };

    let id = store.upsert_config(&req).await?;
    info!(name = %req.name, "saved bot config");
    Ok((
        StatusCode::OK,
        Json(serde_json::json!({ "ok": true, "id": id, "name": req.name })),
    ))
}

#[cfg(feature = "db")]
async fn list_configs_handler(
    State(state): State<AppState>,
) -> Result<Json<serde_json::Value>, SpawnerError> {
    let Some(store) = state.store.as_ref() else {
        return Ok(Json(serde_json::json!({
            "configs": [],
            "total": 0,
            "db_enabled": false,
        })));
    };

    let rows = store.list_configs().await?;
    Ok(Json(serde_json::json!({
        "configs": rows,
        "total": rows.len(),
        "db_enabled": true,
    })))
}

#[cfg(feature = "db")]
async fn delete_config_handler(
    State(state): State<AppState>,
    Path(name): Path<String>,
) -> Result<Json<serde_json::Value>, SpawnerError> {
    let Some(store) = state.store.as_ref() else {
        return Ok(Json(
            serde_json::json!({ "ok": false, "db_enabled": false }),
        ));
    };

    let removed = store.deactivate_config(&name).await?;
    Ok(Json(serde_json::json!({ "ok": removed, "name": name })))
}

async fn logs_sse_handler(
    State(state): State<AppState>,
    Path(id): Path<String>,
    Query(params): Query<LogsQuery>,
) -> Sse<impl futures_util::Stream<Item = Result<Event, Infallible>>> {
    let log_stream = state.docker.stream_logs(&id, params.tail);

    let sse_stream = log_stream
        .map(|line| Ok::<_, Infallible>(Event::default().event("log").data(line.trim_end())));

    Sse::new(sse_stream).keep_alive(
        KeepAlive::new()
            .interval(std::time::Duration::from_secs(15))
            .text("keep-alive"),
    )
}
