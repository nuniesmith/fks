# fks — TODO (Infrastructure & Runtime)

> **Repo:** `github.com/nuniesmith/fks-full`
> **Last synced:** 2026-05-09
>
> This file tracks work that belongs to the infrastructure layer: Docker,
> compose, Dockerfiles, nginx, CI/CD, Postgres schemas, observability config,
> the bot spawner service, and cross-cutting deployment tasks.

---

## ✅ Recently shipped (PRs #1–#15)

The framework + spawner story arc that ran from #1 through #15:

- **`rustrade` open-source trading framework** (PRs #1–#10) — supervisor,
  facade `Bot` builder, risk primitives, backtest replay engine, KuCoin
  adapter, Discord notifier, kucoin-v2 production-shaped example,
  `JANUS_EXTRACTION_PLAN.md`, doc-coverage pass, `CONTRIBUTING.md`.
- **Build rot cleanup** (#11) — root workspace + janus workspace +
  spawner crate compile cleanly again.
- **Spawner DB persistence + tests + README** (#12) — `BotRunStore`
  writes spawn/stop/remove to `bot_runs`, 10 unit tests, gracefully
  degrades to stateless mode when Postgres is unreachable.
- **`/bots` WebUI route** (#13) — spawn form, container list with
  Stop/Restart/Remove, SSE log viewer, run history, Bots tab in TabBar.
- **WebUI build fixes** (#14) — repaired four files that prevented
  `npm run build` (dual `<script>` blocks, abandoned `$props<{...}>()`).
- **Spawner stack landed on main** (#15) — fast-forward merge that
  brought #12 + #13 onto `main` after the stacked merges left them
  on parent branches only.

> ⚠️  PRs #12 and #13 were merged into their stacked-PR base branches
> rather than `main`. **Always merge stacked PRs into `main` directly,
> or remember to fast-forward main after the parent merges.** Lesson
> for next time.

---

## P0 — Active Infra

### Spawner: real `fks-bot-*` example image
- [ ] Create `crates/example-bot/` (or similar) — minimal Rust crate
      using `rustrade::Bot` with a stub brain that prints heartbeat lines.
- [ ] Expose `fks_bot_pnl_dollars`, `fks_bot_signals_total`,
      `fks_bot_trades_total`, `fks_bot_win_rate`, `fks_bot_uptime_seconds`
      on `:9091/metrics` (the contract documented in
      `infrastructure/config/prometheus/prometheus.yml` for the
      `fks-bots` file_sd job).
- [ ] Build image as `fks-bot-example:latest`. Confirm a spawn from
      `/bots` brings it up, the SSE log stream shows output, and
      Prometheus picks it up via the SD file.

### Spawner: WebUI polish
- [ ] Auto-scroll-to-bottom on `/bots` log viewer when new lines
      arrive AND the user hasn't scrolled up. Pause auto-scroll when
      the user scrolls up; resume when they hit the bottom.
- [ ] Fix `signals/+page.svelte` (and any others) calling `api(url, opts)`
      like a fetch wrapper — it's an object now (`api.get/post/put/delete`).

### Spawner: hardening
- [ ] Add an Axum middleware in `src/spawner/src/api.rs` that validates
      `X-Internal-Token` (set by nginx) and rejects requests without
      it. Skip the check if the env var is empty (dev-mode escape hatch).
- [ ] Introduce a `DockerOps` trait in `src/spawner/src/docker_client.rs`
      so handlers depend on a trait, not the concrete `DockerClient`.
      Unblocks HTTP-level integration tests.

### OpenClaw OOM Fix
- [ ] Debug Node.js OOM in `openclaw-gateway` — needs ~760MB V8 heap;
      investigate dependency bloat or memory leak in Discord client init.
- [ ] Rebuild or replace OpenClaw image when fix is found — current
      workaround: `NODE_OPTIONS=--max-old-space-size=768` + 1.5g limit.

### Tailscale verification
- [ ] Test access from another tailnet device (manual check, needs second device).
- [ ] Verify trainer container GPU passthrough:
      `./run.sh all --profile training` + nvidia-container-toolkit.

---

## P0 — Dockerfile: Build from Source

> Dockerfiles still mostly COPY source code. Migrate them to `git clone`
> at build time so each service can pin a `*_REF` independently.

- [ ] `infrastructure/docker/services/data/Dockerfile` — replace COPY
      with `git clone ${RUBY_REPO:-https://github.com/nuniesmith/ruby} \
      --branch ${RUBY_REF:-main}`.
- [ ] `infrastructure/docker/services/web/Dockerfile` — clone `fks-web`,
      `npm ci && npm run build`.
- [ ] `infrastructure/docker/services/rustcode/Dockerfile` — clone rustcode.
- [ ] `infrastructure/docker/base/rust/Dockerfile` for janus — clone fks-janus.
- [ ] Add `RUBY_REF`, `JANUS_REF`, `WEB_REF`, `RUSTCODE_REF` build args
      to `docker-compose.yml` (default `main`).
- [ ] Document the build args in `.env.example`.

> Reminder: `infrastructure/docker/services/*` is for **external apps**
> (postgres, redis, prometheus, grafana, etc.). Our own services
> (janus, ruby, rustcode, spawner) should use the shared base images
> under `infrastructure/docker/base/{rust,python,nodejs,python-gpu}`.

---

## P1 — RustCode workspace is broken

- [ ] **32 errors** in `crates/rustcode` from incomplete `TaskExecutor` +
      `TaskWatcherConfig` work (the TASK-A through TASK-F items in
      `crates/rustcode/TODO.md`). Decision needed: **finish forward**
      (wire `TaskExecutor` properly into `Config` and `server.rs`) or
      **revert** the half-done scaffold and restart from a clean baseline.
- [ ] Until that resolves, `cd crates/rustcode && cargo check --workspace`
      will not pass. Skipped in CI today.

---

## P1 — Janus extraction (Phase 1 sub-tasks)

> Cheap, decision-free sub-tasks from `JANUS_EXTRACTION_PLAN.md` that
> can land in `fks-full` without needing the still-pending decisions
> on crate naming, regime fate, etc.

- [ ] **1a:** Decouple `crates/janus/crates/data-quality` from
      `janus-core` / `janus-cns` (drop the deps or feature-gate them).
      ~half day. No blockers.
- [ ] **1d:** Port `crates/janus/bin/janus/src/main.rs` from
      `JanusSupervisor` to `rustrade::Bot`, mirroring the kucoin-v2 port.
      ~1 day. Once landed, delete `crates/janus/lib/janus-core/src/supervisor/`
      to prevent drift from `rustrade-supervisor`.

---

## P1 — FUTURES-MERGE: Nginx Routing Update (FMERGE-B)

- [ ] Add futures API proxy to `infrastructure/config/nginx/conf.d/dev.conf`:
      ```
      location /futures-api/ {
          proxy_pass http://fks_ruby:8080/api/;
      }
      ```
- [ ] `infrastructure/docker/services/futures/Dockerfile` — remove
      Jinja2 + template COPY steps (after ruby FMERGE-A is done).
- [ ] Verify `ruby` starts clean in API-only mode:
      `docker compose restart ruby && curl localhost:8080/api/health`.

---

## P1 — Multi-Account: Postgres Schema (ACCT-A)

- [ ] Create and apply `src/sql/ruby/008_accounts.sql`:
  - `exchange_accounts` (id, name, exchange_type, mode, is_active,
    credentials_ref, api_key_hint, timestamps, last_test status)
  - `asset_routing_rules` (id, symbol, account_id, size_pct, priority, is_active)
  - `profit_sweep_config` (id, source_account_id, threshold_usd, mode,
    schedule_time, timestamps)
  - `profit_sweep_targets` (id, sweep_config_id, account_id, allocation_pct)
- [ ] Apply via `./run.sh fix-db`.

## P1 — Multi-Account: Janus Execution Router (ACCT-E)

- [ ] Update `crates/janus/services/execution/` — add `RoutingClient`
      in `execution/src/routing.rs`: HTTP client calling
      `GET http://fks_ruby:8000/api/routing/{symbol}`, 60s cache TTL.
- [ ] On signal: create `ExecutionTarget` per routing rule, fan out
      signal to each target with `account_id` label.
- [ ] Add `ROUTING_API_URL=http://fks_ruby:8000` to janus execution env
      in `docker-compose.yml`.

---

## P1 — Observability

- [ ] **PROM:** Sync Grafana config and restart — ensure all alert
      rules are loaded.
- [ ] Add GPU metrics to Prometheus when trainer is running
      (nvidia-container-toolkit exporter).
- [ ] Alertmanager Discord bridge — container not running, causing
      noise in Alertmanager logs; either fix or remove bridge config.
- [ ] Add `BotStopped`, `BotHighDrawdown`, `BotNoSignals` alert rules
      under `infrastructure/config/prometheus/alerts/bot-alerts.yml`
      once we have at least one real `fks-bot-*` image producing the
      metrics they reference.

---

## P1 — RustCode Deployment

### LLM-D: Wire futures app to RC proxy
- [ ] Add `RC_BASE_URL`, `RC_API_KEY`, `RC_TIMEOUT_SECS`, `RC_MODEL`,
      `RC_REPO_ID` env vars to futures service in `docker-compose.yml`.

### RC-INFRA
- [ ] Set required secrets in `.env`: `DISCORD_BOT_TOKEN`,
      `OPENCLAW_GATEWAY_TOKEN`, `RC_PROXY_API_KEYS`, `TAILSCALE_IP`.
- [ ] Re-enable CI/CD — move `.github/disabled/ci-cd.yml` back to
      `.github/workflows/` after OpenClaw OOM fix + Tailscale
      second-device check.
- [ ] Fix GPU / restore Ollama CUDA passthrough (optional — only if
      using Ollama): `sudo dmesg | grep -i nvidia`, reinstall
      `nvidia-container-toolkit`, re-run `nvidia-smi`.

---

## P1 — Spawner follow-ups (lower priority)

- [ ] Bot config templates UI — the `bot_configs` table is sitting
      unused. Add a preset library in `/bots` that fills the spawn
      form from a saved row.
- [ ] **bollard 0.19 deprecation migration** — `bollard::container::*Options`
      are deprecated in favour of `bollard::query_parameters::*Options`
      builders. The current code uses `#![allow(deprecated)]` in
      `src/spawner/src/docker_client.rs`. ~half day of mechanical work.
- [ ] Mobile / narrow-screen layout polish for `/bots` (current grid
      assumes desktop terminal usage, matching the rest of the WebUI).
- [ ] Persistent log capture — when a container is pruned, its logs
      vanish. Decide if Loki/Promtail (already running) is enough or
      if we need spawner-side capture.

---

## P1 — Proto (fks-proto shared crate)

- [ ] Centralize stray `forward/proto/janus/v1/janus.proto` →
      `proto/fks/janus/v1/signal_service.proto` — deferred until gRPC
      endpoint is actually needed.

---

## P2 — CI/CD & Image Persistence

- [ ] Re-enable ARM64 / multi-arch builds in CI (disabled in batch-013).
- [ ] `docker push nuniesmith/fks:janus` — publish Janus image for
      faster deploys.
- [ ] `docker push nuniesmith/fks:spawner` — same.
- [ ] Postgres data migration (optional): use `pgloader` if dev data
      worth preserving across rebuilds.
- [ ] Add `npm run check` to CI as a non-blocking gate, then promote
      to blocking once the existing 29 type errors are cleaned up
      (so the dual-script bug from PR #14 doesn't recur).

---

## P2 — Feature Work

### PAPER-TRADING: Live Validation
- [ ] Test Redis state persistence: `sim:session:{id}:*` keys
      written/readable.
- [ ] Verify SSE streaming: `/sse/paper-trading/{id}` streams to WebUI.

### PINE-INT: Manual Verification
- [ ] Paste generated `ruby.pine` into TradingView Pine editor,
      confirm it compiles.

### CRITICAL-FIX-A: Rithmic (remaining)
- [ ] Live test — verify positions, L1/L2, PnL match dashboard against
      Rithmic paper account (needs credentials).
- [ ] Margin usage field — depends on Rithmic margin data availability.

---

## P3 — Future (Post-Funding)

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
- [ ] **Phase 2 of janus extraction** — publish public sibling crates
      from `JANUS_EXTRACTION_PLAN.md` (rate-limiter-ta, gap-detection-ta,
      dsp-ta, lob-sim, etc.). Needs decisions on crate naming + repo
      strategy first.
- [ ] **Phase 3 of janus extraction** — move private brain IP
      (strategies, compliance, neuromorphic) to a private repo that
      depends on the published siblings.
