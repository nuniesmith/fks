# fks-full — TODO (orchestration / cross-cutting)

> **Repo:** `github.com/nuniesmith/fks-full`
> **Last synced:** 2026-05-11
>
> This file covers **cross-cutting** work — docker-compose, Dockerfiles,
> nginx, CI/CD, Postgres bootstrap, observability, deployment. Anything
> specific to a sub-codebase lives in that sub-codebase's `TODO.md`:
>
> - `crates/rustrade/TODO.md` — framework crates
> - `crates/janus/TODO.md` — ML engine
> - `crates/indicators-ta/TODO.md`
> - `crates/exchange-apiws/TODO.md`
> - `crates/spawner/TODO.md`
> - `src/ruby/TODO.md`
> - `src/web/TODO.md`
>
> The repo-split blueprint is in `SPLIT_PLAN.md`.

---

## P0 — Split prep & CI

### Per-sub-codebase doc readiness

- [x] `SPLIT_PLAN.md` written.
- [x] `CLAUDE.md` + `TODO.md` added to each future-external sub-codebase.
- [x] Root `README.md` / `CLAUDE.md` / `TODO.md` point at the split direction.
- [x] Audit each sub-README for `fks-full` path references. Verified
      clean across all 8 sub-codebases (rustrade family + indicators-ta
      + exchange-apiws + spawner + ruby + web + janus). `fks-full` refs
      that remain are in `TODO.md` / `CLAUDE.md` / `Cargo.toml`
      structural comments — all `exclude`d from the publish tarball or
      intentional dev-time notes that get rewritten at split time.

### CI gates (blocking Phase 2 of `SPLIT_PLAN.md`)

> No Rust CI is configured yet. `.github/workflows/` only has the
> auto-labeler and the paper-trading soak workflow. Without a CI
> workflow that runs `cargo check + test` per nested workspace, a bad
> merge can silently red the build of any sub-codebase that's about
> to be extracted.

- [ ] **`.github/workflows/rust.yml`** — one matrix job per nested
      workspace (`crates/rustrade/`, `crates/janus/`, `crates/spawner/`,
      `crates/indicators-ta/`, `crates/exchange-apiws/`, repo root). Each
      runs `cargo check --workspace`, `cargo test --workspace`,
      `cargo clippy --workspace -- -D warnings`.
- [ ] **`.github/workflows/web.yml`** — `npm run check` on `src/web/`
      (non-blocking until the existing type errors clear).
- [ ] **`.github/workflows/python.yml`** — `pytest tests/` on `src/ruby/`
      (or scoped to whatever subset is green today).

### Pre-publish audit per crate (`SPLIT_PLAN.md` Phase 2)

For every crate slated for crates.io: `indicators-ta`,
`exchange-apiws`, `spawner`, `rustrade-{core,supervisor,risk,backtest,notify}`,
`rustrade-kucoin`, `rustrade` (facade).

- [ ] Walk each `Cargo.toml`: `description`, `license`, `repository`,
      `keywords`, `categories`, `readme` populated.
- [ ] `publish = true` (or absent) on the crates that should publish.
- [ ] `cargo publish --dry-run` from each crate's directory. Produce
      a per-crate blocker list.
- [ ] Decide crate-name convention for the eventual janus public
      siblings — `-ta` suffix vs `trading-` prefix vs `rustrade-`
      prefix (called out in `crates/janus/JANUS_EXTRACTION_PLAN.md`).

---

## P0 — Dockerfile: build from source

> When each sub-codebase becomes its own repo, the Dockerfiles need to
> `git clone --branch ${*_REF:-main} https://github.com/nuniesmith/<repo>`
> instead of `COPY` from the local tree.
>
> **Status:** the underlying Dockerfile infrastructure is in place
> (`infrastructure/docker/base/rust/Dockerfile`,
> `infrastructure/docker/base/nodejs/Dockerfile`,
> `infrastructure/docker/services/spawner/Dockerfile`). All four base
> images already support a dual-mode source acquisition step:
> `REPO_URL=""` → bind-mount the local context (dev default);
> `REPO_URL` set → `git clone --depth=1 --branch ${REPO_REF}` from the
> URL.

- [x] `infrastructure/docker/base/python/Dockerfile` (the ruby service
      image; `services/ruby/` only holds entrypoint + supervisord conf).
      `RUBY_REPO`/`RUBY_REF` wired in `docker-compose.yml`.
- [x] `infrastructure/docker/base/nodejs/Dockerfile` — supports the
      git-clone path; `WEB_REPO`/`WEB_REF` wired in `docker-compose.yml`'s
      `webui:` block.
- [x] `infrastructure/docker/base/rust/Dockerfile` (used for `janus`).
      `JANUS_REPO`/`JANUS_REF` wired in `docker-compose.yml`.
- [x] `infrastructure/docker/services/spawner/Dockerfile`.
      `SPAWNER_REPO`/`SPAWNER_REF` wired in `docker-compose.yml`.
- [x] `RUBY_REPO`/`RUBY_REF`, `JANUS_REPO`/`JANUS_REF`,
      `WEB_REPO`/`WEB_REF`, `SPAWNER_REPO`/`SPAWNER_REF` documented in
      `.env.example`.

> Reminder: `infrastructure/docker/services/*` is for **external apps**
> (postgres, redis, prometheus, grafana, etc.). Our own services use the
> shared base images under
> `infrastructure/docker/base/{rust,python,nodejs,python-gpu}`. The
> `services/ruby/` and `services/spawner/` directories are exceptions —
> ruby only holds entrypoint glue while the actual build lives in the
> python base; spawner has its own standalone Dockerfile that mirrors
> the rust base's git-clone pattern.

---

## P0 — Tailscale verification

- [ ] Test access from a second tailnet device (needs physical second device).
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

- [ ] Update `crates/janus/services/execution/` — add `RoutingClient`
      in `execution/src/routing.rs`: HTTP client calling
      `GET http://fks_ruby:8000/api/routing/{symbol}`, 60s cache TTL.
- [ ] On signal: create `ExecutionTarget` per routing rule, fan out
      signal to each target with `account_id` label.
- [ ] Add `ROUTING_API_URL=http://fks_ruby:8000` to janus execution env
      in `docker-compose.yml`.

---

## P1 — Observability

- [ ] **PROM:** Sync Grafana config and restart — ensure all alert rules load.
- [ ] **GPU metrics** — Prometheus when trainer is running (nvidia-container-toolkit exporter).
- [ ] **Alertmanager Discord bridge** — container occasionally not running, causes noise in Alertmanager logs. Either fix or remove.
- [ ] **`bot-alerts.yml`** under `infrastructure/config/prometheus/alerts/` — `BotStopped`, `BotHighDrawdown`, `BotNoSignals`. Add once we have at least one real `fks-bot-*` image producing the metrics.

---

## P1 — Proto

- [ ] Centralise stray `forward/proto/janus/v1/janus.proto` →
      `proto/fks/janus/v1/signal_service.proto` — deferred until the
      gRPC endpoint is actually used (dead code today).

---

## P2 — Image push & CI hardening

- [ ] Re-enable ARM64 / multi-arch builds in CI (disabled in batch-013).
- [ ] `docker push nuniesmith/fks:janus` — publish Janus image for faster deploys.
- [ ] `docker push nuniesmith/fks:spawner` — same.
- [ ] Postgres data migration (optional): use `pgloader` if dev data
      worth preserving across rebuilds.

---

## P2 — Feature work (Ruby/strategies)

### PAPER-TRADING: live validation
- [ ] Test Redis state persistence: `sim:session:{id}:*` keys
      written/readable.
- [ ] Verify SSE streaming: `/sse/paper-trading/{id}` streams to WebUI.

### PINE-INT: manual verification
- [ ] Paste generated `ruby.pine` into TradingView Pine editor, confirm it compiles.

### CRITICAL-FIX-A: Rithmic (remaining)
- [ ] Live test — verify positions, L1/L2, PnL match dashboard against
      Rithmic paper account (needs credentials).
- [ ] Margin usage field — depends on Rithmic margin data availability.

---

## P3 — Future (post-funding)

- [ ] Retrain: run bracket sweep (`scripts/bracket_sweep.py`), apply
      optimal brackets, retrain vs 93.5% baseline.
- [ ] `POSINT-B`: Multi-account position aggregation (needs multiple
      funded accounts).
- [ ] `DOM-C`: DOM click-to-trade Phase 2 — click price level → limit
      order, drag stops.
- [ ] Profit allocation dashboard: 50% reinvestment / 20% personal /
      15% tax / 10% emergency / 5% education.
- [ ] Multi-exchange: crypto.com, Netcoins, BTC hardware wallet xpub
      monitoring.
- [ ] K8s manifests — `infrastructure/k8s/` for cloud scaling
      (post prop-firm funded).
- [ ] **`strategies/`** — once `fks-full` flips private, this is where
      the actual trading IP lives. Currently empty. Bots get wired up
      to consume the published rustrade + indicators-ta + exchange-apiws
      crates from crates.io.

---

## ✅ Recently shipped (PRs #1–#21)

The 21-PR arc that took fks-full from "broken monolith" to "feature-complete framework + spawner + repo-split-ready":

- **Framework (PRs #1–#10)** — `rustrade-{core,supervisor,risk,backtest,kucoin,notify}` + facade + 4 examples + design invariants documented in `crates/rustrade/CONTRIBUTING.md`. Plus `JANUS_EXTRACTION_PLAN.md` and a doc-coverage pass.
- **Build rot cleanup (#11)** — root + janus + spawner workspaces compile cleanly.
- **Spawner: DB persistence + 21 tests + README (#12, #18)** — `BotRunStore` writes spawn/stop/remove to `bot_runs`; `DockerOps` trait + `MockDockerClient` + 10 HTTP integration tests; `X-Internal-Token` auth middleware.
- **Spawner: WebUI (#13, #19)** — `/bots` route with spawn form, container list, SSE log viewer with follow-tail, run history. `api.*` callsite fixes across signals/backup/performance.
- **WebUI build fixes (#14)** — dual-script bug, abandoned `$props<{...}>()`, `const err;` syntax error.
- **Spawner stack lands on main (#15)** — corrected the stacked-PR merges.
- **Docs sync (#16)** — root `CLAUDE.md` + `TODO.md` updated.
- **`fks-bot-example` reference image (#17)** — produces the documented `fks_bot_*` metrics for the spawner's `file_sd_configs` job.
- **Repo-split prep (#20)** — `SPLIT_PLAN.md`, per-sub-codebase `CLAUDE.md` + `TODO.md`, root docs updated.
- **Cleanup (#21)** — `crates/rustcode/`, `crates/kucoin/` (legacy), `infrastructure/docker/services/{rustcode,openclaw,openclaw_cli,promptfoo,ollama}/`, the matching nginx + env-var entries, and `RC_*` / `OPENCLAW_*` env vars all removed. Sub-codebase SQL co-located with owners. `JANUS_EXTRACTION_PLAN.md` moved to `crates/janus/`. Root `Cargo.toml` slimmed to `members = ["src/proto"]`.

### Structural change worth calling out

**`rustrade-supervisor` deps are now pinned explicitly** (not `workspace = true`). This was the gating change for cross-workspace path deps — `crates/janus/bin/janus/` can now path-dep `rustrade-supervisor` without mirroring its transitive deps into `janus`'s `[workspace.dependencies]`. Same pattern will apply when more rustrade crates need to be consumed by foreign workspaces, including post-publish from crates.io.
