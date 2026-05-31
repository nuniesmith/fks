# fks-full — TODO (orchestration / cross-cutting)

> **Repo:** `github.com/nuniesmith/fks-full`
> **Last synced:** 2026-05-31
>
> This file covers **cross-cutting** orchestration work — consuming the
> external repos/crates, docker-compose, Dockerfiles, CI/CD, Postgres
> bootstrap, observability, deployment. Work specific to a sub-codebase
> now lives in **that repo's** own `TODO.md`:
>
> - [`nuniesmith/rustrade`](https://github.com/nuniesmith/rustrade) — framework
> - [`nuniesmith/janus`](https://github.com/nuniesmith/janus) — brain
> - [`nuniesmith/indicators-ta`](https://github.com/nuniesmith/indicators-ta) — TA math
> - [`nuniesmith/exchange-apiws`](https://github.com/nuniesmith/exchange-apiws) — exchange REST/WS
>
> The repo map is in [`docs/architecture/REPO_TOPOLOGY.md`](docs/architecture/REPO_TOPOLOGY.md);
> the remaining split moves are in [`SPLIT_PLAN.md`](SPLIT_PLAN.md).

---

## Status snapshot (2026-05-31)

The split **happened**. `rustrade`, `janus`, `indicators-ta`, and
`exchange-apiws` are independent repos, and the libraries are on crates.io:

| Crate | crates.io | Consume as |
|-------|-----------|------------|
| `rustrade-framework` (+ core/supervisor/risk/backtest) | **0.2.1** ✅ | `rustrade = { package = "rustrade-framework", version = "0.2" }` |
| `indicators-ta` | **0.1.3** ✅ | `indicators-ta = "0.1"` (imports as `indicators`) |
| `exchange-apiws` | **0.1.10** ✅ | `exchange-apiws = "0.1"` (local tree is 0.3.x — see P0) |
| `jflow-core` (janus) | **0.1.0** ✅ | first janus lib; rest of `jflow-*` prepped, not pushed |

What's left is **consumption + consolidation**, not splitting. `fks-full`
keeps only `src/proto`, `crates/spawner`, `src/ruby`, `src/web`, infra, and
(soon) `bots/` + `strategies/`.

---

## P0 — Finish the consume-from-external-repos setup

### Done in the current pass

- [x] Deleted the stale in-tree duplicates `crates/{janus,indicators-ta,exchange-apiws,kucoin}`.
      They were copies that had drifted **behind** the real repos and were
      orphaned from the build (root workspace is `members = ["src/proto"]`).
- [x] `JANUS_REPO` defaults to `https://github.com/nuniesmith/janus` so the
      janus image builds via `git clone` now that no in-tree copy remains.
- [x] `.env.example` repo URLs corrected to the real repos
      (`nuniesmith/janus`, `nuniesmith/ruby`, `nuniesmith/fks-web`,
      `nuniesmith/spawner`).
- [x] `.github/workflows/rust.yml` matrix trimmed to the workspaces that
      remain here (`root · src/proto`, `crates/spawner`, and the standalone
      `bots/fks-bot-example`).
- [x] **Ported `fks-bot-example` → `bots/fks-bot-example/` and deleted
      `crates/rustrade`** — the last in-tree copy is gone. The bot is now a
      standalone crate depending on crates.io
      (`rustrade = { package = "rustrade-framework", version = "0.2" }`, own
      `[workspace]`). Adapted to the 0.2.1 API: `session_symbol`→`symbol`,
      `.supervisor(SupervisorConfig…)`→`.shutdown_timeout()`, `.build()?`,
      `market_bus()`→`market_data_bus()`, `logging::init()`→`init_tracing()`,
      `ExchangeClient` now takes `&Symbol`, `Tick.symbol` is `Symbol`. Dockerfile
      builds it standalone; it's a `rust.yml` matrix entry. _Verified by CI —
      this repo's env has no crates.io egress._
- [x] Docs re-based on reality — `README.md`, `CLAUDE.md`, `SPLIT_PLAN.md`,
      and the new `docs/architecture/REPO_TOPOLOGY.md`.

### Immediate follow-ups

- [ ] **Reconcile `exchange-apiws` versioning.** crates.io is **0.1.10**; the
      local tree is **0.3.2** (unpublished: signed REST, private WS). Decide
      the version line, then `cargo publish` the 0.3.x release so downstreams
      can depend on the newer surface. (Its own repo's `todo.md` still claims
      "never published" — that's stale; it *is* live at 0.1.10.)
- [ ] **Finish the `jflow-*` publish run** (janus repo). `jflow-core` is live;
      publish the Tier-0 leaves then Tier-1+ bottom-up per janus `PUBLISHING.md`.
      Blocked only on the crates.io token + sequencing.

---

## P1 — Janus consolidation (consume the shared crates)

> The big architectural work. Lives in the **janus** repo; tracked here
> because it's the whole point of the split. Today janus duplicates TA and
> exchange connectivity internally (`jflow-indicators`, `jflow-exchanges`,
> `jflow-bybit-client`) and dropped its `rustrade` dependency. Target: one
> source of truth per concern.

- [ ] **TA → `indicators-ta`.** Migrate janus's `jflow-indicators` consumers
      onto `indicators-ta`; retire the duplicate. (`IncrementalEma`/`IncrementalAtr`
      already lifted into `indicators-ta` — continue from there.)
- [ ] **Connectivity → `exchange-apiws`.** Replace `jflow-exchanges` /
      `jflow-bybit-client` usage with `exchange-apiws`; retire the duplicates.
- [ ] **Framework → `rustrade`.** Re-adopt the framework: janus's signal
      services become `rustrade::Brain`s / `TradingService`s under a
      `rustrade::Bot`/`Supervisor`, instead of bespoke lifecycle code.
- [ ] Decide janus public-vs-private once consolidated (the brain IP can stay
      private while `jflow-*` siblings remain public on crates.io).

---

## P0 — Tailscale verification

- [ ] Test access from a second tailnet device (needs a physical second device).
- [ ] Verify trainer container GPU passthrough:
      `./run.sh all --profile training` + nvidia-container-toolkit.

---

## P1 — Multi-account: Postgres schema (ACCT-A)

- [ ] Create and apply `src/ruby/sql/008_accounts.sql`:
  - `exchange_accounts` (id, name, exchange_type, mode, is_active,
    credentials_ref, api_key_hint, timestamps, last_test status)
  - `asset_routing_rules` (id, symbol, account_id, size_pct, priority, is_active)
  - `profit_sweep_config` (id, source_account_id, threshold_usd, mode,
    schedule_time, timestamps)
  - `profit_sweep_targets` (id, sweep_config_id, account_id, allocation_pct)
- [ ] Apply via `./run.sh fix-db`.

## P1 — Multi-account: Janus execution router (ACCT-E)

> Lives in the janus repo (`services/execution/`); the compose env wiring is here.

- [ ] Add a `RoutingClient` in janus `execution/src/routing.rs`: HTTP client
      calling `GET http://fks_ruby:8000/api/routing/{symbol}`, 60s cache TTL.
- [ ] On signal: create one `ExecutionTarget` per routing rule, fan out the
      signal to each target with an `account_id` label.
- [ ] Add `ROUTING_API_URL=http://fks_ruby:8000` to janus execution env in
      `docker-compose.yml`.

---

## P1 — Observability

- [ ] **PROM:** Sync Grafana config and restart — ensure all alert rules load.
- [ ] **GPU metrics** — Prometheus scrape when the trainer is running
      (nvidia-container-toolkit exporter).
- [ ] **Alertmanager Discord bridge** — container occasionally not running,
      causing noise in Alertmanager logs. Either fix or remove.
- [ ] **`bot-alerts.yml`** under `infrastructure/config/prometheus/alerts/` —
      `BotStopped`, `BotHighDrawdown`, `BotNoSignals`. Add once at least one
      real `fks-bot-*` image produces the metrics (see the `bots/` follow-up).

---

## P1 — Proto

- [ ] Centralise the stray `forward/proto/janus/v1/janus.proto` (janus repo) →
      `proto/fks/janus/v1/signal_service.proto` here — deferred until the
      gRPC endpoint is actually used (dead code today). Mirrors janus
      `TODO.md` STRUCT-C.

---

## P2 — Image push & CI hardening

- [ ] Re-enable ARM64 / multi-arch builds in CI (disabled in batch-013).
- [ ] `docker push nuniesmith/fks:janus` — publish the Janus image for faster deploys.
- [ ] `docker push nuniesmith/fks:spawner` — same.
- [ ] **`rust.yml` clippy gate.** Clippy currently runs `continue-on-error`.
      Flip to `-D warnings` per workspace as each closes out its lint backlog.
- [ ] Postgres data migration (optional): use `pgloader` if dev data is worth
      preserving across rebuilds.

---

## P2 — Feature work (Ruby/strategies)

### PAPER-TRADING: live validation
- [ ] Test Redis state persistence: `sim:session:{id}:*` keys written/readable.
- [ ] Verify SSE streaming: `/sse/paper-trading/{id}` streams to WebUI.

### PINE-INT: manual verification
- [ ] Paste generated `ruby.pine` into TradingView Pine editor, confirm it compiles.

### CRITICAL-FIX-A: Rithmic (remaining)
- [ ] Live test — verify positions, L1/L2, PnL match dashboard against a
      Rithmic paper account (needs credentials).
- [ ] Margin usage field — depends on Rithmic margin data availability.

---

## P3 — Future (post-funding)

- [ ] **`bots/`** — more thin strategy bots that consume the published
      `rustrade` + `indicators-ta` + `exchange-apiws` crates.
      `bots/fks-bot-example` is the first, and the template, for these.
- [ ] **`strategies/`** — once `fks-full` flips **private**, this is where the
      actual trading IP lives. Bots get wired to consume the published crates.
- [ ] Retrain: run bracket sweep (`scripts/bracket_sweep.py`), apply optimal
      brackets, retrain vs the 93.5% baseline.
- [ ] `POSINT-B`: Multi-account position aggregation (needs multiple funded accounts).
- [ ] `DOM-C`: DOM click-to-trade Phase 2 — click price level → limit order, drag stops.
- [ ] Profit allocation dashboard: 50% reinvestment / 20% personal / 15% tax /
      10% emergency / 5% education.
- [ ] Multi-exchange: crypto.com, Netcoins, BTC hardware wallet xpub monitoring
      (note: `exchange-apiws` already covers Binance / Bybit / Kraken /
      Crypto.com / KuCoin public surfaces).
- [ ] K8s manifests — `infrastructure/k8s/` for cloud scaling (post prop-firm funded).

---

## ✅ Recently shipped

- **Repo split executed** — `rustrade`, `janus`, `indicators-ta`,
  `exchange-apiws` are their own repos; rustrade family + `indicators-ta` +
  `exchange-apiws` + `jflow-core` published to crates.io.
- **Docker git-clone build path** — base images acquire source via
  `git clone --branch ${*_REF}` (CI/prod) or local bind-mount (dev), wired for
  janus / ruby / web / spawner.
- **`indicators-ta` consolidation started** — `IncrementalEma` /
  `IncrementalAtr` lifted out of janus into `indicators-ta`.
- **Stale in-tree duplicates removed** — `crates/{janus,indicators-ta,exchange-apiws,kucoin}`
  deleted; docs re-based on the post-split reality.
- **Earlier (PRs #1–#21)** — the arc that took fks-full from "broken monolith"
  to "framework + spawner + repo-split-ready": rustrade family + examples,
  build-rot cleanup, spawner DB persistence + auth + tests + WebUI, the
  `fks-bot-example` reference image, and the `rustcode` / `openclaw` /
  `ollama` / `promptfoo` / legacy-kucoin removal (~23 → ~15 containers).
