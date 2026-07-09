# fks — TODO (orchestration / cross-cutting)

> **Repo:** `github.com/nuniesmith/fks`
> **Last synced:** 2026-07-09 — see **🗺️ NEXT PHASES** below for the current plan
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

> ⚠️ **2026-06-07 — the Python "Ruby" service was removed.** janus is the
> platform now. Tasks below that reference `fks_ruby` / the Ruby data API /
> the `trainer` container / `src/ruby/sql/` are **stale** — the equivalents are
> being rebuilt natively in janus. The plan + remaining follow-ups are in
> [`docs/architecture/RUST_MIGRATION.md`](docs/architecture/RUST_MIGRATION.md).
> The spawner's `ruby_db` schema now lives in `src/sql/spawner/`.

---

# 🗺️ NEXT PHASES — prioritized plan (synced 2026-06-14 · verified 2026-06-18 · updated 2026-07-09)

> **Read this section first.** It's the master roadmap written after a large
> live-stack session. Everything *below the next `---`* (the older "Status
> snapshot" etc.) predates it and contains stale items (esp. `fks_ruby` refs) —
> trust THIS section for current priorities. Deep per-item notes live in the
> Claude memories: `fks-demo-live-data-blockers`, `janus-forward-warmup-gap`,
> `fks-releases-pending-publish`, `fks-stack-live-ops`.

### ✅ Shipped 2026-06-14 — do NOT redo
- **fks:** cred passthrough + `KUCOIN_API_* → KC_*` bridge (#134/#135) ·
  reqwest TLS backend for the demo (#136) · IPv4-preference `gai.conf` so KuCoin
  is reachable from containers (#137) · env-configurable position sizing
  (`DEMO_MARGIN_PER_TRADE_USD`/`DEMO_MAX_CONTRACTS`, #138) · working default
  `synthetic`+`ema-cross` and `JANUS_HTTP_URL→8180` (#139) · bump exchange-apiws
  0.8.1 + drop the TLS workaround (#140) · adapter lockfile (#141) · rustrade
  **0.4** + indicators-ta **0.2.2** (#142).
- **exchange-apiws:** reqwest shipped with NO TLS backend → fixed + **published
  0.8.1** (#50). *(2026-06-18: `main` now has ~12 UNRELEASED commits beyond 0.8.1 —
  `set_margin_mode`, a futures-ws price fix, binance + cryptocom typing (#51/#61),
  and the CI restore (#59). The cryptocom change is breaking → cut **0.9.0**, not
  0.8.2, to use them downstream.)*
- **janus:** forward REST (signals + risk) mounted on 8180 for `DEMO_BRAIN=janus`
  (#117) · stamp `entry_price` so the RiskManager can size live entries — the
  execution path was silently disabled (#118) · warm analyzers from Binance
  history on first sight, ~1 min vs hours after restart (#119 + rustfmt #120).
- **Net:** crypto-demo runs live (Kraken spot + KuCoin futures) → signals → paper
  fills; janus warms fast, sizes entries, gate built + flag-gated; all crates on
  latest. `EXECUTION_MODE=paper_trading` invariant intact throughout.

### ✅ Verified / shipped 2026-06-18 — do NOT redo
A verification pass confirmed several items below were already shipped (the
roadmap had drifted). Confirmed against current `main`:
- **exchange-apiws CI restored** (#59): hmac 0.13 needed `KeyInit` in scope; the
  `msrv` job had been Dependabot-bumped to a nonexistent toolchain `1.100.0` →
  reverted to `1.94.1` + Dependabot `ignore` for `dtolnay/rust-toolchain`.
- **A2 typing — binance + cryptocom DONE on `main`:** `get_exchange_info` typed
  (#51); all 10 `cryptocom/private.rs` methods typed off real Exchange-v1 schemas
  (#61, breaking — numeric fields kept as `String`).
- **Phase C nginx — DONE, NOT 502:** the `proxy_pass` targets already point at
  `fks_webui`; only ~11 explanatory *comments* still mention `fks_ruby`. No live
  route hits a dead service (matches the G4 note far below). The "~74 refs / 502
  now" claim in Phase C was stale.
- **Phase E — mostly DONE:** rustcode has `cargo-audit` + `cargo-deny` jobs +
  `deny.toml`; rustcode `RedisAuditCache` is implemented (the `todo!()` is only a
  stale comment); exchange-apiws has Dependabot + `cargo-deny` (#53).
- **fks safety (#146):** `run.sh setup-env` no longer generates
  `ENABLE_EXECUTION=true` against the documented `=false` default.
- **Still genuinely open (non-blocked)** *(closed 2026-07 — see the next block)*: finish A2 — (a) feed real specs into
  `bots/rustrade-exchange-apiws/src/kraken.rs` (still hardcodes
  `tick/lot/min_notional = 0.0` at ~:301); (b) type the 9 remaining untyped
  `Result<Value>` methods (KuCoin cancels, bybit `get_instruments`/`get_wallet_balance`,
  kraken `get_ohlc`/`get_recent_trades`/`get_spread`); (c) **publish a release** —
  `main` now has ~12 unreleased commits beyond 0.8.1 and the cryptocom change is
  breaking, so cut **0.9.0** (not 0.8.2) → then bump the bot/adapter.
- **Still blocked on you:** live KuCoin-futures order test (rotate keys first);
  Phase B ML brain (GPU + champion goldens).

### ✅ Shipped 2026-07 (early July) — do NOT redo
- **A2 CLOSED end-to-end.** exchange-apiws typed the 9 straggler `Result<Value>`
  methods (#63 cancels/wallet/instruments, #66 kraken market-data — breaking) and
  **published 0.9.0** (2026-07-08); the kraken adapter now sources real instrument
  specs from Kraken AssetPairs (#190) incl. `min_notional` from `costmin`, and the
  bot/adapter are bumped to 0.9.0 (#192). Nothing in A2 remains.
- **The `crypto` repo is dissolved — bots migrated.** The spot bot lives HERE:
  `bots/spot-portfolio` + the shared scaffolding crate `crates/crypto-bot-core`
  (#193), with a deployable image (#194) built from the fks root
  (`docker build -f bots/spot-portfolio/Dockerfile -t fks-bot-crypto-spot:latest .`).
  The futures/funding **edges** moved to the **private `fks-state`** repo
  (`bots/crypto-futures`, git-pins `crypto-bot-core`; the funding image builds
  from the fks-state root). The crypto GitHub repo is being deleted.
- **Net-worth history backbone.** `net_worth_snapshots` schema
  (`src/sql/spawner/006_net_worth_snapshots.sql`) + spawner-side `/status`
  sampler (#188) + db-gated `GET /net-worth` read endpoint (#189); the history
  panel shipped in fks-web.

### Phase A — Live trading real & safe  · *mostly DONE*
- [x] 9-gate execution gate wired + flag-gated (`JANUS_GATE_ENFORCE`), 37 tests.
- [x] `entry_price` producer gap (janus #118); warmup-from-history (#119/#120).
- [x] **A2 — exchange-apiws instrument typing** · *DONE 2026-07 — see the
      shipped block above*. Typed the untyped `serde_json::Value` returns so
      callers get tick/lot/min-notional + precision for order validation &
      quantity rounding:
      - [x] `exchange-apiws/src/binance/rest.rs get_exchange_info` → typed (#51).
      - [x] `exchange-apiws/src/cryptocom/private.rs` (10 methods) → typed off real
        Exchange-v1 schemas, numeric fields kept **as `String`** (#61, breaking).
      - [x] the 9 stragglers → typed (exchange-apiws #63 KuCoin cancels + bybit
        instruments/wallet, #66 kraken `get_ohlc`/`get_recent_trades`/`get_spread`).
      - [x] real specs fed into `bots/rustrade-exchange-apiws/src/kraken.rs` — from
        Kraken AssetPairs (#190), `min_notional` from `costmin` (#192).
      - [x] Chain: exchange-apiws code → **0.9.0 published 2026-07-08** → bot/adapter
        bumped (#192).
- [ ] **Gate-enforce end-to-end check** (do during the live-order test): with a
      sandbox/sub-account execution service connected, set `JANUS_GATE_ENFORCE=1`
      + `ENABLE_EXECUTION=true` and confirm a blocking verdict suppresses the
      submit. Can't be fully exercised today (no execution service connected).
- [ ] **Live KuCoin-futures order test** (the headline — **needs key rotation
      first**). Ready: `DEMO_SYMBOLS=SOLUSDTM DEMO_MARGIN_PER_TRADE_USD=7
      DEMO_LEVERAGE=1 DEMO_MAX_CONTRACTS=1 DEMO_MAX_POSITIONS=1
      DEMO_EXCHANGE=kucoin` → ~1 contract (~$6.74). Arm → **human confirm** the
      order → watch the fill → stop + flatten. Account had 38.76 USDT (verified).

### Phase B — Activate the ML brain  · *BLOCKED ON YOU*
- [ ] **(you)** Dump CNN champion goldens (~1,000 `(20×60 → logits)` pairs) +
      the champion `.pt` weights from your local Python env into
      `janus/crates/ml/tests/golden/`. *Only you can — needs the Python model.*
      (RUST_MIGRATION §12-A.)
- [ ] Then janus: run the GAF go/no-go probe (**needs GPU**) → train a burn
      champion from scratch → shadow-run → flip `ENABLE_CNN_INFERENCE` /
      `ENABLE_BRAIN_RUNTIME` only if it shows edge. (janus TODO Track B; #59–62
      merged.) *Effort L · Risk M.*

### Phase C — Finish the Ruby-removal cutover  · *P1 (nginx part done)*
- [x] **nginx** — DONE (verified 2026-06-18). The `proxy_pass` targets already point
      at `fks_webui`/spawner; only ~11 explanatory *comments* still name `fks_ruby`
      in `conf.d/*.conf`. No live route hits a dead service → **no 502 from this**.
      (The earlier "~74 refs / 502 now" was stale; the G4 note far below already
      recorded the comment-only sweep.)
- [ ] **WebUI ↔ janus data contract** — `PUBLIC_API_URL`→janus:7000 but janus
      doesn't serve the old Ruby API shape; shape it on janus or adapt the WebUI.
      Test scripts still probe `fks_ruby`.
- [ ] **Retire `python_data_client.rs`** (janus `services/data`) so janus is the
      sole QuestDB/Postgres/Redis writer — closes the two-data-paths divergence.
      *Effort M–L · Risk M (routing). DoD: no 502s; WebUI reads janus; one data path.*

### Phase D — Split-to-private orchestrator  · *structural · lower urgency*
- [ ] `SPLIT_PLAN.md` Phase 5: make fks **private**; add top-level
      `strategies/` for trading IP; all images → git-clone external / private
      registry.
- [ ] Carve out `crates/spawner` → own repo/crate (crates.io `spawner` is taken →
      use **`fks-spawner`**; add Cargo metadata + `LICENSE`). See
      `crates/spawner/TODO.md`.
- [ ] Flip `src/web` → `fks-web` repo "when ready". *Effort L · Risk M–H.*

### Phase E — CI / supply-chain / hygiene  · *cheap, parallelizable*
- [x] **rustcode CI-B (security):** DONE — `cargo-audit` + `cargo-deny` jobs +
      `deny.toml` present in rustcode (verified 2026-06-18).
- [x] **rustcode AUDIT-CACHE:** DONE — `src/audit/cache.rs` `RedisAuditCache` is
      implemented (#77); the remaining `todo!()` is only a stale *comment* at :18
      (a 1-line rustcode doc fix, not a real stub).
- [ ] **rustcode ort/ONNX build block:** `ort-sys` CDN 403s cloud/sandbox IPs →
      `rustcode`+`rag` can't build in CI; biggest CI-health lever (vendor/proxy
      the ONNX runtime). *(still open; the `build`/`docker-build` jobs are
      `continue-on-error` for this.)*
- [ ] exchange-apiws: [x] `cargo-deny` + Dependabot added (#53); [ ] refresh stale
      `todo.md` header + add `cargo-semver-checks` (F2/F6).
- [ ] Commit `Cargo.lock` where binaries ship (rustcode); keep the janus/bot
      `--locked` discipline (every dep bump needs a lock refresh in **each**
      workspace — the adapter has its own lock, see #141).
- [x] Refresh stale docs: this NEXT-PHASES section reconciled 2026-06-18. *(The
      older sections below still carry stale `fks_ruby` refs — superseded by this
      section; low priority.)*

### ⚠️ Standing — your action
- [ ] **Rotate the KuCoin + Kraken API keys** — they were printed in the
      2026-06-14 session transcript. After rotating, put new ones in
      `fks/.env`: `KUCOIN_API_KEY/SECRET/PASSPHRASE` + `KRAKEN_API_KEY/SECRET`
      (compose bridges KuCoin → the bot's `KC_*`).

### Recommended order for a fresh session  *(updated 2026-07-09)*
Most of **C** and **E** are done (verified-2026-06-18 block) and **A2 is closed**
(shipped-2026-07 block: typing + 0.9.0 publish + real kraken specs). The
remaining non-blocked work: **B** (when goldens + GPU exist, your action) →
**D** (split-to-private, last — the crypto-repo dissolution already moved the
trading edges into the private `fks-state`). Live KuCoin order test whenever
ready (**rotate keys first**).

### Ops quick-reference
- Rebuild janus from local source (no push): `docker build --target workspace -f
  infrastructure/docker/base/rust/Dockerfile --build-arg SERVICE_NAME=janus
  --build-arg RUST_VERSION=1.94.1 -t nuniesmith/fks:janus ~/github/janus` then
  `docker compose up -d --no-deps janus`. **`cargo fmt` before pushing janus Rust**
  (the `rust check` gate is rustfmt; #119 merged red, fixed by #120).
- Rebuild the demo bot: `docker compose build crypto-demo`.
- Run the demo: `docker compose --profile demo up -d`. Health: `./run.sh health`.
- janus default is **operator-start** (`JANUS_AUTO_START=false`); set `=true` to
  auto-run the brain for verification.

---

## Status snapshot (2026-06-02)

The split + consolidation are **done**. `rustrade`, `janus`, `indicators-ta`,
and `exchange-apiws` are independent repos; the libraries are on crates.io and
janus consumes them:

| Crate | crates.io | Consume as |
|-------|-----------|------------|
| `rustrade-framework` (+ core/supervisor/risk/backtest) | **0.3.0** ✅ | `rustrade = { package = "rustrade-framework", version = "0.3" }` |
| `indicators-ta` | **0.1.5** ✅ | `indicators-ta = "0.1"` (imports as `indicators`) |
| `exchange-apiws` | **0.7.0** ✅ | `exchange-apiws = "0.7"` (signed REST across 6 exchanges + private user-data WS + `f64` quantities) |
| `jflow-core` (janus) | **0.1.0** ✅ | first janus lib; rest of `jflow-*` prepped, not pushed |

`fks` keeps only `src/proto`, `src/sql`, `crates/spawner`, `src/web`,
infra, and `bots/` (with `strategies/` to come). The two reference bots
(`fks-bot-example`, `crypto-demo`) build as `fks-bot-*` images via
`./run.sh build-bots` and are spawnable from the WebUI `/bots`.

**Next:** turn the demo wiring into a real risk-aware multi-asset brain — see
[`docs/MULTI_ASSET_BRAIN_ROADMAP.md`](docs/MULTI_ASSET_BRAIN_ROADMAP.md).

---

## WebUI buildout — status (2026-06-09)

The `src/web` SvelteKit dashboard buildout (plan:
[`docs/architecture/WEBUI_BUILDOUT_PLAN.md`](docs/architecture/WEBUI_BUILDOUT_PLAN.md),
Phases A–G) is **substantially shipped**. Every data-bearing page is
janus / Prometheus / QuestDB-backed through the `src/web/src/hooks.server.ts`
adapter; the web CI gates (`svelte-check` 0/0 · `vitest` · `vite build`) are green.

**Shipped:** route/nav cleanup + prod log-stream nginx block (A); symbol catalog +
1m→N resample fallback (B2/B3); full server-side indicator engine + `/api/indicators/catalog`
+ charts picker/presets/persistence (C); charting polish — crosshair OHLC readout,
log/linear scale, shareable `?symbol=&tf=` URLs, client crypto WS (D2); exchange
API-key entry (submit-only → spawner Postgres) + connection badge (E); `/bots` spawn
presets, saved configs, per-bot CPU/mem/uptime, SSE log viewer (F1); risk panel real
save + `EmptyState` empty/error audit (G1/G2); reconciled Playwright suite (G3).

**Remaining — live-stack / janus-side (not runnable in the CI sandbox):**
- [x] **B1** — janus writes Binance candles → QuestDB `candles_crypto`.
      *Code-traced 2026-06-10: the deployed unified binary published klines only
      to the in-process bus — nothing wrote `candles_crypto` (the writer lived in
      the standalone factory binary the container doesn't run). Fixed janus-side:
      janus PR #106 adds a bus-subscribed candle sink (`DATA_PERSIST_CANDLES`,
      default on).* **✅ Verified 2026-06-14** on a full local stack built from
      `janus@main`: with `JANUS_AUTO_START=true` the data module connects 10 Binance
      kline WS streams and the sink flushes each closed 1m candle to QuestDB over ILP
      — `candles_crypto` confirmed growing (1k+ rows, real OHLCV). janus still boots
      in STANDBY by default; ingestion (and the sink) run only after
      `POST /api/services/start` or `JANUS_AUTO_START=true` (now set in `.env`).
- [x] **D1 activate** — the janus bars SSE endpoint now exists
      (`GET /sse/bars/{symbol}?interval=1m`, `event: bar` frames — janus PR #106)
      and compose passes `JANUS_BARS_SSE_URL` through to the webui (empty default
      = idle stub). **✅ Activated 2026-06-14**: set
      `JANUS_BARS_SSE_URL=http://fks_janus:8080/sse/bars` in `.env`; the endpoint
      serves `content-type: text/event-stream` (HTTP 200) and the webui is wired to it.
- [x] **F2 run** — `scripts/testing/f2-keyless-spawn-smoke.sh` against a running
      stack. **✅ Passed 2026-06-14**: keyless paper bot spawned on `fks_fks-network`,
      reached `running`, connected to the janus brain, ran rustrade candle-pollers +
      emitted `fks_bot_*` (paper/mock — no live-order path). Fixed two latent bugs en
      route: the spawner's `ALLOWED_NETWORK` resolved to a non-existent `fks_network`
      (real name is `fks_fks-network`), and the webui candle query selected a
      non-existent `ts` column (janus's sink writes `timestamp`) → charts were
      silently empty despite B1 data.
- [ ] **G3 run** — run the reconciled Playwright suite vs. a dev/preview server
      (needs the browser download, blocked in CI; `--list` enumerates 84 clean).

**G4 — local finish-line cleanup (done):**
- [x] **G4 (panels)** — removed the Ruby/futures-era `/settings` fake-save panels
      (**Data Sources**, **Rithmic**, **Analysis Preferences** — POSTed to endpoints
      with no in-tree janus backend; orphaned radio/chip/status CSS pruned, `check`
      0/0). The wired Kraken-keys / Risk / Janus-Optimizer / System / Observability
      panels stay.
- [x] **G4 (residual)** — trimmed `TabBar.workspaceTabs()` to the Dashboard+Signals
      seed (dropped `pnl/cnn/trades/logging/tasks/assets/reporting`, which pointed at
      deleted routes; dead today — `WORKSPACES` is empty), and swept the stale
      `fks_ruby` comments out of both nginx confs (`dev.conf` + `fkstrading.xyz.conf`)
      — the `proxy_pass` targets already pointed at `fks_webui`, only the comments
      lagged. Comment/scaffold-only; no routing or runtime change.

**Deferred polish (non-blocking follow-ups):** per-indicator params; fold RSI/MACD
into the generic `IndicatorPane`; dedicated volume pane; wire `exchange-apiws`
authenticated account/balance behind the key-status badge; ~~pgcrypto-encrypt
stored secrets~~ (done 2026-07: spawner-side ChaCha20-Poly1305 encryption-at-rest
via `SPAWNER_SECRETS_KEY`, #161, + spawn-time injection #162); per-bot Prometheus
scrape so `bot-alerts.yml` goes live (spawned bots get file-SD automatically; the
transitional systemd crypto bots are scraped by the static job added in #160).

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

- [x] **Reconciled `exchange-apiws` versioning.** Published through **0.7.0**
      (signed REST across six exchanges, private user-data WS, `f64`
      order/position quantities); the bots + janus consume it from crates.io.
- [ ] **Finish the `jflow-*` publish run** (janus repo). `jflow-core` is live;
      publish the Tier-0 leaves then Tier-1+ bottom-up per janus `PUBLISHING.md`.
      Blocked only on the crates.io token + sequencing.

---

## ✅ Janus consolidation — DONE

> The big architectural work is complete (janus repo). Kept here as a record.

- [x] **TA → `indicators-ta`** — `jflow-indicators` retired (janus#35).
- [x] **Connectivity → `exchange-apiws`** — `jflow-bybit-client` retired (Bybit,
      janus#36); `jflow-exchanges` adapters retired (Coinbase/Kraken/OKX
      ingestion, janus#37); dead adapter code deleted, −2.6k LOC (janus#38).
- [x] **Framework → reframed, not adopted by janus.** janus is a multi-service
      ML engine, not a thin bot; `rustrade` lives in the **`bots/` layer** here
      that *consumes* janus's signals (the `JanusBrain` ↔ rustrade tie-in).

---

## P1 — Multi-asset risk-aware brain (the headline goal)

> **See [`docs/MULTI_ASSET_BRAIN_ROADMAP.md`](docs/MULTI_ASSET_BRAIN_ROADMAP.md)
> for the full cross-repo plan + evidence.** The items below are the
> **fks / `bots/`** slice. The rest live in `janus/TODO.md` and
> `rustrade/TODO.md`.

### Track 1 — make execution real (the #1 blocker)
- [x] **`exchange-apiws → rustrade::ExchangeClient` adapter.** Shipped:
      `bots/rustrade-exchange-apiws/` (`KucoinExchangeAdapter`) over exchange-apiws's
      signed KuCoin Futures REST. Maps plain orders (market/limit/IOC/FOK), brackets
      (SL/TP → `place_stop_order`), `close_position`, `get_position`/`get_balance`,
      `cancel_all` (orders + stop-orders), and order tracking. `Capability` is
      truthful (no PostOnly — the surface has no post-only flag); `contract_value`
      from cached `get_contract().multiplier`. 10 unit tests + doctest green against
      the published crates.
- [x] **Point `crypto-demo` at the real adapter.** `DEMO_EXCHANGE=kucoin` selects
      `KucoinExchangeAdapter` (needs `KC_*`; use a sandbox/sub-account to paper-trade
      the same path). Paper `MockExchange` stays the default. (Bumped crypto-demo's
      exchange-apiws 0.1→0.5.)
- [x] **Real fills via the private WS** — `KucoinFillSource` (`FillSource`) streams
      the exchange's executions into the bot: private `tradeOrders` WS as a
      low-latency trigger + `/recentFills` for authoritative price/size/fee (deduped
      by trade id, baselined at startup, poll-only fallback). Enables the framework's
      SL/TP bracket + OCO handling. `crypto-demo` wires it on `DEMO_EXCHANGE=kucoin`
      and disables the paper PnL simulator to avoid double-counting. 5 unit tests.
- [ ] **`OrderUpdate` match price/size in exchange-apiws** — expose per-execution
      `matchPrice`/`matchSize` on the private feed so the fill source can drop the
      `/recentFills` REST hydration (today `OrderUpdate.price` is `0.0` for market
      orders). Small additive change; would let the WS carry fill prices directly.
- [x] **Kraken spot adapter + real fills** over `exchange-apiws`'s `KrakenPrivateClient`
      (spot-only: long-only, `position` = base-asset balance, no leverage →
      `AssetClass::CryptoSpot`, `contract_value` 1.0; market/limit, `OrderTracking` only).
      `KrakenFillSource` streams real fills by polling `/private/TradesHistory` (Kraken
      has no private own-trades WS here), deduped by trade id + baselined at startup.
      `crypto-demo` selects both via `DEMO_EXCHANGE=kraken` (base-asset codes from
      `DEMO_KRAKEN_BASE_ASSETS`, e.g. `XBTUSD:XXBT`). KuCoin (futures) + Kraken (spot) are
      the two target venues; **Bybit is out (not available in Canada).**
- [x] **Multi-venue `class_risk` end-to-end** — `RoutingExchange` + `CompositeFillSource`
      (in `rustrade-exchange-apiws`) compose KuCoin + Kraken into one symbol-routed
      `ExchangeClient`, so a single bot trades both classes at once. Each symbol's
      `instrument_spec` carries its venue's `AssetClass`, so the framework's `resolve_risk`
      applies `crypto_perp()` (5×) vs `crypto_spot()` (1×) per symbol — the per-class presets
      finally diverge in a running bot. `crypto-demo` wires it as `DEMO_EXCHANGE=multi`
      (symbols split by KuCoin's `M` suffix, or `DEMO_KUCOIN_SYMBOLS` / `DEMO_KRAKEN_SYMBOLS`);
      `supports` is the intersection across venues, `get_balance` the sum.
- [x] **Per-venue market data** — `KrakenCandleSource` (Kraken public OHLC) + a
      `RoutingCandleSource` that polls each symbol's candles from its own venue, so the
      `multi` mode no longer shares one feed (KuCoin klines for perps, Kraken OHLC for spot).
      `build_source` follows `DEMO_EXCHANGE` (override with `DEMO_SOURCE`), synthetic fallback.

### Track 2 — portfolio + asset-class risk · `rustrade` ✅ SHIPPED
All five items merged in `rustrade` main, **published as `rustrade-framework`
0.3.0**, and consumed in `crypto-demo`: `PortfolioRisk`, `InstrumentSpec`/`AssetClass`,
per-asset-class `RiskConfig` presets, the `RiskSweepService` (UTC rollover), and the
`JsonFileStore` durable store.
- [x] **Publish `rustrade-framework` 0.3** — released `0.3.0` (workspace version + the
      5 internal dep pins bumped, CHANGELOG cut, published in dep order via
      `release.sh minor`). *(Owner action — done.)*
- [x] **Consume in `crypto-demo`**: bumped `rustrade` to `0.3` and wired
      `portfolio_config(...)` (daily-loss / max-concurrent / gross-exposure caps from the
      `DEMO_MAX_*` env vars) + opt-in `with_state_store(JsonFileStore::open(...))` via
      `DEMO_STATE_FILE`. `class_risk(...)` is now wired too via the multi-venue mode (see the
      multi-venue item above): `DEMO_EXCHANGE=multi` applies `crypto_perp()` / `crypto_spot()`
      per asset class, so all of Track 2 is live in the demo.

### Track 4 — the janus↔rustrade risk contract
- [x] **`JanusBrain` v2** (`bots/crypto-demo/src/janus_brain.rs`): each entry now
      consults janus's risk engine — `risk_validate` (`POST /api/v1/risk/validate`; a
      veto → `Hold`) then `risk_size` (`POST /api/v1/risk/calculate/position-size` →
      `SizeHint::Quantity`). Sends signal + market-data + position context with each
      request, gated by `JanusBrainConfig::use_risk_engine` (default on) and **failing
      open** (proceed on the raw signal) if janus's risk API is unreachable.
- [x] **Position-event feedback (entry)**: `on_fill` reports the resulting position to
      `POST /api/v1/risk/portfolio/positions` so janus tracks live exposure + affinity.
- [x] **Close/outcome feedback**: `JanusBrain` mirrors each symbol's position from
      the fill stream (`apply_fill`) and, on a reducing/closing fill, computes the
      realised PnL and POSTs it to janus's new `POST /api/v1/risk/portfolio/positions/close`
      endpoint (added in `services/forward`), which folds it into the portfolio's daily
      PnL and frees the slot. So janus now sees trade *outcomes*, not just open exposure.
      *(Further refinement: route the outcome into the affinity/memory learner specifically.)*

### Multi-account (existing, pre-roadmap)
- [ ] **ACCT-A** — schema `src/ruby/sql/008_accounts.sql` **created** (verified: 5 tables —
      exchange_accounts, asset_routing_rules, profit_sweep_config/targets/log); only the
      `./run.sh fix-db` apply (runtime, against a live DB) remains.
- [ ] **ACCT-E** — janus execution router: `RoutingClient` calling
      `GET http://fks_ruby:8000/api/routing/{symbol}`, fan out per routing rule.

---

## P0 — Tailscale verification

- [ ] Test access from a second tailnet device (needs a physical second device).
- [ ] Verify trainer container GPU passthrough:
      `./run.sh all --profile training` + nvidia-container-toolkit.

---

## P1 — Multi-account: Postgres schema (ACCT-A)

- [x] **Created** `src/ruby/sql/008_accounts.sql` (verified: all five tables present). Schema:
  - `exchange_accounts` (id, name, exchange_type, mode, is_active,
    credentials_ref, api_key_hint, timestamps, last_test status)
  - `asset_routing_rules` (id, symbol, account_id, size_pct, priority, is_active)
  - `profit_sweep_config` (id, source_account_id, threshold_usd, mode,
    schedule_time, timestamps)
  - `profit_sweep_targets` (id, sweep_config_id, account_id, allocation_pct)
- [ ] Apply via `./run.sh fix-db` (runtime DB step — not verifiable in-sandbox).

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
- [ ] **GPU metrics (raw exporter)** — a `nvidia-container-toolkit` / DCGM
      exporter for *raw* GPU utilisation / temp / power. (The `trainer` job
      already scrapes the trainer's self-reported `trainer_gpu_available` /
      `trainer_gpu_memory_total_bytes`.)
- [ ] **Trainer / GPU alert rules** — NOT SHIPPED (this item was a false
      completion claim). There is no `trainer-alerts.yml` in
      `infrastructure/config/prometheus/alerts/`, the prometheus Dockerfile
      COPYs each alert file individually (a new file would need adding there —
      the runtime `alerts/*.yml` glob does not pick it up at build), and
      `prometheus.yml` defines no `trainer` scrape job, so `trainer_up` /
      `trainer_gpu_*` are never scraped. Note: CNN training now runs via the
      `train_cnn_champion` binary in the janus repo (GPU backend, walk-forward,
      backtest), not a long-lived trainer service — so these alerts would need
      a real scrape target before they mean anything.
- [ ] **Alertmanager Discord bridge** — container occasionally not running,
      causing noise in Alertmanager logs. Either fix or remove.
- [x] **`bot-alerts.yml`** under `infrastructure/config/prometheus/alerts/` —
      present with `BotStopped` / `BotHighDrawdown` / `BotNoSignals` plus
      `BotUptimeTooShort`, `BotLowWinRate`, `BotNoTrades`, and the spawner-health
      rule `SpawnerDown`. (`SpawnerAtBotCapacity` was pruned — its metric
      `fks_spawner_max_bots_limit` is never exported.) The bot rules go live once
      a real `fks-bot-*` image emits the `fks_bot_*` gauges at `:9091/metrics`.
      The crypto bots now emit that contract (spot :9091 / funding :9095, scraped
      via the transitional `fks-bots-transitional` job).

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
- [x] **`rust.yml` clippy gate.** Flipped from `continue-on-error` to a blocking
      `-D warnings` gate — all five matrix workspaces (root·proto,
      fks-bot-example, crypto-demo, rustrade-exchange-apiws, spawner) are
      clippy-clean. The proto crate allows `doc_lazy_continuation` crate-wide for
      tonic-generated docs.
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
- [ ] **`strategies/`** — once `fks` flips **private**, this is where the
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
- **Earlier (PRs #1–#21)** — the arc that took fks from "broken monolith"
  to "framework + spawner + repo-split-ready": rustrade family + examples,
  build-rot cleanup, spawner DB persistence + auth + tests + WebUI, the
  `fks-bot-example` reference image, and the `rustcode` / `openclaw` /
  `ollama` / `promptfoo` / legacy-kucoin removal (~23 → ~15 containers).
