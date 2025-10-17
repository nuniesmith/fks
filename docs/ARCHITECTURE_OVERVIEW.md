<!--
 Step 1 / Prompt 2: Populated architecture overview leveraging current Rust sources:
 - compose.rs (Docker Compose orchestration)
 - monitor.rs (service health + event emission)
 - websocket.rs (real‑time streaming interface)
 - config.rs (service + monitoring + alerts config)
 - metrics.rs (Prometheus instrumentation)
 - models.rs (shared data structures & event model)
-->

# FKS Master Orchestration Architecture

The `fks_master` service coordinates lifecycle, health, metrics, and real‑time insight across the FKS microservice fleet. It exposes:

1. Internal health monitoring & event broadcasting
2. Docker Compose orchestration actions (build / up / restart / logs …)
3. A WebSocket channel for near real‑time service + system state
4. Prometheus metrics for observability and alert routing

---
## High‑Level Component Map

| Component | File | Responsibility |
|-----------|------|----------------|
| Compose Orchestrator | `src/compose.rs` | Executes docker compose actions, records metrics |
| Config Loader | `src/config.rs` | Loads / defaults service + monitoring + alerts config |
| Health Monitor | `src/monitor.rs` | Parallel health checks, latency classification, event emission, resource sampling |
| Metrics Layer | `src/metrics.rs` | Prometheus registry & domain metrics (health, restarts, compose actions, WS connections, resource usage) |
| WebSocket Hub | `src/websocket.rs` | Bi‑directional client channel (initial state, periodic updates, events, commands) |
| Data Model | `src/models.rs` | Strongly typed service metadata, statuses, events, metrics payloads |

---
## Configuration & Alerting (`config.rs`)

`Config` aggregates three domains:

* `services[]`: Static service catalogue (id, health endpoint, service type, criticality, expected latency)
* `monitoring`: Tuning of cadence (interval, timeout, retry attempts, batch size) + feature flags (Docker stats)
* `alerts`: Thresholds for high latency + notification toggle

If no config file is present, a sane default set for core FKS services is synthesized (see hard‑coded defaults). This guarantees boot safety in ephemeral environments.

Alert hooks (webhooks / notifications) are currently structural only; high latency detection triggers `EventType::HighLatency` events which downstream alerting layers (e.g. Grafana Alerting / Alertmanager) can consume via Prometheus rules.

---
## Service Health Lifecycle (`monitor.rs`)

1. A monitoring loop runs at `check_interval_seconds` batching services to limit pressure.
2. Each service endpoint is probed with bounded timeout + retry semantics.
3. Response latency is evaluated vs `expected_response_time_ms` to classify Healthy vs Degraded.
4. Failures transition to Unhealthy, capturing error context and emitting `ServiceDown`.
5. Recovery from Unhealthy -> Healthy emits `ServiceUp`.
6. High latency crossing `alerts.high_latency_threshold_ms` emits `HighLatency` event.
7. A secondary metrics loop emits periodic `MetricsUpdate` events and (optionally) updates container resource gauges via `docker stats`.

Event retention: last 100 per service (trimmed ring) for lightweight historical context.

---
## Event Model (`models.rs`)

`MonitorEvent { event_type, service_id?, message, timestamp, data? }`

Current `EventType` variants:

* `ServiceUp`
* `ServiceDown`
* `ServiceRestarted` (reserved – to be emitted on successful restart integration)
* `HighLatency`
* `SystemAlert`
* `MetricsUpdate`

These map directly to WebSocket frames (`type: "event"`).

---
## Docker Compose Orchestration (`compose.rs`)

The orchestrator wraps the Docker CLI (`docker compose ...`) providing a typed `ComposeAction` enum (build, pull, up, start, stop, restart, push, ps, logs). Actions:

1. Arguments assembled (compose file, optional `-p` project, per‑action flags e.g. `-d`, `--tail`).
2. External process executed; stdout/stderr + exit code captured.
3. Prometheus counter `fks_compose_actions_total{action,success}` incremented.
4. JSON result optionally emitted for programmatic callers.

Planned Enhancement (Step 2 Prompt 3): Replace shell invocation with Bollard (Docker Engine API) for: security (no shell injection surface), structured error handling, future streaming log attachment, and multi‑arch awareness.

---
## Real‑Time WebSocket Interface (`websocket.rs`)

Connection lifecycle:

1. On connect → metrics counter incremented; initial payload includes full service state + system metrics.
2. Periodic (5s) update frames push refreshed aggregate metrics & service statuses.
3. Monitor events fan‑out via `broadcast::channel` to subscribed sockets (already wired in initial implementation).
4. Client commands parsed JSON → dispatch:
	* `restart_service` → orchestrated container restart (delegates to monitor handle) → emits `restart_result` frame.
	* `get_service_details` → returns point‑in‑time health & metrics for the service.
	* `subscribe_events` → (placeholder) will confirm event streaming (already effectively active via select loop).

Planned Enhancements:

* JWT handshake authentication (Step 2 Prompt 4)
* Explicit subscription model (service / event filtering)
* Backpressure & rate limiting
* Event replay window negotiation (client asks for last N events)

Message taxonomy:

* `initial` – bootstrap snapshot
* `update` – periodic summary
* `event` – single monitor event
* `restart_result` – outcome of restart attempt
* `service_details` – granular metrics for one service
* `subscription_confirmed` – (temporary placeholder)

---
## Metrics & Observability (`metrics.rs`)

Prometheus registry exports domain‑specific series: health status gauges, latency histograms, restart counters, compose action counts, WebSocket connections, error rates, resource utilization (CPU / memory / network / block IO), HTTP request counts & durations. Uptime increments every second via async task.

These power downstream dashboards (Grafana) for SLO tracking & alert rule evaluation (e.g., alert on sustained unhealthy critical service or rising error rate).

Upcoming (Step 3 Prompt 6): histogram(s) for compose action latency + per‑service restart latency distribution.

---
## Security Considerations

Current risks:

* Shelling out to `docker` introduces potential injection (mitigated by enum + controlled args, but still a surface).
* WebSocket lacks authentication / authorization – any network peer could issue restart commands.

Scheduled mitigations (Step 2):

* Adopt Bollard + restrict allowed images / services map.
* Introduce JWT middleware at handshake + per‑command authorization checks (role claims). Increment unauthorized counters (`compose_unauthorized_total`, `restart_unauthorized_total`).

---
## Compose Lifecycle Flow

```text
Client/API → ComposeRequest → (dry_run? short‑circuit) → arg assembly → docker compose exec → capture → metrics increment → structured ComposeResult → caller
```

Future (Bollard): Replace external exec with Docker API calls (container create/start/logs) enabling:

* Fine‑grained error categories
* Non‑blocking streaming logs over WS
* Policy enforcement (deny unknown services)

---
## Roadmap Snapshot

| Step | Theme | Key Changes |
|------|-------|-------------|
| 2 | Security | Bollard integration; JWT auth |
| 3 | Features | Event subscription refinement; metrics expansion |
| 4 | Testing | Unit + integration test harness (mock Bollard, WS tests) |
| 5 | Optimization | Cross‑platform load metrics; multi‑arch Docker build |
| 6 | Finalization | OpenAPI health, orchestration completion doc |

---
## Appendix: Extensibility Hooks

* Add new service: extend config file or default vector; no code change needed for baseline health.
* Add event type: extend `EventType`, update any match statements (WS serialization already generic via serde).
* Add metric: define static metric, register in `PROMETHEUS_REGISTRY`, expose via existing scrape endpoint.

---
Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

