# fks-full — TODO (orchestration / cross-cutting)

> **Repo:** `github.com/nuniesmith/fks-full`
> **Last synced:** 2026-06-02
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

## Status snapshot (2026-06-02)

The split + consolidation are **done**. `rustrade`, `janus`, `indicators-ta`,
and `exchange-apiws` are independent repos; the libraries are on crates.io and
janus consumes them:

| Crate | crates.io | Consume as |
|-------|-----------|------------|
| `rustrade-framework` (+ core/supervisor/risk/backtest) | **0.3.0** ✅ | `rustrade = { package = "rustrade-framework", version = "0.3" }` |
| `indicators-ta` | **0.1.5** ✅ | `indicators-ta = "0.1"` (imports as `indicators`) |
| `exchange-apiws` | **0.5.0** ✅ | `exchange-apiws = "0.5"` (signed Bybit + Coinbase/OKX connectors) |
| `jflow-core` (janus) | **0.1.0** ✅ | first janus lib; rest of `jflow-*` prepped, not pushed |

`fks-full` keeps only `src/proto`, `crates/spawner`, `src/ruby`, `src/web`,
infra, and `bots/` (with `strategies/` to come). The two reference bots
(`fks-bot-example`, `crypto-demo`) build as `fks-bot-*` images via
`./run.sh build-bots` and are spawnable from the WebUI `/bots`.

**Next:** turn the demo wiring into a real risk-aware multi-asset brain — see
[`docs/MULTI_ASSET_BRAIN_ROADMAP.md`](docs/MULTI_ASSET_BRAIN_ROADMAP.md).

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
> **fks-full / `bots/`** slice. The rest live in `janus/TODO.md` and
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
