// =============================================================================
// db.rs — optional Postgres persistence for the FKS Bot Spawner
//
// Wraps the `bot_runs` table defined in src/sql/ruby/007_spawner.sql. The
// spawner runs perfectly without a database — the `BotRunStore` is wrapped
// in `Option` everywhere it's used, and missing/failed Postgres connections
// degrade gracefully to "stateless" operation (logged as a warning at boot).
//
// Schema this code expects (see 007_spawner.sql for the full definition):
//
//   bot_runs (
//       id              UUID PRIMARY KEY,
//       bot_config_id   UUID NULL,
//       container_id    TEXT NOT NULL,
//       container_name  TEXT,
//       image           TEXT NOT NULL,
//       mode            TEXT NOT NULL DEFAULT 'paper',
//       status          TEXT NOT NULL DEFAULT 'spawning',
//       started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
//       stopped_at      TIMESTAMPTZ,
//       runtime_secs    INTEGER,        -- computed by trigger
//       error_message   TEXT,
//       ...
//   )
//
// Status values used here mirror the CHECK constraint in the SQL:
//   'spawning' | 'running' | 'stopping' | 'stopped' | 'error' | 'pruned'
// =============================================================================

#![cfg(feature = "db")]

use std::time::Duration;

use chrono::{DateTime, Utc};
use sqlx::postgres::{PgPoolOptions, PgRow};
use sqlx::{PgPool, Row};
use tracing::{debug, info, warn};
use uuid::Uuid;

use crate::error::SpawnerError;

// ─────────────────────────────────────────────────────────────────────────────
// BotRunStore — thin wrapper around a sqlx PgPool, scoped to bot_runs ops.
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Clone)]
pub struct BotRunStore {
    pool: PgPool,
}

impl BotRunStore {
    /// Connect to Postgres. Returns `Ok(None)` when `database_url` is empty
    /// or the connection fails — callers treat that as "stateless mode" and
    /// continue running.
    pub async fn try_connect(database_url: &str) -> Option<Self> {
        if database_url.is_empty() {
            info!("spawner DB disabled (DATABASE_URL not set) — running stateless");
            return None;
        }

        let pool = PgPoolOptions::new()
            .max_connections(5)
            .acquire_timeout(Duration::from_secs(5))
            .connect(database_url)
            .await;

        match pool {
            Ok(pool) => {
                info!(url_host = %sanitize_url(database_url), "spawner connected to Postgres");
                Some(Self { pool })
            }
            Err(e) => {
                warn!(
                    error = %e,
                    url_host = %sanitize_url(database_url),
                    "spawner failed to connect to Postgres — running stateless"
                );
                None
            }
        }
    }

    /// Check the bot_runs table exists. Logs a warning if it doesn't but does
    /// not fail — we want the spawner to keep running even if migrations
    /// haven't been applied yet.
    pub async fn check_schema(&self) -> bool {
        match sqlx::query(
            "SELECT 1 FROM information_schema.tables \
             WHERE table_schema = 'public' AND table_name = 'bot_runs'",
        )
        .fetch_optional(&self.pool)
        .await
        {
            Ok(Some(_)) => true,
            Ok(None) => {
                warn!(
                    "bot_runs table not found — apply src/sql/ruby/007_spawner.sql \
                     (writes to bot_runs will be skipped)"
                );
                false
            }
            Err(e) => {
                warn!(error = %e, "schema probe failed — writes to bot_runs may fail");
                false
            }
        }
    }

    /// Insert a new bot_runs row when a container has been successfully
    /// created and started.
    pub async fn record_spawn(&self, args: RecordSpawn<'_>) -> Result<Uuid, SpawnerError> {
        let id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO bot_runs (\
                 id, container_id, container_name, image, mode, status, started_at\
             ) VALUES ($1, $2, $3, $4, $5, 'running', $6)",
        )
        .bind(id)
        .bind(args.container_id)
        .bind(args.container_name)
        .bind(args.image)
        .bind(args.mode)
        .bind(args.started_at)
        .execute(&self.pool)
        .await
        .map_err(map_sqlx)?;

        debug!(run_id = %id, container_id = %args.container_id, "bot_runs row inserted");
        Ok(id)
    }

    /// Mark a run as stopping → stopped. The DB trigger will compute
    /// `runtime_secs` from `started_at` automatically. Matches by short
    /// container_id (the spawner exposes 12-char IDs everywhere).
    pub async fn record_stop(&self, container_id: &str) -> Result<(), SpawnerError> {
        let rows = sqlx::query(
            "UPDATE bot_runs \
             SET status = 'stopped', stopped_at = NOW() \
             WHERE container_id = $1 AND stopped_at IS NULL",
        )
        .bind(container_id)
        .execute(&self.pool)
        .await
        .map_err(map_sqlx)?;

        debug!(
            container_id = %container_id,
            rows_affected = rows.rows_affected(),
            "bot_runs row updated to stopped"
        );
        Ok(())
    }

    /// Mark a run as removed/pruned. Used by both DELETE /container/:id and
    /// the auto-prune background task.
    pub async fn record_remove(&self, container_id: &str) -> Result<(), SpawnerError> {
        let rows = sqlx::query(
            "UPDATE bot_runs \
             SET status = CASE WHEN status = 'stopped' THEN 'pruned' ELSE 'stopped' END, \
                 stopped_at = COALESCE(stopped_at, NOW()) \
             WHERE container_id = $1",
        )
        .bind(container_id)
        .execute(&self.pool)
        .await
        .map_err(map_sqlx)?;

        debug!(
            container_id = %container_id,
            rows_affected = rows.rows_affected(),
            "bot_runs row updated to pruned/stopped"
        );
        Ok(())
    }

    /// Record a failure — used when spawn fails AFTER container creation
    /// (e.g. start_container failed).
    #[allow(dead_code)] // exposed for future use; spawn() currently rolls back via remove()
    pub async fn record_error(
        &self,
        container_id: &str,
        message: &str,
    ) -> Result<(), SpawnerError> {
        sqlx::query(
            "UPDATE bot_runs \
             SET status = 'error', error_message = $2, stopped_at = NOW() \
             WHERE container_id = $1",
        )
        .bind(container_id)
        .bind(message)
        .execute(&self.pool)
        .await
        .map_err(map_sqlx)?;
        Ok(())
    }

    /// Recent run history — newest first. Limit is clamped to 1..=500.
    pub async fn recent_runs(&self, limit: i64) -> Result<Vec<BotRunRow>, SpawnerError> {
        let limit = limit.clamp(1, 500);
        let rows = sqlx::query(
            "SELECT id, container_id, container_name, image, mode, status, \
                    started_at, stopped_at, runtime_secs, error_message \
             FROM bot_runs \
             ORDER BY started_at DESC \
             LIMIT $1",
        )
        .bind(limit)
        .fetch_all(&self.pool)
        .await
        .map_err(map_sqlx)?;

        Ok(rows.into_iter().map(BotRunRow::from_row).collect())
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// DTOs
// ─────────────────────────────────────────────────────────────────────────────

/// Arguments to `record_spawn` — borrowed strings to avoid pointless clones.
pub struct RecordSpawn<'a> {
    pub container_id: &'a str,
    pub container_name: &'a str,
    pub image: &'a str,
    pub mode: &'a str,
    pub started_at: DateTime<Utc>,
}

/// A row from `bot_runs` exposed via GET /runs.
#[derive(Debug, serde::Serialize)]
pub struct BotRunRow {
    pub id: Uuid,
    pub container_id: String,
    pub container_name: Option<String>,
    pub image: String,
    pub mode: String,
    pub status: String,
    pub started_at: DateTime<Utc>,
    pub stopped_at: Option<DateTime<Utc>>,
    pub runtime_secs: Option<i32>,
    pub error_message: Option<String>,
}

impl BotRunRow {
    fn from_row(r: PgRow) -> Self {
        Self {
            id: r.try_get("id").unwrap_or_else(|_| Uuid::nil()),
            container_id: r.try_get("container_id").unwrap_or_default(),
            container_name: r.try_get("container_name").ok(),
            image: r.try_get("image").unwrap_or_default(),
            mode: r.try_get("mode").unwrap_or_default(),
            status: r.try_get("status").unwrap_or_default(),
            started_at: r.try_get("started_at").unwrap_or_else(|_| Utc::now()),
            stopped_at: r.try_get("stopped_at").ok(),
            runtime_secs: r.try_get("runtime_secs").ok(),
            error_message: r.try_get("error_message").ok(),
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

fn map_sqlx(e: sqlx::Error) -> SpawnerError {
    SpawnerError::Other(format!("postgres: {e}"))
}

/// Strip user:password from a postgres URL for safe logging.
/// `postgres://user:pass@host:5432/db` → `host:5432/db`
fn sanitize_url(url: &str) -> String {
    if let Some(after_scheme) = url.split_once("://").map(|(_, rest)| rest) {
        if let Some((_, host)) = after_scheme.split_once('@') {
            return host.to_string();
        }
        return after_scheme.to_string();
    }
    "<unparseable>".to_string()
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::sanitize_url;

    #[test]
    fn sanitize_strips_credentials() {
        assert_eq!(
            sanitize_url("postgres://fks_user:secret@postgres:5432/ruby_db"),
            "postgres:5432/ruby_db"
        );
    }

    #[test]
    fn sanitize_handles_no_creds() {
        assert_eq!(
            sanitize_url("postgres://postgres:5432/ruby_db"),
            "postgres:5432/ruby_db"
        );
    }

    #[test]
    fn sanitize_handles_garbage() {
        assert_eq!(sanitize_url("not-a-url"), "<unparseable>");
    }
}
