# FKS Platform Architecture — The Complete Reference

> **The single map**: how the `fks` orchestrator repo relates to every repo it
> consumes, what each repo does, how it supports the running platform, and the
> contracts that bind them.
>
> **Last updated:** 2026-07-03 (post signal-bridge / observability / secrets /
> exchanges-integration work). Supersedes
> [`REPO_TOPOLOGY.md`](REPO_TOPOLOGY.md) (2026-05-31, pre-web-split).

---

## 1. One-picture overview

```
                          ┌─────────────────────────────────────────────────────┐
                          │              nuniesmith/fks  (THIS REPO)            │
                          │   docker-compose orchestrator · infra config ·      │
                          │   spawner crate · sql bootstrap · demo bots         │
                          └───┬───────────┬────────────┬───────────┬────────────┘
              git-clone image │           │ git-clone  │ local     │ in-tree
                              ▼           ▼ image      ▼ systemd*  ▼ crates
                     ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
                     │   janus    │ │ fks-web  │ │  crypto  │ │crates/spawner│
                     │ (brain)    │ │ (webui)  │ │ (bots)   │ │ (lifecycle)  │
                     └─────┬──────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘
                           │ consumes    │ proxies    │ consumes     │ spawns
                           ▼ crates.io   ▼ APIs       ▼ crates.io    ▼ fks-bot-*
        ┌─────────────┬────────────┬─────────────┐          containers on
        │  rustrade   │indicators- │ exchange-   │          fks_network
        │ (framework) │    ta      │   apiws     │
        └─────────────┴────────────┴─────────────┘
                           ▲                                 ┌──────────────┐
                           │ read-only API client            │ technical_   │
                     ┌─────┴──────┐                          │ papers       │
                     │ fks-kotlin │                          │ (the theory) │
                     │ (mobile)   │                          └──────────────┘
                     └────────────┘
        * crypto bots run as user systemd units during the transitional phase;
          Phase 2 of crypto/FKS-INTEGRATION.md moves them to spawner-managed
          fks-bot-* containers.
```

**Design doctrine** (from the split): *consume, don't absorb*. Reusable pieces
live in their own repos, published to crates.io or built as git-clone Docker
images pinned by ref. `fks` wires them together at runtime and owns nothing it
can consume.

---

## 2. The repo family

| Repo | Role | Consumed by fks as | Visibility |
|------|------|--------------------|-----------|
| [`nuniesmith/fks`](https://github.com/nuniesmith/fks) | **Orchestrator** — compose, infra config, spawner, SQL, demo bots | — (this repo) | public |
| [`nuniesmith/janus`](https://github.com/nuniesmith/janus) | **Trading brain** — signals, regime, risk, data ingestion, ML research | Docker image (git-clone `JANUS_REPO@JANUS_REF`) | public |
| [`nuniesmith/fks-web`](https://github.com/nuniesmith/fks-web) | **Operator UI** — SvelteKit dashboard | Docker image (git-clone `WEB_REPO@WEB_REF`) | public |
| [`nuniesmith/rustrade`](https://github.com/nuniesmith/rustrade) | **Bot framework** — `Bot`/`Brain` traits, risk primitives, supervisor, backtest | crates.io `rustrade-framework` **0.4.x** | public |
| [`nuniesmith/indicators-ta`](https://github.com/nuniesmith/indicators-ta) | **TA math** — RSI/EMA/ATR/MACD/Bollinger + regime detection | crates.io `indicators-ta` **0.2.x** | public |
| [`nuniesmith/exchange-apiws`](https://github.com/nuniesmith/exchange-apiws) | **Exchange connectivity** — REST + WS for Kraken/KuCoin/Crypto.com/Bybit/Binance | crates.io `exchange-apiws` **0.8.x** | public |
| [`nuniesmith/crypto`](https://github.com/nuniesmith/crypto) | **Production bots** — spot portfolio (live) + futures funding (paper) | systemd today → `fks-bot-*` images (Phase 2) | **private** |
| [`nuniesmith/fks-kotlin`](https://github.com/nuniesmith/fks-kotlin) | **Mobile/KMP client** — read-only janus API surface | independent client of janus's HTTP APIs | public |
| [`nuniesmith/technical_papers`](https://github.com/nuniesmith/technical_papers) | **Theory** — the JANUS paper (`project_janus/janus.tex`) | reference; reconciled with code periodically | public |

> **Private-repo consequence:** `nuniesmith/crypto` is private, so the
> git-clone-in-Dockerfile pattern used for janus/fks-web **cannot** build its
> images without credential-baking. The `fks-bot-crypto-*` Dockerfiles belong
> in the crypto repo itself, built from the local checkout on the host.

---

## 3. What runs: the compose stack

~21 containers, all ports bound to `127.0.0.1` (reachable via localhost or the
Tailscale-served nginx edge only).

| Service | Container | Source | Host ports | Purpose |
|---|---|---|---|---|
| janus | `fks_janus` | janus repo (git-clone image) | 7000 (api :8080), 7001 (forward REST :8180), 7002 (exec gRPC :50052), 9051 (gRPC :50051), 9092 (unified /metrics :9090) | the platform brain |
| webui | `fks_webui` | fks-web repo (git-clone image) | 3001 (:3000) | operator dashboard |
| spawner | `fks_bot_spawner` | `crates/spawner` (in-tree) | 8090 | bot-container lifecycle + secret store |
| nginx | `fks_nginx` | in-tree config | 80 | TLS edge, `X-Internal-Token` injection |
| postgres | `fks_postgres` | custom image | 5432 | `janus_db` + `ruby_db` (spawner schema) |
| redis | `fks_redis` | custom image | 6379 | signals cache, kill switch, pub/sub, state |
| questdb | `fks_questdb` | custom image | 9000/9009/8812 | market-data time series (`candles_crypto`) |
| qdrant | `fks_qdrant` | upstream | 6333/6334 | vector store (schema/memory research) |
| prometheus | `fks_prometheus` | custom image (config baked) | 9090 | metrics + **audited alert rules** (85 rules, every one backed by an exported metric) |
| grafana | `fks_grafana` | custom image | 3000 | dashboards (host-mounted, 10s live reload) |
| alertmanager (+discord) | `fks_alertmanager` | upstream | 9093 | alert routing → Discord |
| node-exporter | `fks_node_exporter` | upstream | 9100 | host disk/CPU/mem (backs HostDiskSpace* alerts) |
| loki + promtail | | upstream | 3100 | log aggregation |
| jaeger | `fks_jaeger` | upstream | 16686 | tracing |
| exporters | postgres/redis/questdb | | 9187/9121/9191 | DB metrics |

**Host processes (transitional):** the crypto bots run as *user systemd units*
(`spot-portfolio.service`, `funding-paper.service`) with status/metrics
servers expected on host **:9091** (spot) and **:9095** (funding — 9092/9093
are taken by janus metrics and alertmanager). Prometheus scrapes them via the
static `fks-bots-transitional` job (`host.docker.internal`, host-gateway).

---

## 4. Per-repo deep dive: how each repo supports the platform

### 4.1 `fks` — the orchestrator (this repo)

Owns everything that wires the platform together and nothing that other repos
publish:

- **`docker-compose.yml`** — the deployment: service definitions, hardened
  defaults (`cap_drop: ALL`, `no-new-privileges`, localhost-only ports),
  env passthroughs (`JANUS_*`, `WEB_REF`, `CRYPTO_*_INTERNAL_URL`,
  `BRAIN_API_TOKEN`, `SPAWNER_SECRETS_KEY`).
- **`infrastructure/`** — Prometheus config + alert rules, Grafana dashboards
  (live-reloading host mount), nginx conf, per-service Dockerfiles including
  the shared rust/nodejs base images with the `REPO_URL` git-clone pattern.
- **`crates/spawner`** — the bot-lifecycle service (see §5.3): spawn/stop/logs
  via bollard, Prometheus file-SD for spawned bots, `bot_runs` history,
  `bot_configs` templates, and the **exchange secret store** (encrypted at
  rest, ChaCha20-Poly1305 via `SPAWNER_SECRETS_KEY`; decrypted only at
  spawn-time injection).
- **`src/sql/`** — DB bootstrap baked into the postgres image (`janus/` +
  `spawner/` schemas).
- **`src/proto/`** — `fks-proto` crate (protobuf contracts, `fks.<svc>.v1`).
- **`bots/`** — reference bots (`fks-bot-example`, `crypto-demo`) that
  demonstrate the spawn contract end-to-end using only published crates.
- **`src/web/`** — legacy in-tree copy of the webui (dev fallback; production
  clones `fks-web`).

### 4.2 `janus` — the trading brain

A Rust workspace (~26 crates + 8 service crates) deployed as **one unified
binary**: a supervisor spawns the **Data, Forward, Backward, CNS, and API
modules in-process** with per-module health and restart policies. The
standalone-service topology still exists for scale-out.

How it supports the platform:

- **Market data (Data module):** native Binance WebSocket ingestion
  (`DATA_SOURCE=live`, combined kline+trade streams per asset), closed klines
  published on the in-process `MarketDataBus` and persisted to QuestDB
  `candles_crypto` (the WebUI chart source). Computes the
  **`data_completeness_percent` SLI** in the live loop (30-min
  boundary-aligned rolling window, cold-start gated) — this SLI + its SLO
  alert caught a silently dead exchange stream (MATIC→POL delisting) on its
  first armed day.
- **Signals (Forward module):** indicator-consensus strategy engine
  (EMA-crossover / RSI-reversal / MACD-momentum / Bollinger-breakout with
  consensus voting) over live klines, gated by regime detection, prop-firm
  rules, risk checks, and the brain pipeline. Published on the in-process
  `SignalBus` **and persisted to Redis** (`janus:signal:{id}`,
  `janus:signals:recent`, `janus:signals:symbol:{SYM}`) so the read APIs and
  WebUI are real. Warm-starts analyzers from history on restart (no cold-start
  signal blackout).
- **APIs:** `:8080` (host 7000) — signals read/publish, dashboard, pipeline
  scores, services start/stop; `:8180` (host 7001) — full REST incl. brain
  health/affinity and the **token-gated kill-switch endpoints**
  (`BRAIN_API_TOKEN`; fail-open when unset — set it); `:9090` (host 9092) —
  unified Prometheus metrics; `:50051/:50052` gRPC.
- **Safety:** kill switch (in-process + Redis-coordinated), RiskManager
  enforcement on the order path (`JANUS_RISK_ENFORCE=1`), execution disabled
  by default (`EXECUTION_MODE=paper_trading`, human-gated by doctrine).
- **Research crates** (standalone, not in the live loop — see the paper's
  maturity-gap section): vision (DiffGAF/ViViT), LTN, ml/training, memory,
  lob simulator, quantum, dsp, compliance.
- Consumes `rustrade`/`indicators-ta`/`exchange-apiws` from crates.io.

Operational notes: image builds by git-clone at `JANUS_REF` (use `--no-cache`
to bust a stale clone; **`--locked` build — dep changes need a `Cargo.lock`
bump**); local-context build for uncommitted work:
`docker build -f fks/infrastructure/docker/base/rust/Dockerfile --build-arg
SERVICE_NAME=janus ~/github/janus`. `JANUS_AUTO_START=false` — modules idle in
standby until `POST /api/services/start`. Config `janus.toml` is a **live RO
mount** from `fks/infrastructure/config/janus/` (restart to re-read; mind
which git branch is checked out on the host).

### 4.3 `fks-web` — the operator UI

SvelteKit 5 (runes) dashboard; **`src/hooks.server.ts` is the single backend
seam** — every browser call is same-origin and the hook proxies path prefixes
to internal services (janus `:8080`/`:8180`, spawner, Prometheus, QuestDB,
crypto-bot status servers) with graceful-empty degradation.

Pages and what feeds them:

| Page | Backing |
|---|---|
| `/` overview | janus dashboard overview + recent signals (Redis-persisted) |
| `/charts` | QuestDB `candles_crypto` (designated ts column `timestamp`) |
| `/signals` | janus `/api/signals/latest` (live feed) |
| `/bots` | spawner (spawn form **with secrets-injection checkboxes**, saved configs, SSE logs, run history) |
| `/exchanges` + `/exchanges/[exchange]` | crypto bots' `/status` servers via `CRYPTO_SPOT/FUNDING_INTERNAL_URL` (net worth, holdings vs targets, rebalance trades) |
| `/settings` | risk config (janus) + **3-exchange API-key entry** (Kraken/KuCoin+passphrase/Crypto.com → spawner secret store; submit-only, encrypted at rest) |
| `/monitoring`, `/performance`, `/janus-ai` | Prometheus / janus forward REST |

CI gates: `svelte-check` 0/0, vitest, vite build. Deploys as a git-clone image
(`WEB_REF`).

### 4.4 `rustrade` — the bot framework (crates.io `rustrade-framework`)

The scaffolding every bot would otherwise rewrite: `Bot`/`Brain` traits, the
supervisor loop, risk primitives (sliding-window circuit breaker, daily-loss
halt), backtest engine (incl. OCO bracket simulation as of 0.4.1). Consumed by
the crypto bots, the demo bots in `fks/bots/`, and janus. **Never re-vendored**
into fks.

### 4.5 `indicators-ta` — TA math (crates.io `indicators-ta`, import `indicators`)

Incremental O(1) indicators (RSI, EMA, ATR, MACD, Bollinger) + regime helpers.
The shared math under both the crypto bots' strategies and janus's inline
forward indicators. 0.2.3 current.

### 4.6 `exchange-apiws` — exchange connectivity (crates.io `exchange-apiws`)

REST + WebSocket clients for Kraken, KuCoin, Crypto.com, Bybit, Binance —
market data and the authenticated order path. Hard-won operational fixes live
here: rustls provider wiring (`rustls-no-provider` + ring install — the class
of bug that once broke both janus wss and bot HTTPS), 429/Retry-After backoff,
IPv4 forcing for dual-stack venues. 0.8.1 current. Consumed by the crypto
bots, `fks/bots/rustrade-exchange-apiws` (the live order-path adapter), and
janus forward (Bybit connectivity).

### 4.7 `crypto` — the production bots (private)

Two binaries built on the three published crates:

- **`spot-portfolio`** — multi-venue spot rebalancer (Kraken + KuCoin +
  Crypto.com), threshold-based deposit-rebalance; runs **LIVE** with real
  funds (small). Leave-alone by doctrine.
- **`kucoin-futures` (funding)** — funding-extreme reversion strategy on
  KuCoin USDT-M perps; **paper**, two-key arm gate (`live=true` +
  `DIP_ARM_LIVE=1`) before it can ever trade real money.

Both serve the **FKS bot contract** (§5.1) natively: `/health`, `/metrics`
(`fks_bot_*` gauges incl. net worth, per-exchange totals, positions) and a
rich `/status` JSON document that the WebUI `/exchanges` pages read. The
integration plan (`crypto/FKS-INTEGRATION.md`) tracks the move from systemd to
spawner-managed containers: Phase 1 (status servers) done; Phase 2
(fks-bot images, `BOT_CONFIG` env parsing, Postgres state store), Phase 3 UI
(done on the fks side), Phase 4 (systemd retirement) pending.

### 4.8 `fks-kotlin` — mobile/KMP client

Kotlin Multiplatform read surface over janus's HTTP APIs (signals, dashboard,
health) — repointed from the removed Ruby API to janus. Now that the signal
read APIs return real data, its wire-smoke DTO tests can validate against the
live stack.

### 4.9 `technical_papers` — the theory

`project_janus/janus.tex`: the JANUS architecture paper (neuromorphic
multi-region design, Quant 4.0 framing, crowding resistance, validation
framework) with an explicit **research-to-production maturity gap** section
that is kept reconciled with the code (live path = deterministic regime/rule
engine + safety/observability infra; neural core standalone). CI auto-compiles
PDFs. When code reality changes (e.g. unified deployment, signal persistence,
completeness SLI), the paper gets a reconciliation PR.

---

## 5. The contracts that bind the repos

### 5.1 The FKS bot contract (spawner ⇄ any bot)

1. Image named `fks-bot-*` (spawner `ALLOWED_IMAGE_PREFIX`), non-root,
   caps dropped; joins `fks_network`; labels `fks.bot=true`, `fks.bot_id`,
   `fks.mode` injected.
2. HTTP on **:9091**: `GET /health`, `GET /metrics` with at minimum
   `fks_bot_pnl_dollars`, `fks_bot_signals_total`, `fks_bot_trades_total`,
   `fks_bot_win_rate`, `fks_bot_uptime_seconds` (the crypto bots add net-worth
   / per-exchange / position gauges + `GET /status`).
3. All config via env. Spawner sets `FKS_BOT_ID`/`FKS_BOT_MODE`; requesting
   `secrets: ["kraken", …]` at spawn injects stored credentials as
   `{EXCHANGE}_API_KEY/_API_SECRET(/_API_PASSPHRASE)` — decrypted from the
   at-rest store only at spawn; the spawn **fails** if keys aren't stored.
4. Prometheus discovers spawned bots automatically via the spawner's file-SD.

### 5.2 Signal path (janus → UI)

```
klines (Binance WS) → MarketDataBus → forward strategy consensus
  → regime/prop-firm/risk/brain gates → SignalBus (in-process broadcast)
  → signal_redis persistence → Redis (janus:signals:*)
  → janus read APIs (/api/signals/*, /api/pipeline/scores/json, dashboard)
  → fks-web adapter → /signals page + overview panel
```

### 5.3 Secrets path (UI → bot)

```
/settings card (submit-only) → webui adapter /api/settings/{exchange}-keys
  → nginx X-Internal-Token → spawner POST /secrets
  → ChaCha20-Poly1305 encrypt (SPAWNER_SECRETS_KEY) → Postgres ruby_db
  → (spawn with secrets:[...]) → decrypt at BotRunStore boundary
  → container env {EXCHANGE}_API_* → exchange-apiws authenticated path
```

### 5.4 Observability path

Prometheus scrapes janus `:9090` (unified), exporters, spawner, node-exporter,
file-SD bots, and the transitional systemd bots. **Every alert rule references
an exported metric** (audited); Grafana dashboards live-reload from the host
mount; alertmanager routes to Discord. Key SLO: `data_completeness_percent`
(janus-computed) behind `DataCompletenessLow`.

---

## 6. Security model

- Edge: nginx (TLS via Tailscale certs) injects `X-Internal-Token`; all
  container ports bind 127.0.0.1.
- janus brain kill-switch/affinity-reset: Bearer `BRAIN_API_TOKEN`
  (**fail-open when unset — keep it set**).
- Exchange credentials: encrypted at rest (spawner, `SPAWNER_SECRETS_KEY`,
  `enc:v1:` format; invalid key disables the DB rather than risk plaintext
  writes); browser is submit-only; decrypt only at spawn injection.
- Execution doctrine: **no autonomous execution** — `EXECUTION_MODE`
  defaults to paper; the live order path stays behind the manual execution
  gate; the funding bot additionally needs a two-key arm.

---

## 7. Current integration status (2026-07-03)

| Thread | State |
|---|---|
| janus signal read APIs + dashboards | ✅ live (Redis persistence) |
| data-completeness SLI/SLO | ✅ live (caught MATIC→POL day one) |
| Alert board + Grafana | ✅ audited — 85 real rules, repointed dashboards |
| WebUI: charts/signals/exchanges/settings/bots | ✅ live |
| Secrets: encrypt-at-rest + spawn injection + UI | ✅ live |
| Crypto bots on the platform | ⏳ transitional systemd; Phase-1 status servers built, awaiting restart (spot :9091 / funding :9095); Phase 2 containerization pending in the crypto repo |
| JANUS neural core in live loop | 🔬 research (per the paper's maturity gap) |
