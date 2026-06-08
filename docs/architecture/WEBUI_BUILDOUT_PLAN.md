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
- [ ] **A2** Trim `$lib/api` + `$lib/types` of now-unused clients/types; drive
  `npm run check` toward clean (most of the 29 pre-existing warnings lived in the
  deleted dirs).
- [ ] **A3** Add a dedicated prod `/api/spawner/` SSE block (+ `@spawner_unavailable`)
  to `fkstrading.xyz.conf` so `/bots` log-tail streams over nginx.
- *Done = no dead nav/URLs of value, `npm run check` near-clean, prod log streaming.*

### Phase B — Solidify the keyless crypto data path  *(verify janus / webui)*
- [ ] **B1** Verify janus writes Binance candles → `candles_crypto` (which symbols,
  which intervals); confirm `/bars/:sym/candles` returns real bars end-to-end.
- [x] **B2** **Symbol catalog**: adapter endpoints over QuestDB —
  `/api/assets/search?q=` (`SELECT DISTINCT symbol …`) powers the chart's symbol
  search with real symbols; `/api/assets/:short` maps the stored exchange →
  `source`/`source_chain` so the page picks the right live-data path.
- [ ] **B3** Interval coverage: ensure 1m/5m/15m/1h/4h/1D exist, or resample higher
  TFs from 1m in the adapter.
- *Done = charts show live Binance data for the available symbols; search works.*

### Phase C — Indicators everywhere  *(webui adapter + charts UI)*
- [x] **C1** TS indicators module (`$lib/server/indicators.ts`) computed from QuestDB
  candles, wired to `/api/chart/:sym/indicators` — lights up the existing
  BB/RSI/MACD/ATR chart toggles server-side. Ships EMA/SMA/RSI/MACD/BBands/ATR/VWAP
  + an `INDICATOR_CATALOG` for the picker. *(Follow-up: WMA, Stochastic, ADX, OBV,
  Keltner, Donchian + per-indicator params.)*
- [ ] **C2** Charts **indicator catalog UI**: searchable list, per-indicator toggle,
  parameter controls (period, stddev, fast/slow/signal…), overlay-vs-subpane.
- [ ] **C3** Indicator presets + persistence (per symbol/timeframe).
- *Done = full indicator set renders, parameterized, aligned to candles.*

### Phase D — Charting polish  *(webui)*
- [ ] **D1** Harden live updates: client Binance/Kraken WS (reconnect/backoff,
  multi-symbol) + an adapter `/sse/bars/:sym` bridge for futures.
- [ ] **D2** Crosshair OHLCV readout, multi-pane time-scale sync, volume pane,
  timeframe/symbol from URL + persistence, drawing tools.
- *Done = smooth live chart with indicators, clean reconnects, no console errors.*

### Phase E — API key management (secure, server-side)  *(webui + spawner/janus)*  — **decision needed**
- [ ] **E1** Settings form → POST key/secret to a server endpoint → persisted
  server-side (never returned to browser; masked input). Default keyless.
- [ ] **E2** Connection-status badge (public vs authenticated); wire `exchange-apiws`
  authenticated calls (account/balance) behind it.
- [ ] **E3** Update `src/web/CLAUDE.md` policy note to reflect server-side storage.
- **Decision:** storage target — gitignored `.env` via a spawner endpoint, or a
  janus secret config? Keys enable the live order path → stays behind the gate.

### Phase F — Bot spawner deepening  *(webui + spawner)*
- [ ] **F1** Richer `/bots`: presets (crypto-demo / exchange-apiws bot), config
  editor, per-bot Prometheus metrics, clearer lifecycle/status.
- [ ] **F2** Spawn a paper crypto bot end-to-end from the UI on the keyless path.

### Phase G — Robustness & finish
- [ ] **G1** `/settings` risk-config **write** aligned to janus's real schema
  (`max_daily_loss≤0`, `max_positions`, `max_gross_exposure_usd`,
  `daily_loss_limit_pct`) + a GET to load current limits.
- [ ] **G2** Error / empty / loading-state audit across every panel.
- [ ] **G3** Playwright E2E for the wired pages.
- [ ] **G4** Final nginx comment cleanup; refresh docs; remove remaining dead surface.

---

## Open decisions
1. **A1:** `journal` + `db` kept for now — delete them too, or keep for a janus rebuild?
2. **E:** API-key storage target + confirmation that the browser only submits (never holds) secrets.

## Cross-repo note
Most tasks live in **this repo** (`src/web` + the adapter + nginx). Items touching
janus's own ingestion/indicators internals are **janus-repo** work (external) and
are flagged where they arise; the adapter shields the UI from that boundary.
