# Roadmap — A Risk-Aware, Multi-Asset Trading Brain

> **The goal, in one sentence:** the **janus** brain decides *what to trade and
> how much* across different asset classes under explicit risk rules, and those
> decisions execute through the **rustrade** framework using the published
> crates (`indicators-ta`, `exchange-apiws`).
>
> **Status:** the repo split + consolidation is **done** — janus consumes the
> published crates, and `fks-full` has a working demo (`bots/crypto-demo`) that
> runs rustrade + indicators-ta + exchange-apiws together, optionally delegating
> decisions to janus via `JanusBrain`. This document is the forward plan to turn
> that wiring into the real thing.
>
> **Last updated:** 2026-06-01. Based on a full evidence-based survey of all
> five repos (see per-repo `TODO.md` for the granular checklists).

---

## The architecture we're building toward

```
                    ┌──────────────────────────────────────┐
                    │  janus (the brain — its own repo)    │
                    │                                      │
   market data ───► │  signal generation                  │
   (exchange-apiws) │   • indicator consensus (live today) │
                    │   • regime detection (built)         │
                    │   • ML / neuromorphic (built, unwired)│
                    │  risk evaluation                     │
                    │   • prop-firm rules                  │
                    │   • position sizing / stops / TP     │
                    │   • portfolio exposure / correlation │
                    │   • kill switch                      │
                    │  per-asset params (optimizer)        │
                    └───────────────┬──────────────────────┘
                                    │ REST / gRPC  (signals + risk verdicts)
                                    ▼
                    ┌──────────────────────────────────────┐
                    │  bots/* (fks-full)  — the consumers   │
                    │  JanusBrain : rustrade::Brain         │
                    │   asks janus, maps to a Decision      │
                    └───────────────┬──────────────────────┘
                                    │
                    ┌───────────────▼──────────────────────┐
                    │  rustrade (the framework)            │
                    │  Bot · Supervisor · ExecutionService │
                    │  risk gate (per-symbol + PORTFOLIO*) │
                    │  ExchangeClient ◄── exchange-apiws*  │
                    └──────────────────────────────────────┘
                       * = the two biggest framework gaps
```

`indicators-ta` (TA math) feeds both janus's signal engine and any local-strategy
bot. `exchange-apiws` provides market data **and** order execution.

---

## Where each piece actually stands (survey findings)

### ✅ Solid and reusable today
- **rustrade `Brain` contract + per-brain supervised execution** with a 4-stage
  pre-trade gate (session-halt → breaker → capability → sizing), SL+TP **bracket
  orders** with OCO sibling-cancel, order tracking + reconnect reconciliation,
  auto-PnL from fills. Per-symbol risk **with per-symbol overrides**.
- **janus signal generation (live)** — multi-symbol indicator-consensus voting
  (`services/forward/src/lib.rs`), published to a signal bus, gated by the
  `TradingPipeline` (kill-switch → regime → hypothalamus scale → amygdala →
  strategy affinity → correlation).
- **janus risk *toolkit*** — `crates/risk` (Kelly sizing, correlation tracker),
  `services/forward/src/risk/` (`RiskValidator` with portfolio exposure + daily
  loss + per-symbol limits, stop/TP calculators), `crates/models::PropFirmValidator`.
- **janus regime detection** — `crates/regime` (indicator + HMM + ensemble),
  `MarketRegime` with `recommended_strategy` / `size_multiplier`.
- **janus per-asset optimization** — `crates/optimizer` with `AssetCategory`
  (Major/L1L2/DeFi/Meme/AiCompute/Gaming/Forex) + per-class search spaces →
  `OptimizedParams` hot-reloaded by forward.
- **The published crates** — `indicators-ta` 0.1.5, `exchange-apiws` 0.5.0
  (KuCoin/Binance/Bybit/Kraken/Crypto.com/Coinbase/OKX; signed Bybit + KuCoin;
  Coinbase/OKX/Kraken WS connectors).

### ⚠️ Built but **not wired into the live path** (the "exists on disk, absent in production" gaps)
- **janus `event_loop.rs` (4,114 LOC) is orphaned** — no `mod event_loop`. The
  rich single-symbol pipeline it contains (5-strategy suite, **inline prop-firm
  enforcement on every entry**, regime gating) is **dead code**. The live loop is
  the simpler multi-symbol block in `lib.rs`.
- **janus risk enforcement is partial** — `RiskManager::apply_risk_management` and
  `PropFirmValidator` are exposed via REST for Ruby to consult, but the **live
  signal loop doesn't call them inline**. The richest enforcement lives in the
  dead `event_loop.rs`.
- **janus regime detector is under-fed live** — `RegimeManager` is never
  `update()`d in the live loop; current regime/fear are read opportunistically
  from `signal.metadata` and **nothing emits them** (JFLOW-C producer gap), so
  position guidance is effectively P&L-only today.
- **janus ML + neuromorphic** — ONNX inference (`inference.rs`) is real but
  **off by default** and not on the live path; the 251K-LOC neuromorphic stack is
  **entirely disconnected** from live trading.

### ✅ Now built (Track 1.1 + 1.3 — was the #1 blocker)
- **`exchange-apiws → rustrade::ExchangeClient` adapter** — shipped as
  `bots/rustrade-exchange-apiws/` (`KucoinExchangeAdapter`). Maps orders,
  brackets (SL/TP via `place_stop_order`), positions, balance, `cancel_all`,
  and order tracking onto KuCoin Futures; advertises `Capability` truthfully;
  resolves `contract_value` from cached contract multipliers. `crypto-demo`
  selects it with `DEMO_EXCHANGE=kucoin` (paper `MockExchange` stays default).
- **Real fills** — `KucoinFillSource` (`FillSource`) streams the exchange's
  executions in via the private `tradeOrders` WS trigger + `/recentFills`,
  enabling the framework's bracket/OCO handling; `crypto-demo` wires it on the
  live path and disables the paper simulator. *Remaining on Track 1:* surface
  `matchPrice`/`matchSize` on exchange-apiws's `OrderUpdate` (drop the REST
  hydration), and a Kraken **spot** adapter (Track 5; Bybit dropped — N/A in Canada).

### ❌ Greenfield (doesn't exist anywhere yet)
- **Portfolio-/account-level risk in rustrade.** Every `SessionPnl` /
  `CircuitBreaker` is per-symbol. No account-wide daily loss, gross/net exposure
  cap, max concurrent positions, or buying-power budget across symbols.
- **Asset-class awareness in rustrade.** `Symbol` is an opaque string; the only
  asset metadata is `contract_value: f64`. No tick/lot/min-notional, no per-class
  rule sets (crypto-perp vs spot vs FX vs futures).
- **Futures / equities** anywhere — janus's asset registry is crypto + forex only.
- **A durable `StateStore`** — rustrade's trait + in-memory impl exist and are
  wired, but no `JsonFileStore`/sqlite, so risk state doesn't survive restart.
- **A `JanusBrain` that consumes janus's *risk verdicts*** — today's `JanusBrain`
  (`bots/crypto-demo`) consumes janus *signals + a stop price*, not the prop-firm
  / portfolio / position-guidance risk engine.

---

## The plan — six tracks, sequenced

Each track lists the owning repo(s). Granular, checkable items live in each
repo's `TODO.md`; this is the cross-cutting sequence and the "why."

### Track 1 — Make execution real (highest leverage) · `rustrade` + `fks-full`
Without a real exchange adapter, nothing trades. This unblocks everything else.
1. ✅ **`exchange-apiws → rustrade::ExchangeClient` adapter.** Shipped as
   `bots/rustrade-exchange-apiws/` (`KucoinExchangeAdapter`) over `exchange-apiws`'s
   signed KuCoin Futures REST (`rest/orders`, `rest/account`, `place_stop_order`,
   `get_contract`). `Capability` is advertised truthfully (StopOrders / ReduceOnly
   / Ioc / Fok / OrderTracking yes; PostOnly no — no post-only flag on the surface);
   `contract_value` resolves from cached contract multipliers. Unit-tested against
   the published crates. ✅ **Real fills** also done — `KucoinFillSource` routes the
   exchange's executions in via the private `tradeOrders` WS + `/recentFills`,
   enabling bracket/OCO handling. *Still open:* per-execution `matchPrice`/`matchSize`
   on exchange-apiws's `OrderUpdate` (to drop the REST hydration), and a Kraken
   **spot** adapter (`KrakenPrivateClient`) — tracked in the bot TODO + Track 5.
2. **rustrade `SimulatedExchange`** (its TODO 0.3a) as the paper/backtest-fidelity
   reference — so `crypto-demo` can do realistic paper fills instead of `MockExchange`.
3. ✅ **`crypto-demo` can use the real adapter.** `DEMO_EXCHANGE=kucoin` routes
   orders through `KucoinExchangeAdapter` (needs `KC_*` creds; point them at a
   sandbox/sub-account to paper-trade the identical path). The paper `MockExchange`
   remains the default — consistent with the stack's "no autonomous execution" rule.

### Track 2 — Portfolio & asset-class risk in rustrade · `rustrade` ✅ FRAMEWORK-COMPLETE
The framework's risk tier was per-symbol only; multi-asset trading needs
account-level rules. **All five items are now merged in `rustrade` main**
(pending a `rustrade-framework` 0.3 publish before the bots can consume them):
1. ✅ **`PortfolioRisk`** in `rustrade-risk`: account-wide latching daily-loss
   halt, gross-exposure cap, max concurrent positions — checked as a third
   pre-trade gate (entries only). *(Net-exposure + an explicit buying-power
   budget remain as follow-ups; the gross-exposure cap covers most of the intent.)*
2. ✅ **`InstrumentSpec` + `AssetClass`** on `ExchangeClient::instrument_spec`:
   contract value, tick size, lot size, min notional, asset class. The execution
   service sizes from it, enforces min-notional, and snaps limit prices to the tick.
3. ✅ **Per-asset-class `RiskConfig` presets** (`crypto_perp` / `crypto_spot` /
   `fx` / `futures` / `equity` / `preset_for`) + `BotConfig::per_class_risk`,
   resolved per-symbol → per-class → default for gates *and* sizing.
4. ✅ **`RiskSweepService`** ticks per-symbol + portfolio risk on a cadence, so
   the daily-loss halt rolls over at UTC midnight in a live bot.
5. ✅ **`JsonFileStore`** durable `StateStore` — per-symbol risk survives restart
   via `Bot::with_state_store`; the portfolio halt re-derives via the sweep.

> **Bot-side, after `rustrade-framework` 0.3 is published:** bump the bots to
> 0.3, then wire `crypto-demo` with `portfolio_config(...)`, `class_risk(...)`,
> and `with_state_store(JsonFileStore::open(...))`. That's the consume step that
> makes this real in the running stack (and the natural lead-in to Track 4).

### Track 3 — Wire janus's real brain + risk into the live path · `janus`
The sophistication exists; it's just not in the running binary.
1. **Decide the fate of `event_loop.rs`**: either re-wire it (`mod event_loop` +
   entry point) or **port its capabilities** (strategy suite, inline prop-firm,
   regime gating) into the live `lib.rs` loop. Document the decision.
2. **Apply risk inline**: call `RiskManager::apply_risk_management` +
   `PropFirmValidator` on each generated signal in-loop, not just via REST.
3. **Feed the regime detector live**: `RegimeManager::update()` in the loop;
   **emit `regime` + `fear` into `signal.metadata`** (JFLOW-C producer gap) so
   position guidance stops being P&L-only.
4. **Unify the three prop-firm/risk implementations** (`crates/models::prop_firm`,
   `crates/compliance`, `crates/logic::risk_engine`) into one.

### Track 4 — The janus↔rustrade contract · `fks-full` (`bots/`) + `janus`
Make `JanusBrain` consume janus's *risk verdicts*, not just signals.
1. **Extend the janus brain API** (or use the existing `/api/v1/risk/evaluate` +
   `/api/v1/positions/event`) so a bot can ask "given this signal + my current
   portfolio, what size / stop / should I even trade?" and get a verdict that
   already accounts for prop-firm + portfolio limits.
2. **`JanusBrain` v2** in `bots/`: send portfolio state + position with each
   request; honor janus's `GuidanceAction` (Hold/Reduce/Exit) and sizing verdict;
   map to a rustrade `Decision` with the janus-computed stop/TP/size.
3. **Position-event feedback loop**: the bot reports fills/closes back to
   `/api/v1/positions/{event,close}` so janus's affinity learning sees outcomes.

### Track 5 — Multi-asset breadth · `janus` + `exchange-apiws`
1. **Futures + equities asset classes** in janus's `AssetCategory` + registry
   (currently crypto + forex only) — class params, liquidity tiers, venues.
2. **exchange-apiws signed surface for more venues** (its own roadmap B/C):
   Kraken (spot) + Binance private REST/WS, private user-data streams — so
   non-KuCoin venues can execute, not just stream. *(Bybit is available in
   exchange-apiws but unused — not tradeable from Canada.)*
3. **Optimizer emits `stop_loss_pct` / `take_profit_pct`** (the Python side) so
   per-asset risk params actually flow (today they default).

### Track 6 — Backtest & validation fidelity · `rustrade` + `janus`
You can't trust a multi-asset risk brain you can't backtest faithfully.
1. **rustrade backtest applies the risk gates** (today it doesn't) + **honors
   limit/stop fills** (today taker-at-close) + **funding model** for perps.
2. **Portfolio-level backtest metrics** (expectancy, avg win/loss, per-asset).
3. **janus's 30-day neuromorphic live-validation gate** before treating
   ML/neuromorphic output as authoritative (its TODO P3).

---

## Suggested order of attack

1. ✅ **Track 1** — exchange adapter + real fills (`bots/rustrade-exchange-apiws/`):
   orders, brackets, and `KucoinFillSource` real fills flow through the framework.
   Remaining: the `OrderUpdate` match-price enhancement and a Kraken spot adapter.
2. ✅ **Track 2** — portfolio + asset-class risk in `rustrade` (all five items
   merged: PortfolioRisk, InstrumentSpec/AssetClass, class presets, risk sweep,
   `JsonFileStore`). **Framework-complete; pending a `rustrade-framework` 0.3 publish.**
3. **← LEADING EDGE: publish + consume.** Publish `rustrade-framework` 0.3, bump
   the bots, and wire `crypto-demo` (`portfolio_config` + `class_risk` +
   `with_state_store`) — the step that puts Tracks 1–2 into the running stack.
4. **Track 4** — `JanusBrain` v2 consuming risk verdicts. Connects the two halves.
5. **Track 3** — wire janus's real brain/risk inline. The brain gets serious.
6. **Tracks 5 & 6** — breadth (Kraken spot, futures/equities) + backtest
   validation, in parallel as capacity allows.

The first three turn the existing demo into a genuine paper-trading system with
janus making risk-aware, multi-symbol decisions through rustrade. Everything after
deepens the brain and broadens the asset universe.

---

## Cross-references

- `fks-full/TODO.md` — orchestration + the `bots/` consumer work (Tracks 1.3, 4).
- `janus/TODO.md` — brain/risk wiring, multi-asset breadth (Tracks 3, 5).
- `janus/CONSOLIDATION_PLAN.md` — the (now complete) crate-consumption history.
- `rustrade/TODO.md` — exchange adapter, portfolio risk, durable store, backtest
  fidelity (Tracks 1, 2, 6).
- `exchange-apiws/todo.md` — signed surfaces for more venues (Track 5.2).
- `indicators-ta` — no TODO yet; see this repo's note in `fks-full/TODO.md`.
