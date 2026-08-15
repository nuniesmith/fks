# FKS Platform Architecture — The Complete Reference

> **The single map**: how the `fks` orchestrator repo relates to every repo it
> consumes, what each repo does, how it supports the running platform, and the
> contracts that bind them.
>
> **Last updated:** 2026-07-13 (post #196 prune: the bot factory — spawner,
> `crypto-bot-core`, all bots incl. `spot-portfolio` — lives in the
> **`fks-spawner`** repo; `rithmic-connector` + the funded-side `advisor`/`orb-*`
> crates live in the private **`fks-state`** repo, whose services ride the
> compose `state`/`rithmic` profiles).
> Supersedes [`REPO_TOPOLOGY.md`](REPO_TOPOLOGY.md) (2026-05-31, pre-web-split).

---

## 1. One-picture overview

```
                          ┌─────────────────────────────────────────────────────┐
                          │              nuniesmith/fks  (THIS REPO)            │
                          │   docker-compose orchestrator · infra config ·      │
                          │   sql bootstrap · proto · ops scripts               │
                          └───┬───────────┬────────────┬───────────┬────────────┘
              git-clone image │           │ git-clone  │ local     │ git-clone
                              ▼           ▼ image      ▼ image*    ▼ image (pinned)
                     ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
                     │   janus    │ │ fks-web  │ │fks-state │ │ fks-spawner  │
                     │ (brain)    │ │ (webui)  │ │ (edges)  │ │ (bot factory)│
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
        * the production bots run as spawner-managed fks-bot-* containers.
          The bot images build from the SIBLING checkouts: the spot rebalancer
          from fks-spawner (bots/spot-portfolio), the private futures/funding
          edges from fks-state (bots/crypto-futures) — the old `crypto` repo
          is dissolved (and deleted from GitHub).
```

**Design doctrine** (from the split): *consume, don't absorb*. Reusable pieces
live in their own repos, published to crates.io or built as git-clone Docker
images pinned by ref. `fks` wires them together at runtime and owns nothing it
can consume.

---

## 2. The repo family

| Repo | Role | Consumed by fks as | Visibility |
|------|------|--------------------|-----------|
| [`nuniesmith/fks`](https://github.com/nuniesmith/fks) | **Orchestrator** — compose, infra config, SQL bootstrap, proto, ops scripts (the bot factory left in #196) | — (this repo) | public |
| [`nuniesmith/janus`](https://github.com/nuniesmith/janus) | **Trading brain** — signals, regime, risk, data ingestion, ML research | Docker image (git-clone `JANUS_REPO@JANUS_REF`) | public |
| [`nuniesmith/fks-web`](https://github.com/nuniesmith/fks-web) | **Operator UI** — SvelteKit dashboard | Docker image (git-clone `WEB_REPO@WEB_REF`) | public |
| [`nuniesmith/fks-spawner`](https://github.com/nuniesmith/fks-spawner) | **Bot factory** — spawner lifecycle service + `crypto-bot-core` SDK + the bots (`spot-portfolio` **production**, `crypto-demo`, `fks-bot-example`, `rustrade-exchange-apiws`) | spawner Docker image (git-clone `SPAWNER_REPO@SPAWNER_REF`, sha-pinned via `SPAWNER_COMMIT`); bot images build from the sibling checkout (`./run.sh build-bots`) | public |
| [`nuniesmith/rustrade`](https://github.com/nuniesmith/rustrade) | **Bot framework** — `Bot`/`Brain` traits, risk primitives, supervisor, backtest | crates.io `rustrade-framework` **0.4.x** | public |
| [`nuniesmith/indicators-ta`](https://github.com/nuniesmith/indicators-ta) | **TA math** — RSI/EMA/ATR/MACD/Bollinger + regime detection | crates.io `indicators-ta` **0.2.x** | public |
| [`nuniesmith/exchange-apiws`](https://github.com/nuniesmith/exchange-apiws) | **Exchange connectivity** — REST + WS for Kraken/KuCoin/Crypto.com/Bybit/Binance | crates.io `exchange-apiws` **0.9.x** | public |
| `nuniesmith/fks-state` | **Private layer** — futures/funding trading edges (`bots/crypto-futures`), `crates/{rithmic-connector,advisor,orb,orb-backtest,orb-briefing}`, encrypted state snapshots, strategy docs | images built from the local checkout: `advisor`/`orb-briefing` via the compose **`state`** profile (run.sh auto-enables it when `../fks-state` exists), `rithmic-connector` via **`rithmic`**, `fks-bot-crypto-funding` by hand; snapshots via `scripts/fks-state.sh` | **private** |
| [`nuniesmith/fks-kotlin`](https://github.com/nuniesmith/fks-kotlin) | **Mobile/KMP client** — read-only janus API surface | independent client of janus's HTTP APIs | public |
| [`nuniesmith/technical_papers`](https://github.com/nuniesmith/technical_papers) | **Theory** — the JANUS paper (`project_janus/janus.tex`) | reference; reconciled with code periodically | public |

> **Where the bot images build** (the `crypto` repo is dissolved, and #196
> moved the factory out of this tree): the spot image builds from the
> **fks-spawner** sibling checkout — `docker build -f
> bots/spot-portfolio/Dockerfile -t fks-bot-crypto-spot:latest .` from the
> fks-spawner root (`./run.sh build-bots` builds the reference bots the same
> way). `fks-state` is private, so the git-clone-in-Dockerfile pattern used
> for janus/fks-web **cannot** build its images without credential-baking —
> they build from the local checkout on the host: the funding image via
> `docker build -t fks-bot-crypto-funding:latest bots/crypto-futures` from
> the fks-state root, and `advisor`/`orb-briefing`/`rithmic-connector` via
> compose (`context: ../fks-state`, profiles `state`/`rithmic`).

---

## 3. What runs: the compose stack

~21 containers, all ports bound to `127.0.0.1` (reachable via localhost or the
Tailscale-served nginx edge only).

| Service | Container | Source | Host ports | Purpose |
|---|---|---|---|---|
| janus | `fks_janus` | janus repo (git-clone image) | 7000 (api :8080), 7001 (forward REST :8180), 7002 (exec gRPC :50052), 9051 (gRPC :50051), 9092 (unified /metrics :9090) | the platform brain |
| webui | `fks_webui` | fks-web repo (git-clone image) | 3001 (:3000) | operator dashboard |
| spawner | `fks_bot_spawner` | fks-spawner repo (git-clone image, sha-pinned) | 8090 | bot-container lifecycle + secret store + net-worth sampler + edge factory |
| advisor | `fks_advisor` | fks-state `crates/advisor` (**`state`** profile, local sibling build) | — | daily 17:30 + Sun 18:00 ET Discord digests |
| orb-briefing | `fks_orb_briefing` | fks-state `crates/orb-briefing` (**`state`** profile, local sibling build) | — | weekday pre-market briefing + sized ORB day-plan to Discord |
| rithmic-connector | `fks_rithmic_connector` | fks-state `crates/rithmic-connector` (**`rithmic`** profile; runtime-gated `RITHMIC_ENABLED`) | 9091 (opt-in) | read-only futures feed (foundation; idle without creds) |
| nginx | `fks_nginx` | in-tree config | 80 | TLS edge, `X-Internal-Token` injection |
| postgres | `fks_postgres` | custom image | 5432 | `janus_db` + `fks_db` (spawner schema) |
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

**Crypto bots:** spawner-managed containers since 2026-07-06 —
`fks-bot-crypto-spot` (**live** since 2026-07: `SPOT_LIVE=1`, real keys
injected from the encrypted secret store; spawnable from the saved
`crypto-spot-live` config) and `fks-bot-crypto-funding` (paper, saved
`crypto-funding-paper` config); the transitional user systemd units are
retired. Prometheus discovers spawned bots via the spawner's file-SD (the
static `fks-bots-transitional` job in `prometheus.yml` is a leftover of the
systemd phase, awaiting removal).

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
- **`src/sql/`** — DB bootstrap baked into the postgres image (`janus/` +
  `spawner/` schemas: bot runs/configs, secrets, notifications, `ui_layouts`,
  `net_worth_snapshots`, treasury, edge factory, and the scoped
  `fks_backtest` role — **every** script is COPY'd into the image, #201).
- **`src/proto/`** — `fks-proto` crate (protobuf contracts, `fks.<svc>.v1`).
- **`scripts/fks-state.sh`** — the encrypted private-state backup/restore
  tool (see `docs/STATE_BACKUP.md`; live + restore-verified).
- **`src/web/`** — legacy in-tree copy of the webui (dev fallback; production
  clones `fks-web`).

> The spawner service, the `crypto-bot-core` SDK, and the bots (incl. the
> production `spot-portfolio`) moved to the **`fks-spawner`** repo in the
> #196 prune — the spawner deep-dive in §5.3 still applies, the code just
> lives there now. `rithmic-connector` moved to **`fks-state`**.

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
the crypto bots, the demo bots in `fks-spawner/bots/`, and janus. **Never re-vendored**
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
IPv4 forcing for dual-stack venues. 0.9.0 current (typed instrument
specs/wallet/cancel + kraken market-data returns). Consumed by the crypto
bots, `fks-spawner/bots/rustrade-exchange-apiws` (the live order-path adapter), and
janus forward (Bybit connectivity).

### 4.7 The production bots — `fks-spawner:bots/spot-portfolio` + `fks-state` (private)

Two binaries built on the three published crates, migrated out of the
dissolved `crypto` repo into their post-split homes (and out of this tree in
the #196 prune):

- **`spot-portfolio`** (`fks-spawner/bots/spot-portfolio`) — multi-venue
  spot rebalancer (Kraken + KuCoin + Crypto.com), threshold-based
  deposit-rebalance. The image bakes a **dry-run** config; the production
  instance runs **live** via the deliberate `SPOT_LIVE=1` override in the
  saved `crypto-spot-live` spawn config (real keys injected from the secret
  store) — going live stays an explicit operator act, never a default (see
  [`WEBUI_PLATFORM_ROADMAP.md`](WEBUI_PLATFORM_ROADMAP.md) P9).
  Shares the generic scaffolding via fks-spawner's `crates/crypto-bot-core`.
- **`kucoin-futures` (funding)** (`fks-state/bots/crypto-futures`, private) —
  funding-extreme reversion strategy on KuCoin USDT-M perps; **paper**,
  two-key arm gate (`live=true` + `DIP_ARM_LIVE=1`) before it can ever trade
  real money. Git-pins `crypto-bot-core` from the `fks-spawner` repo.

Both serve the **FKS bot contract** (§5.1) natively: `/health`, `/metrics`
(`fks_bot_*` gauges incl. net worth, per-exchange totals, positions) and a
rich `/status` JSON document that the WebUI `/exchanges` pages read. The
systemd→spawner integration plan (now at
`fks-state/bots/crypto-futures/FKS-INTEGRATION.md`) is essentially complete:
both bots run as spawner-managed `fks-bot-*` containers (2026-07-06) and the
systemd units are retired; durable funding state (Postgres `StateStore`)
continues in `fks-state`.

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
2b. **Any bot that reports money** (i.e. serves `GET /status`) MUST carry
    these fields — they are not optional decoration, they are what the
    spawner's net-worth truth guards (`fks-spawner` `net_worth.rs`) key on,
    and each one **fails open** (silently disables its guard, not an error)
    when absent:
    - `expected_venues` (int) — how many venues the bot is CONFIGURED with,
      not how many are currently reporting. Without it, a venue that never
      checks in is invisible and `net_worth_usd` is a partial sum that looks
      complete.
    - `exchanges[].mode` (`"paper"` \| `"dry-run"` \| `"live"`) — lets the
      guard tell a real venue from a fabricated-cash one. `dry-run` holds
      REAL balances (orders only are suppressed) and must never be treated
      as equivalent to `paper`; a venue silently degraded to `paper` after a
      failed key check must be catchable from this field alone.
    - `exchanges[].updated` (epoch seconds) — per-venue staleness. Freshness
      is judged **per venue** (the MIN across `exchanges[]`), never from a
      root-level timestamp — a production bot may not publish one at all,
      and its absence must not read as "fresh by default."
    - `exchanges[]` itself, present-but-empty (`[]`) vs. absent — the two
      mean different things (see `fks-spawner`'s
      `crates/spawner/CLAUDE.md` "Bot-status contract & the net-worth truth
      guards" for the guard-chain detail) and a bot's HTTP server can start
      answering `exchanges: []` before its engine has completed a single
      venue cycle.

    A bot that satisfies point 2 above (health/metrics only) but skips these
    `/status` fields is fully spawnable and looks healthy in every dashboard
    while receiving **zero** staleness, completeness, or fabricated-cash
    protection on its treasury figures. Reference implementation:
    `fks-spawner` `crates/crypto-bot-core/src/status.rs` (`VenueStatus`,
    `expected_venues`).
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
  → ChaCha20-Poly1305 encrypt (SPAWNER_SECRETS_KEY) → Postgres fks_db
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

## 7. Current integration status (2026-07-13)

| Thread | State |
|---|---|
| janus signal read APIs + dashboards | ✅ live (Redis persistence) |
| data-completeness SLI/SLO | ✅ live (caught MATIC→POL day one) |
| Alert board + Grafana | ✅ audited — 85 real rules, repointed dashboards |
| WebUI: charts/signals/exchanges/settings/bots | ✅ live |
| Secrets: encrypt-at-rest + spawn injection + UI | ✅ live |
| Crypto bots on the platform | ✅ spawner-managed containers (2026-07-06); code homes settled — spot + `crypto-bot-core` → `fks-spawner`, funding edges → private `fks-state`; spot **live** (`SPOT_LIVE=1` saved config) |
| Treasury layer (transfers ledger + accounts) | ✅ schema `007` (#197) + fks-web `/treasury` (stale-account amber flag) |
| Edge factory (edges registry + `backtest_runs`) | ✅ schema `008` (#199) + scoped `fks_backtest` role (#202) + weekly edge-decay scheduler (fks-spawner #6; `EDGE_DECAY_ENABLED`, default off) |
| Encrypted private-state backups (`fks-state.sh`) | ✅ live + restore-verified (2026-07-12; #203/#206) |
| Advisor + ORB briefing Discord services | ✅ compose `state` profile (#198/#200/#202), built from `../fks-state` |
| Rithmic read-only connector | 🏗 foundation in `fks-state` (compose `rithmic` profile) — idle until paid dev-kit creds exist |
| JANUS neural core in live loop | 🔬 research (per the paper's maturity gap) |
