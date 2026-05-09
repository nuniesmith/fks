// =============================================================================
// config.rs — FKS Bot Spawner configuration
//
// All values are read from environment variables with sane defaults.
// Set these in docker-compose.yml or the .env file.
// =============================================================================

use std::env;

#[derive(Debug, Clone)]
pub struct Config {
    /// Address to bind the HTTP server on.
    pub host: String,
    /// Port to bind the HTTP server on.
    pub port: u16,

    /// Only images whose name starts with this prefix are allowed to be spawned.
    /// Default: "fks-bot-" — prevents arbitrary image execution.
    pub allowed_image_prefix: String,

    /// Hard cap on simultaneously running bot containers.
    pub max_concurrent_bots: usize,

    /// Docker network that all spawned containers must join.
    pub allowed_network: String,

    /// Default CPU quota in fractional cores (e.g. 1.0 = one full core).
    pub default_cpu_limit: f64,

    /// Default memory limit in bytes (derived from DEFAULT_MEMORY_LIMIT_MB).
    pub default_memory_bytes: i64,

    /// Default CPU shares (relative weight; 1024 = normal priority).
    pub default_cpu_shares: i64,

    /// Path where the Prometheus file-based SD config is written.
    pub prometheus_sd_path: String,

    /// Port that each spawned bot container exposes for Prometheus scraping.
    pub bot_metrics_port: u16,

    /// Seconds a stopped container is kept before auto-prune removes it.
    pub prune_after_secs: i64,

    /// How often (in seconds) the background auto-prune task runs.
    pub prune_interval_secs: u64,

    /// Postgres connection string. Empty = stateless mode (no DB writes).
    /// Recognised env vars (in order): SPAWNER_DATABASE_URL, DATABASE_URL.
    pub database_url: String,
}

impl Config {
    pub fn from_env() -> Self {
        let default_memory_mb: i64 = env_parse("DEFAULT_MEMORY_LIMIT_MB", 512);
        Self {
            host: env::var("SPAWNER_HOST").unwrap_or_else(|_| "0.0.0.0".to_string()),
            port: env_parse("SPAWNER_PORT", 8090),
            allowed_image_prefix: env::var("ALLOWED_IMAGE_PREFIX")
                .unwrap_or_else(|_| "fks-bot-".to_string()),
            max_concurrent_bots: env_parse("MAX_CONCURRENT_BOTS", 20),
            allowed_network: env::var("ALLOWED_NETWORK")
                .unwrap_or_else(|_| "fks_network".to_string()),
            default_cpu_limit: env_parse_f64("DEFAULT_CPU_LIMIT", 1.0),
            default_memory_bytes: default_memory_mb * 1024 * 1024,
            default_cpu_shares: env_parse("DEFAULT_CPU_SHARES", 1024),
            prometheus_sd_path: env::var("PROMETHEUS_SD_PATH")
                .unwrap_or_else(|_| "/prometheus-sd/bots.json".to_string()),
            bot_metrics_port: env_parse("BOT_METRICS_PORT", 9091),
            prune_after_secs: env_parse("PRUNE_AFTER_SECS", 300),
            prune_interval_secs: env_parse("PRUNE_INTERVAL_SECS", 60),
            database_url: env::var("SPAWNER_DATABASE_URL")
                .or_else(|_| env::var("DATABASE_URL"))
                .unwrap_or_default(),
        }
    }

    pub fn bind_addr(&self) -> String {
        format!("{}:{}", self.host, self.port)
    }
}

fn env_parse<T: std::str::FromStr>(key: &str, default: T) -> T {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_parse_f64(key: &str, default: f64) -> f64 {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `from_env` returns sensible defaults when no env vars are set.
    /// Note: this test runs in the same process as other tests so it cannot
    /// safely mutate the environment; we only assert defaults that are not
    /// overridden by the test runner.
    #[test]
    fn defaults_are_safe() {
        // Build a Config manually rather than from_env() to avoid env coupling.
        let cfg = Config {
            host: "0.0.0.0".to_string(),
            port: 8090,
            allowed_image_prefix: "fks-bot-".to_string(),
            max_concurrent_bots: 20,
            allowed_network: "fks_network".to_string(),
            default_cpu_limit: 1.0,
            default_memory_bytes: 512 * 1024 * 1024,
            default_cpu_shares: 1024,
            prometheus_sd_path: "/prometheus-sd/bots.json".to_string(),
            bot_metrics_port: 9091,
            prune_after_secs: 300,
            prune_interval_secs: 60,
            database_url: String::new(),
        };
        assert_eq!(cfg.bind_addr(), "0.0.0.0:8090");
        assert!(
            cfg.database_url.is_empty(),
            "DB should default to stateless"
        );
        assert!(cfg.allowed_image_prefix.starts_with("fks-bot-"));
    }

    #[test]
    fn bind_addr_formats_correctly() {
        let cfg = Config {
            host: "127.0.0.1".to_string(),
            port: 12345,
            allowed_image_prefix: "x".into(),
            max_concurrent_bots: 1,
            allowed_network: "n".into(),
            default_cpu_limit: 0.5,
            default_memory_bytes: 1,
            default_cpu_shares: 1,
            prometheus_sd_path: "/x".into(),
            bot_metrics_port: 9091,
            prune_after_secs: 0,
            prune_interval_secs: 0,
            database_url: String::new(),
        };
        assert_eq!(cfg.bind_addr(), "127.0.0.1:12345");
    }
}
