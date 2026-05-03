# JANUS Brain Runtime — Operator Runbook

> **Audience:** SRE / Ops engineers responsible for running the JANUS forward service  
> **Last updated:** 2025-07-11  
> **Service:** `janus-forward` (Brain Runtime subsystem)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Boot Sequence](#2-boot-sequence)
3. [Environment Variables Reference](#3-environment-variables-reference)
4. [Startup Modes](#4-startup-modes)
5. [Kill Switch Operations](#5-kill-switch-operations)
6. [REST API Endpoints](#6-rest-api-endpoints)
7. [Prometheus Metrics](#7-prometheus-metrics)
8. [Grafana Dashboard](#8-grafana-dashboard)
9. [Watchdog & Component Health](#9-watchdog--component-health)
10. [Affinity State Persistence (Redis)](#10-affinity-state-persistence-redis)
11. [Common Failure Scenarios](#11-common-failure-scenarios)
12. [Recovery Procedures](#12-recovery-procedures)
13. [Tuning Guide](#13-tuning-guide)
14. [Appendix: Pipeline Stages](#appendix-pipeline-stages)

---

## 1. Overview

The **Brain Runtime** is a brain-inspired trading pipeline embedded within the
JANUS forward service. It evaluates every trading signal through a sequence of
biological-metaphor stages before allowing execution:

```
Signal
  │
  ▼
┌──────────────┐
│ RegimeBridge  │  ← Maps market regime (Trending / MeanReverting / Volatile / Crisis)
└──────┬───────┘
       ▼
┌──────────────┐
│ Hypothalamus │  ← Scales position size based on regime confidence & volatility
└──────┬───────┘
       ▼
┌──────────────┐
│  Amygdala    │  ← Threat filter: detects high-risk conditions, forces ReduceOnly in crisis
└──────┬───────┘
       ▼
┌──────────────┐
│ StrategyGate │  ← Affinity-based gating: enables/disables strategies per asset
└──────┬───────┘
       ▼
┌──────────────┐
│ Correlation  │  ← Blocks excess correlated positions
│   Filter     │
└──────┬───────┘
       ▼
┌──────────────┐
│ Kill Switch  │  ← Global halt: blocks all trading when activated
└──────┬───────┘
       ▼
   Proceed / Block / ReduceOnly
```

The runtime also includes:

- **Pre-flight checks** — validated before trading begins
- **CNS Watchdog** — continuous health monitoring with heartbeats
- **Prometheus metrics** — full observability via `janus_brain_*` metrics
- **Redis persistence** — durable affinity tracker state across restarts
- **REST health endpoint** — `/api/v1/brain/health` for operators and load balancers

---

## 2. Boot Sequence

The forward service boot proceeds in this order:

```
1. Load configuration
   ├── Service config (host, ports, etc.)
   ├── Param reload config
   └── Brain runtime config (env vars → BrainRuntimeConfig)

2. Check BRAIN_PREFLIGHT_ONLY mode
   └── If true: run pre-flight checks, print report, exit

3. Boot BrainRuntime (if ENABLE_BRAIN_RUNTIME=true)
   ├── 3a. Run pre-flight checks
   │       ├── PipelineConstructCheck
   │       ├── GatingConfigCheck
   │       ├── CorrelationConfigCheck
   │       └── PipelineConfigCheck
   ├── 3b. Initialize TradingPipeline
   │       ├── CorrelationTracker
   │       ├── StrategyAffinityTracker
   │       └── StrategyGate
   ├── 3c. (Optional) Load affinity state from Redis
   └── 3d. (Optional) Start CNS Watchdog
           ├── Register components
           └── Wire kill switch (watchdog → pipeline)

4. Create ForwardService (REST, gRPC, WebSocket)

5. Start parameter hot-reload (if ENABLE_PARAM_RELOAD=true)

6. Start heartbeat loop (watchdog keep-alive)

7. Wait for SIGINT / SIGTERM

8. Graceful shutdown
   ├── Abort heartbeat loop
   ├── Save affinity state to Redis
   ├── Activate kill switch (safety)
   ├── Stop watchdog
   └── Log final health report
```

### Boot Failure Behavior

| Condition | `BRAIN_ENFORCE_PREFLIGHT=true` | `BRAIN_ENFORCE_PREFLIGHT=false` |
|-----------|-------------------------------|--------------------------------|
| Pre-flight check fails (critical) | Process exits with error | Warning logged, boot continues |
| Redis connection fails for affinity load | Warning logged, fresh tracker used | Same |
| Watchdog start fails | Error returned, process exits | Same (watchdog is optional) |

---

## 3. Environment Variables Reference

### Core Brain Runtime

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_BRAIN_RUNTIME` | bool | `true` | Master switch for the brain runtime |
| `BRAIN_PREFLIGHT_ONLY` | bool | `false` | Run pre-flight checks and exit (dry run) |
| `BRAIN_ABORT_ON_BOOT_FAILURE` | bool | `true` | Exit process if brain runtime boot fails |
| `BRAIN_ENFORCE_PREFLIGHT` | bool | `true` | Fail boot on critical pre-flight check failure |
| `BRAIN_AUTO_START_WATCHDOG` | bool | `true` | Start the CNS watchdog automatically on boot |
| `BRAIN_WIRE_KILL_SWITCH` | bool | `true` | Wire watchdog kill trigger to pipeline kill switch |
| `BRAIN_HEARTBEAT_MS` | u64 | `5000` | Heartbeat interval for watchdog keep-alive (ms) |
| `BRAIN_API_TOKEN` | string | _(unset)_ | Bearer token for destructive REST endpoints. When unset, all endpoints are open (dev mode). |

### Brain-Gated Execution

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BRAIN_ALLOW_REDUCE_ONLY` | bool | `true` | Forward `ReduceOnly` decisions to execution (else treat as block) |
| `BRAIN_APPLY_SCALE` | bool | `true` | Scale signal confidence by pipeline position-scale factor before submission |
| `BRAIN_MAX_SIGNAL_AGE_SECS` | u64 | `120` | Reject signals older than this many seconds (0 = no staleness check) |
| `BRAIN_RECORD_TRADE_RESULTS` | bool | `true` | Feed trade results back into the affinity tracker after execution |

> **Note:** Brain-gated execution is automatically wired when `ENABLE_BRAIN_RUNTIME=true` and
> an execution endpoint is configured. The `SignalGenerator` and `EventLoop` submission paths
> both route through the brain pipeline before orders reach the execution service / Bybit REST API.

### Pipeline Stages

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BRAIN_ENABLE_HYPOTHALAMUS` | bool | `true` | Enable position-size scaling by regime |
| `BRAIN_ENABLE_AMYGDALA` | bool | `true` | Enable threat/crisis detection filter |
| `BRAIN_ENABLE_GATING` | bool | `true` | Enable strategy affinity gating |
| `BRAIN_ENABLE_CORRELATION` | bool | `true` | Enable correlated-position blocking |

### Pipeline Tuning

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BRAIN_MAX_POSITION_SCALE` | f64 | `2.0` | Maximum position scale (hypothalamus output) |
| `BRAIN_MIN_POSITION_SCALE` | f64 | `0.1` | Minimum position scale |
| `BRAIN_HIGH_RISK_SCALE` | f64 | `0.5` | Scale factor when amygdala detects high risk |
| `BRAIN_ALLOW_CRISIS_POSITIONS` | bool | `false` | Allow new positions during crisis regime |
| `BRAIN_MIN_REGIME_CONFIDENCE` | f64 | `0.3` | Minimum regime confidence to proceed |

### Watchdog

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BRAIN_WATCHDOG_CHECK_INTERVAL_MS` | u64 | `5000` | How often the watchdog checks component health |
| `BRAIN_WATCHDOG_DEGRADED_THRESHOLD` | u32 | `3` | Missed heartbeats before a component is "degraded" |
| `BRAIN_WATCHDOG_DEAD_THRESHOLD` | u32 | `5` | Missed heartbeats before a component is "dead" |
| `BRAIN_WATCHDOG_KILL_ON_CRITICAL_DEATH` | bool | `true` | Trigger kill switch when a critical component dies |

### Pre-flight

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BRAIN_PREFLIGHT_TIMEOUT_SECS` | u64 | `30` | Global timeout for all pre-flight checks |
| `BRAIN_SKIP_INFRUSTCODE_CHECKS` | bool | `false` | Skip infrastructure-level pre-flight checks |

### Affinity Redis Persistence

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BRAIN_AFFINITY_REDIS_URL` | string | `redis://127.0.0.1:6379` | Redis URL for affinity state |
| `REDIS_URL` | string | (fallback) | Fallback if `BRAIN_AFFINITY_REDIS_URL` is not set |
| `BRAIN_AFFINITY_REDIS_KEY` | string | `janus:affinity:state` | Redis key for the serialized state |
| `BRAIN_AFFINITY_REDIS_TTL_SECS` | u64 | `604800` (7 days) | TTL on the state key |
| `BRAIN_AFFINITY_REDIS_CONNECT_TIMEOUT_SECS` | u64 | `5` | Connection timeout to Redis |
| `BRAIN_AFFINITY_MIN_TRADES` | usize | `10` | Minimum trades before affinity scores influence gating |
| `BRAIN_AFFINITY_AUTOSAVE_INTERVAL_SECS` | u64 | `300` | How often (seconds) to auto-save affinity state to Redis (0 = disabled) |

### Multi-Instance Redis Kill Switch

When running multiple `janus-forward` replicas, enable the shared Redis-backed
kill switch so that activating the kill switch on **any** instance halts trading
on **all** instances.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BRAIN_KILL_SWITCH_REDIS_URL` | string | `redis://127.0.0.1:6379` | Redis URL for kill switch state |
| `REDIS_URL` | string | (fallback) | Fallback if `BRAIN_KILL_SWITCH_REDIS_URL` is not set |
| `BRAIN_KILL_SWITCH_REDIS_KEY` | string | `janus:kill_switch` | Redis key for the kill switch flag (`"1"` = active, `"0"` = inactive) |
| `BRAIN_KILL_SWITCH_POLL_MS` | u64 | `1000` | How often (ms) to poll Redis for remote state changes |
| `BRAIN_KILL_SWITCH_TTL_SECS` | u64 | `0` | TTL for auto-deactivation (dead-man's switch). `0` = no expiry |
| `BRAIN_KILL_SWITCH_CONNECT_TIMEOUT_SECS` | u64 | `5` | Connection timeout to Redis |
| `BRAIN_KILL_SWITCH_INSTANCE_ID` | string | `$HOSTNAME` | Instance identifier for audit trail |

**Redis keys used:**

| Key | Purpose |
|-----|---------|
| `janus:kill_switch` | Kill switch state (`"1"` / `"0"`) |
| `janus:kill_switch:meta` | JSON metadata (who activated, when, reason) |
| `janus:kill_switch:audit` | Last 100 state-change events (LIFO list) |

**Dead-man's switch mode:** Set `BRAIN_KILL_SWITCH_TTL_SECS` to a non-zero value
(e.g. `3600`). The sync task will automatically refresh the TTL while the instance
is alive. If all instances die without deactivating, the kill switch key expires and
trading resumes on restart. Use with caution.

### Logging

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RUST_LOG` | string | `info,janus_forward=debug` | Standard Rust log filter |

---

## 4. Startup Modes

### Normal Production Start

```bash
ENABLE_BRAIN_RUNTIME=true \
BRAIN_ENFORCE_PREFLIGHT=true \
BRAIN_AUTO_START_WATCHDOG=true \
BRAIN_WIRE_KILL_SWITCH=true \
RUST_LOG=info,janus_forward=debug \
./janus-forward
```

### Pre-flight Dry Run

Validates configuration without starting the service. Use in CI or before a deploy:

```bash
BRAIN_PREFLIGHT_ONLY=true ./janus-forward
# Exit code 0 = all checks passed
# Exit code 1 = critical check(s) failed
```

### Degraded Mode (No Brain)

Runs the forward service without the brain pipeline (signals go straight to execution):

```bash
ENABLE_BRAIN_RUNTIME=false ./janus-forward
```

### Soft Pre-flight (Warn Only)

Logs pre-flight failures but does not block boot:

```bash
BRAIN_ENFORCE_PREFLIGHT=false ./janus-forward
```

### Minimal Pipeline (Stages Disabled)

Useful for debugging — pipeline exists but every stage is a no-op pass-through:

```bash
BRAIN_ENABLE_HYPOTHALAMUS=false \
BRAIN_ENABLE_AMYGDALA=false \
BRAIN_ENABLE_GATING=false \
BRAIN_ENABLE_CORRELATION=false \
./janus-forward
```

---

## 5. Kill Switch Operations

The **kill switch** is a global trading halt. When active, every signal
evaluation returns `TradeAction::Block` with stage `KillSwitch`.

### Activation Sources

| Source | Trigger |
|--------|---------|
| Watchdog | Critical component marked dead (`BRAIN_WATCHDOG_KILL_ON_CRITICAL_DEATH=true`) |
| REST API | `POST /api/v1/brain/kill-switch/activate` |
| Graceful shutdown | Automatically activated during `BrainRuntime::shutdown()` |
| Code | `pipeline.activate_kill_switch().await` |
| Redis (multi-instance) | Any instance activates via `RedisKillSwitch::activate()` |
| Redis sync failure | 10 consecutive Redis poll failures auto-activate local kill switch |

### Deactivation

| Source | Action |
|--------|--------|
| REST API | `POST /api/v1/brain/kill-switch/deactivate` |
| Code | `pipeline.deactivate_kill_switch().await` |
| Redis (multi-instance) | Any instance deactivates via `RedisKillSwitch::deactivate()` |
| Restart | In-memory kill switch resets on restart. Redis kill switch persists. |
| TTL expiry | If `BRAIN_KILL_SWITCH_TTL_SECS > 0`, key expires when all instances die |

### Verification

```bash
# Check current status via REST
curl -s http://localhost:8080/api/v1/brain/health | jq '.pipeline.is_killed'

# Check via Prometheus
curl -s http://localhost:9090/api/v1/query?query=janus_brain_kill_switch_active

# Check Redis directly (multi-instance mode)
redis-cli GET janus:kill_switch        # "1" = active, "0" = inactive
redis-cli GET janus:kill_switch:meta   # JSON: who activated, when, reason

# View audit trail (last 10 events)
redis-cli LRANGE janus:kill_switch:audit 0 9
```

### Multi-Instance Kill Switch (Redis)

When running multiple replicas, the `RedisKillSwitch` provides coordinated
trading halts across all instances:

```rust,ignore
use janus_forward::persistence::kill_switch_redis::{
    RedisKillSwitch, RedisKillSwitchConfig,
    wire_and_spawn_redis_kill_switch,
};

// Option A: Wire from env and spawn sync task
let (ks, sync_handle) = wire_and_spawn_redis_kill_switch(pipeline.clone()).await?;

// Option B: Manual setup
let config = RedisKillSwitchConfig::from_env();
let ks = Arc::new(RedisKillSwitch::new(config).await?);
let sync_handle = ks.spawn_sync_task(pipeline.clone());

// Activate from any instance — all instances see it within poll_interval_ms
ks.activate("operator", "market crash detected").await?;

// View state including metadata and TTL
let state = ks.state().await?;
println!("Active: {}, Last event: {:?}", state.active, state.last_event);

// View audit trail
let trail = ks.audit_trail(10).await?;
for event in &trail {
    println!("{}: {} by {} — {}", event.timestamp, 
        if event.active { "ACTIVATED" } else { "DEACTIVATED" },
        event.actor, event.reason);
}

// On shutdown, abort the sync task
sync_handle.abort();
```

**Propagation latency:** State changes propagate to other instances within
`BRAIN_KILL_SWITCH_POLL_MS` (default: 1000ms). For faster propagation, reduce
the poll interval at the cost of increased Redis load.

**Safety on Redis failure:** If the sync task encounters 10 consecutive Redis
read failures, it automatically activates the local pipeline's kill switch as
a safety measure (fail-closed). Trading resumes only when Redis connectivity
is restored and the remote state is confirmed inactive.

### ⚠️ Important

- The **in-memory** kill switch does NOT persist across restarts.
- The **Redis** kill switch persists across restarts and coordinates multiple instances.
- Activating the kill switch does **not** close existing positions — it only blocks new trades.
- The Redis kill switch stores an audit trail of the last 100 state changes for post-incident review.

---

## 6. REST API Endpoints

All brain-related endpoints are under `/api/v1/brain/`.

### Authentication

Destructive endpoints (kill-switch activate/deactivate, affinity reset) are
protected by bearer-token authentication when `BRAIN_API_TOKEN` is set.
Read-only endpoints (health, pipeline, affinity export) are always public.

| Endpoint | Method | Auth Required |
|----------|--------|---------------|
| `/api/v1/brain/health` | GET | ❌ No |
| `/api/v1/brain/pipeline` | GET | ❌ No |
| `/api/v1/brain/affinity` | GET | ❌ No |
| `/api/v1/brain/kill-switch/activate` | POST | 🔒 Yes |
| `/api/v1/brain/kill-switch/deactivate` | POST | 🔒 Yes |
| `/api/v1/brain/affinity/reset` | POST | 🔒 Yes |

**Setup:**

```bash
# Set the token in your environment (production)
export BRAIN_API_TOKEN="your-secret-token-here"
```

**Usage:**

```bash
# Protected endpoints require Authorization: Bearer <token>
curl -X POST localhost:8080/api/v1/brain/kill-switch/activate \
  -H "Authorization: Bearer your-secret-token-here"

# Without token → 401 Unauthorized
curl -X POST localhost:8080/api/v1/brain/kill-switch/activate
# {"error":"unauthorized","message":"Missing Authorization header. Use: Authorization: Bearer <BRAIN_API_TOKEN>"}

# Wrong token → 403 Forbidden
curl -X POST localhost:8080/api/v1/brain/kill-switch/activate \
  -H "Authorization: Bearer wrong-token"
# {"error":"forbidden","message":"Invalid bearer token"}
```

> **⚠️ Dev mode:** When `BRAIN_API_TOKEN` is not set, all endpoints are
> unprotected. A warning is logged at startup. Always set this variable in
> production and staging environments.

### `GET /api/v1/brain/health`

Full health report including runtime state, boot status, watchdog snapshot,
pipeline metrics, and kill switch status.

**Response (200 OK):**

```json
{
  "healthy": true,
  "state": "Running",
  "boot_passed": true,
  "boot_summary": "4 passed, 0 failed, 0 skipped",
  "watchdog": {
    "uptime_secs": 3621.5,
    "total_components": 8,
    "alive_count": 8,
    "degraded_count": 0,
    "dead_count": 0,
    "health_score": 1.0,
    "is_operational": true,
    "components": [
      {
        "name": "forward_service",
        "state": "Alive",
        "criticality": "Critical",
        "missed_heartbeats": 0,
        "last_heartbeat_ago_secs": 1.2
      }
    ]
  },
  "pipeline": {
    "total_evaluations": 1523,
    "proceed_count": 1200,
    "block_count": 280,
    "reduce_only_count": 43,
    "avg_evaluation_us": 142.3,
    "block_rate_pct": 18.4,
    "is_killed": false
  },
  "timestamp": "2025-07-11T14:30:00Z"
}
```

**Health semantics:**  
`healthy = true` when ALL of:
- `state == Running`
- `boot_passed == true`
- Watchdog operational (no dead critical components)
- Pipeline kill switch NOT active

### `GET /api/v1/brain/pipeline`

Pipeline-only metrics (lighter weight than full health).

**Response (200 OK):**

```json
{
  "total_evaluations": 1523,
  "proceed_count": 1200,
  "block_count": 280,
  "reduce_only_count": 43,
  "avg_evaluation_us": 142.3,
  "block_rate_pct": 18.4,
  "is_killed": false
}
```

**Response (503 Service Unavailable):** if pipeline is not initialized.

### `POST /api/v1/brain/kill-switch/activate`

Activates the pipeline kill switch (halts all trading).

**Response (200 OK):**

```json
{
  "success": true,
  "is_killed": true,
  "message": "Kill switch activated — all trading is halted",
  "timestamp": "2025-07-11T14:30:00Z"
}
```

### `POST /api/v1/brain/kill-switch/deactivate`

Deactivates the pipeline kill switch (resumes trading).

**Response (200 OK):**

```json
{
  "success": true,
  "is_killed": false,
  "message": "Kill switch deactivated — trading resumed",
  "timestamp": "2025-07-11T14:30:00Z"
}
```

### `GET /api/v1/brain/affinity`

Exports the current strategy affinity tracker state as JSON. Useful for debugging
which strategy–asset pairs have been recorded and what their affinity weights are.

**Response (200 OK):**

```json
{
  "available": true,
  "pair_count": 5,
  "state": {
    "affinities": { "...": "..." },
    "min_trades_for_confidence": 10
  },
  "timestamp": "2025-07-11T14:30:00Z"
}
```

When the pipeline is not initialized, returns `available: false` with `state: null`.

### `POST /api/v1/brain/affinity/reset`

Resets the strategy affinity tracker to an empty state, clearing all recorded
strategy–asset performance data. The `min_trades_for_confidence` setting is preserved.

> ⚠️ **Use with caution in production.** After a reset the tracker will need to
> re-learn strategy affinities from scratch. All gating weights revert to the
> neutral default (0.5) until enough new trades are recorded.

**Response (200 OK):**

```json
{
  "success": true,
  "cleared_pairs": 5,
  "message": "Affinity tracker reset — 5 strategy-asset pairs cleared",
  "timestamp": "2025-07-11T14:30:00Z"
}
```

**Response (503 Service Unavailable)** — when the brain pipeline is not initialized.

---

## 7. Prometheus Metrics

All brain pipeline metrics use the `janus_brain_` prefix.

### Counters

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `janus_brain_evaluations_total` | Counter | — | Total pipeline evaluations |
| `janus_brain_proceeds_total` | Counter | — | Signals that received `Proceed` |
| `janus_brain_blocks_total` | Counter | `stage` | Signals blocked, labeled by pipeline stage |
| `janus_brain_reduce_only_total` | Counter | — | Signals that received `ReduceOnly` |
| `janus_brain_amygdala_high_risk_total` | Counter | — | Times amygdala detected high-risk regime |
| `janus_brain_gate_rejections_total` | Counter | — | Times the strategy gate rejected a signal |
| `janus_brain_correlation_blocks_total` | Counter | — | Times correlation filter blocked a position |

### Histograms

| Metric | Type | Description |
|--------|------|-------------|
| `janus_brain_evaluation_duration_us` | Histogram | Pipeline evaluation latency in microseconds |
| `janus_brain_scale_histogram` | Histogram | Distribution of position scale factors |
| `janus_brain_confidence_histogram` | Histogram | Distribution of regime confidence values |

### Gauges

| Metric | Type | Description |
|--------|------|-------------|
| `janus_brain_kill_switch_active` | Gauge | 1 if kill switch is active, 0 otherwise |
| `janus_brain_boot_passed` | Gauge | 1 if boot pre-flight checks passed |
| `janus_brain_regime_evaluations` | Gauge (labeled) | Counter by regime type (`Trending`, `MeanReverting`, `Volatile`, `Crisis`, `Unknown`) |
| `janus_brain_watchdog_components_total` | Gauge | Total registered watchdog components |
| `janus_brain_watchdog_alive_count` | Gauge | Components in `Alive` state |
| `janus_brain_watchdog_degraded_count` | Gauge | Components in `Degraded` state |
| `janus_brain_watchdog_dead_count` | Gauge | Components in `Dead` state |

### Key Alerting Rules (Example)

```yaml
# Kill switch activated
- alert: JanusBrainKillSwitchActive
  expr: janus_brain_kill_switch_active == 1
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "JANUS brain kill switch is ACTIVE — all trading halted"

# High block rate
- alert: JanusBrainHighBlockRate
  expr: >
    sum(janus_brain_blocks_total) / janus_brain_evaluations_total > 0.5
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Brain pipeline blocking >50% of signals for 10+ minutes"

# Dead watchdog component
- alert: JanusBrainWatchdogDead
  expr: janus_brain_watchdog_dead_count > 0
  for: 30s
  labels:
    severity: critical
  annotations:
    summary: "One or more brain watchdog components are DEAD"

# Pipeline latency spike
- alert: JanusBrainHighLatency
  expr: >
    histogram_quantile(0.99,
      rate(janus_brain_evaluation_duration_us_bucket[5m])) > 10000
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Brain pipeline p99 latency > 10ms"
```

---

## 8. Grafana Dashboard

Import the dashboard from:

```
services/forward/grafana/brain-dashboard.json
```

### Sections

| Row | Title | What it shows |
|-----|-------|---------------|
| 1 | Overview | Kill switch status, boot status, total evaluations, proceeds, blocks, reduce-only |
| 2 | Evaluation Rates & Decisions | Decision rate timeseries, block rate gauge, blocks by pipeline stage |
| 3 | Latency & Scaling | p50/p90/p99 evaluation latency, position scale distribution |
| 4 | Regime & Confidence | Regime evaluations by type, confidence distribution |
| 5 | Pipeline Stages | Amygdala / Gate / Correlation event rates and totals |
| 6 | Watchdog Health | Component states (alive/degraded/dead), health score gauge |

### Setup

1. Import the JSON into Grafana (Dashboards → Import)
2. Select your Prometheus datasource when prompted
3. Dashboard auto-refreshes every 10 seconds
4. Default time range: 1 hour

---

## 9. Watchdog & Component Health

The CNS watchdog monitors these registered components:

| Component | Criticality | Description |
|-----------|-------------|-------------|
| `forward_service` | Critical | The forward service process itself |
| `regime_detector` | High | Regime detection subsystem |
| `trading_pipeline` | Critical | The brain trading pipeline |
| `data_feed` | High | Market data feed |
| `execution_client` | Critical | Connection to execution service |
| `risk_manager` | High | Risk management subsystem |
| `strategy_engine` | Medium | Strategy execution engine |
| `correlation_tracker` | Medium | Correlation tracking subsystem |

### Component States

| State | Meaning | Action |
|-------|---------|--------|
| `Alive` | Receiving heartbeats normally | None |
| `Degraded` | Missed ≥ `degraded_threshold` heartbeats | Investigate, may auto-recover |
| `Dead` | Missed ≥ `dead_threshold` heartbeats | Triggers kill switch if critical |

### Heartbeat Flow

```
Forward Service Main Loop
    │
    │  every BRAIN_HEARTBEAT_MS (default 5s)
    ▼
WatchdogHandle.heartbeat("forward_service")
WatchdogHandle.heartbeat("trading_pipeline")
    │
    ▼
CNS Watchdog (background task)
    │  every BRAIN_WATCHDOG_CHECK_INTERVAL_MS
    ▼
Check all components for missed heartbeats
    │
    ├── Missed < degraded_threshold → Alive
    ├── Missed ≥ degraded_threshold → Degraded
    └── Missed ≥ dead_threshold → Dead
                                       │
                                       ▼ (if critical + KILL_ON_CRITICAL_DEATH)
                                    Trigger Kill Switch
```

---

## 10. Affinity State Persistence (Redis)

The `StrategyAffinityTracker` records per-(strategy, asset) performance data
that determines which strategies are enabled for which assets. This data is
valuable and should survive restarts.

### How It Works

1. **On boot:** `AffinityRedisStore::load()` attempts to read from Redis key `janus:affinity:state`
2. **During runtime:** (optional) `spawn_affinity_autosave()` periodically saves state
3. **On shutdown:** `save_pipeline_affinity()` writes the final state to Redis

### Redis Key

| Key | Default | Description |
|-----|---------|-------------|
| `janus:affinity:state` | — | JSON-serialized `StrategyAffinityTracker` |

### Inspecting State

```bash
# Check if state exists
redis-cli EXISTS janus:affinity:state

# Check TTL
redis-cli TTL janus:affinity:state

# Check size
redis-cli STRLEN janus:affinity:state

# View raw state (careful — may be large)
redis-cli GET janus:affinity:state | python3 -m json.tool | head -50

# Delete state (forces fresh start)
redis-cli DEL janus:affinity:state
```

### Failure Modes

| Scenario | Behavior |
|----------|----------|
| Redis unreachable on boot | Warning logged, service starts with fresh (empty) tracker |
| Redis unreachable on shutdown | Error logged, state lost for this session |
| Corrupted state in Redis | Deserialization fails, warning logged, fresh tracker used |
| State exceeds 10 MB | Save rejected with error (safety guard against runaway growth) |

---

## 11. Common Failure Scenarios

### Scenario: All signals being blocked

**Symptoms:**
- `janus_brain_blocks_total` rising rapidly
- `janus_brain_proceeds_total` flat
- Block rate > 80%

**Diagnosis:**

```bash
# Check kill switch
curl -s localhost:8080/api/v1/brain/health | jq '.pipeline.is_killed'

# Check which stage is blocking
curl -s localhost:9090/api/v1/query?query=janus_brain_blocks_total
# Look at the 'stage' label to identify the blocking stage
```

**Resolution by stage:**

| Stage | Likely Cause | Fix |
|-------|-------------|-----|
| `KillSwitch` | Kill switch active | Deactivate via REST API or restart |
| `RegimeBridge` | Low regime confidence | Lower `BRAIN_MIN_REGIME_CONFIDENCE` or investigate regime detector |
| `Amygdala` | Persistent crisis detection | Check if market is actually in crisis; set `BRAIN_ALLOW_CRISIS_POSITIONS=true` temporarily |
| `StrategyGate` | Strategies disabled by poor performance | Check affinity tracker state; delete Redis key to reset |
| `CorrelationFilter` | Too many correlated positions open | Reduce positions or adjust correlation thresholds |

### Scenario: Watchdog triggers kill switch

**Symptoms:**
- Log message: `🛑 Watchdog triggered kill switch on pipeline`
- `janus_brain_kill_switch_active` = 1
- `janus_brain_watchdog_dead_count` > 0

**Diagnosis:**

```bash
curl -s localhost:8080/api/v1/brain/health | jq '.watchdog.components[] | select(.state == "Dead")'
```

**Resolution:**

1. Identify the dead component
2. Check if the component's subsystem is actually down (e.g., data feed disconnected)
3. Fix the underlying issue
4. Deactivate kill switch: `POST /api/v1/brain/kill-switch/deactivate`
5. If false positive: tune `BRAIN_WATCHDOG_DEAD_THRESHOLD` higher or set `BRAIN_WATCHDOG_KILL_ON_CRITICAL_DEATH=false`

### Scenario: Pre-flight checks failing

**Symptoms:**
- Log shows `❌ Pre-flight checks failed`
- Process exits (if `BRAIN_ENFORCE_PREFLIGHT=true`)

**Diagnosis:**

```bash
# Run in preflight-only mode for detailed output
BRAIN_PREFLIGHT_ONLY=true ./janus-forward
```

**Common pre-flight failures:**

| Check | Failure Cause | Fix |
|-------|--------------|-----|
| `PipelineConstructCheck` | Bug in pipeline construction | Check TradingPipelineConfig for invalid values |
| `GatingConfigCheck` | Invalid gating weights (< 0 or > 1) | Fix strategy gating config |
| `CorrelationConfigCheck` | Zero window, bad threshold, or zero max_positions | Fix correlation config |
| `PipelineConfigCheck` | Invalid scales (min > max), bad risk_factor, bad confidence | Fix pipeline env vars |

### Scenario: High evaluation latency

**Symptoms:**
- `janus_brain_evaluation_duration_us` p99 > 10,000 µs (10 ms)

**Resolution:**

1. Check if correlation tracker has too many pairs: reduce position count
2. Check if strategy gate has too many affinity entries: reset Redis state
3. Disable non-critical stages to isolate:
   ```bash
   BRAIN_ENABLE_GATING=false  # test without gating
   BRAIN_ENABLE_CORRELATION=false  # test without correlation
   ```

---

## 12. Recovery Procedures

### Procedure: Safe Restart After Kill Switch Event

```bash
# 1. Check current state
curl -s localhost:8080/api/v1/brain/health | jq '.'

# 2. If kill switch is active but system is actually healthy:
curl -X POST localhost:8080/api/v1/brain/kill-switch/deactivate

# 3. If system is unhealthy, fix the root cause first, then:
#    Option A: Deactivate kill switch via REST (no restart needed)
curl -X POST localhost:8080/api/v1/brain/kill-switch/deactivate

#    Option B: Restart the service (kill switch resets automatically)
kill -SIGTERM <pid>
./janus-forward
```

### Procedure: Reset Affinity State

When the affinity tracker is producing bad gating decisions (e.g., disabling
good strategies), reset the state:

```bash
# 1. Save current state for forensics
redis-cli GET janus:affinity:state > /tmp/affinity_backup_$(date +%s).json

# 2. Delete the state
redis-cli DEL janus:affinity:state

# 3. Restart the service to pick up a fresh tracker
kill -SIGTERM <pid>
./janus-forward

# The service will start with an empty affinity tracker.
# All strategies will be enabled (benefit of the doubt) until
# enough trade results accumulate for data-driven gating.
```

### Procedure: Emergency Trading Halt

```bash
# Option 1: REST API (preferred — no restart needed)
curl -X POST localhost:8080/api/v1/brain/kill-switch/activate

# Option 2: Environment variable (requires restart)
BRAIN_ALLOW_CRISIS_POSITIONS=false \
BRAIN_MIN_REGIME_CONFIDENCE=1.0 \
./janus-forward
# This effectively blocks everything since confidence is never 1.0

# Option 3: Disable brain runtime entirely
ENABLE_BRAIN_RUNTIME=false ./janus-forward
# ⚠️  This removes the brain gate — signals go directly to execution!
# Only use if the brain pipeline itself is the problem.
```

### Procedure: Bringing System Back Online After Halt

```bash
# 1. Verify root cause is resolved

# 2. Deactivate kill switch
curl -X POST localhost:8080/api/v1/brain/kill-switch/deactivate

# 3. Monitor the health endpoint
watch -n 5 'curl -s localhost:8080/api/v1/brain/health | jq ".healthy, .pipeline.block_rate_pct"'

# 4. Verify signals are flowing
watch -n 5 'curl -s localhost:8080/api/v1/brain/pipeline | jq ".total_evaluations, .proceed_count"'
```

---

## 13. Tuning Guide

### Block Rate Too High

The pipeline is blocking too many signals:

| Parameter | Current | Try | Effect |
|-----------|---------|-----|--------|
| `BRAIN_MIN_REGIME_CONFIDENCE` | 0.3 | 0.15 | Accept lower-confidence regimes |
| `BRAIN_ENABLE_GATING` | true | false | Disable strategy affinity gating |
| `BRAIN_ENABLE_CORRELATION` | true | false | Disable correlation blocking |
| `BRAIN_ALLOW_CRISIS_POSITIONS` | false | true | Allow trading in crisis regimes |

### Not Enough Risk Control

The pipeline is letting too many risky signals through:

| Parameter | Current | Try | Effect |
|-----------|---------|-----|--------|
| `BRAIN_MIN_REGIME_CONFIDENCE` | 0.3 | 0.5 | Require higher regime confidence |
| `BRAIN_HIGH_RISK_SCALE` | 0.5 | 0.25 | Scale down more in high-risk conditions |
| `BRAIN_MAX_POSITION_SCALE` | 2.0 | 1.0 | Cap maximum position scaling |
| `BRAIN_ALLOW_CRISIS_POSITIONS` | true | false | Block new positions in crisis |

### Position Sizing

| Parameter | Range | Guidance |
|-----------|-------|----------|
| `BRAIN_MIN_POSITION_SCALE` | 0.01–0.5 | Lower = smaller minimum positions |
| `BRAIN_MAX_POSITION_SCALE` | 1.0–3.0 | Higher = larger max positions in strong regimes |
| `BRAIN_HIGH_RISK_SCALE` | 0.1–0.8 | Lower = more aggressive risk reduction |

### Watchdog Sensitivity

| Parameter | Conservative | Moderate | Permissive |
|-----------|-------------|----------|------------|
| `BRAIN_WATCHDOG_DEGRADED_THRESHOLD` | 2 | 3 | 5 |
| `BRAIN_WATCHDOG_DEAD_THRESHOLD` | 3 | 5 | 10 |
| `BRAIN_HEARTBEAT_MS` | 2000 | 5000 | 10000 |
| `BRAIN_WATCHDOG_CHECK_INTERVAL_MS` | 2000 | 5000 | 10000 |

> **Tip:** In staging, use permissive settings. In production, use moderate or
> conservative settings.

---

## Appendix: Pipeline Stages

### RegimeBridge

Maps the incoming `RoutedSignal`'s `MarketRegime` to internal scaling and
filtering decisions. Blocks signals when regime confidence is below
`min_regime_confidence`.

- **Metric:** `janus_brain_regime_evaluations{regime="..."}`
- **Block stage label:** `RegimeBridge`
- **Tuning:** `BRAIN_MIN_REGIME_CONFIDENCE`

### Hypothalamus

Scales position size based on regime type and volatility:

| Regime | Scaling Behavior |
|--------|-----------------|
| Trending | Scale up (high confidence + low volatility = larger positions) |
| MeanReverting | Moderate scale (regime-appropriate sizing) |
| Volatile | Scale down (higher uncertainty) |
| Crisis | Minimal scale (amygdala may override to ReduceOnly) |

- **Metric:** `janus_brain_scale_histogram`
- **Tuning:** `BRAIN_MAX_POSITION_SCALE`, `BRAIN_MIN_POSITION_SCALE`

### Amygdala

Threat detection stage. Detects high-risk conditions and can:
- Scale down positions via `high_risk_scale_factor`
- Force `ReduceOnly` in crisis regimes
- Block new positions entirely if `allow_new_positions_in_crisis=false`

- **Metric:** `janus_brain_amygdala_high_risk_total`
- **Tuning:** `BRAIN_HIGH_RISK_SCALE`, `BRAIN_ALLOW_CRISIS_POSITIONS`

### StrategyGate

Uses the `StrategyAffinityTracker` to decide whether a strategy should be
enabled for a given asset in the current regime. Strategies with insufficient
trade history get the benefit of the doubt (enabled). Strategies with a poor
track record on a specific asset are disabled.

- **Metric:** `janus_brain_gate_rejections_total`
- **Tuning:** `BRAIN_ENABLE_GATING`, affinity tracker state (Redis)

### CorrelationFilter

Checks whether accepting a new position would create excess correlation risk
with existing positions. Uses the `CorrelationTracker` which maintains a
rolling window of price correlations.

- **Metric:** `janus_brain_correlation_blocks_total`
- **Tuning:** `BRAIN_ENABLE_CORRELATION`, correlation config in `TradingPipelineConfig`

### KillSwitch

Binary halt — if active, blocks everything unconditionally.

- **Metric:** `janus_brain_kill_switch_active`
- **Control:** REST API, watchdog auto-trigger, graceful shutdown

---

## Brain-Gated Execution Architecture

When `ENABLE_BRAIN_RUNTIME=true` and an execution endpoint is configured, the
forward service automatically wraps the execution client with the brain pipeline
gate. Every signal submission is evaluated through the full pipeline before
reaching the execution service.

### Submission Paths

| Path | Where | Gate |
|------|-------|------|
| `SignalGenerator::submit_to_execution` | REST signal generation, unified binary | `BrainGatedExecutionClient` wraps `ExecutionClient` |
| `SignalGenerator::submit_signal_to_execution` | Unified binary (`start_module`) | Routed through `submit_to_execution` when gated client is set |
| `EventLoop::execute_order` | Live Bybit WebSocket event loop | `brain_gate_check()` called before each buy handler |

### EventLoop Brain Gate

Each buy handler in the event loop (`handle_buy_signal`, `handle_mean_reversion_buy`,
`handle_squeeze_breakout_buy`, `handle_vwap_buy`, `handle_orb_buy`, `handle_ema_ribbon_buy`,
`handle_trend_pullback_buy`, `handle_momentum_surge_buy`, `handle_multi_tf_buy`) calls
`brain_gate_check("<strategy_name>")` before executing the order. If the pipeline blocks
the trade, the order is skipped and a rejection metric is recorded. If the pipeline
approves with a scale < 1.0, the position size is reduced accordingly.

Sell/close handlers are **not** gated — you can always close an existing position.

### Wiring Order (main.rs)

1. Load configuration
2. Boot `BrainRuntime` (creates `TradingPipeline`)
3. Build `BrainHealthState` from runtime components (pipeline, watchdog handle, boot report)
4. Connect to Redis and **restore affinity state** (`load_pipeline_affinity`)
5. Create `ForwardService`
6. **Wire brain health state** (`service.set_brain_health_state(...)`) — mounts `/brain/*` REST endpoints
7. **Wire brain-gated client** (`service.set_brain_gated_client(...)`) — must happen before `start()` or `start_with_param_reload()`
8. **Spawn affinity autosave** (`spawn_affinity_autosave`) — periodic Redis persistence
9. Start param reload / service
10. Start watchdog heartbeat loop
11. On shutdown: abort autosave, **save affinity one final time** (`save_pipeline_affinity`), then shut down brain runtime

### Wiring Order (start_module — unified binary)

The unified binary path (`start_module()`) performs the same wiring automatically:

1. Boot `BrainRuntime` with default config (respects `ENABLE_BRAIN_RUNTIME` env var)
2. Wire brain-gated execution into `SignalGenerator`
3. Build and attach `BrainHealthState` for REST endpoints
4. Load affinity state from Redis and spawn autosave task
5. On shutdown: save affinity, shut down brain runtime

---

## Quick Reference Card

```
# Health check (public — no auth needed)
curl localhost:8080/api/v1/brain/health | jq .

# Is the kill switch on? (public)
curl localhost:8080/api/v1/brain/health | jq '.pipeline.is_killed'

# Pipeline metrics (public)
curl localhost:8080/api/v1/brain/pipeline | jq .

# Export affinity state (public)
curl localhost:8080/api/v1/brain/affinity | jq .

# Activate kill switch (🔒 requires BRAIN_API_TOKEN)
curl -X POST localhost:8080/api/v1/brain/kill-switch/activate \
  -H "Authorization: Bearer $BRAIN_API_TOKEN"

# Deactivate kill switch (🔒 requires BRAIN_API_TOKEN)
curl -X POST localhost:8080/api/v1/brain/kill-switch/deactivate \
  -H "Authorization: Bearer $BRAIN_API_TOKEN"

# Reset affinity state via REST API (🔒 requires BRAIN_API_TOKEN)
curl -X POST localhost:8080/api/v1/brain/affinity/reset \
  -H "Authorization: Bearer $BRAIN_API_TOKEN"

# Reset affinity state (via Redis + restart — no token needed)
redis-cli DEL janus:affinity:state && kill -SIGTERM <pid> && ./janus-forward

# Pre-flight dry run
BRAIN_PREFLIGHT_ONLY=true ./janus-forward

# Check watchdog component health (public)
curl localhost:8080/api/v1/brain/health | jq '.watchdog.components'

# Prometheus queries
# Block rate:     sum(janus_brain_blocks_total) / janus_brain_evaluations_total
# Evaluation p99: histogram_quantile(0.99, rate(janus_brain_evaluation_duration_us_bucket[5m]))
# Kill switch:    janus_brain_kill_switch_active
```
