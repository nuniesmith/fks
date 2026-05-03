use redis::AsyncCommands;
use serde_json::Value;
use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::RwLock;
use tracing::{debug, info, warn};

const HEARTBEAT_TTL: usize = 120;
const PNL_MAX: usize = 500;
const ALERTS_MAX: usize = 200;

/// Returns the current Unix timestamp as a f64.
fn now_ts() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

#[derive(Default)]
struct InMemoryStore {
    // Stores (value, expire_ts)
    strings: HashMap<String, (String, Option<f64>)>,
    lists: HashMap<String, VecDeque<String>>,
}

/// Single-asset async Redis store for the SAR bot.
/// Falls back silently to in-memory dicts when Redis is unavailable.
pub struct RedisStore {
    url: String,
    password: Option<String>,
    prefix: String,
    redis: Arc<RwLock<Option<redis::aio::MultiplexedConnection>>>,
    mem: Arc<RwLock<InMemoryStore>>,
}

impl RedisStore {
    pub fn new(redis_url: &str, password: Option<&str>, prefix: &str) -> Self {
        Self {
            url: redis_url.to_string(),
            password: password.map(ToString::to_string),
            prefix: prefix.to_string(),
            redis: Arc::new(RwLock::new(None)),
            mem: Arc::new(RwLock::new(InMemoryStore::default())),
        }
    }

    // ------------------------------------------------------------------
    // Key builder
    // ------------------------------------------------------------------
    fn key(&self, suffix: &str) -> String {
        format!("{}{suffix}", self.prefix)
    }

    // ------------------------------------------------------------------
    // Connection lifecycle
    // ------------------------------------------------------------------
    pub async fn connect(&self) {
        // Construct the client URL, injecting password if present.
        // redis-rs accepts auth via `redis://:password@host:port`.
        let effective_url = if let Some(pw) = &self.password {
            let url = &self.url;
            if let Some(rest) = url.strip_prefix("redis://") {
                format!("redis://:{pw}@{rest}")
            } else if let Some(rest) = url.strip_prefix("rediss://") {
                format!("rediss://:{pw}@{rest}")
            } else {
                url.clone()
            }
        } else {
            self.url.clone()
        };
        let client_res = redis::Client::open(effective_url.as_str());

        let client = match client_res {
            Ok(c) => c,
            Err(e) => {
                warn!("Failed to parse Redis URL ({e}): using in-memory fallback");
                return;
            }
        };

        match client.get_multiplexed_async_connection().await {
            Ok(mut conn) => {
                let ping: redis::RedisResult<String> =
                    redis::cmd("PING").query_async(&mut conn).await;
                match ping {
                    Ok(_) => {
                        // Assign and immediately drop the write guard.
                        *self.redis.write().await = Some(conn);
                        info!("Redis connected at {} (prefix='{}')", self.url, self.prefix);
                    }
                    Err(e) => {
                        warn!("Redis PING failed ({e}): using in-memory fallback");
                    }
                }
            }
            Err(e) => {
                warn!("Redis unavailable ({e}): using in-memory fallback");
            }
        }
    }

    pub async fn close(&self) {
        *self.redis.write().await = None;
        info!("Redis connection closed");
    }

    pub async fn is_connected(&self) -> bool {
        self.redis.read().await.is_some()
    }

    // ------------------------------------------------------------------
    // Low-level helpers — named without underscore prefix so clippy is
    // happy; they are private (no `pub`) so callers outside this module
    // cannot see them.
    // ------------------------------------------------------------------
    async fn kv_set(&self, key: &str, value: &str, ex: Option<usize>) {
        // Clone the connection (MultiplexedConnection is Clone) so the lock is
        // released before we do any I/O. A read lock suffices — we are not
        // mutating the Option itself, only using the cloned connection handle.
        let conn_opt = self.redis.read().await.clone();
        if let Some(mut conn) = conn_opt {
            let res: redis::RedisResult<()> = match ex {
                Some(seconds) => conn.set_ex(key, value, seconds as u64).await,
                None => conn.set(key, value).await,
            };
            if let Err(e) = res {
                warn!("Redis set error: {e}");
                // Drop the broken connection so the reconnect loop takes over.
                self.drop_connection().await;
            }
            return;
        }

        let expire_ts = ex.map(|secs| now_ts() + secs as f64);
        self.mem
            .write()
            .await
            .strings
            .insert(key.to_string(), (value.to_string(), expire_ts));
    }

    async fn kv_get(&self, key: &str) -> Option<String> {
        // Read lock — we only need to clone the connection handle.
        let conn_opt = self.redis.read().await.clone();
        if let Some(mut conn) = conn_opt {
            let res: redis::RedisResult<Option<String>> = conn.get(key).await;
            return match res {
                Ok(val) => val,
                Err(e) => {
                    warn!("Redis get error: {e}");
                    // Drop the broken connection so the reconnect loop takes over.
                    self.drop_connection().await;
                    None
                }
            };
        }

        // Check under a read lock first; only upgrade to a write lock if the
        // entry is expired and needs to be evicted.
        let expired = {
            let mem = self.mem.read().await;
            if let Some((value, expire_ts)) = mem.strings.get(key) {
                match expire_ts {
                    Some(ts) if now_ts() > *ts => true, // expired — needs eviction
                    _ => return Some(value.clone()),    // live — return early
                }
            } else {
                return None;
            }
        };

        if expired {
            self.mem.write().await.strings.remove(key);
        }
        None
    }

    async fn kv_ttl(&self, key: &str) -> i64 {
        // Read lock — cloning the connection handle does not mutate the Option.
        let conn_opt = self.redis.read().await.clone();
        if let Some(mut conn) = conn_opt {
            let res: redis::RedisResult<i64> = conn.ttl(key).await;
            return res.unwrap_or(-2);
        }

        // Extract expire_ts inside a tightly-scoped block so the read lock
        // is released before we do any arithmetic on the value.
        let expire_opt: Option<Option<f64>> = {
            let mem = self.mem.read().await;
            mem.strings.get(key).map(|(_, ts)| *ts)
        };

        match expire_opt {
            None => -2,
            Some(None) => -1,
            Some(Some(ts)) => {
                let remaining = ts - now_ts();
                if remaining < 0.0 {
                    -2
                } else {
                    remaining as i64
                }
            }
        }
    }

    #[allow(clippy::significant_drop_tightening)]
    async fn kv_incr(&self, key: &str) -> i64 {
        let conn_opt = self.redis.read().await.clone();
        if let Some(mut conn) = conn_opt {
            let res: redis::RedisResult<i64> = conn.incr(key, 1).await;
            return match res {
                Ok(v) => v,
                Err(e) => {
                    warn!("Redis incr error: {e}");
                    // Drop the broken connection so the reconnect loop takes over.
                    self.drop_connection().await;
                    0
                }
            };
        }

        {
            let mut mem = self.mem.write().await;
            let entry = mem
                .strings
                .entry(key.to_string())
                .or_insert_with(|| ("0".to_string(), None));
            let v = entry.0.parse::<i64>().unwrap_or(0) + 1;
            entry.0 = v.to_string();
            v
        } // mem guard dropped
    }

    #[allow(clippy::significant_drop_tightening)]
    async fn kv_lpush_trim(&self, key: &str, value: &str, maxlen: usize) {
        let conn_opt = self.redis.read().await.clone();
        if let Some(mut conn) = conn_opt {
            let mut pipe = redis::pipe();
            pipe.lpush(key, value)
                .ltrim(key, 0, maxlen.cast_signed() - 1);
            let res: redis::RedisResult<()> = pipe.query_async(&mut conn).await;
            if let Err(e) = res {
                warn!("Redis lpush_trim error: {e}");
                // Drop the broken connection so the reconnect loop takes over.
                self.drop_connection().await;
            }
            return;
        }

        let mut mem = self.mem.write().await;
        let lst = mem
            .lists
            .entry(key.to_string())
            .or_insert_with(VecDeque::new);
        lst.push_front(value.to_string());
        if lst.len() > maxlen {
            lst.truncate(maxlen);
        }
    }

    #[allow(clippy::significant_drop_tightening)]
    async fn kv_lrange(&self, key: &str, start: isize, stop: isize) -> Vec<String> {
        // Read lock — cloning the connection handle does not mutate the Option.
        let conn_opt = self.redis.read().await.clone();
        if let Some(mut conn) = conn_opt {
            let res: redis::RedisResult<Vec<String>> = conn.lrange(key, start, stop).await;
            return res.unwrap_or_default();
        }

        let mem = self.mem.read().await;
        if let Some(lst) = mem.lists.get(key) {
            let len = lst.len();
            let start_idx = if start < 0 {
                len.saturating_sub(start.unsigned_abs())
            } else {
                start as usize
            };
            let mut stop_idx = if stop < 0 {
                len.saturating_sub(stop.unsigned_abs())
            } else {
                stop as usize
            };

            if start_idx >= len || start_idx > stop_idx {
                return vec![];
            }
            if stop_idx >= len {
                stop_idx = len - 1;
            }

            return lst.range(start_idx..=stop_idx).cloned().collect();
        }
        vec![]
    }

    // ------------------------------------------------------------------
    // Domain methods
    // ------------------------------------------------------------------

    pub async fn save_trade_state(&self, state: &Value) {
        match serde_json::to_string(state) {
            Ok(payload) => self.kv_set(&self.key("trade_state"), &payload, None).await,
            Err(e) => warn!("save_trade_state serialization failed: {e}"),
        }
    }

    pub async fn load_trade_state(&self) -> Option<Value> {
        if let Some(raw) = self.kv_get(&self.key("trade_state")).await {
            return serde_json::from_str(&raw).ok();
        }
        None
    }

    pub async fn incr_loss_count(&self) -> i64 {
        self.kv_incr(&self.key("consec_losses")).await
    }

    pub async fn reset_loss_count(&self) {
        self.kv_set(&self.key("consec_losses"), "0", None).await;
    }

    pub async fn get_loss_count(&self) -> i64 {
        if let Some(raw) = self.kv_get(&self.key("consec_losses")).await {
            raw.parse().unwrap_or(0)
        } else {
            0
        }
    }

    pub async fn set_breaker_cooldown(&self, seconds: usize) {
        self.kv_set(&self.key("breaker_cooldown"), "1", Some(seconds))
            .await;
    }

    pub async fn is_breaker_open(&self) -> bool {
        self.kv_get(&self.key("breaker_cooldown")).await.is_some()
    }

    pub async fn breaker_cooldown_remaining(&self) -> i64 {
        let ttl = self.kv_ttl(&self.key("breaker_cooldown")).await;
        std::cmp::max(ttl, 0)
    }

    pub async fn record_pnl(&self, trade: &Value) {
        match serde_json::to_string(trade) {
            Ok(payload) => {
                self.kv_lpush_trim(&self.key("pnl_history"), &payload, PNL_MAX)
                    .await;
            }
            Err(e) => warn!("record_pnl serialization failed: {e}"),
        }
    }

    pub async fn get_pnl_history(&self, limit: usize) -> Vec<Value> {
        let limit = std::cmp::min(limit, PNL_MAX);
        let raw_items = self
            .kv_lrange(&self.key("pnl_history"), 0, limit.cast_signed() - 1)
            .await;
        raw_items
            .into_iter()
            .filter_map(|raw| serde_json::from_str(&raw).ok())
            .collect()
    }

    pub async fn save_best_params(&self, params: &Value, score: f64) {
        let payload = serde_json::json!({ "score": score, "params": params });
        if let Ok(raw) = serde_json::to_string(&payload) {
            self.kv_set(&self.key("best_params"), &raw, None).await;
        }
    }

    pub async fn load_best_params(&self) -> Option<Value> {
        if let Some(raw) = self.kv_get(&self.key("best_params")).await {
            return serde_json::from_str(&raw).ok();
        }
        None
    }

    pub async fn heartbeat(&self, status: &Value) {
        if let Value::Object(mut map) = status.clone() {
            map.insert("last_seen".to_string(), serde_json::json!(now_ts()));
            if let Ok(payload) = serde_json::to_string(&map) {
                self.kv_set(&self.key("heartbeat"), &payload, Some(HEARTBEAT_TTL))
                    .await;
            }
        }
    }

    pub async fn push_alert(&self, alert: &Value) {
        if let Ok(payload) = serde_json::to_string(alert) {
            self.kv_lpush_trim(&self.key("alerts"), &payload, ALERTS_MAX)
                .await;
        }
    }

    pub async fn get_alerts(&self, limit: usize) -> Vec<Value> {
        let limit = std::cmp::min(limit, ALERTS_MAX);
        let raw_items = self
            .kv_lrange(&self.key("alerts"), 0, limit.cast_signed() - 1)
            .await;
        raw_items
            .into_iter()
            .filter_map(|raw| serde_json::from_str(&raw).ok())
            .collect()
    }

    pub async fn save_optuna_trials(&self, trials: &[Value]) {
        match serde_json::to_string(trials) {
            Ok(payload) => {
                self.kv_set(&self.key("optuna_trials"), &payload, None)
                    .await;
                info!(
                    "save_optuna_trials: persisted {} trials (JSON)",
                    trials.len()
                );
            }
            Err(e) => warn!("save_optuna_trials failed: {e}"),
        }
    }

    pub async fn load_optuna_trials(&self) -> Vec<Value> {
        if let Some(raw) = self.kv_get(&self.key("optuna_trials")).await {
            match serde_json::from_str::<Vec<Value>>(&raw) {
                Ok(trials) => {
                    info!(
                        "load_optuna_trials: loaded {} trials from Redis (JSON)",
                        trials.len()
                    );
                    return trials;
                }
                Err(e) => warn!("load_optuna_trials failed (starting cold): {e}"),
            }
        }
        vec![]
    }

    pub async fn save_optimizer_meta(&self, meta: &Value) {
        match serde_json::to_string(meta) {
            Ok(payload) => {
                self.kv_set(&self.key("optimizer_meta"), &payload, None)
                    .await;
                debug!("save_optimizer_meta: {payload}");
            }
            Err(e) => warn!("save_optimizer_meta failed: {e}"),
        }
    }

    pub async fn load_optimizer_meta(&self) -> Option<Value> {
        if let Some(raw) = self.kv_get(&self.key("optimizer_meta")).await {
            return serde_json::from_str(&raw).ok();
        }
        None
    }

    // ------------------------------------------------------------------
    // Connection management
    // ------------------------------------------------------------------

    /// Mark the Redis connection as lost so the reconnect loop picks it up.
    async fn drop_connection(&self) {
        *self.redis.write().await = None;
        warn!(prefix = %self.prefix, "Redis connection dropped — falling back to in-memory");
    }

    // ------------------------------------------------------------------
    // Schema versioning
    // ------------------------------------------------------------------

    /// Bump this constant whenever the set of keys written to Redis changes
    /// shape (e.g. a `BotSettings` field is renamed or a new list is added).
    /// On startup `check_and_migrate_schema` will detect the mismatch, flush
    /// all prefixed keys, and write the new version — preventing a restarted
    /// bot from deserialising stale indicator or settings state silently.
    pub const SCHEMA_VERSION: u32 = 1;

    /// Call once after `connect()`. Compares the stored schema version key
    /// against `SCHEMA_VERSION`; if they differ (or the key is absent on a
    /// first-time init), every key under this store's prefix is deleted and
    /// the new version is written.
    pub async fn check_and_migrate_schema(&self) {
        let version_key = self.key("schema_version");
        let expected = Self::SCHEMA_VERSION.to_string();

        match self.kv_get(&version_key).await {
            Some(stored) if stored == expected => {
                // Schema is current — nothing to do.
            }
            Some(stored) => {
                warn!(
                    prefix   = %self.prefix,
                    stored   = %stored,
                    expected = %expected,
                    "Redis schema version mismatch — flushing stale state and reinitialising",
                );
                self.flush_prefix().await;
                self.kv_set(&version_key, &expected, None).await;
            }
            None => {
                info!(
                    prefix  = %self.prefix,
                    version = %expected,
                    "Redis schema: first-time initialisation",
                );
                self.kv_set(&version_key, &expected, None).await;
            }
        }
    }

    /// Delete every Redis key that starts with this store's prefix, plus
    /// clear the in-memory fallback maps.
    ///
    /// Uses `KEYS` (O(N)) which is acceptable at bot startup on a small
    /// keyspace. If the keyspace ever grows large, replace with a cursor-based
    /// `SCAN` loop to avoid blocking the Redis server.
    async fn flush_prefix(&self) {
        // ── Redis ─────────────────────────────────────────────────────────────
        let conn_opt = self.redis.read().await.clone();
        if let Some(mut conn) = conn_opt {
            let pattern = format!("{}*", self.prefix);
            let keys: redis::RedisResult<Vec<String>> = redis::cmd("KEYS")
                .arg(&pattern)
                .query_async(&mut conn)
                .await;
            match keys {
                Ok(keys) if !keys.is_empty() => {
                    let n = keys.len();
                    let _: redis::RedisResult<i64> = conn.del(keys).await;
                    info!(prefix = %self.prefix, deleted = n, "Redis: flushed stale keys");
                }
                Ok(_) => {} // nothing to delete
                Err(e) => warn!(prefix = %self.prefix, err = %e, "Redis KEYS failed during flush"),
            }
            return;
        }

        // ── In-memory fallback ────────────────────────────────────────────────
        let mut mem = self.mem.write().await;
        let before = mem.strings.len() + mem.lists.len();
        mem.strings.clear();
        mem.lists.clear();
        drop(mem);
        info!(prefix = %self.prefix, deleted = before, "in-memory store: flushed stale keys");
    }

    /// Spawn a background task that attempts to reconnect to Redis every 30 s
    /// whenever the connection is absent. The task holds an `Arc` clone so it
    /// stays alive as long as any caller still holds a reference to the store.
    ///
    /// Call this once after the initial `connect()`. Safe to call multiple
    /// times — each call spawns an independent loop, so only call it once.
    pub fn spawn_reconnect_loop(self: Arc<Self>) {
        tokio::spawn(async move {
            const INTERVAL: Duration = Duration::from_secs(30);
            loop {
                tokio::time::sleep(INTERVAL).await;
                if !self.is_connected().await {
                    info!(prefix = %self.prefix, "Redis: attempting reconnect");
                    self.connect().await;
                    if self.is_connected().await {
                        info!(prefix = %self.prefix, "Redis: reconnection successful");
                    }
                }
            }
        });
    }
}
