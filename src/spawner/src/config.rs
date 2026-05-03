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
