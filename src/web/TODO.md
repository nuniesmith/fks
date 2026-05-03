# fks-web — TODO

> **Repo:** `github.com/nuniesmith/fks-web`
> **Last synced from master todo:** 2026-04-03

---

## P0 — Visual QA (WEBUI-B)

- [ ] Test all workspaces at 1920×1080 and 1440×900
- [ ] Verify strip cells update independently
- [ ] Verify SSE reconnect + toast notifications
- [ ] Verify responsive collapse at 1024px breakpoint
- [ ] Verify redirects: `/dom`, `/posint`, `/paper-trading`, `/trainer` → terminal tabs
- [ ] Verify standalone routes: `/dom/standalone`, `/posint/standalone`, `/paper-trading/standalone`, `/trainer/standalone`
- [ ] End-to-end browser test — dashboard loads, API responds, SSE streams, paper trading works

---

## P1 — New Workspaces

### SVK-18: Futures Workspace — `/futures`
> Depends on FMERGE-A/B/C (Ruby + nginx side done first)

- [ ] **SVK-18a:** Left pane — worker cards panel (5s poll): `GET /api/workers/status`, state badge, action buttons (Start/Stop/Restart)
- [ ] **SVK-18b:** Left pane — live signals feed (3s poll): `GET /api/signals/recent`, direction badge, CNN risk score color-coded
- [ ] **SVK-18c:** Right pane — PnL summary (10s poll): `GET /api/pnl/summary`, StatCard grid, per-asset breakdown, CSV export
- [ ] **SVK-18d:** Right pane — CNN risk status (15s poll): `GET /api/cnn/status`, risk gauge arc (0–1), per-asset signal cards
- [ ] **SVK-18e:** Right pane — trade history (30s poll): `GET /api/trades/history`, color-coded P&L, fee breakdown on expand
- [ ] **SVK-18f:** Grok AI reports tab: day/week/month tabs, `GET /api/reports/{period}`, regenerate button with spinner
- [ ] Add `/futures` to TabBar under **Trading** group

### SVK-19: Bot Manager — `/bots`
> Depends on SPAWN-A/B/C in fks repo

- [ ] **SVK-19a:** Header + sidebar — bot list (10s poll), accent border on selected
- [ ] **SVK-19b:** New Bot modal wizard — 5-step form: Identity → Assets → Accounts → Modules → Resources
- [ ] **SVK-19c:** Detail pane — metrics panel (5s poll): `GET /api/bots/{id}/metrics`, 6 StatCard grid
- [ ] **SVK-19d:** Detail pane — live log stream: SSE `EventSource` to `/api/bots/{id}/logs/stream`, log level filter chips
- [ ] **SVK-19e:** Detail pane — module pipeline visualizer: horizontal flow diagram, latency badges
- [ ] **SVK-19f:** Detail pane — sim→live promotion (only when SIM bot ≥7 days runtime)
- [ ] **SVK-19g:** Bot actions toolbar: Start/Stop/Restart/Delete/Clone
- [ ] Add `/bots` to TabBar under **Trading** group

### SVK-20: Accounts Workspace — `/accounts`
> Depends on ACCT-A/B/C in fks-ruby

- [ ] **SVK-20a:** Left pane — account list (30s poll): exchange type badge, mode badge, credential masking, Add Account form
- [ ] **SVK-20b:** Left pane — test connection per account
- [ ] **SVK-20c:** Right pane — account detail: balance snapshot, activate/deactivate toggle
- [ ] **SVK-20d:** Right pane — asset routing table: editable rows, drag-to-reorder, Preview button
- [ ] **SVK-20e:** Right pane — profit sweep config panel: source account, threshold, targets with allocation %
- [ ] Add `/accounts` to TabBar under **System** group

### SVK-21: Module Browser — `/modules`
> Depends on MOD-A/B/C in fks-ruby

- [ ] **SVK-21a:** Left sidebar — module registry browser: category filter chips, module list, search input
- [ ] **SVK-21b:** Right pane — module manifest panel: ID/version/category, supported types/timeframes, JSON Schema config viewer
- [ ] **SVK-21c:** Right pane — module test runner: symbol/TF/date selector, config editor, run button, result display
- [ ] **SVK-21d:** Right pane — module pipeline builder (bonus): drag-and-drop chain, save as named pipeline
- [ ] **SVK-21e:** Right pane — module health panel (60s poll): all loaded modules with latency + error counts
- [ ] Add `/modules` to TabBar under **System** (or Analysis)

---

## P1 — SVK-22: Analysis Route Split

> `src/routes/analysis/+page.svelte` is ~66k lines — split into sub-routes.

- [ ] **SVK-22a:** Audit current page — map 5 inner-tab sections (Briefing, Correlation, Scanner, Checklist, Rotation + Labs)
- [ ] **SVK-22b:** Create sub-routes: `/analysis` (hub), `/analysis/technical`, `/analysis/correlation`, `/analysis/scanner`, `/analysis/sentiment`, `/analysis/chain`
- [ ] **SVK-22c:** Add inner-nav (horizontal pill tabs) to `/analysis` landing
- [ ] **SVK-22d:** Update TabBar — `/analysis` stays as Shift+1, sub-routes via in-page nav

---

## P1 — Charting Enhancements

- [ ] **SVK-15b:** Binance WS integration — `@kline_1m` streams (public, no auth) — Kraken downtime fallback
- [ ] **SVK-15c:** Bybit WS integration — `kline.1.{symbol}` for Bybit-listed assets
- [ ] **SVK-15d:** Multi-chart grid layout (2×1, 2×2 configurable)
- [ ] **SVK-15e:** Drawing tools — trendline, horizontal line, fib retracement (DrawingTools.svelte exists, wire into charts page)
- [ ] Quick-pick configurable from registry categories (currently hardcoded buttons)

---

## P1 — Trading Workspace Enhancements

- [ ] Display Janus guidance in Trading workspace: take-profit/stop-adjust suggestions (JFLOW-C from fks-janus)
- [ ] Impeccable UI audit: `/audit dashboard` on Overview + Trading pages

---

## P2 — Misc Remaining

- [ ] Tab group collapse/expand for small screens
- [ ] SVK-4d remaining: symbol selector disabled-while-connected UX polish
- [ ] `/factory/status/json` endpoint audit — if only HTML variant exists, add JSON version
- [ ] Audit remaining endpoint JSON responses needed for any workspace
- [ ] Journal replay — trade replay with entry/exit chart markers
- [ ] DOM / Positions / Paper Trading: native Svelte rebuild (replace iframes, lower priority)
- [ ] OSS-C: Impeccable — run `/harden checkout` on Trading order entry form; `/normalize` on Charts and Analysis pages

---

## Completed (reference)

- ✅ SVK-1 through SVK-17 (all 19 workspaces, all components, all stores)
- ✅ Panel.svelte refactor (header snippet, badge, noPad, fill) + full migration across 14 pages
- ✅ All 20 pages with per-page `<title>` tags
- ✅ Playwright E2E rebuilt — 55 tests across 6 describe blocks
- ✅ News: Live SSE push (SVK-4d partial — raw EventSource, connection dot, flash animation)
- ✅ DB Explorer: Janus tab + lazy tab loading
- ✅ StatusBar reactive dots, clock, error boundary, EmbedPage component
- ✅ DRY refactor: shared types, format utils, Panel usage
