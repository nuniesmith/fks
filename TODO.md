# fks-full — TODO (orchestration / cross-cutting)

> **Repo:** `github.com/nuniesmith/fks-full`
> **Last synced:** 2026-05-10
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

## P0 — Split prep & cleanup

### Finish the in-flight reorganisation

> Right now the working tree has uncommitted moves
> (`src/spawner/` → `crates/spawner/`, `src/kucoin/` → `crates/kucoin/`,
> sql tree co-located with each owner, `JANUS_EXTRACTION_PLAN.md` →
> `crates/janus/`). Land them.

- [ ] Commit the working-tree moves on a single focused branch
      ("Co-locate sub-codebase assets before the split"). One commit is
      fine since `git mv` history will trace it.
- [ ] Update the root `Cargo.toml` workspace members:
      `members = ["src/proto", "crates/spawner"]` (or remove
      `crates/spawner` if it becomes its own nested workspace; see
      `crates/spawner/TODO.md`).
- [ ] Verify `cargo check --workspace` from the repo root passes after
      the move. Currently fails because `src/spawner/Cargo.toml` no
      longer exists.

### Remove rustcode + openclaw + promptfoo + ollama

- [ ] Delete `crates/rustcode/`.
- [ ] Delete `infrastructure/docker/services/{rustcode,openclaw,openclaw-base,openclaw_cli,promptfoo,ollama}/`.
- [ ] Delete `infrastructure/config/{openclaw,rustcode,promptfoo}/`.
- [ ] Delete `infrastructure/promptfoo/`.
- [ ] Strip the `/api/code/*`, `/api/openclaw/*`, `/api/rc/*` nginx location blocks from `infrastructure/config/nginx/conf.d/*.conf`.
- [ ] Strip `RC_*`, `OPENCLAW_*`, `XAI_API_KEY` (if only used by RC) entries from `.env.example`.
- [ ] Strip the `rustcode`, `fks_ollama`, `fks_ollama_init`, `openclaw`, `openclaw_cli`, `promptfoo` service blocks from `docker-compose.yml`. *(already done in the working tree as of 2026-05-10 — confirm + commit.)*
- [ ] Remove the corresponding `./run.sh rc` subcommand and any other run-script entries.

### Remove `crates/kucoin/` (legacy bot)

- [ ] Delete `crates/kucoin/` after confirming `rustrade-kucoin` +
      `crates/rustrade/examples/kucoin-v2/` cover the use case.
- [ ] No docker-compose / nginx changes needed — `crates/kucoin/` isn't
      wired into the runtime.

### Per-sub-codebase doc readiness

- [x] `SPLIT_PLAN.md` written.
- [x] `CLAUDE.md` + `TODO.md` added to each future-external sub-codebase.
- [x] Root `README.md` / `CLAUDE.md` / `TODO.md` updated to point at the
      split direction.
- [ ] Audit each sub-README for `fks-full` path references. Replace
      with public-repo-shaped equivalents before split.

---

## P0 — Dockerfile: build from source

> When each sub-codebase becomes its own repo, the Dockerfiles need to
> `git clone --branch ${*_REF:-main} https://github.com/nuniesmith/<repo>`
> instead of `COPY` from the local tree. Today they `COPY`.

- [ ] `infrastructure/docker/services/data/Dockerfile` — clone `ruby`.
- [ ] `infrastructure/docker/services/web/Dockerfile` (or
      `infrastructure/docker/base/nodejs/Dockerfile`) — clone `fks-web`.
- [ ] `infrastructure/docker/base/rust/Dockerfile` for `janus` — clone `janus`.
- [ ] `infrastructure/docker/services/spawner/Dockerfile` — clone `spawner`.
- [ ] Add `RUBY_REF`, `JANUS_REF`, `WEB_REF`, `SPAWNER_REF` build args
      to `docker-compose.yml` (default `main`).
- [ ] Document the build args in `.env.example`.

> Reminder: `infrastructure/docker/services/*` is for **external apps**
> (postgres, redis, prometheus, grafana, etc.). Our own services should
> use the shared base images under
> `infrastructure/docker/base/{rust,python,nodejs,python-gpu}`.

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

## P2 — CI/CD & image persistence

- [ ] Re-enable ARM64 / multi-arch builds in CI (disabled in batch-013).
- [ ] `docker push nuniesmith/fks:janus` — publish Janus image for faster deploys.
- [ ] `docker push nuniesmith/fks:spawner` — same.
- [ ] Postgres data migration (optional): use `pgloader` if dev data
      worth preserving across rebuilds.
- [ ] **CI gates:**
  - [ ] `cargo check --workspace` from every nested workspace.
  - [ ] `npm run check` on `src/web` (non-blocking until the 29 type errors clear).
  - [ ] `pytest tests/` on `src/ruby`.

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

## ✅ Recently shipped (PRs #1–#19 in this repo)

The 19-PR arc that built the rustrade framework + the spawner + the
`/bots` WebUI route:

- **Framework (PRs #1–#10)** — `rustrade-{core,supervisor,risk,backtest,kucoin,notify}` + facade + 4 examples + design invariants documented in `CONTRIBUTING.md`.
- **Build rot cleanup (#11)** — root + janus + spawner workspaces compile cleanly.
- **Spawner: DB persistence + 21 tests + README (#12, #18)** — `BotRunStore` writes spawn/stop/remove to `bot_runs`; `DockerOps` trait + `MockDockerClient` + 10 HTTP integration tests; `X-Internal-Token` auth middleware.
- **Spawner: WebUI (#13, #19)** — `/bots` route with spawn form, container list, SSE log viewer with follow-tail, run history. `api.*` callsite fixes across signals/backup/performance.
- **WebUI build fixes (#14)** — dual-script bug, abandoned `$props<{...}>()`, `const err;` syntax error.
- **Spawner stack lands on main (#15)** — corrected the stacked-PR merges.
- **Docs sync (#16)** — root `CLAUDE.md` + `TODO.md` updated.
- **`fks-bot-example` reference image (#17)** — produces the documented `fks_bot_*` metrics for the spawner's `file_sd_configs` job.
- **Janus port to rustrade-supervisor (PR #19 / "Janus port" commit)** — `crates/janus/bin/janus/` uses `rustrade-supervisor` directly; `rustrade-supervisor`'s deps pinned explicitly so the cross-workspace path dep works. Caught a real axum 0.8 path-syntax bug in the spawner along the way.
