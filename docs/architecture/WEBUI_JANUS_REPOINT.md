# WebUI → janus repoint (RUST_MIGRATION §12-C)

> **Status:** Plan / in progress — 2026-06-07
> **Why:** the SvelteKit dashboard (`src/web/`) was built against the Python
> "Ruby" data API. Ruby was removed, so every data panel 404s. This is the plan
> to repoint the dashboard onto janus's real API (and drop the Ruby-only panels).

## The gap (from a two-sided endpoint audit)

- **WebUI calls ~130 endpoints**, all as **same-origin relative URLs**
  (`/api/*`, `/sse/*`, `/bars/*`, `/factory/*`, `/kraken/*`), resolved by a proxy:
  Vite `server.proxy` in dev and nginx in prod — both targeting `fks_ruby:8000`
  (gone). `hooks.server.ts` does **not** proxy; it only does auth/session.
  `/api/spawner/*` → `fks_bot_spawner:8090` (this one still works).
- **janus serves ~90 endpoints** but in a **different shape**:
  - janus-api (`fks_janus:8080` → host 7000): `/`, `/health`, `/status`,
    `/api/dashboard/{overview,performance,signals/summary}`, `/api/signals/*`
    (latest/publish/summary/categories/generate/by-id/by-symbol),
    `/api/modules/health`, `/api/services/{status,start,stop}`,
    `/api/v1/positions/{event,close}`, `/api/log-level`, `/metrics`.
  - forward (`fks_janus:8180` → host 7001): `/api/v1/{health,version}`,
    `/api/v1/signals/{generate,batch}`, `/api/v1/risk/*`
    (config/portfolio/metrics/performance/validate/calculate-*), `/api/v1/account`,
    `/api/v1/brain/{health,pipeline,affinity,kill-switch/*}`.
  - data (integrated): `/api/v1/gaps`, `/api/v1/indicators/*`, `/api/v1/signals/*`,
    `WS /ws/stream`, `WS /ws/signals`.

**Almost no path overlaps.** The dashboard's `/api/trades`, `/api/journal`,
`/factory/*`, `/api/db/*`, `/api/grok/*`, `/api/chain/*`, `/api/crypto/*`,
`/api/paper-trading/*`, `/api/cnn/*`, `/fapi/*` have **no janus equivalent** —
they were Ruby features (data factory, journal, on-chain, news, DB explorer,
grok, paper-trading, futures task runner). What janus *can* feed: status,
service control, signals, brain/pipeline health, risk/portfolio, affinity,
indicators, metrics.

> ⚠️ **Networking detail:** the SvelteKit server (in the `webui` container) must
> call janus over the Docker network at **`http://fks_janus:8080`** (api) and
> **`http://fks_janus:8180`** (forward) — *not* `:7000/:7001`, which are the
> host-published ports. (`PUBLIC_API_URL` was set to `:7000`; the adapter uses
> the in-container `:8080`.)

## Approach: trim + a thin SvelteKit→janus adapter (path B)

Rather than reproduce Ruby's whole API in janus (path A — large, and much of it
is dead-feature surface), **keep the dashboard, add a server-side adapter, and
drop the Ruby-only panels.** The adapter lives in the SvelteKit server
(`adapter-node`), so the existing same-origin `/api/*` calls keep working:

- **`src/routes/api/[...]/+server.ts`** (or per-area `+server.ts`): map the
  *repoint* endpoints to janus/forward/spawner and reshape JSON to what each
  panel expects; for *drop* endpoints return a graceful `200 {}`/`[]` (no console
  404 spam) with an `x-fks-unmapped` header.
- SSE (`/sse/*`) → either bridge to janus `WS /ws/*` server-side, or disable the
  live-stream panels in Phase 1 (poll instead).

## Keep / Repoint / Drop matrix (per page)

| Page | Decision | janus source(s) |
|---|---|---|
| `/` overview | **Repoint** | `/status`, `/api/dashboard/overview`, `/api/signals/latest`, `/api/services/status` |
| `/bots` | **Keep (works)** | spawner `/api/spawner/*` |
| `/signals` | **Repoint** | `/api/signals/{latest,summary,categories}`; approve/reject → drop (no staging workflow in janus) |
| `/janus-ai` | **Repoint** | `/status` (state), forward `/api/v1/brain/{health,affinity}`; memories/AI-sessions → drop |
| `/performance` | **Repoint** | forward `/api/v1/risk/performance`, `/api/dashboard/performance` |
| `/monitoring` | **Repoint** | proxy Prometheus (`fks_prometheus:9090`) directly; or embed Grafana |
| `/settings` (risk) | **Repoint (partial)** | forward `/api/v1/risk/config` (GET/PUT); data-source/kraken/rithmic → drop |
| `/charts`, `/trading` (bars) | **Repoint (needs work)** | OHLC from QuestDB — needs a small janus (or adapter→QuestDB) candles endpoint; indicators → data `/api/v1/indicators/*` |
| `/analysis` | **Mostly drop** | `cnn/regime` → janus burn ML (gated, later); correlation/scanner/rotation/checklist/grok → drop |
| `/journal` | **Drop** | (Ruby journal — could rebuild on janus positions later) |
| `/data` (factory) | **Drop** | (Ruby data factory; `/api/v1/gaps` exists if wanted) |
| `/db` (explorer) | **Drop** | (Ruby DB explorer — niche dev tool) |
| `/crypto`, `/simulations`, `/chains`, `/backup`, `/news`, `/backtesting`, `/tasks` | **Drop** | (Ruby-only features) |

## Phased plan

- **Phase 1 (foundation):** adapter scaffolding + kill the 404 spam (graceful
  empty for unmapped) + make **`/` overview** janus-native (status, signals,
  services, module health). Hide/disable the dropped pages in the nav.
- **Phase 2:** repoint `/signals`, `/janus-ai`, `/performance`, `/settings(risk)`,
  `/monitoring` (Prometheus proxy).
- **Phase 3:** candles/`/charts` (QuestDB OHLC endpoint) + indicators; optional
  live SSE via janus `/ws/*` bridge.
- **Phase 4:** remove the dropped pages/components + the dead `vite.config.ts`
  proxies + the Ruby-era nginx routes; trim `$lib/api`.

## Progress (as built)

The adapter lives in `src/web/src/hooks.server.ts` (the strangler seam). Landed:

- **#79 — Phase 1:** server proxy in `hooks.server.ts`; `/api/spawner/*` → spawner;
  unmapped backend paths degrade quietly (empty REST / idle SSE) → kills the 404 spam.
- **#80 — Phase 2a:** status bar live (`/api/health` ← janus `/health`) + favicon + SSE keepalive.
- **#81 — Phase 2b:** signals wired — overview "recent signals"
  (`/api/db/redis/get/fks:memories:new`) and the `/signals` page (`/api/signals`)
  ← janus `/api/dashboard/signals/summary`. Approve/reject stay no-ops.
- **#82 — Phase 2c:** `/janus-ai` brain panels — `/api/janus/state` ← forward
  `/api/v1/brain/health` (status) + recent signals; `/api/janus/affinity` ←
  forward `/api/v1/brain/affinity`. Live-signals tab already rides the #81 mapping.
  *Deferred/dropped:* per-symbol `regime` (no janus feed wired yet → empty),
  `sessions`/`memories` (no janus equivalent → graceful empty).
- **Phase 2d:** `/monitoring` ← Prometheus (`fks_prometheus:9090`). `/api/metrics/`
  `{query,query_range,targets}` are straight pass-throughs (identical shapes);
  `/api/metrics/alerts` reshapes `/api/v1/alerts` (+ derived `age_str`);
  `/api/metrics/layout` ships a small default of synthetic-metric panels
  (`up`, `scrape_duration_seconds`) since Ruby's layout service is gone.
  *Caveat:* the page's hardcoded **CPU%/Memory%** health stats query `node_*`
  metrics — the active `prometheus.yml` has no node-exporter, so those read "—"
  until one is scraped (Targets/Alerts/PromQL/Redis-ops are live now).

Remaining: `/performance` + `/settings` (risk) — both ← forward `/api/v1/risk/*`,
which is empty in the paper demo (correct shapes, no data until a live order path);
then candles/`/charts` (Phase 3), then the Phase 4 cleanup.

## Notes
- nginx `conf.d/*.conf` still routes `/api/*`/`/factory/*`/`/trading*` at
  `fks_ruby` — to be rewritten in Phase 4 (janus + spawner + monitoring only).
- The adapter is the strangler seam: it lets us repoint panel-by-panel without a
  big-bang dashboard rewrite, and degrades cleanly while panels are unmapped.
