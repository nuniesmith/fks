<!--
Refactored on: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Purpose: Remove duplication, clarify responsibilities, highlight actionable gaps.
-->

# FKS Services Architecture Summary (Refactored)

Concise catalog of FKS services plus cross‑cutting concerns and prioritized improvement gaps.

## 1. Core Principles

1. Explicit contracts (OpenAPI + JSON Schema) over implicit coupling.
2. Separation of concerns: ingestion (fks_data), intelligence (fks_training / fks_transformer), decision (fks_engine), action (fks_execution), coordination (fks_master), presentation (fks_web), security (fks_auth), infra config (fks_config).
3. Observability as a first‑class feature (metrics, traces, logs, events) feeding `fks_master`.
4. Deterministic reproducibility (versioned data + models) to support audit & research.
5. Progressive hardening: start with correctness & contract stability; add performance + resilience layers.

## 2. Service Catalog (Summary)

| Service | Lang | Purpose (1‑liner) | Interfaces | Depends On | Provides |
|---------|------|-------------------|------------|------------|----------|
| fks_master | Rust | Orchestrates & monitors all services | REST, WS, Dashboard | Health endpoints, Docker | Status, control plane |
| fks_api | Python | Unified façade & aggregation layer | REST, WS | future auth/data/engine | Public API surface |
| fks_auth | Python | (Planned) identity, tokens, RBAC | REST (future) | user store, signing keys | AuthN/Z tokens & claims |
| fks_data | Python | Market data ingestion & normalization | Python API (future REST) | External APIs, creds | Canonical time‑series data |
| fks_engine | Python | Strategy orchestration & signal gen | REST (planned), Python | data, transformer | Signals, backtests |
| fks_transformer | Python | Model inference over enriched series | REST, Python | models, data | Probabilities / features |
| fks_training | Python | Train & output versioned models | CLI / Python | data, GPUs | Model artifacts & metrics |
| fks_worker | Python | Scheduled & async task runner | CLI (future queue) | data, training | Automation jobs |
| fks_execution | Rust | Low‑latency execution & (future) orders | REST | engine signals | Execution acknowledgements |
| fks_nodes | Rust | Distributed IO / worker mesh | TCP, CLI | (future engine/execution tasks) | Scalable IO fabric |
| fks_config | Rust | Config compiler & validation | CLI, optional REST | YAML sources | Generated env + schema |
| fks_nginx | Nginx | Edge routing, static hosting | HTTP(S) | upstream services | Ingress / proxy |
| fks_web | TS/React | User dashboard & visualization | Browser SPA | api, master, engine | UI / control surface |
| fks_ninja | C# + Py | Desktop strategy + packaging | NinjaTrader, Docker | Market data | Packaged strategies |
| fks_analyze | Rust | Codebase & repo analysis tooling | REST, Discord bot | repos, scripts | Analytics & reports |

## 3. Cross‑Cutting Modules

| Module | Scope | Key Capabilities | Action Needed |
|--------|-------|------------------|---------------|
| shared_python | Python services | logging, config, metrics, types | Add error & retry utilities; unify logging format |
| shared_rust | Rust crates | env loading, common types | Add tracing + error context helpers |
| shared_react | Frontend | shared hooks, types | Add typed contracts generated from schemas |
| shared_schema | Contracts | JSON Schemas (health, bars, signals) | Expand to full API & event schemas |
| shared_scripts | Automation | analysis, build, deploy | Add contract validation + drift check script |
| shared_docker/nginx | Infra | base images, nginx templates | Add security scanning & buildx support |

## 4. Dependency Graph (Conceptual)

```text
 ingress
   fks_nginx -> fks_web -> fks_api -> (fks_auth) -> fks_engine -> fks_data
                                                \-> fks_transformer
 fks_engine -> fks_execution -> fks_nodes
 fks_training <-> fks_transformer
 fks_worker schedules across data/training/engine
 fks_master observes all
 fks_config generates env consumed by every runtime
```

## 5. Current Gaps (Ranked)

1. Missing distinct authentication/authorization (fks_auth placeholder).
2. No unified machine‑readable contracts (schemas + OpenAPI) across services.
3. Absence of event/message backbone (everything is synchronous coupling today).
4. Observability depth limited (basic health; lacking traces, structured correlation IDs, alerting rules).
5. Data & model reproducibility (no versioned model registry or dataset lineage store).
6. Execution risk controls (idempotency, circuit breakers, position limits) not implemented.
7. Config consumption consistency (some services may not yet use generated `.env.generated`).
8. Security hardening (mTLS, secret management, image scanning) partial.

## 6. Immediate Focus Recommendation

Theme: "Platform Contracts & Security Hardening" (foundational sprint enabling safe scaling & future performance work).

Primary Outcomes (2 weeks target):
1. Contract Baseline: Schemas + OpenAPI for fks_api, fks_engine, fks_transformer, fks_execution; code‑gen types into shared_react & shared_python.
2. Auth MVP: fks_auth minimal JWT issuer + user store + RBAC claim model; gateway (nginx) auth enforcement for protected routes.
3. Observability Core: Structured logging, trace propagation (OpenTelemetry), service metrics unified format; master displays latency SLO breaches.
4. Messaging Spine (Phase 0): Select broker (Redis Streams or NATS for simplicity) and introduce one async path (engine -> execution) as prototype.
5. Security & Config: All services load `.env.generated`; enable image scanning (Trivy) & dependency audit in CI.

Definition of Done: All new/updated APIs have versioned OpenAPI & schema contract tests; `fks_auth` issues tokens used by at least fks_api + fks_engine; traces visible in a viewer (Jaeger/OTel collector); async prototype functioning; CI fails on contract drift or critical vulnerabilities.

## 7. Roadmap Snapshot (After Focus Sprint)

| Phase | Goal | Key Items |
|-------|------|-----------|
| A (Now) | Contracts & Security | Sections 6 outcomes |
| B | Event & Model Layer | Full event bus, model registry service, dataset lineage |
| C | Execution & Risk | Circuit breakers, limits, idempotent order flow |
| D | Performance & Scale | Load tests, latency budgets, autoscaling (K8s) |
| E | Advanced Analytics | Drift detection, A/B model routing, strategy partitioning |

## 8. Actionable Next Steps (Week 0 Kickoff)

1. Generate initial OpenAPI & JSON Schemas; commit under `shared_schema` + add contract check script.
2. Scaffold `fks_auth` (token issuance, validate endpoint, middleware lib for Python & Rust).
3. Add tracing & structured logging dependencies to Rust & Python services; propagate request IDs.
4. Introduce broker container in dev compose; implement engine -> execution async path (publish signal, execution consumes & responds).
5. Update CI pipeline (shared_actions) with: schema diff check, Trivy scan, dependency audit (pip/cargo/npm), fail on high severity.

---
Generated (refactored): $(date -u +"%Y-%m-%dT%H:%M:%SZ")

## Appendix: Original Detailed Entries

The verbose, repeated sections were removed for brevity. Refer to git history if a fully expanded narrative per service is required.

High-level overview of each FKS repository/service: purpose, primary responsibilities ("actions"), key interfaces, and relationships. Generated via code/readme inspection + `shared/scripts/utils/analyze_codebase.sh` patterns, enhanced with 2025 best practices from industry sources on microservices in trading platforms.

## Legend

- Lang: Primary implementation language
- Interface: External surface (HTTP API, Web UI, CLI, TCP, Files)
- Depends: Direct runtime/data dependencies (conceptual)
- Provides: Capabilities offered to rest of platform

---

## 1. fks_master (Monitor / Orchestrator)

- Lang: Rust
- Purpose: Real-time health monitoring, control plane, dashboard & restart orchestration for all FKS microservices.
- Key Actions:
  - Poll /health endpoints with batching + latency metrics.
  - Expose REST (`/api/services`, `/api/services/:id/health`, restart) & WebSocket `/ws` for live status streaming.
  - Perform Docker-based service restarts (when socket mounted).
  - Aggregate and classify service status (Healthy/Degraded/Unhealthy/Unknown).
- Interfaces: HTTP (REST, WebSocket), Web dashboard (port 9090).
- Provides: Central observability & operational control; service registry style discovery.
- Depends: Each service's health endpoint; Docker socket (optional).

## 2. fks_api (Public API Facade)

- Lang: Python (FastAPI)
- Purpose: Lightweight API & WebSocket layer for UI development and platform integration; synthetic data provider placeholder.
- Key Actions:
  - Serve OpenAPI docs & health/info endpoints.
  - Provide synthetic chart/indicator data (temporary stand‑in for real `fks_data`).
  - (Optional) Background model fetch (Ollama) for enhanced routes.
  - Modular router loading with graceful degradation if optional deps missing.
- Interfaces: HTTP REST + WebSocket (FastAPI/Uvicorn).
- Provides: Unified API surface for front-end; staging ground for future auth & data integration.
- Depends: Planned future integration with `fks_auth`, `fks_data`, `fks_engine`.

## 3. fks_auth (Authentication Service - Placeholder)

- Lang: Python (FastAPI) (README currently duplicates `fks_api`).
- Purpose: Intended dedicated authN/Z microservice (tokens, sessions, identity) – presently scaffolded.
- Key Actions (Planned): Issue/validate tokens, user/session management, permission checks, middleware for other services.
- Interfaces: HTTP REST (future), potential OIDC / OAuth integration.
- Provides: Centralized security boundary (future state).
- Current Gap: README duplication & missing implementation (action item to differentiate from `fks_api`).

## 4. fks_data (Market/Data Ingestion & Management)

- Lang: Python
- Purpose: Unified ingestion, normalization, validation, transformation, and serving of raw & derived market datasets.
- Key Actions:
  - Adapter-based external data fetching (e.g., Binance, Polygon) with rate limiting, retries, structured logging.
  - Data normalization to canonical schema (ts, open, high, low, close, volume).
  - Validation & quality checks (validation module).
  - Dataset partitioning / splitting for training & backtesting.
  - DataManager façade for provider abstraction.
- Interfaces: (Planned/implicit) Python API, potential HTTP service; current modules consumed directly by other Python services.
- Provides: Clean, validated time-series data to `fks_engine`, `fks_training`, `fks_transformer`.
- Depends: External market APIs, env credentials.

## 5. fks_engine (Strategy / Backtesting Orchestrator)

- Lang: Python
- Purpose: Coordinate strategies, backtesting, and signal generation combining data + model outputs.
- Key Actions:
  - Expose strategy-related endpoints (/backtest, /signals, /forecast per README note).
  - Run pluggable strategy logic (currently simple MA prototype) and generate forecasts.
  - Orchestrate data fetch (via `fks_data`) and transform/inference (via `fks_transformer`).
- Interfaces: HTTP API (FastAPI style template) + Python modules.
- Provides: Trading signals & analytics to downstream execution / UI.
- Depends: `fks_data` for market bars, `fks_transformer` for model inference, future `fks_config` for runtime overrides.

## 6. fks_transformer (Model Inference Service)

- Lang: Python
- Purpose: Run sequence models / feature enrichment pipelines for predictive tasks over time-series.
- Key Actions:
  - Load transformer (and related) models; perform inference over enriched feature inputs.
  - Provide batch/real-time inference (future batch queue + ONNX export roadmap).
  - Pipeline organization for enrichment/processors.
- Interfaces: Python module & HTTP (FastAPI) endpoints (main/app.py).
- Provides: Model outputs (signals, probabilities, features) to `fks_engine`, `fks_training`, `fks_worker`.
- Depends: Model artifacts, `fks_data` for input series.

## 7. fks_training (Model Training Orchestrator)

- Lang: Python
- Purpose: Manage model training cycles including dataset assembly, GPU allocation, experiment orchestration.
- Key Actions:
  - Coordinate dataset extraction via `dataset_manager.py`.
  - Control GPU resources (selection / reservation) via `gpu_manager.py`.
  - Execute training pipelines & output models to shared storage.
  - Future: Experiment tracking (MLflow), dataset versioning, distributed training.
- Interfaces: CLI / module invocation (`python -m fks_training.main`); potential API expansion.
- Provides: Trained model artifacts & metrics to `fks_transformer` (deployment) and `fks_engine`.
- Depends: `fks_data` for raw/enriched data, shared storage / GPUs.

## 8. fks_worker (Background Task & Scheduling Service)

- Lang: Python
- Purpose: Central asynchronous job runner for maintenance, data refresh, training triggers, periodic tasks.
- Key Actions:
  - Schedule recurring tasks (cron-like) & ad-hoc jobs.
  - Future integration with distributed queue (Redis/RQ or Celery) and retry/backoff policies.
  - Offload long-running or resource-intensive processes from synchronous APIs.
- Interfaces: CLI/module (`python -m fks_worker.main`), future queue endpoints / metrics.
- Provides: Operational automation (data refresh, model retraining triggers, cleanup jobs).
- Depends: `fks_data`, `fks_training`, potentially message broker.

## 9. fks_execution (Execution API)

- Lang: Rust (Axum)
- Purpose: Low-latency simulation & (future) live order execution interface bridging signals to actionable trades.
- Key Actions:
  - Serve `/execute/signal` producing synthetic execution signal payload with latency measurement.
  - Provide `/health` for monitoring.
  - Future: Order routing, risk checks, exchange connectivity, latency benchmarks.
- Interfaces: HTTP REST (port configurable via `--listen`).
- Provides: Execution readiness & latency metrics; (future) trade placement APIs.
- Depends: `fks_engine` signals, possibly `fks_nodes` network for distributed routing.

## 10. fks_nodes (Distributed Node Network)

- Lang: Rust
- Purpose: Master/worker TCP mesh for external API proxying, coordination, and horizontal scaling of IO-bound tasks.
- Key Actions:
  - Master accepts worker registrations over raw TCP.
  - Workers periodically connect/register (lightweight heartbeat simulation).
  - CLI flags to simulate latency, replicate workers.
  - Future: Task dispatch, load balancing, backpressure & failure detection.
- Interfaces: TCP protocol (custom lightweight), CLI.
- Provides: Scalable network substrate for high-concurrency data fetching or execution fan-out.
- Depends: Downstream services needing distributed IO (e.g., `fks_data`, `fks_execution`).

## 11. fks_config (Configuration Generator / Service)

- Lang: Rust
- Purpose: Source-of-truth configuration compiler: YAML -> derived `.env` artifacts, schema generation, validation, optional health service.
- Key Actions:
  - `generate`: Parse YAML, derive env values, output `.env.generated`.
  - `schema`: Emit JSON Schema for config model (ensures front-end & other services align).
  - `validate`: Full parse + computed validations without output side-effects.
  - `serve` (feature flag): Provide `/health` endpoint for runtime presence.
- Interfaces: CLI subcommands; optional HTTP `/health`.
- Provides: Consistent environment & configuration artifacts to all services (reducing drift).
- Depends: YAML config sources, optional shared schemas.

## 12. fks_nginx (Edge / Reverse Proxy & Static Content)

- Lang: Nginx (containerized)
- Purpose: Central ingress/load balancer, SSL termination, static asset hosting for dashboard & web UI.
- Key Actions:
  - Route external traffic to internal services based on host/path.
  - Provide basic health endpoint (root) used by Docker healthcheck.
  - Serve static HTML/assets (dashboard, health page) & apply common proxy params.
  - (Via shared templates) Support SSL cert management scripts.
- Interfaces: HTTP/HTTPS (port 80/443), file serving.
- Provides: Unified entrypoint, performance tuning, security headers, WebSocket proxying.
- Depends: Upstream service endpoints & certificates.

## 13. fks_web (Front-End Web UI)

- Lang: TypeScript (Vite + React + Tailwind)
- Purpose: User interface for monitoring, interacting with strategies, visualization of data & signals.
- Key Actions:
  - Fetch service statuses & metrics (planned integration with `fks_master`).
  - Display charts, indicators, model outputs, and configuration panels.
  - Provide client-side state management & real-time (WebSocket) hooks.
- Interfaces: Browser SPA served via Vite build; proxied by `fks_nginx`.
- Provides: Human-facing visualization & control layer.
- Depends: `fks_api`, `fks_master`, `fks_engine`, others for data.

## 14. fks_ninja (NinjaTrader Strategy & Tooling)

- Lang: C# (NinjaTrader 8) + Python + Docker
- Purpose: Desktop trading strategy implementation with AI-enhanced signal suite, packaging & cross-language tooling.
- Key Actions:
  - Provide refactored modular strategy (AddOns & Indicators) packaged for NT8.
  - Python bridge for strategy replication & monitoring / backtests.
  - Build & packaging scripts (tarball, ZIP) with CI/CD integration.
  - Risk management enforcement & documentation hub.
- Interfaces: NinjaTrader GUI, Python FastAPI, Docker dev environment.
- Provides: Production-grade discretionary+systematic hybrid trading strategy & artifacts.
- Depends: Market data feeds (NinjaTrader), optional Python services.

---

## Cross-Cutting Shared Modules

- `shared/python`: Common config, logging, types, risk, metrics utilities consumed by Python services.
- `shared/rust`: Env & type abstractions for Rust crates.
- `shared/react`: Shared TS types, hooks, config for front-end.
- `shared/schema`: JSON Schemas (health, market bar, trade signal) for contract consistency.
- `shared/scripts`: Automation scripts (deployment, testing, environment setup, analysis) powering CI/CD & ops.
- `shared/docker` & `shared/nginx`: Templated Dockerfiles, docker-compose fragments, base images, nginx configs.

## Service Dependency Graph (Conceptual)

```text
            +-------------+
            |  fks_nginx  |  (Ingress / SSL / Static)
            +------+------+ 
                   |
              +----v----+       +--------------+
              | fks_web |<----->|  fks_master  | (Monitor WS/API)
              +----+----+        ^      ^
                   |             |      |
                   |             |      |
               +---+-------------+------+-----------+
               |      fks_api (Facade / Aggregation) |
               +---+-------------+------+-----------+
                   |             |      |
        +----------+---+     +---+--+   |
        | fks_auth (F) |     |fks_engine|<----+
        +--------------+     +---+--+   |     |
                                       v     |
                               +-------+--+  |
                               | fks_data |  |
                               +----+-----+  |
                                    |        |
                              +-----v--+  +--v----------+
                              |fks_training|  fks_transformer |
                              +-----+--+  +-------+------+
                                    |             |
                                    +----+   +----+
                                         v   v
                                      fks_worker
                                         |
                                         v
                                     fks_execution (Low-latency)
                                         |
                                         v
                                       fks_nodes (Distributed IO)
```
(F) = future expansion / placeholder.

## Observations & Recommendations

Updated with 2025 best practices for microservices in trading platforms, emphasizing low-latency, resilience, scalability, and AI integration. Prioritize these for improvements to achieve enterprise-grade reliability in high-frequency trading scenarios.

1. **Differentiate and Harden fks_auth**: Implement distinct JWT/OAuth logic with RBAC; add mTLS for secure inter-service communication to prevent unauthorized access in sensitive trading ops.

2. **Formalize Inter-Service Contracts**: Use OpenAPI + JSON Schema for all APIs (e.g., `fks_engine` outputs); introduce API versioning to support gradual updates without breaking downstream consumers like `fks_execution`.

3. **Introduce Event-Driven Architecture**: Adopt a message broker (e.g., Kafka or RabbitMQ) for async communication between `fks_worker`, `fks_training`, and `fks_engine` to decouple services, improve scalability, and handle high-throughput events like trade signals.

4. **Enhance Risk and Resilience in fks_execution**: Add circuit breakers, retries, and idempotency for order routing; integrate real-time risk checks (e.g., exposure limits) to prevent failures in live trading.

5. **Expand fks_data with Advanced Persistence**: Implement event sourcing and perpetual storage (e.g., using Chronicle Queue or Parquet with metadata registry) for reproducible datasets; add database-per-service pattern to isolate data failures.

6. **Implement a Dedicated Model Registry Service**: Create a new `fks_models` service for versioned model storage, A/B testing, and deployment; integrate MLflow for experiment tracking in `fks_training`.

7. **Harden Monitoring and Observability**: In `fks_master`, add real-time performance tracing (e.g., OpenTelemetry), centralized logging (ELK Stack), and alert webhooks (Slack/PagerDuty); monitor circuit breaker states and latency thresholds for low-latency trading.

8. **Align and Secure Configuration**: Ensure all services consume `.env.generated` from `fks_config`; add secrets management (e.g., Vault) and encrypt configs/data in transit/rest.

9. **Adopt Domain-Driven Design (DDD)**: Redefine service boundaries around business capabilities (e.g., separate microservices for strategies like arbitrage in `fks_engine`); this enables independent scaling per trading function.

10. **Implement API Gateway**: Use `fks_nginx` or a dedicated gateway (e.g., Kong) as a single entry point for authentication, rate-limiting, and routing to enhance security and manage real-time client requests.

11. **Containerization and Orchestration for Cloud Migration**: Fully migrate to Kubernetes (from Docker Compose) with autoscaling; use single-threaded designs in Rust services for low-latency; enable piecemeal cloud adoption for hybrid bare-metal/cloud setups.

12. **Automated Testing and CI/CD**: Layer testing (unit, integration, contract, E2E) across services; integrate into `shared_actions` for CI/CD pipelines to validate real-time data flows and prevent disruptions.

13. **Low-Latency Optimizations**: For services like `fks_execution` and `fks_nodes`, prioritize single-threaded processing and event sourcing; benchmark against 1M+ events/sec for high-frequency trading.

14. **Security Enhancements**: Enforce network policies, token-based auth, and anomaly detection in `fks_auth` and risk services; conduct regular audits for compliance (e.g., data privacy in trading logs).

15. **Scalability and Resilience Patterns**: Add backpressure handling in `fks_nodes`; use snapshots for state recovery in data-heavy services to minimize downtime during failures.

---
Generated: 2025-08-31T00:00:00Z


# FKS Services Architecture Summary

High-level overview of each FKS repository/service: purpose, primary responsibilities ("actions"), key interfaces, and relationships. Generated via code/readme inspection + `shared/scripts/utils/analyze_codebase.sh` patterns, enhanced with 2025 best practices from industry sources on microservices in trading platforms.

## Legend

- Lang: Primary implementation language
- Interface: External surface (HTTP API, Web UI, CLI, TCP, Files)
- Depends: Direct runtime/data dependencies (conceptual)
- Provides: Capabilities offered to rest of platform

---

## 1. fks_master (Monitor / Orchestrator)

- Lang: Rust
- Purpose: Real-time health monitoring, control plane, dashboard & restart orchestration for all FKS microservices.
- Key Actions:
  - Poll /health endpoints with batching + latency metrics.
  - Expose REST (`/api/services`, `/api/services/:id/health`, restart) & WebSocket `/ws` for live status streaming.
  - Perform Docker-based service restarts (when socket mounted).
  - Aggregate and classify service status (Healthy/Degraded/Unhealthy/Unknown).
- Interfaces: HTTP (REST, WebSocket), Web dashboard (port 9090).
- Provides: Central observability & operational control; service registry style discovery.
- Depends: Each service's health endpoint; Docker socket (optional).

## 2. fks_api (Public API Facade)

- Lang: Python (FastAPI)
- Purpose: Lightweight API & WebSocket layer for UI development and platform integration; synthetic data provider placeholder.
- Key Actions:
  - Serve OpenAPI docs & health/info endpoints.
  - Provide synthetic chart/indicator data (temporary stand‑in for real `fks_data`).
  - (Optional) Background model fetch (Ollama) for enhanced routes.
  - Modular router loading with graceful degradation if optional deps missing.
- Interfaces: HTTP REST + WebSocket (FastAPI/Uvicorn).
- Provides: Unified API surface for front-end; staging ground for future auth & data integration.
- Depends: Planned future integration with `fks_auth`, `fks_data`, `fks_engine`.

## 3. fks_auth (Authentication Service - Placeholder)

- Lang: Python (FastAPI) (README currently duplicates `fks_api`).
- Purpose: Intended dedicated authN/Z microservice (tokens, sessions, identity) – presently scaffolded.
- Key Actions (Planned): Issue/validate tokens, user/session management, permission checks, middleware for other services.
- Interfaces: HTTP REST (future), potential OIDC / OAuth integration.
- Provides: Centralized security boundary (future state).
- Current Gap: README duplication & missing implementation (action item to differentiate from `fks_api`).

## 4. fks_data (Market/Data Ingestion & Management)

- Lang: Python
- Purpose: Unified ingestion, normalization, validation, transformation, and serving of raw & derived market datasets.
- Key Actions:
  - Adapter-based external data fetching (e.g., Binance, Polygon) with rate limiting, retries, structured logging.
  - Data normalization to canonical schema (ts, open, high, low, close, volume).
  - Validation & quality checks (validation module).
  - Dataset partitioning / splitting for training & backtesting.
  - DataManager façade for provider abstraction.
- Interfaces: (Planned/implicit) Python API, potential HTTP service; current modules consumed directly by other Python services.
- Provides: Clean, validated time-series data to `fks_engine`, `fks_training`, `fks_transformer`.
- Depends: External market APIs, env credentials.

## 5. fks_engine (Strategy / Backtesting Orchestrator)

- Lang: Python
- Purpose: Coordinate strategies, backtesting, and signal generation combining data + model outputs.
- Key Actions:
  - Expose strategy-related endpoints (/backtest, /signals, /forecast per README note).
  - Run pluggable strategy logic (currently simple MA prototype) and generate forecasts.
  - Orchestrate data fetch (via `fks_data`) and transform/inference (via `fks_transformer`).
- Interfaces: HTTP API (FastAPI style template) + Python modules.
- Provides: Trading signals & analytics to downstream execution / UI.
- Depends: `fks_data` for market bars, `fks_transformer` for model inference, future `fks_config` for runtime overrides.

## 6. fks_transformer (Model Inference Service)

- Lang: Python
- Purpose: Run sequence models / feature enrichment pipelines for predictive tasks over time-series.
- Key Actions:
  - Load transformer (and related) models; perform inference over enriched feature inputs.
  - Provide batch/real-time inference (future batch queue + ONNX export roadmap).
  - Pipeline organization for enrichment/processors.
- Interfaces: Python module & HTTP (FastAPI) endpoints (main/app.py).
- Provides: Model outputs (signals, probabilities, features) to `fks_engine`, `fks_training`, `fks_worker`.
- Depends: Model artifacts, `fks_data` for input series.

## 7. fks_training (Model Training Orchestrator)

- Lang: Python
- Purpose: Manage model training cycles including dataset assembly, GPU allocation, experiment orchestration.
- Key Actions:
  - Coordinate dataset extraction via `dataset_manager.py`.
  - Control GPU resources (selection / reservation) via `gpu_manager.py`.
  - Execute training pipelines & output models to shared storage.
  - Future: Experiment tracking (MLflow), dataset versioning, distributed training.
- Interfaces: CLI / module invocation (`python -m fks_training.main`); potential API expansion.
- Provides: Trained model artifacts & metrics to `fks_transformer` (deployment) and `fks_engine`.
- Depends: `fks_data` for raw/enriched data, shared storage / GPUs.

## 8. fks_worker (Background Task & Scheduling Service)

- Lang: Python
- Purpose: Central asynchronous job runner for maintenance, data refresh, training triggers, periodic tasks.
- Key Actions:
  - Schedule recurring tasks (cron-like) & ad-hoc jobs.
  - Future integration with distributed queue (Redis/RQ or Celery) and retry/backoff policies.
  - Offload long-running or resource-intensive processes from synchronous APIs.
- Interfaces: CLI/module (`python -m fks_worker.main`), future queue endpoints / metrics.
- Provides: Operational automation (data refresh, model retraining triggers, cleanup jobs).
- Depends: `fks_data`, `fks_training`, potentially message broker.

## 9. fks_execution (Execution API)

- Lang: Rust (Axum)
- Purpose: Low-latency simulation & (future) live order execution interface bridging signals to actionable trades.
- Key Actions:
  - Serve `/execute/signal` producing synthetic execution signal payload with latency measurement.
  - Provide `/health` for monitoring.
  - Future: Order routing, risk checks, exchange connectivity, latency benchmarks.
- Interfaces: HTTP REST (port configurable via `--listen`).
- Provides: Execution readiness & latency metrics; (future) trade placement APIs.
- Depends: `fks_engine` signals, possibly `fks_nodes` network for distributed routing.

## 10. fks_nodes (Distributed Node Network)

- Lang: Rust
- Purpose: Master/worker TCP mesh for external API proxying, coordination, and horizontal scaling of IO-bound tasks.
- Key Actions:
  - Master accepts worker registrations over raw TCP.
  - Workers periodically connect/register (lightweight heartbeat simulation).
  - CLI flags to simulate latency, replicate workers.
  - Future: Task dispatch, load balancing, backpressure & failure detection.
- Interfaces: TCP protocol (custom lightweight), CLI.
- Provides: Scalable network substrate for high-concurrency data fetching or execution fan-out.
- Depends: Downstream services needing distributed IO (e.g., `fks_data`, `fks_execution`).

## 11. fks_config (Configuration Generator / Service)

- Lang: Rust
- Purpose: Source-of-truth configuration compiler: YAML -> derived `.env` artifacts, schema generation, validation, optional health service.
- Key Actions:
  - `generate`: Parse YAML, derive env values, output `.env.generated`.
  - `schema`: Emit JSON Schema for config model (ensures front-end & other services align).
  - `validate`: Full parse + computed validations without output side-effects.
  - `serve` (feature flag): Provide `/health` endpoint for runtime presence.
- Interfaces: CLI subcommands; optional HTTP `/health`.
- Provides: Consistent environment & configuration artifacts to all services (reducing drift).
- Depends: YAML config sources, optional shared schemas.

## 12. fks_nginx (Edge / Reverse Proxy & Static Content)

- Lang: Nginx (containerized)
- Purpose: Central ingress/load balancer, SSL termination, static asset hosting for dashboard & web UI.
- Key Actions:
  - Route external traffic to internal services based on host/path.
  - Provide basic health endpoint (root) used by Docker healthcheck.
  - Serve static HTML/assets (dashboard, health page) & apply common proxy params.
  - (Via shared templates) Support SSL cert management scripts.
- Interfaces: HTTP/HTTPS (port 80/443), file serving.
- Provides: Unified entrypoint, performance tuning, security headers, WebSocket proxying.
- Depends: Upstream service endpoints & certificates.

## 13. fks_web (Front-End Web UI)

- Lang: TypeScript (Vite + React + Tailwind)
- Purpose: User interface for monitoring, interacting with strategies, visualization of data & signals.
- Key Actions:
  - Fetch service statuses & metrics (planned integration with `fks_master`).
  - Display charts, indicators, model outputs, and configuration panels.
  - Provide client-side state management & real-time (WebSocket) hooks.
- Interfaces: Browser SPA served via Vite build; proxied by `fks_nginx`.
- Provides: Human-facing visualization & control layer.
- Depends: `fks_api`, `fks_master`, `fks_engine`, others for data.

## 14. fks_ninja (NinjaTrader Strategy & Tooling)

- Lang: C# (NinjaTrader 8) + Python + Docker
- Purpose: Desktop trading strategy implementation with AI-enhanced signal suite, packaging & cross-language tooling.
- Key Actions:
  - Provide refactored modular strategy (AddOns & Indicators) packaged for NT8.
  - Python bridge for strategy replication & monitoring / backtests.
  - Build & packaging scripts (tarball, ZIP) with CI/CD integration.
  - Risk management enforcement & documentation hub.
- Interfaces: NinjaTrader GUI, Python FastAPI, Docker dev environment.
- Provides: Production-grade discretionary+systematic hybrid trading strategy & artifacts.
- Depends: Market data feeds (NinjaTrader), optional Python services.

## 15. fks_analyze (Code Analysis Service)

- Lang: Rust
- Purpose: Codebase analysis and Discord bot integration for repo insights and automation.
- Key Actions:
  - Analyze codebase structure, languages, patterns via scripts.
  - Bot handles Discord interactions for queries and reports.
  - Generate summaries, dependency graphs, and file trees.
- Interfaces: HTTP REST (health, analysis endpoints), CLI (scripts), Discord bot.
- Provides: Development tools for maintaining the FKS ecosystem; insights for refactoring.
- Depends: Shared scripts, Ollama for optional AI enhancements, Discord API.

---

## Cross-Cutting Shared Modules

- `shared/python`: Common config, logging, types, risk, metrics utilities consumed by Python services.
- `shared/rust`: Env & type abstractions for Rust crates.
- `shared/react`: Shared TS types, hooks, config for front-end.
- `shared/schema`: JSON Schemas (health, market bar, trade signal) for contract consistency.
- `shared/scripts`: Automation scripts (deployment, testing, environment setup, analysis) powering CI/CD & ops.
- `shared/docker` & `shared/nginx`: Templated Dockerfiles, docker-compose fragments, base images, nginx configs.

## Service Dependency Graph (Conceptual)

```text
            +-------------+
            |  fks_nginx  |  (Ingress / SSL / Static)
            +------+------+ 
                   |
              +----v----+       +--------------+
              | fks_web |<----->|  fks_master  | (Monitor WS/API)
              +----+----+        ^      ^
                   |             |      |
                   |             |      |
               +---+-------------+------+-----------+
               |      fks_api (Facade / Aggregation) |
               +---+-------------+------+-----------+
                   |             |      |
        +----------+---+     +---+--+   |
        | fks_auth (F) |     |fks_engine|<----+
        +--------------+     +---+--+   |     |
                                       v     |
                               +-------+--+  |
                               | fks_data |  |
                               +----+-----+  |
                                    |        |
                              +-----v--+  +--v----------+
                              |fks_training|  fks_transformer |
                              +-----+--+  +-------+------+
                                    |             |
                                    +----+   +----+
                                         v   v
                                      fks_worker
                                         |
                                         v
                                     fks_execution (Low-latency)
                                         |
                                         v
                                       fks_nodes (Distributed IO)
```
(F) = future expansion / placeholder.

## Observations & Recommendations

Updated with 2025 best practices for microservices in trading platforms, emphasizing low-latency, resilience, scalability, and AI integration. Docker/Compose review: Strong multi-stage builds (e.g., Rust with distroless, Python venvs), consistent timezones, healthchecks, and networks. Gaps: Inconsistent template usage (e.g., fks_api Dockerfile truncated/missing shared extends); add resource limits; central compose has good DB isolation but lacks volume backups. Prioritize these for improvements to achieve enterprise-grade reliability in high-frequency trading scenarios.

1. **Differentiate and Harden fks_auth**: Implement distinct JWT/OAuth logic with RBAC; add mTLS for secure inter-service communication to prevent unauthorized access in sensitive trading ops.

2. **Formalize Inter-Service Contracts**: Use OpenAPI + JSON Schema for all APIs (e.g., `fks_engine` outputs); introduce API versioning to support gradual updates without breaking downstream consumers like `fks_execution`.

3. **Introduce Event-Driven Architecture**: Adopt a message broker (e.g., Kafka or RabbitMQ) for async communication between `fks_worker`, `fks_training`, and `fks_engine` to decouple services, improve scalability, and handle high-throughput events like trade signals.

4. **Enhance Risk and Resilience in fks_execution**: Add circuit breakers, retries, and idempotency for order routing; integrate real-time risk checks (e.g., exposure limits) to prevent failures in live trading.

5. **Expand fks_data with Advanced Persistence**: Implement event sourcing and perpetual storage (e.g., Chronicle Queue or Parquet with metadata registry) for reproducible datasets; add database-per-service pattern to isolate data failures.

6. **Implement a Dedicated Model Registry Service**: Create a new `fks_models` service for versioned model storage, A/B testing, and deployment; integrate MLflow for experiment tracking in `fks_training`.

7. **Harden Monitoring and Observability**: In `fks_master`, add real-time performance tracing (e.g., OpenTelemetry), centralized logging (ELK Stack), and alert webhooks (Slack/PagerDuty); monitor circuit breaker states and latency thresholds for low-latency trading.

8. **Align and Secure Configuration**: Ensure all services consume `.env.generated` from `fks_config`; add secrets management (e.g., Vault) and encrypt configs/data in transit/rest.

9. **Adopt Domain-Driven Design (DDD)**: Redefine service boundaries around business capabilities (e.g., separate microservices for strategies like arbitrage in `fks_engine`); this enables independent scaling per trading function.

10. **Implement API Gateway**: Use `fks_nginx` or a dedicated gateway (e.g., Kong) as a single entry point for authentication, rate-limiting, and routing to enhance security and manage real-time client requests.

11. **Containerization and Orchestration for Cloud Migration**: Fully migrate to Kubernetes (from Docker Compose) with autoscaling; use single-threaded designs in Rust services for low-latency; enable piecemeal cloud adoption for hybrid bare-metal/cloud setups.

12. **Automated Testing and CI/CD**: Layer testing (unit, integration, contract, E2E) across services; integrate into `shared_actions` for CI/CD pipelines to validate real-time data flows and prevent disruptions.

13. **Low-Latency Optimizations**: For services like `fks_execution` and `fks_nodes`, prioritize single-threaded processing and event sourcing; benchmark against 1M+ events/sec for high-frequency trading.

14. **Security Enhancements**: Layer network policies, token-based auth, and anomaly detection in `fks_auth` and risk services; conduct regular audits for compliance (e.g., data privacy in trading logs).

15. **Scalability and Resilience Patterns**: Add backpressure handling in `fks_nodes`; use snapshots for state recovery in data-heavy services to minimize downtime during failures.

16. **Docker Image Security Scanning**: Integrate vulnerability scanners (e.g., Trivy or Clair) into build pipelines for all Dockerfiles (e.g., fks_api, fks_worker) to detect and remediate CVEs before deployment.

17. **Multi-Architecture and Efficient Builds**: Use Docker Buildx for multi-arch images (amd64/arm64) in shared templates; minimize layers and use smaller base images (e.g., alpine variants) to reduce build times and attack surfaces.

18. **Resource Management in Compose/K8s**: Define explicit CPU/memory requests/limits in docker-compose.yml files (e.g., fks_worker with Redis) and K8s manifests to enable autoscaling and prevent OOM kills in production clusters.

19. **Service Mesh for Advanced Networking**: Implement Istio or Linkerd on K8s for automatic mTLS, traffic shifting, and observability; extend `fks_nginx` routing to handle canary deployments for services like `fks_api`.

20. **Hybrid Orchestration Strategies**: Use Docker Swarm as a lightweight alternative for early-stage testing before full K8s migration; integrate with tools like Kompose for converting Compose files to K8s resources.

---
Generated: 2025-08-31T00:00:00Z