// =============================================================================
// docker_client.rs — Docker SDK wrapper for FKS Bot Spawner
//
// Wraps bollard to provide:
//   spawn()        — create + start a bot container with safety guards
//   stop()         — graceful stop
//   restart()      — restart
//   remove()       — force remove
//   inspect()      — container details as ContainerInfo
//   list_bots()    — all containers with fks.bot=true label
//   stream_logs()  — streaming log output (used for SSE endpoint)
//   auto_prune()   — remove exited bot containers older than threshold
// =============================================================================

use std::{collections::HashMap, sync::Arc, time::Duration};

use bollard::{
    container::{
        Config as ContainerConfig, CreateContainerOptions, InspectContainerOptions,
        ListContainersOptions, LogOutput, LogsOptions, RemoveContainerOptions,
        RestartContainerOptions, StartContainerOptions, StopContainerOptions,
    },
    models::{HostConfig, NetworkingConfig, EndpointSettings, Resources},
    network::ConnectNetworkOptions,
    Docker,
};
use chrono::{DateTime, Utc};
use futures_util::StreamExt;
use tokio_stream::Stream;
use tracing::{debug, info, warn};
use uuid::Uuid;

use crate::{
    config::Config,
    error::{SpawnerError, SpawnerResult},
    models::{ContainerInfo, SpawnRequest, SpawnResponse},
};

// ─────────────────────────────────────────────────────────────────────────────
// DockerClient
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Clone)]
pub struct DockerClient {
    docker: Docker,
    config: Arc<Config>,
}

impl DockerClient {
    /// Connect to the Docker daemon via the Unix socket (default path).
    pub fn new(config: Arc<Config>) -> SpawnerResult<Self> {
        let docker = Docker::connect_with_unix_defaults()
            .map_err(SpawnerError::Docker)?;
        Ok(Self { docker, config })
    }

    // ─────────────────────────────────────────────────────────────────────────
    // spawn — create + start a bot container
    // ─────────────────────────────────────────────────────────────────────────

    pub async fn spawn(&self, req: SpawnRequest) -> SpawnerResult<SpawnResponse> {
        // ── Safety guard: image prefix ────────────────────────────────────────
        if !req.image.starts_with(&self.config.allowed_image_prefix) {
            return Err(SpawnerError::InvalidImage(req.image));
        }

        // ── Safety guard: concurrent bot cap ──────────────────────────────────
        let running = self.list_bots().await?.len();
        if running >= self.config.max_concurrent_bots {
            return Err(SpawnerError::TooManyBots(running));
        }

        // ── Bot identity ──────────────────────────────────────────────────────
        let bot_id = req.bot_id
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| Uuid::new_v4().to_string());
        let container_name = format!("fks-bot-{}", bot_id);
        let now = Utc::now();

        // ── Labels ────────────────────────────────────────────────────────────
        let mut labels: HashMap<String, String> = req.labels.clone();
        labels.insert("fks.bot".into(), "true".into());
        labels.insert("fks.mode".into(), req.mode.clone());
        labels.insert("fks.bot_id".into(), bot_id.clone());
        labels.insert("fks.created_by".into(), "spawner".into());
        labels.insert("fks.created_at".into(), now.to_rfc3339());
        labels.insert("fks.image".into(), req.image.clone());

        // ── Environment ───────────────────────────────────────────────────────
        let env: Vec<String> = req.env
            .iter()
            .map(|(k, v)| format!("{}={}", k, v))
            .chain(std::iter::once(format!("FKS_BOT_ID={}", bot_id)))
            .chain(std::iter::once(format!("FKS_BOT_MODE={}", req.mode)))
            .collect();

        // ── Resource limits ───────────────────────────────────────────────────
        let cpu_quota = req.cpu_limit
            .unwrap_or(self.config.default_cpu_limit);
        // Docker CPU quota: period=100_000µs, quota = cores × period
        let cpu_quota_us = (cpu_quota * 100_000.0) as i64;

        let memory_bytes = req.memory_limit_mb
            .map(|mb| mb * 1024 * 1024)
            .unwrap_or(self.config.default_memory_bytes);

        // ── Networking ────────────────────────────────────────────────────────
        let mut endpoints: HashMap<String, EndpointSettings> = HashMap::new();
        endpoints.insert(self.config.allowed_network.clone(), EndpointSettings::default());

        // ── Host config ───────────────────────────────────────────────────────
        let host_config = HostConfig {
            memory: Some(memory_bytes),
            memory_swap: Some(memory_bytes), // disable swap
            cpu_period: Some(100_000),
            cpu_quota: Some(cpu_quota_us),
            cpu_shares: Some(self.config.default_cpu_shares),
            // Log config: json-file driver with 50 MB cap, 3 rotations
            log_config: Some(bollard::models::HostConfigLogConfig {
                typ: Some("json-file".to_string()),
                config: Some(HashMap::from([
                    ("max-size".to_string(), "50m".to_string()),
                    ("max-file".to_string(), "3".to_string()),
                ])),
            }),
            // Security: no privilege escalation
            security_opt: Some(vec!["no-new-privileges:true".to_string()]),
            ..Default::default()
        };

        let networking_config = NetworkingConfig {
            endpoints_config: Some(endpoints),
        };

        // ── Container config ──────────────────────────────────────────────────
        let mut container_cfg: ContainerConfig<String> = ContainerConfig {
            image: Some(req.image.clone()),
            env: Some(env),
            labels: Some(labels.clone()),
            host_config: Some(host_config),
            networking_config: Some(networking_config),
            ..Default::default()
        };

        if let Some(cmd) = req.cmd {
            container_cfg.cmd = Some(cmd);
        }
        if let Some(ep) = req.entrypoint {
            container_cfg.entrypoint = Some(ep);
        }

        // ── Create ────────────────────────────────────────────────────────────
        info!(
            container_name = %container_name,
            image = %req.image,
            mode = %req.mode,
            bot_id = %bot_id,
            "spawning bot container"
        );

        let create_opts = CreateContainerOptions {
            name: container_name.as_str(),
            platform: None,
        };

        let created = self.docker
            .create_container(Some(create_opts), container_cfg)
            .await
            .map_err(SpawnerError::Docker)?;

        let container_id = created.id.clone();

        // ── Start ─────────────────────────────────────────────────────────────
        self.docker
            .start_container(&container_id, None::<StartContainerOptions<String>>)
            .await
            .map_err(|e| {
                warn!(container_id = %container_id, error = %e, "failed to start container — will try to remove");
                SpawnerError::Docker(e)
            })?;

        info!(container_id = %&container_id[..12], "bot container started");

        Ok(SpawnResponse {
            container_id: container_id[..12].to_string(),
            container_name,
            bot_id,
            image: req.image,
            mode: req.mode,
            started_at: Utc::now(),
        })
    }

    // ─────────────────────────────────────────────────────────────────────────
    // stop
    // ─────────────────────────────────────────────────────────────────────────

    pub async fn stop(&self, id: &str) -> SpawnerResult<()> {
        debug!(container = %id, "stopping bot container");
        self.docker
            .stop_container(id, Some(StopContainerOptions { t: 30 }))
            .await
            .map_err(SpawnerError::Docker)?;
        info!(container = %id, "bot container stopped");
        Ok(())
    }

    // ─────────────────────────────────────────────────────────────────────────
    // restart
    // ─────────────────────────────────────────────────────────────────────────

    pub async fn restart(&self, id: &str) -> SpawnerResult<()> {
        debug!(container = %id, "restarting bot container");
        self.docker
            .restart_container(id, Some(RestartContainerOptions { t: 10 }))
            .await
            .map_err(SpawnerError::Docker)?;
        info!(container = %id, "bot container restarted");
        Ok(())
    }

    // ─────────────────────────────────────────────────────────────────────────
    // remove
    // ─────────────────────────────────────────────────────────────────────────

    pub async fn remove(&self, id: &str) -> SpawnerResult<()> {
        debug!(container = %id, "removing bot container");
        self.docker
            .remove_container(
                id,
                Some(RemoveContainerOptions { force: true, v: false, link: false }),
            )
            .await
            .map_err(SpawnerError::Docker)?;
        info!(container = %id, "bot container removed");
        Ok(())
    }

    // ─────────────────────────────────────────────────────────────────────────
    // status / inspect
    // ─────────────────────────────────────────────────────────────────────────

    pub async fn inspect(&self, id: &str) -> SpawnerResult<ContainerInfo> {
        let data = self.docker
            .inspect_container(id, None::<InspectContainerOptions>)
            .await
            .map_err(|e| match e {
                bollard::errors::Error::DockerResponseServerError { status_code: 404, .. } => {
                    SpawnerError::NotFound(id.to_string())
                }
                other => SpawnerError::Docker(other),
            })?;

        Ok(container_info_from_inspect(data))
    }

    // ─────────────────────────────────────────────────────────────────────────
    // list_bots — all containers with the fks.bot=true label
    // ─────────────────────────────────────────────────────────────────────────

    pub async fn list_bots(&self) -> SpawnerResult<Vec<ContainerInfo>> {
        let mut filters: HashMap<String, Vec<String>> = HashMap::new();
        filters.insert("label".to_string(), vec!["fks.bot=true".to_string()]);

        let opts = ListContainersOptions {
            all: true,
            filters,
            ..Default::default()
        };

        let summaries = self.docker
            .list_containers(Some(opts))
            .await
            .map_err(SpawnerError::Docker)?;

        let infos = summaries
            .into_iter()
            .map(container_info_from_summary)
            .collect();

        Ok(infos)
    }

    // ─────────────────────────────────────────────────────────────────────────
    // stream_logs — returns an async Stream of log line strings
    // ─────────────────────────────────────────────────────────────────────────

    pub fn stream_logs(
        &self,
        id: &str,
        tail: Option<String>,
    ) -> impl Stream<Item = String> + 'static {
        let docker = self.docker.clone();
        let id = id.to_string();
        let tail_str = tail.unwrap_or_else(|| "100".to_string());

        async_stream::stream! {
            let opts = LogsOptions::<String> {
                follow:     true,
                stdout:     true,
                stderr:     true,
                timestamps: true,
                tail:       tail_str,
                ..Default::default()
            };

            let mut log_stream = docker.logs(&id, Some(opts));

            while let Some(item) = log_stream.next().await {
                match item {
                    Ok(LogOutput::StdOut { message }) |
                    Ok(LogOutput::StdErr { message }) => {
                        let line = String::from_utf8_lossy(&message).to_string();
                        yield line;
                    }
                    Ok(LogOutput::Console { message }) => {
                        let line = String::from_utf8_lossy(&message).to_string();
                        yield line;
                    }
                    Ok(_) => {}
                    Err(e) => {
                        warn!(container = %id, error = %e, "log stream error");
                        break;
                    }
                }
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // auto_prune — remove exited bot containers older than `prune_after_secs`
    // ─────────────────────────────────────────────────────────────────────────

    pub async fn auto_prune(&self) -> SpawnerResult<usize> {
        let mut filters: HashMap<String, Vec<String>> = HashMap::new();
        filters.insert("label".to_string(), vec!["fks.bot=true".to_string()]);
        filters.insert("status".to_string(), vec!["exited".to_string(), "dead".to_string()]);

        let opts = ListContainersOptions { all: true, filters, ..Default::default() };
        let stopped = self.docker.list_containers(Some(opts)).await.map_err(SpawnerError::Docker)?;

        let threshold = chrono::Duration::seconds(self.config.prune_after_secs);
        let cutoff = Utc::now() - threshold;

        let mut pruned = 0usize;

        for c in stopped {
            let id = c.id.as_deref().unwrap_or("");
            if id.is_empty() {
                continue;
            }

            // Use the Created timestamp from the summary as a proxy for
            // "finished_at" (good enough for prune purposes).
            let created_ts = c.created.unwrap_or(0);
            let created_at = DateTime::from_timestamp(created_ts, 0)
                .unwrap_or(Utc::now());

            if created_at < cutoff {
                match self.remove(id).await {
                    Ok(_) => {
                        info!(container = %&id[..12.min(id.len())], "auto-pruned stopped bot container");
                        pruned += 1;
                    }
                    Err(e) => warn!(container = %id, error = %e, "auto-prune remove failed"),
                }
            }
        }

        if pruned > 0 {
            info!(count = pruned, "auto-prune complete");
        }

        Ok(pruned)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers — convert bollard types to ContainerInfo
// ─────────────────────────────────────────────────────────────────────────────

fn container_info_from_summary(s: bollard::models::ContainerSummary) -> ContainerInfo {
    let id_full = s.id.clone().unwrap_or_default();
    let id = id_full[..12.min(id_full.len())].to_string();

    let name = s
        .names
        .as_ref()
        .and_then(|n| n.first())
        .map(|n| n.trim_start_matches('/').to_string())
        .unwrap_or_else(|| id.clone());

    let labels = s.labels.clone().unwrap_or_default();
    let bot_id = labels.get("fks.bot_id").cloned().unwrap_or_default();
    let mode = labels.get("fks.mode").cloned().unwrap_or_default();

    let created_at = s
        .created
        .and_then(|ts| DateTime::from_timestamp(ts, 0));

    ContainerInfo {
        id,
        id_full,
        name,
        image: s.image.clone().unwrap_or_default(),
        status: s.status.clone().unwrap_or_default(),
        state: s.state.clone().unwrap_or_default(),
        bot_id,
        mode,
        created_at,
        started_at: None,
        finished_at: None,
        labels,
        cpu_percent: None,
        memory_bytes: None,
    }
}

fn container_info_from_inspect(d: bollard::models::ContainerInspectResponse) -> ContainerInfo {
    let id_full = d.id.clone().unwrap_or_default();
    let id = id_full[..12.min(id_full.len())].to_string();

    let name = d
        .name
        .as_ref()
        .map(|n| n.trim_start_matches('/').to_string())
        .unwrap_or_else(|| id.clone());

    let labels = d
        .config
        .as_ref()
        .and_then(|c| c.labels.clone())
        .unwrap_or_default();

    let bot_id = labels.get("fks.bot_id").cloned().unwrap_or_default();
    let mode = labels.get("fks.mode").cloned().unwrap_or_default();

    let state = d.state.as_ref();
    let status = state.and_then(|s| s.status.as_ref()).map(|s| s.to_string()).unwrap_or_default();
    let state_str = status.clone();

    let parse_dt = |s: Option<&String>| -> Option<DateTime<Utc>> {
        s.and_then(|ts| {
            // Docker returns times like "0001-01-01T00:00:00Z" for "never"
            let dt = DateTime::parse_from_rfc3339(ts).ok()?;
            let utc = dt.with_timezone(&Utc);
            if utc.year() < 2000 { None } else { Some(utc) }
        })
    };

    let started_at = state.and_then(|s| parse_dt(s.started_at.as_ref()));
    let finished_at = state.and_then(|s| parse_dt(s.finished_at.as_ref()));

    let created_at = d
        .created
        .as_ref()
        .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
        .map(|dt| dt.with_timezone(&Utc));

    ContainerInfo {
        id,
        id_full,
        name,
        image: d.config.as_ref().and_then(|c| c.image.clone()).unwrap_or_default(),
        status,
        state: state_str,
        bot_id,
        mode,
        created_at,
        started_at,
        finished_at,
        labels,
        cpu_percent: None,
        memory_bytes: None,
    }
}
