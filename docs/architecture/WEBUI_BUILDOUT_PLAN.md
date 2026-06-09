# WebUI Buildout Plan

> **Status:** active — 2026-06-08
> **Predecessor:** [`WEBUI_JANUS_REPOINT.md`](WEBUI_JANUS_REPOINT.md) (the migration
> that repaired the dashboard). That work is **done**: every data-bearing page is
> janus / Prometheus / QuestDB-backed via the `src/web/src/hooks.server.ts` adapter,
> and both nginx confs route through `fks_webui`.
> **This doc:** the forward plan to make the WebUI a *complete, robust* front end —
> connected to everything, all indicators available, charting polished, optional
> exchange API-key entry, keyless public crypto data for testing.

## Grounding facts (verified in-tree)

- **Keyless public data is the default.** janus ingests **Binance public WS**
  (`DATA_SOURCE=live`, `DATA_EXCHANGE=binance`,
  `DATA_WS_URL=wss://stream.binance.com:9443/ws`) → QuestDB `candles_crypto`
  (`ts, symbol, exchange, interval, open, high, low, close, volume`).
  `ENABLE_EXECUTION=false`. So no API keys are needed for charts/indicators —
  keys only unlock the **authenticated/live order path** (`exchange-apiws`),
  which stays behind the manual execution gate.
- **Indicators math = `indicators-ta`** (crates.io, imported as `indicators`).
  Today it's used only inside `bots/crypto-demo` (Rust: `EMA`, `ATR`, `RSI`).
  There is **no HTTP indicators endpoint** yet.
- **The adapter is the seam.** `hooks.server.ts` already proxies/reshapes
  `/api/*`, `/sse/*`, `/bars/*` and queries QuestDB directly (the candles
  endpoint). It runs in Node, so it can also *compute* over candles.
- **webui API clients:** only `$lib/api/client.ts` + `spawner.ts` exist today.

## Architecture decisions

1. **Indicators are computed in the adapter (TS), from QuestDB candles.**
   Rationale: keeps everything in this repo (no janus-external dependency),
   server-computed (one source of truth, cacheable), and the adapter already has
   the candles. `GET /api/chart/:sym/indicators?interval=&indicators=rsi,macd,...`
   returns `{ indicators: { rsi: [{time,value}], macd_line: [...], ... } }`
   aligned to candle timestamps. *(Parity option later: back these with janus +
   `indicators-ta` for canonical math.)*
2. **API keys are stored server-side; the browser only submits them.** The
   settings form POSTs key/secret to a server endpoint that persists them
   server-side (gitignored `.env` / secret store) for `exchange-apiws`; the key
   is never returned to or held by the browser (masked input, Tailscale HTTPS).
   This is compatible with the "no browser-credential handling" policy *if* the
   browser never stores/uses the secret. **Default = keyless/public.**
3. **Strangler discipline continues:** small, reviewable PRs; the adapter stays
   the single backend seam; pages degrade gracefully while a feature is unmapped.

---

## Phases

### Phase A — Foundation & cleanup  *(webui)*
- [x] **A1** Delete the de-navved Ruby route dirs (`analysis, assets, backtesting,
  backup, chains, cnn, crypto, data, dom, logging, news, paper, pnl, positions,
  reporting, simulations, tasks, trades`). Kept `journal` + `db` (URL-only) for a
  possible later janus rebuild.
- [x] **A2** `$lib` trim — **no-op**: `$lib` is already lean (`api/{client,spawner}`,
  `types/{index,spawner}`, `stores/{focusSymbol,poll,sse,strip}`, all in active
  use). The pruned routes held their types inline, so nothing was orphaned.
- [x] **A3** Added a dedicated prod `/api/spawner/` block to `fkstrading.xyz.conf`
  (→ `fks_bot_spawner:8090`, unbuffered) so `/bots` log-tail streams over nginx
  instead of buffering through the `/api/` adapter route. *(Verify with `nginx -t`.)*
- *Done = no dead nav/URLs of value, `npm run check` near-clean, prod log streaming.*

### Phase B — Solidify the keyless crypto data path  *(verify janus / webui)*
- [ ] **B1** Verify janus writes Binance candles → `candles_crypto` (which symbols,
  which intervals); confirm `/bars/:sym/candles` returns real bars end-to-end.
- [x] **B2** **Symbol catalog**: adapter endpoints over QuestDB —
  `/api/assets/search?q=` (`SELECT DISTINCT symbol …`) powers the chart's symbol
  search with real symbols; `/api/assets/:short` maps the stored exchange →
  `source`/`source_chain` so the page picks the right live-data path.
- [x] **B3** Interval coverage: the candles adapter now **resamples from 1m** when
  an interval isn't stored natively — if the direct `interval = '<tf>'` query is
  empty, it fetches 1m bars and aggregates them into the requested bucket
  (`resampleCandles` / `intervalToSeconds`, unit-tested). Fires only on the
  otherwise-"no data" path, so it can't change a populated chart. *(Which
  intervals janus stores natively is still a live-stack check — B1.)*
- *Done = charts show live Binance data for the available symbols; search works.*

### Phase C — Indicators everywhere  *(webui adapter + charts UI)*
- [x] **C1** TS indicators module (`$lib/server/indicators.ts`) computed from QuestDB
  candles, wired to `/api/chart/:sym/indicators` — lights up the existing
  BB/RSI/MACD/ATR chart toggles server-side.
- [x] **C1b** Expanded the engine: EMA/SMA/**WMA**/RSI/MACD/BBands/ATR/VWAP +
  **Stochastic, Williams %R, CCI, OBV, Donchian, Keltner** (`ema<N>`/`sma<N>`/`wma<N>`
  accept any period) + **ADX (+DI/−DI)**. Serves the metadata at
  **`GET /api/indicators/catalog`** (`INDICATOR_CATALOG`) for the picker.
  *(Follow-up: per-indicator params.)*
- [x] **C2** Charts indicator UI. **Overlay toggles** for SMA/VWAP/WMA/Donchian/
  Keltner (BB/ATR pattern), **plus a catalog-driven picker** (`+ IND`) that adds
  any **oscillator sub-pane** from `/api/indicators/catalog` — Stoch/Williams %R/
  CCI/OBV/ADX — via a generic `IndicatorPane.svelte` (own chart instance, synced
  to the main chart, removable, self-cleaning). *(Follow-up: per-indicator params
  + fold RSI/MACD into the same generic pane.)*
- [x] **C3** Indicator **presets + layout persistence**. The active indicator
  set (all overlay/sub-pane toggles + oscillator panes) now survives a full page
  reload via `localStorage` (`fks_chart_indicators`), restored on mount after the
  chart + catalog load. Plus a **☰ Presets** menu (Clean / Trend / Bands /
  Momentum / Volume / Full) that one-click reconciles the chart to a named layout
  via `applyIndicatorState`. *(Persistence is global/last-layout — the more
  standard UX — rather than per-symbol; per-indicator params remain a follow-up.)*
- *Done = full indicator set renders, parameterized, aligned to candles.*

### Phase D — Charting polish  *(webui)*
- [~] **D1** Harden live updates. **Client crypto WS is done** — the chart runs
  Kraken→Binance with reconnect + exponential backoff (and a per-chart WS in the
  grid). The **adapter `/sse/bars/:sym` futures bridge** is now wired but
  **env-gated**: empty `JANUS_BARS_SSE_URL` keeps today's graceful idle stub
  (no behaviour change); set it to a janus SSE base and the upstream is piped
  straight through (`event: bar` frames). *(Activating it is janus-side work —
  janus doesn't expose a bars stream yet; the bridge is ready for when it does.)*
- [x] **D2** Charts polish: **symbol/timeframe persistence** (localStorage),
  **crosshair OHLC readout** (hover → bar O/H/L/C + change%), **shareable URLs**
  (`?symbol=&tf=` — URL wins over localStorage, synced via `replaceState`), and a
  **log/linear price-scale toggle**. (Drawing tools already shipped via
  `DrawingTools`.) *(Optional later: dedicated volume pane.)*
- *Done = smooth live chart with indicators, clean reconnects, no console errors.*

### Phase E — API key management (secure, server-side)  *(webui + spawner)*  — **decision made: spawner → Postgres**
- [x] **E1** Settings form → `POST /api/settings/kraken-keys {api_key, api_secret}`
  → adapter forwards to the spawner's **`POST /secrets`**, which UPSERTs into
  `ruby_db.exchange_secrets` (new `003_secrets.sql`, gated on the spawner `db`
  feature, behind `X-Internal-Token`). The write is **awaited** (honest save, no
  fake "Saved ✓"); inputs are masked (`type="password"`) and **cleared on save**
  so the browser submits then forgets. The secret is never returned.
- [x] **E2** Connection-status badge: `/api/settings/kraken-status` → spawner
  **`GET /secrets/status`** (reports only *which* exchanges are configured, never
  the keys). The Kraken block shows "API keys stored — authenticated path
  available" vs "No keys — using public/keyless data". *(Follow-up: wire
  `exchange-apiws` authenticated account/balance calls behind the badge.)*
- [x] **E3** `src/web/CLAUDE.md` policy note updated to document submit-only
  server-side storage.
- **Decision (made):** storage target = the **spawner's Postgres `ruby_db`**
  (reuses the existing pool/`BotRunStore`; no new service). Plaintext-at-rest for
  now — internal/Tailscale-only; pgcrypto column encryption is a tracked
  follow-up. Keys enable the live order path → stays behind the execution gate.

### Phase F — Bot spawner deepening  *(webui + spawner)*
- [~] **F1** `/bots` **spawn presets** done: one-click pre-fill of the spawn form
  with the verified `crypto-demo` config (image `fks-bot-crypto-demo:latest`,
  paper/synthetic/mock, janus-brain & local-ema-cross variants — exact compose
  env, no keys). Editable before submit. **Per-bot live metrics** done too: the
  spawner now enriches the `/containers` listing with real **CPU% + memory** from
  the Docker stats API (concurrent, timeout-bounded; `/health` stays cheap), so
  the `/bots` resource cells — already wired in the UI — light up. **Persisted
  spawn configs** done too: the spawner exposes `GET`/`POST /configs` +
  `DELETE /configs/{name}` (backed by the long-dormant `bot_configs` table), and
  `/bots` now has a **Saved** row — save the current form as a named config,
  one-click apply, delete — alongside the built-in presets. **Lifecycle/status**
  clearer too: each running container shows live **uptime** (↑ from start time,
  refreshed on the 3s poll) and **memory used / limit** (the spawner now carries
  `memory_limit_bytes` alongside the usage stat). F1 done.
- [~] **F2** Spawn a paper crypto bot end-to-end from the UI on the keyless path.
  Delivered the **runbook + automated smoke test** that encode the exact path
  (`scripts/testing/F2-KEYLESS-SPAWN-RUNBOOK.md` + `f2-keyless-spawn-smoke.sh`):
  spawner `POST /spawn` (crypto-demo · paper · synthetic · mock) → janus brain over
  HTTP → MockExchange (no keys, no real orders), with a **paper-safety assertion**
  that the logs never show a live-order path. *(The actual run is a live-stack
  check — no Docker daemon in the CI sandbox; the script is the repeatable proof.)*

### Phase G — Robustness & finish
- [x] **G1** `/settings` risk panel **now actually saves** (was a fake "Saved ✓"
  no-op). Restructured to the rustrade `PortfolioRiskConfig` shape — **Max Daily
  Loss ($) · Max Positions · Max Gross Exposure ($)** — with `GET /api/settings/risk`
  ← forward `/api/v1/risk/config` (load current) and `POST` → real **PUT** with
  `{ max_daily_loss: -usd, max_concurrent_positions, max_gross_exposure }`. Honest
  failure surfaced (502) instead of a fake success. *(If janus's actual contract
  differs, the GET reveals it and the adapter mapping is a one-line tweak.)*
- [x] **G2** Error / empty / loading-state audit. Added a reusable **`EmptyState`**
  primitive (`$components/ui/EmptyState.svelte`, with an optional `action` snippet
  for a CTA button) and adopted it across every panel-level empty/error state:
  **charts** (no-data vs. fetch-error overlay), **signals**, **performance**,
  **janus-ai** (regime/affinity/sessions — the "No sessions" case keeps its
  *Create Session* button via the action snippet — live-signals/memories), and the
  **overview** (briefing/trades/factory/signals). Each shows a consistent icon +
  title + hint, error-tinted on failures; the old `.empty*` / `.err*` / `.error-*`
  CSS is pruned. *(Monitoring's compact inline cell placeholders are intentionally
  left — `EmptyState` is panel-sized.)*
- [~] **G3** Playwright E2E. The suite existed but had gone **stale against the
  Phase-A1 deletions** — `smoke.spec.ts` + `workspaces.spec.ts` tested removed
  routes (`analysis`/`news`/`data`/`chains`/`crypto`/`simulations`/`dom`/`paper`/
  `positions`) and the wrong keyboard map, so it would have failed wholesale.
  Reconciled to the **actual** routes + nav (titles verified from source; `5`→
  `/performance`, `⇧1`→`/docs` per TabBar; nav click → Janus AI), added the wired
  janus pages, and gave `/bots` the `<title>` it was missing. `playwright test
  --list` enumerates 84 tests clean. *(Full run needs the dev/preview server +
  browsers, which the CI sandbox can't download — runs via `paper-trading-test`.)*
- [ ] **G4** Final nginx comment cleanup; refresh docs; remove remaining dead surface.

---

## Open decisions
1. **A1:** `journal` + `db` kept for now — delete them too, or keep for a janus rebuild?
2. **E:** API-key storage target + confirmation that the browser only submits (never holds) secrets.

## Cross-repo note
Most tasks live in **this repo** (`src/web` + the adapter + nginx). Items touching
janus's own ingestion/indicators internals are **janus-repo** work (external) and
are flagged where they arise; the adapter shields the UI from that boundary.
