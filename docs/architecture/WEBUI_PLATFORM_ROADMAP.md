# WebUI Platform Roadmap — from dashboard to trading platform

> **Status: design doc.** Nothing in the "target" sections is implemented
> unless the ground-truth section says so. This designs the evolution of the
> FKS WebUI (and the janus/spawner surfaces that feed it) from a fixed
> route-per-page dashboard into a real trading platform: dockable panel
> layouts, a multi-source data platform (news, non-crypto assets, Rithmic),
> the crypto-bot / net-worth backbone, credential-driven feature gating, and
> TradingView-parity charts with Rust indicator auto-discovery.
>
> Grounded in a read-only survey (2026-07-06) of `fks-web` (shell, charts,
> settings, `hooks.server.ts` adapter), `janus` (`services/data`, unified
> binary, workspace deps), `indicators-ta` (registry), `crates/spawner`
> (secret store), the then-extant `crypto` repo (Dockerfile,
> `FKS-INTEGRATION.md` — since **dissolved**: spot → this repo's
> `bots/spot-portfolio` + `crates/crypto-bot-core`, futures/funding edges →
> the private `fks-state` repo's `bots/crypto-futures`), and
> the live Docker host. Companion docs:
> [`PLATFORM_ARCHITECTURE.md`](PLATFORM_ARCHITECTURE.md) (the platform map),
> [`WEBUI_BUILDOUT_PLAN.md`](WEBUI_BUILDOUT_PLAN.md) (the phase log that got
> the dashboard to its current state).

---

## TL;DR

- **The shell is tabs-over-routes, not panels.** The TabBar renders static
  nav groups plus groups generated from a workspace registry that is
  **empty** (`fks-web src/lib/workspaces.ts` — every entry commented out;
  `TabBar.svelte`'s `workspaceTabs()` is documented dead code). The only
  "layout" feature that exists is `/charts/grid`: fixed 1×1/1×2/2×2 CSS
  presets. Recommendation: **dockview-core** hosted in one new `/workspace`
  route over a small panel registry — existing pages untouched (§2).
- **Market data is one healthy path and one dormant one.** Unified janus
  ingests Binance WS klines → `MarketDataBus` → QuestDB `candles_crypto`.
  The entire historical-backfill subsystem (`janus
  services/data/src/backfill/`, 9 modules) is wired **only** into the
  standalone data binary behind `JANUS_CANDLE_SCAN=1`; the unified
  `start_module` path never invokes it — verified (§3.1). No news source, no
  non-crypto asset, and no Rithmic connectivity exist anywhere.
- **The bots are on the platform now** (new ground truth, 2026-07-06): both
  crypto bots run on this host as spawner-managed containers —
  `fks-bot-crypto-spot` (dry-run, real keys injected) and
  `fks-bot-crypto-funding` (paper) — via crypto PR #4; the desktop systemd
  units are retired. (The images now build from the post-migration homes:
  spot from the fks-spawner root since the #196 prune, funding from the
  `fks-state` root.) Remaining: the
  deliberate live flip for spot, the funding Postgres `StateStore` (now in
  the private `fks-state` repo, the edges' home), a future read-only BTC
  xpub watcher (§4) — and durable net-worth history, since **shipped**
  (fks #188/#189 + the fks-web panel; §4.2).
- **Credentials generalized one step** (fks-web #24, merged 2026-07-06): the
  `/settings` provider picker covers 5 exchanges + Rithmic + a free-slug
  escape hatch, all mapped onto the spawner's fixed 3-slot secret record.
  Next: a `kind`-aware secret schema (Discord webhooks have a URL and **no
  secret** — `POST /secrets` requires both today, verified §5.1),
  Rithmic-gated UI features, and spawner-side signed credential validation
  (the existing "Test" button pings **public** endpoints only, deliberately).
- **Chart indicators are TypeScript, not Rust** — verified: the charts
  dropdown is fed by `INDICATOR_CATALOG` in `fks-web
  src/lib/server/indicators.ts` and computed by that same TS engine; the
  Rust `indicators-ta` crate (a janus workspace dep) is never in the chart
  path. `indicators-ta` already has a runtime registry
  (`REGISTRY.list()/create(name, params)`) but **no param metadata**. Design:
  a janus catalog + compute API the dropdown *merges*, so a new indicator
  registered in Rust shows up on the charts page with zero TS work (§6).

---

## 1. Current-state ground truth

Everything in this section was verified against the working trees and the
live host on 2026-07-06. Re-verification commands are collected in §9.

### 1.1 The WebUI shell

- **Chrome:** `fks-web src/lib/components/shell/` = `Strip.svelte` (top
  status strip), `TabBar.svelte` (grouped nav tabs + `1`–`9` keyboard
  shortcuts), `StatusBar.svelte`. One page renders at a time under the tab
  bar — classic route-per-page.
- **TabBar groups** are hardcoded (`Markets`, `Trading`, `Analysis`,
  `System`) plus groups generated from `workspaceList`. The comment block in
  `TabBar.svelte` is explicit: the Ruby-era tabs were pruned, `journal`/`db`
  are URL-routable but off the nav, and `workspaceTabs()` is *"Dead today —
  `WORKSPACES` is empty, so this never runs."*
- **The dormant workspace registry:** `src/lib/workspaces.ts` defines
  `WorkspaceConfig { label, apiBase, tasksBase?, hasCnn?, color }` and a
  `WORKSPACES` record whose every entry (futures, crypto_spot, rithmic) is
  commented out, awaiting a backing API. The concept — *named environments
  whose pages read their backend from config* — is exactly the right seed
  for panel-level data binding, but it binds at the **page** level and
  assumes a Ruby-shaped REST contract that no longer exists.
- **Routes** (one folder per feature): `charts`, `signals`, `bots`,
  `exchanges(/[exchange])`, `futures`, `trading`, `performance`,
  `monitoring`, `janus-ai`, `settings`, `docs`, `journal`, `db`, plus
  auth shells. All backend access goes through the single
  `src/hooks.server.ts` adapter seam (janus `:8080`/`:8180`, spawner,
  Prometheus, QuestDB, crypto-bot status servers) with graceful-empty
  degradation.
- **The only layout precedent:** `/charts/grid` (`routes/charts/grid/
  +page.svelte`) — fixed preset layouts (`1×1`, `1×2`, `2×2`) of
  `ChartGrid.svelte` with editable symbol slots. Presets, not docking; charts
  only, not arbitrary panels.

### 1.2 Market data

- **The live path (unified janus):** `bin/janus/src/main.rs:194` →
  `janus_data::start_module` (`services/data/src/lib.rs:328`). With
  `DATA_SOURCE=live`, `run_live_mode` subscribes combined Binance
  kline+trade WS streams per configured asset (`connectors/binance.rs`;
  `bybit.rs`/`kucoin.rs` also exist), publishes closed klines on the
  in-process `MarketDataBus`, and persists them to QuestDB via
  `candle_sink.rs` — **table name is a hardcoded const:**
  `const TABLE: &str = "candles_crypto"` (`candle_sink.rs:35`). That table
  is the WebUI chart source. Assets/exchange come from
  `fks/infrastructure/config/janus/janus.toml` (`[assets]`,
  `exchange = "binance"`).
- **The dormant backfill subsystem — verified NOT in the unified path.**
  `services/data/src/backfill/` contains a complete machine: `candle_scan`
  (gap detection over `candles_crypto`), `scheduler`, `executor`,
  `gap_integration`, `historical_candles` (`deep_warmup`),
  `indicator_warmup`, `lock` (Redis distributed lock), `throttle`
  (disk-aware), `signal_backtest`. It is wired **only** in the standalone
  data binary: `services/data/src/main.rs::start_candle_scan`, gated on
  `JANUS_CANDLE_SCAN=1` (*"Inert unless… wires the (otherwise dormant)
  backfill scheduler"* — the code's own words). The unified
  `start_module`/`run_live_mode` path never constructs any of it; the only
  backfill references in `lib.rs` are **metric pre-registration at zero** so
  `BackfillFailureRateHigh`-class alerts can arm (`lib.rs` ~517). Since
  production deploys the unified binary (`fks_janus`), the deployed stack
  has gap *alerts* but no gap *repair*.
- **What does not exist:** no news ingestion of any kind (no matches in
  `services/data`), no non-crypto asset path (the sink table name and the
  Binance symbol scheme are crypto-shaped), no Rithmic/futures feed
  (`exchange-apiws` covers Kraken/KuCoin/Crypto.com/Bybit/Binance only).

### 1.3 Crypto bots + net worth (new ground truth, 2026-07-06)

Supersedes the "transitional systemd" row in
[`PLATFORM_ARCHITECTURE.md`](PLATFORM_ARCHITECTURE.md) §7 (2026-07-03):

- **Both bots run on this host as spawner-managed containers** (verified via
  `docker inspect`): `fks-bot-crypto-spot` (labels `fks.bot_id=crypto-spot`,
  `fks.mode=dry-run`, `fks.market=spot`, created-by spawner 2026-07-06) with
  **real Kraken/KuCoin/Crypto.com keys injected** from the encrypted secret
  store, and `fks-bot-crypto-funding` (`fks.bot_id=crypto-funding`,
  `fks.mode=paper`, `fks.market=futures`). Images built from crypto PR #4
  (*"feat(docker): fks-bot spawner images for spot-portfolio and
  kucoin-futures"*, merged; with the crypto repo since dissolved, the spot
  image builds from the fks-spawner sibling — `docker build -f
  bots/spot-portfolio/Dockerfile -t fks-bot-crypto-spot:latest .` from the
  fks-spawner root (post-#196) — and the funding image from the `fks-state`
  root). No `spot-portfolio`/`funding-paper` user systemd units remain on
  this host; the desktop units are disabled.
- **Spot is deliberately dry-run:** the spot `Dockerfile` (now
  `fks-spawner/bots/spot-portfolio/Dockerfile` after the #196 prune) bakes the
  spot TOML with `live = false` and documents that going live *"must be an
  explicit, deliberate override — never the default of whatever someone
  spawns from the UI."* *(The production live flip has since happened as
  exactly that kind of explicit override — see P9.)*
- **Funding state is durable now** *(was ephemeral at survey time)*: the
  `StateStore` trait with file + Postgres impls (`FKS-INTEGRATION.md`
  Phase-2 item 4a — that plan now lives at
  `fks-state/bots/crypto-futures/FKS-INTEGRATION.md`) **shipped** in the
  private `fks-state` repo — the funding bot resumes its Postgres state
  across container recreates (verified on the prod host, 2026-07-12).
- **Net worth today:** the bots export `fks_bot_*` gauges (net worth,
  per-exchange totals, positions) and rich `/status` JSON; the `/exchanges`
  pages read `/status` live. *(At survey time the only history was
  Prometheus scrape data with `--storage.tsdb.retention.time=30d`; the
  durable backbone has since **shipped** — `net_worth_snapshots` schema +
  spawner `/status` sampler, fks #188, db-gated `GET /net-worth` read
  endpoint, fks #189, and the fks-web history panel. See §4.2.)*

### 1.4 Credentials

- **Provider picker exists** — fks-web PR #24 merged 2026-07-06
  (`routes/settings/+page.svelte`): a dropdown of `ProviderSpec`s — Kraken,
  KuCoin, KuCoin Futures, Crypto.com, Binance (`kind: 'exchange'`,
  testable) and **Rithmic** (`kind: 'broker'`, not testable, with the 3-slot
  mapping documented in-code: User → `api_key`, Password → `api_secret`,
  System → `api_passphrase`) plus an "Other…" free-slug escape hatch.
  Per-provider field labels/placeholders; switching providers clears inputs.
- **The store is 3-slot and both-required:** spawner `SecretRequest`
  (`crates/spawner/src/models.rs:71`) = `exchange: String`, `api_key:
  String`, `api_secret: String`, `api_passphrase: Option<String>`; the
  `exchange_secrets` table (`src/sql/spawner/003_secrets.sql`) has
  `api_key TEXT NOT NULL, api_secret TEXT NOT NULL` and **no kind column**.
  A Discord webhook (URL, no secret pair) cannot be stored without either
  lying in the slots or evolving the schema (§5.1).
- **"Test" is public-only, deliberately:** the `/settings` Test buttons hit
  `GET /api/exchanges/:venue/ping` (`hooks.server.ts:585` —
  `venuePing`), a reachability check against *"the venue's cheapest PUBLIC
  endpoint. This deliberately does NOT validate"* credentials. No signed
  validation exists anywhere.

### 1.5 Chart indicators

- **The TS engine is the chart path — verified.** `fks-web
  src/lib/server/indicators.ts` (491 lines of pure functions, unit-tested)
  computes RSI/EMA/SMA/WMA/BB/MACD/ATR/Stoch/Williams %R/CCI/OBV/ADX/VWAP/
  Donchian/Keltner from QuestDB candles. `hooks.server.ts` serves the
  catalog at `GET /api/indicators/catalog` (returns the static
  `INDICATOR_CATALOG`, 16 entries with `{id, label, pane, keys}`) and
  computation at `GET /api/chart/:symbol/indicators?indicators=rsi:9,bb:20:2`
  (colon-separated params, per-slot defaults). The charts page's oscillator
  picker is already **catalog-driven** (`routes/charts/+page.svelte` ~1286
  fetches `/api/indicators/catalog`) — an important hook for §6.
- **`indicators-ta` (Rust) is never in that path.** It *is* a janus
  workspace dep (`janus/Cargo.toml:107` — `janus-indicators = { package =
  "indicators-ta", version = "0.2" }`, consumed by `crates/strategies`,
  `crates/backtest`, `crates/optimizer`, `services/forward`,
  `services/optimizer`) and it already has a **runtime registry**
  (`src/registry.rs`): `REGISTRY.list()`, `REGISTRY.create(name,
  &HashMap<String,String>)` → `Box<dyn Indicator>` whose
  `calculate(&[Candle])` returns `IndicatorOutput` — named `Vec<f64>`
  columns with NaN warm-up. Registered names span trend (sma, ema, wma,
  macd, parabolicsar, linearregression), momentum (rsi, stochastic,
  stochasticrsi, williamsr, schafftrendcycle, elderrayindex…), volatility
  (atr, bollingerbands, keltnerchannels, choppinessindex), volume (adl,
  chaikinmoneyflow, cvd, vwap, vzo) and regime helpers. **Gap:** the
  registry stores only factory functions — there is no `describe()`/param
  schema, so a catalog endpoint cannot report params without adding
  metadata (§6.1).
- Recent chart UX work (fks-web #23 TradingView-style indicator dropdown +
  history backfill, #25 price-scale menu) means the *front half* of
  TradingView parity is progressing; this design covers the *engine* half.

---

## 2. Dockable panel layouts ("snap windows like a real platform")

### 2.1 Options, evaluated honestly

| Option | What it gives | Cost / risk | Verdict |
|---|---|---|---|
| **dockview-core** (framework-agnostic core of dockview; MIT, actively maintained) | True docking: drag-to-dock with drop hints, tab groups, splitters, floating panels, maximize, **serializable layout JSON** | No official Svelte adapter — panels mount via a DOM-element API, so we write a thin Svelte 5 adapter (`mount()`/`unmount()` per panel, ~150–250 lines); client-only (skip SSR); its own CSS theme to reconcile with `app.css` variables | ✅ **Recommended.** The only option that actually delivers "snap windows"; the adapter cost is bounded and the layout JSON gives persistence/presets for free |
| golden-layout v2 | Same category of docking | Effectively unmaintained for years; heavier legacy API; known friction with modern bundlers/strict TS | ❌ Don't adopt an unmaintained load-bearing dependency |
| gridstack.js / svelte-grid | Drag + resize widgets on a grid | No tab groups, no dock targets, no splitters — it's a widget board, not a trading-platform layout | ❌ Wrong shape for the ask (fine for a future "overview board", not the platform shell) |
| CSS-grid presets (extend `/charts/grid`) | Zero deps; already proven in-tree | No drag, no snap, no per-user layouts — it's what exists, and the user is explicitly asking for more | ⚠️ Keep as the fallback and as the mobile/degraded rendering of saved layouts |
| Incremental panels-in-pages only | Refactor value without layout risk | Never delivers docking by itself | ✅ **Do it anyway** — it's the prerequisite step (§2.2 Phase A) regardless of library choice |

### 2.2 Target architecture: panel registry + one workspace route

The migration is explicitly **not** a big-bang: no existing route changes
behaviour in Phases A–B.

**Phase A — panel extraction + registry (the real work).** Today's pages own
their data fetching inline. Extract the reusable units into self-contained
panel components (`src/lib/panels/`): `ChartPanel`, `SignalsFeedPanel`,
`NetWorthPanel`, `HoldingsPanel`, `BotListPanel`, `BotLogsPanel`,
`MonitoringPanel`, `JanusAiPanel`, … Each panel:

- takes its inputs as props (symbol, exchange, bot id, …) and does its own
  polling/SSE via the existing `$stores/poll.ts` / `$stores/sse.ts`;
- registers in a typed **panel registry** (`src/lib/panels/registry.ts`):
  `{ id, title, component, params schema, defaultSize, singleton? }` — the
  spiritual successor of the dormant `workspaces.ts` (which binds an API
  base to a *page group*; the registry binds data to a *panel instance*).
  `workspaces.ts` stays for nav grouping and is documented as such.

Existing routes are then recomposed as thin arrangements of their own
panels — same DOM, same behaviour, `svelte-check`/vitest/Playwright gates
keep it honest. This is refactoring, so it is the slow part: budget it
per-page, not as one PR.

**Phase B — the `/workspace` route.** One new route hosting dockview-core:

- **Svelte adapter:** dockview panel `init` receives a DOM element → Svelte
  5 `mount(Component, { target, props })`; `dispose` → `unmount()`. Panel
  params round-trip through dockview's panel `params` so layouts serialize.
- **Layout persistence:** `layout.toJSON()` → `localStorage` first
  (instant), then a saved-layouts store server-side so layouts follow the
  operator across browsers — smallest honest home is a `ui_layouts` table
  next to the spawner's existing `bot_configs` (same Postgres, same
  X-Internal-Token surface), exposed via the adapter as
  `GET/PUT /api/layouts/:name`.
- **Preset layouts** ship in-repo: "Trading" (chart + signals + positions),
  "Ops" (bots + logs + monitoring), "Net worth" (exchanges + history) —
  presets make the feature useful before anyone hand-builds a layout, and
  they subsume `/charts/grid` (which can later become a redirect to a
  preset).
- **"Add panel" menu** reads the panel registry; Rithmic-gated panels
  consult credential status (§5.2).

**Phase C (later, optional) — nav convergence.** If `/workspace` proves out,
individual routes can become "open this preset" shortcuts and the TabBar
gains a layouts group. Explicitly deferred; route-per-page keeps working
throughout, and deep links (`/exchanges/kraken`) must keep working forever
(they're also the mobile story — dockview is a desktop interaction model).

### 2.3 Risks stated plainly

- Multiple live panels multiply concurrent polls; the poll stores must
  dedupe by key (one shared poller per endpoint+params) before a 6-panel
  layout ships, or the adapter/backends see 6× traffic.
- `lightweight-charts` needs explicit `resize()` on dockview
  resize/maximize events — wire the panel-resize callback through the
  adapter from day one.
- dockview CSS theming to the terminal look is real but bounded work (it
  ships CSS-variable-driven themes).

---

## 3. The data platform: many sources, one registry

### 3.1 Target architecture

Doctrine stays: **janus is the single data path** (root `CLAUDE.md`: "don't
add a second data path elsewhere"). "Bring in all sorts of data" therefore
means making janus's Data module **multi-source**, not sprouting sidecars —
with one honest exception (Rithmic, below) that still writes through the
same storage contracts.

```
                       janus Data module (unified binary)
  ┌──────────────────────────────────────────────────────────────────────┐
  │  SourceRegistry (from janus.toml [[data.sources]] + status API)      │
  │                                                                      │
  │  kind=klines-ws      kind=backfill-rest     kind=news     kind=book  │
  │  Binance WS (today)  historical_candles/    RSS/API       Rithmic    │
  │  Bybit/KuCoin (have  candle_scan (exists,   poller        connector  │
  │  connectors)         dormant — wire it)     (new)         (external, │
  │        │                   │                  │            gated)    │
  │        ▼                   ▼                  ▼               │      │
  │  MarketDataBus       QuestDB candles_<class> Postgres        ▼      │
  │        │             (crypto today; futures  news_items   QuestDB    │
  │        ▼              later, asset_class     (janus_db)   book_*     │
  │  candle_sink → QuestDB      tagged)                                  │
  └──────────────────────────────────────────────────────────────────────┘
                 │                        │                    │
                 ▼                        ▼                    ▼
        /charts, indicators        /news panel (§2)      DOM/footprint
        (fks-web adapter)                                panels (later)
```

- **Source registry:** `[[data.sources]]` entries in `janus.toml` (`kind`,
  venue, symbols/feeds, credentials-by-reference — never inline). The Data
  module exposes `GET /api/data/sources` (id, kind, state, last-event age,
  completeness where applicable) so the WebUI gets a "Data" panel showing
  every registered source, replacing today's implicit
  single-source health. Registering a new source = TOML + restart in v1;
  a mutating API is deliberately out of scope (config is a live RO mount
  from this repo — keep topology in git).
- **Storage contracts:** klines → QuestDB `candles_<asset_class>` (make
  `candle_sink.rs`'s hardcoded `candles_crypto` a per-source parameter, and
  carry venue+symbol columns so KuCoin BTC-USDT and Binance BTCUSDT stop
  being implicitly the same series); news → Postgres `janus_db.news_items`
  (text is relational, not time-series: `source, published_at, symbols[],
  headline, body/url, sentiment?`), optional Qdrant embeddings later
  (Qdrant is already in the stack); book data → QuestDB ILP (`book_events_
  futures`), which is the highest-volume store decision and gets its own
  sizing pass before the Rithmic connector lands.
- **Symbol namespace:** adopt `venue:SYMBOL` (`binance:BTCUSDT`,
  `rithmic:MESU6`) at the API/UI boundary now, while only one venue exists —
  every later phase gets cheaper. The chart symbol picker and QuestDB
  queries in the adapter are the two touch points.

### 3.2 The missing pieces, honestly sized

1. **Wire the dormant backfill into the unified path** (days, not weeks —
   the machine exists and is described as verified against live
   QuestDB/Redis in the standalone path). Call the equivalent of
   `start_candle_scan` from `run_live_mode` behind the same
   `JANUS_CANDLE_SCAN=1` gate, defaulting symbol list from the live asset
   config instead of requiring `JANUS_CANDLE_SCAN_SYMBOLS`. This closes the
   real operational gap (deployed stack alerts on gaps it cannot repair) and
   is the prerequisite for honest "deep history" charts.
2. **News (new build, weeks).** A `news` source kind: poll N feeds
   (provider choice is an open question — §8.3), normalize to `news_items`,
   tag symbols by simple matching first (no NLP claims), serve
   `GET /api/news?symbols=&since=` from the janus API, add a `NewsPanel` to
   the §2 registry. Sentiment/embeddings are explicitly later.
3. **Non-crypto assets** ride on the storage-contract work (asset_class
   tables + venue-tagged symbols). Equities/ETF daily bars via a REST
   backfill source kind is the cheap on-ramp *for charts*; live non-crypto
   streams are venue-by-venue decisions.
4. **Rithmic futures feed incl. book-level data (weeks, the honest hard
   one).** R|API+ is a proprietary C++/.NET SDK gateway protocol — not a
   public WebSocket; there is no maintained Rust client to lean on, and
   `exchange-apiws` (crypto venues) is the wrong home for it. Design: a
   dedicated **rithmic-connector** container (own repo or `fks` service,
   likely wrapping the official SDK) that authenticates from the secret
   store (the 3-slot Rithmic record already exists — §1.4), subscribes
   trades + depth for configured CME symbols, and writes through the same
   contracts (klines aggregated → `candles_futures`; depth →
   `book_events_futures`). It registers itself in the source-status API so
   the UI treats it as just another source. Activation is credential-gated
   end to end (§5.2). Until the SDK evaluation is done, treat every
   estimate here as **weeks, plus an unknown** — that evaluation is the
   first task, not the connector.

---

## 4. Crypto bots + the net-worth backbone

### 4.1 What's left after the 2026-07-06 milestone

With both bots spawner-managed (§1.3), the remaining work is:

1. **The live flip for spot (deliberate, small) — ✅ done 2026-07.** Per the
   spot Dockerfile's doctrine (`bots/spot-portfolio/Dockerfile`, now in
   fks-spawner), live had to be an explicit operator act. It shipped as the
   saved `crypto-spot-live` spawn config (`SPOT_LIVE=1` + secrets injection +
   `REDIS_URL`) rather than the live-variant *image* this item sketched —
   the decision is still a deliberate config choice, never a default. The
   dry-run image remains the baseline.
2. **Funding Postgres `StateStore` — ✅ shipped.** The private `fks-state`
   repo (`bots/crypto-futures`, the edges' post-migration home) implemented
   `FKS-INTEGRATION.md` Phase-2 item 4a (a `StateStore` trait — load/save
   open trade, append paper record — with file + Postgres impls); the
   funding bot resumes Postgres state across recreates. Its second-order
   effect stands: a **queryable trade ledger in Postgres**, which is what
   the WebUI needs for real trade-history panels.
3. **Net-worth history panels (§4.2).**
4. **BTC hardware-wallet xpub watcher (§4.3, future).**

### 4.2 Net-worth history: stop relying on Prometheus retention

> **Shipped (2026-07):** `net_worth_snapshots` schema
> (`src/sql/spawner/006_net_worth_snapshots.sql`) + the spawner-side
> `/status` sampler (fks #188), the db-gated `GET /net-worth` read endpoint
> (fks #189), and the fks-web `NetWorthHistoryPanel`. The design below is
> the record of what was built.

Today the only net-worth time series is `fks_bot_*` gauges in Prometheus
with 30-day retention (§1.3) — fine for ops, wrong for a years-horizon
net-worth backbone. Design:

- **`net_worth_snapshots` table** (Postgres — schema shipped from this
  repo's `src/sql/`, either `fks_db` next to the spawner's tables or the
  `fks-state` StateStore's schema; decided: `fks_db`, spawner-side — §8.4):
  `(ts, source, exchange, currency, balance, usd_value, net_worth_usd)` at
  a coarse cadence (e.g. every 15 min + on-demand).
- **Writer:** a small sampler that polls each registered bot's `/status`
  (the spawner already knows every running bot and its DNS name; fixed
  `bot_id`s from `FKS-INTEGRATION.md` make names deterministic) and appends
  snapshots. Spawner-side is the natural home (it has the Postgres pool,
  the bot inventory, and the internal network); a standalone sampler
  container is the fallback if the spawner should stay lifecycle-only
  (§8.4). The xpub watcher (§4.3) later writes the same table with
  `source=onchain`.
- **UI:** `NetWorthHistoryPanel` (total + per-exchange stacked, 1w/1m/1y
  ranges) reading a new adapter route backed by that table; slots straight
  into the §2 panel registry and the "Net worth" preset layout.

Effort: table + sampler + panel is ~1 week end to end once the StateStore
PR settles where bot-adjacent Postgres schema lives.

### 4.3 BTC hardware-wallet xpub watcher (read-only, future)

Purpose: the cold-storage BTC that never touches an exchange should still
appear in net worth. Design constraints: **read-only by construction** — an
xpub can derive addresses and see balances, never spend.

- Store the xpub in the secret store as a `kind=watch-only` record (§5.1) —
  an xpub is not a spending secret, but it is privacy-sensitive (it reveals
  the whole wallet's history), so it gets the same encrypted-at-rest,
  never-returned-to-browser treatment.
- A watcher task (janus Data module source kind `onchain`, or a tiny
  standalone container) derives the first N receive/change addresses
  (BIP32/84), polls an Esplora-compatible API — self-hosted preferred,
  public endpoint acceptable at day-one with the privacy caveat stated —
  and writes `net_worth_snapshots` rows (`source=onchain`,
  `currency=BTC`) priced via the existing market data.
- UI: the `/exchanges` page gains an "On-chain" entry; the TabBar comment
  already anticipates this ("Backing accounts (spot venues + hardware
  wallet) — the backbone").

Explicitly future: after net-worth history (§4.2) exists to write into.

---

## 5. Credential & key evolution

### 5.1 A `kind`-aware secret store (the Discord-webhook forcing function)

Verified today: `POST /secrets` requires `api_key` **and** `api_secret`
(`models.rs:71`), and `exchange_secrets` has both `NOT NULL` with no kind
column (§1.4). A Discord webhook is a single URL with no secret pair —
it cannot be stored without schema evolution. Design (additive, no
breaking change):

- **Schema:** add `kind TEXT NOT NULL DEFAULT 'exchange'` and relax nothing
  in place; new kinds validate differently at the API layer. Existing rows
  keep working, existing UI keeps working.
- **API:** `POST /secrets` v2 accepts `{ name, kind, fields: {..} }` with
  per-kind required fields — `exchange`: key+secret(+passphrase) (today's
  contract, unchanged as the default); `broker`: user+password+system (what
  Rithmic already stuffs into the 3 slots, now named honestly); `webhook`:
  `url` only; `watch-only`: `xpub`. Storage: encrypt the whole `fields` map
  with the existing ChaCha20-Poly1305 cipher into one column (the 3 legacy
  columns remain for `exchange` rows, or are migrated into `fields` behind
  a read-compat shim — implementation detail for the PR).
  `GET /secrets/status` grows `kind` so the UI can group.
- **Notification channels:** with `kind=webhook` stored, the spawner (or a
  small notifier task in it) can POST bot lifecycle/PnL events to Discord.
  Note the stack **already** routes alerts → Discord via Alertmanager's
  bridge (env-configured, not operator-managed); the secret-store webhook
  path is for *operator-configured, per-channel* notifications from the
  application layer (spawn/stop/live-flip events, net-worth digests) —
  don't duplicate Alertmanager's job, complement it.
- **UI:** the provider picker (fks-web #24) already carries `kind` on
  `ProviderSpec` — add a "Discord webhook" provider whose single field maps
  to `fields.url`. Minimal change on top of the merged picker.

### 5.2 Credential-gated features ("focus logic only when Rithmic creds exist")

The primitive already exists: `GET /secrets/status` reports which providers
are configured (never the values). Formalize it:

- The adapter exposes `GET /api/capabilities` → `{ rithmic: true, discord:
  false, watchOnlyBtc: true, … }` derived from secrets-status (+ source
  status from §3.1), cached briefly.
- The WebUI consumes it in one `$lib/stores/capabilities.ts` store; gated
  surfaces — the Rithmic/futures workspace group in the TabBar (finally a
  real use for the `workspaces.ts` rithmic entry), Rithmic panels in the
  §2 registry, the futures focus logic — render only when their capability
  is true. One mechanism, no per-page ad-hoc checks.
- The rithmic-connector (§3.2) uses the same signal on the backend: it
  idles (or isn't deployed) until Rithmic creds exist.

### 5.3 Spawner-side credential validation (signed test calls)

Today's Test button proves *reachability*, deliberately not *validity*
(§1.4). Real validation must happen server-side where the plaintext lives —
the spawner is the only component that ever decrypts:

- `POST /secrets/{name}/verify` (X-Internal-Token gated): decrypt, perform
  the **lowest-privilege signed read** for that venue (Kraken
  `Balance`-class call, KuCoin account list, Crypto.com summary — all via
  `exchange-apiws`, which becomes a spawner dependency), and return
  `{ ok, checkedAt, detail }` — never balances, never the credentials.
  Rate-limit hard (signed-call abuse is a lockout risk) and record
  `last_verified_at` on the row so `/secrets/status` and the settings page
  can show verification state.
- Honest limits: **Rithmic is not verifiable this way** (proprietary
  gateway, no cheap signed HTTP read — verification happens implicitly when
  the connector authenticates); webhook verification = a test POST with an
  operator-visible message; xpub verification = derivation sanity check
  (no network).

---

## 6. TradingView-parity charts + Rust indicator auto-discovery

**The user's acceptance test:** *"if I add new indicators into the rust
code `indicators-ta`, they should show up under the charts page drop
down."*

### 6.1 `indicators-ta` 0.3: metadata on the registry

The registry can already list and construct by name (§1.5) but reports no
parameters. Add, alongside each factory registration, an
`IndicatorDescriptor`:

```rust
pub struct IndicatorDescriptor {
    pub name: &'static str,            // registry key, e.g. "bollingerbands"
    pub label: &'static str,           // "Bollinger Bands"
    pub category: Category,            // Trend | Momentum | Volatility | Volume | Regime
    pub params: &'static [ParamSpec],  // { name, kind: Usize|F64|Str, default, min?, max? }
    pub outputs: &'static [&'static str], // column names as emitted by calculate()
    pub pane_hint: PaneHint,           // Overlay | Separate (UI hint, not contract)
}
```

`REGISTRY.describe_all()` returns them; `register_all` in each module
supplies the descriptor with the factory. The `param_usize`/`param_f64`
defaults that factories already use become the single source of the
`default` values (no drift). This is the only change that lives in the
published crate; everything else is janus/fks-web. (~2–3 days incl. filling
descriptors for the existing ~25 indicators.)

### 6.2 Janus catalog + compute API

Janus already consumes `indicators-ta` (five workspace crates — §1.5) and
already owns QuestDB candle access; the natural home is the janus API
service (`:8080`, host 7000), version-locked to whatever indicators-ta the
deployed janus was built with:

- `GET /api/indicators/catalog` → `[{ name, label, category, params:[{name,
  kind, default, min, max}], outputs, pane_hint, source: "indicators-ta",
  version }]` straight from `describe_all()`.
- `GET /api/indicators/compute?symbol=&interval=&days_back=&name=
  bollingerbands&params=period:20,std_dev:2` → fetch candles from QuestDB
  (same query shape the fks-web adapter uses today), `REGISTRY.create(name,
  params)`, `calculate()`, emit `{ outputs: { <column>: [{time, value}] } }`
  with NaN warm-up rows omitted — the exact point shape the chart already
  consumes, `time` in epoch seconds for lightweight-charts. Cap
  candle count; cache `(symbol, interval, name, params, last_candle_ts)`
  briefly.

### 6.3 The dropdown merges; the TS engine stays honest

The charts picker is already catalog-driven against
`/api/indicators/catalog` (§1.5), which makes the merge surgical, in the
**adapter** (`hooks.server.ts`), not the page:

- `/api/indicators/catalog` returns TS `INDICATOR_CATALOG` entries (tagged
  `source: "ts"`) **merged** with janus's catalog (tagged
  `source: "indicators-ta"`), deduped by normalized id with the TS entry
  winning for the ~16 overlapping ids (they're the tuned, tested defaults
  the chart ships with). Janus unreachable ⇒ TS-only list — the existing
  graceful-empty degradation pattern, so charts never regress when the
  brain is down.
- `/api/chart/:sym/indicators` routes each requested indicator by source:
  TS ids compute in-process exactly as today; janus-sourced ids proxy to
  `/api/indicators/compute`. Params UI is generated from `ParamSpec` (the
  page already has per-indicator param editors; they generalize).
- **Result:** publish an indicator in `indicators-ta` → bump janus's dep →
  it appears in the dropdown with its params and renders. Zero TS changes.
  (Full acceptance includes the crates.io publish + janus rebuild — that
  is the deploy loop, stated so nobody expects hot discovery.)

**Parity/migration story, honestly:** the TS engine is not a wart to
remove on a deadline — it is the zero-round-trip, janus-down-safe compute
for the core 16. The risk is silent *drift* (its header already promises
"mirrors the math of `indicators-ta`" with nothing enforcing that). So: add
a **golden-fixture parity test** — one candle fixture checked into fks-web,
expected outputs generated from `indicators-ta` (via the janus endpoint or
a tiny generator bin), asserted against the TS engine within tolerance in
vitest. Overlapping indicators are then provably interchangeable, and
*migration becomes optional*: if the janus path proves fast and reliable,
TS entries can be retired one by one by flipping the dedupe preference —
a config change, not a rewrite. TradingView-parity beyond the engine
(drawing tools, compare series, more pane types) continues in fks-web
(#23/#25 lineage) independently of where indicator math runs.

---

## 7. Phased plan

Each phase is independently shippable and reversible; none blocks another
except where noted. Effort tags are honest single-person estimates —
"days" means days of focused work, not calendar guarantees.

| # | Phase | Contents | Repos | Effort | Depends on |
|---|---|---|---|---|---|
| P1 | **Backfill goes live** | Wire the dormant candle-scan/backfill into unified `run_live_mode` behind `JANUS_CANDLE_SCAN=1`; default symbols from live config | janus | **days (2–4)** | — |
| P2 | **Indicator discovery** | indicators-ta 0.3 descriptors (§6.1); janus catalog+compute API (§6.2); adapter merge + routing + parity fixture (§6.3) | indicators-ta, janus, fks-web | **~1.5–2 weeks** across 3 PRs, each shippable | — |
| P3 | **Panel extraction** | `src/lib/panels/` + registry; recompose 3–4 pages (charts, signals, exchanges, bots) as panels; poll-dedupe in `$stores/poll.ts` | fks-web | **~2 weeks** (refactor-heavy; per-page PRs) | — |
| P4 | **`/workspace` docking** — **✅ shipped 2026-07** (fks-web `/workspace` route; server-side layouts via the spawner `ui_layouts` table + API, fks #184, schema `005_ui_layouts.sql`) | dockview-core + Svelte 5 adapter; layout persist (localStorage → `ui_layouts` + adapter routes); 3 preset layouts | fks-web, fks (sql) | — (done) | P3 |
| P5 | **Net-worth history** — **✅ shipped 2026-07** (fks #188/#189 + fks-web panel) | `net_worth_snapshots` schema; spawner-side `/status` sampler; `NetWorthHistoryPanel` | fks, fks-web | — (done) | schema home resolved: spawner `fks_db` |
| P6 | **Secret kinds + webhooks** — **partially shipped 2026-07**: Discord-webhook notifications landed via a dedicated `notification_channels` store + management API (fks #179, schema `004_notifications.sql`) and a spawner-side sender firing on bot lifecycle events (fks #181) — **not** via the §5.1 kind-aware secret store, which remains open | `kind` column + `fields` v2 API (§5.1); Discord-webhook provider in picker; spawn/stop/live-flip notifications | fks (spawner, sql), fks-web | remaining: the §5.1 schema evolution | — |
| P7 | **Capabilities gating** | `/api/capabilities` + capabilities store; Rithmic-gated nav/panels | fks-web | **days (2–3)** | P6 for kinds (soft) |
| P8 | **Signed credential verify** | spawner `POST /secrets/{name}/verify` via exchange-apiws; settings-page verification state | fks (spawner), fks-web | **~1 week** (new dep in spawner + per-venue calls + rate limiting) | — |
| P9 | **Spot live flip** — **✅ done 2026-07**: the spot bot runs **live** as a spawner-managed container via the deliberate `SPOT_LIVE=1` override in the saved `crypto-spot-live` spawn config (secrets-injected), rather than the live-variant *image* this row designed — the "explicit operator act" doctrine held, the mechanism differed | Tuned TOML + live-variant image; saved spawn template; runbook | fks-spawner (`bots/spot-portfolio`) | — (done) | P5 recommended first (watch history before/after) |
| P10 | **News source** | `news` source kind + `news_items` + `/api/news` + `NewsPanel` | janus, fks-web | **~2 weeks** (provider choice adds unknowns) | P3 (panel home); §8.3 decision |
| P11 | **Multi-asset storage contracts** — *partially shipped*: `candles_futures` exists as the rithmic-connector's write target (fks #182); the janus candle-sink parameterization + venue-tagged symbols remain open | Parameterize candle sink table; venue-tagged symbols; `candles_futures` | janus, fks-web (symbol picker) | remainder ~1 week | best before P12 |
| P12 | **Rithmic connector** — *foundation shipped 2026-07* (fks #180/#182/#183/#185: read-only connector w/ mechanically-enforced doctrine, `candles_futures` persistence, positions/PnL `GET /positions`; spike report: [`RITHMIC_INTEGRATION_SPIKE.md`](RITHMIC_INTEGRATION_SPIKE.md)). Code now lives in **fks-state** `crates/rithmic-connector` (compose `rithmic` profile, runtime-gated `RITHMIC_ENABLED`); **idle until paid dev-kit credentials exist** (spike Phase 0 — the long pole) | SDK evaluation spike (**timeboxed 1 week, decides everything after**), then connector container: auth from secret store, trades+depth → QuestDB, source-status registration | fks-state, janus | remaining gate: **access/conformance**, not engineering | P11, P7; creds already storable |
| P13 | **xpub watcher** | `kind=watch-only` xpub; derivation + Esplora poller; on-chain rows in net-worth history + `/exchanges` entry | fks or janus, fks-web | **~1 week** (self-hosted Esplora excluded — that's infra, priced separately) | P5, P6 |

Sequencing notes: P1 and P2 are the highest leverage-per-effort and touch
nothing UI-structural. P3 is the strategic refactor — start it early, land
it page by page. P12 is the only genuinely uncertain line item; its spike
is cheap and everything Rithmic-flavored (P7's gating already works with
creds-present-but-no-connector) degrades gracefully until it lands.

---

## 8. Open questions

1. **dockview-core vs. a leaner hand-rolled splitter.** If Phase A's panel
   registry lands and dockview's adapter friction turns out high, a
   two-axis split + tab-group implementation (no floating windows) is
   plausible in-house — but history says layout engines are iceberg code.
   Decide after a 1–2 day dockview spike against real panels, not in the
   abstract.
2. **Where does per-operator UI state live long-term?** `ui_layouts` next
   to `bot_configs` is expedient but stretches the spawner's "lifecycle
   service" identity; alternatives: a tiny KV in Postgres owned by the
   adapter, or Redis with periodic Postgres snapshot. Single-operator
   reality makes this low-stakes today.
3. **News provider(s).** Free RSS aggregation (venue blogs, Coindesk-class
   feeds) vs. a paid API with symbol tagging. Cost/ToS/quality tradeoff —
   pick during P10 planning, and design `news_items` so the source is just
   a column.
4. **Schema home for `net_worth_snapshots`** — spawner's `fks_db` schema
   vs. the `fks-state` StateStore's schema. **Resolved 2026-07:** the
   spawner owns the writes, so the schema landed in `fks_db`
   (`src/sql/spawner/006_net_worth_snapshots.sql`, fks #188).
5. **Rithmic book-data volume.** Depth updates for even a few CME symbols
   dwarf kline traffic; whether QuestDB ILP on this host absorbs full depth
   or the connector downsamples (top-N levels, conflated snapshots) is a
   P12-spike measurement, and it shapes the `book_events_*` schema.
6. **Does the TS indicator engine ever fully retire?** Only if the janus
   compute path beats it on latency and availability in practice. The
   dedupe-preference mechanism (§6.3) makes this a data-driven flip, not a
   commitment — revisit after P2 has months of runtime.
7. **Symbol namespace migration.** `venue:SYMBOL` is cheap now and annoying
   later; but today's QuestDB rows are unprefixed. Decide whether P11
   rewrites history (one-off QuestDB migration) or maps at the query layer
   and lets old rows age out with retention.

---

## 9. Re-verify the ground truth

```bash
# Workspace registry is empty; workspaceTabs() is dead code:
grep -n "Dead today" ~/github/fks-web/src/lib/components/shell/TabBar.svelte
sed -n '50,78p' ~/github/fks-web/src/lib/workspaces.ts

# Backfill wired only in the standalone data binary, behind JANUS_CANDLE_SCAN:
grep -n "start_candle_scan\|JANUS_CANDLE_SCAN" ~/github/janus/services/data/src/main.rs
grep -n "backfill" ~/github/janus/services/data/src/lib.rs   # → metric arming only
grep -n "start_module" ~/github/janus/bin/janus/src/main.rs  # unified entry

# Candle sink table is hardcoded crypto:
grep -n 'const TABLE' ~/github/janus/services/data/src/candle_sink.rs

# Bots are spawner-managed containers (2026-07-06):
docker inspect fks-bot-crypto-spot fks-bot-crypto-funding \
  --format '{{.Name}} {{.Config.Labels}}'
systemctl --user list-unit-files | grep -E "spot|funding"   # → nothing

# Spot image bakes dry-run (spot lives in fks-spawner since the #196 prune):
grep -n "live = false" ~/github/fks-spawner/bots/spot-portfolio/Dockerfile

# Secret store requires key+secret; no kind column (spawner code → fks-spawner):
sed -n '60,85p' ~/github/fks-spawner/crates/spawner/src/models.rs
grep -n "api_secret" ~/github/fks/src/sql/spawner/003_secrets.sql

# Provider picker merged (fks-web #24) incl. Rithmic 3-slot mapping:
gh -R nuniesmith/fks-web pr view 24 --json state,mergedAt
grep -n "rithmic" ~/github/fks-web/src/routes/settings/+page.svelte

# Venue "Test" is public-endpoint-only, deliberately:
sed -n '585,590p' ~/github/fks-web/src/hooks.server.ts

# Chart indicators: TS engine + local catalog endpoint; picker is catalog-driven:
grep -n "INDICATOR_CATALOG\|/api/indicators/catalog" ~/github/fks-web/src/hooks.server.ts
grep -n "api/indicators/catalog" ~/github/fks-web/src/routes/charts/+page.svelte

# indicators-ta registry exists, factories only (no descriptors):
sed -n '1,40p' ~/github/indicators-ta/src/registry.rs
grep -rn "janus-indicators" ~/github/janus/Cargo.toml

# Net-worth history bound by Prometheus retention:
grep -n "retention" ~/github/fks/docker-compose.yml
```
