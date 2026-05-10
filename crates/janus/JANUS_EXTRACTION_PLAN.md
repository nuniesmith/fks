# Janus Extraction Plan

> **Status:** plan only — no code moved yet. Companion to
> `crates/rustrade/NEXT_STEPS.md` step 5.
>
> **2026-05-06 update:** I tried to start phase 1 and hit three real
> blockers the original plan glossed over. The "Findings from
> attempted execution" section below captures them. The phase 1 section
> further down has been corrected; the rest of the plan still stands.

---

## Findings from attempted execution

When PR #7 (this plan) merged, I started phase 1 (delete
`janus-indicators` + `janus-regime` + `janus-backtest` and migrate
consumers). Three blockers surfaced that the original survey didn't
catch:

### 1. `janus-regime` is NOT a duplicate of `indicators-ta`

The original plan grouped `janus-regime` with `janus-indicators` as
"already covered by `indicators-ta`". That was wrong.

`janus-regime` is **~5,000 lines across 7 files**:

```
detector.rs       760  ADX/Bollinger/ATR/EMA-based regime classifier
ensemble.rs       754  combines indicator + HMM detectors
hmm.rs            845  Hidden Markov Model regime detector
indicators.rs    1057  per-detector indicator helpers
router.rs         961  EnhancedRouter — strategy selection per regime
types.rs          538  RegimeConfig, RoutedSignal, etc.
```

The HMM + router code has **no equivalent in `indicators-ta`**.
Deleting `janus-regime` would lose this functionality unless either
(a) it's ported into `indicators-ta` upstream, or (b) it stays as a
private crate, or (c) it lifts into a new public sibling
`regime-router-ta`. **Decision needed before phase 1 can complete.**

We should port any new code that would be math and indicators into indicators-ta, so HMM and router code might be good with indicators-ta and then use it with janus

### 2. `janus-indicators::IncrementalEma` is missing from `indicators-ta`

`indicators-ta` exposes a struct `EMA` with different warmup
semantics (averages first `period` bars, returns NaN until ready).
`janus-indicators::IncrementalEma` initialises on the *first* tick
(uses it as the initial state). These are not interchangeable for
backtest replay code that expects per-tick output starting from bar 1.

`crates/janus/crates/backtest/src/replay.rs` uses `IncrementalEma`.
Migrating it requires either:
- Adding `IncrementalEma` to `indicators-ta` upstream, or
- Inlining the ~30-line struct into the consumer, or
- Keeping `janus-indicators` private as a thin compatibility shim.

The struct is small enough that **option (b) — inline it — is the
pragmatic path**, since `crates/janus/crates/backtest/` is itself
slated for deletion (replaced by `rustrade-backtest`).

### 3. `bin/backtest-cli` uses APIs `rustrade-backtest` MVP doesn't expose

`bin/backtest-cli/src/main.rs` imports from
`janus_backtest::ohlcv_loader::*` (parquet/CSV loaders) and
`janus_backtest::strategy_backtester::*` (a different replay surface
from `rustrade-backtest`'s `BacktestEngine`).

`rustrade-backtest` MVP intentionally deferred parquet/CSV loaders
("write your own `Vec<Candle>` for now"). Migrating the CLI requires
either:
- Lifting `ohlcv_loader.rs` (~1,700 lines) into `rustrade-backtest`
  behind a `polars` feature flag, or
- Rewriting the CLI to use the simpler `BacktestEngine` API + roll
  its own parquet/CSV loading code, or
- Keeping `bin/backtest-cli` on `janus-backtest` until both
  alternatives mature.

### 4. `bin/janus` still uses `JanusSupervisor`

The plan suggested `lib/janus-core/src/supervisor/` could be deleted
to prevent drift from `rustrade-supervisor`. But `bin/janus/src/main.rs`
still imports `JanusSupervisor`, `BackoffConfig`, `ApiModuleAdapter`,
`SpawnOptions`, `ModuleAdapter` from it. Deleting the supervisor
module from `janus-core` means rewriting `bin/janus/main.rs` to use
`rustrade::Bot` (mirror of the kucoin-v2 port).

That's a real port — analogous in scope to the kucoin-v2 PR, just
inside the janus repo.

### Net implication

Phase 1 is **not 1–2 days of mechanical work**. It's:
- ~3–5 days of structural decisions (regime routing, IncrementalEma,
  ohlcv loaders) and ports
- Or it can be split into smaller, less ambitious phase-1 sub-tasks

See "Revised phase 1" below.

---

This document maps every sub-crate in `crates/janus/` to one of three
destinations:

| Destination | What goes there |
|---|---|
| **A. Public siblings** | Generic, exchange-agnostic crates published alongside `indicators-ta` and the `rustrade-*` framework. Open-source MIT, anyone can `cargo add` them. |
| **B. Private janus repo** | Domain-specific brain IP — neuromorphic regions, prop-firm compliance, FKS-specific glue. Lives in a private repo that depends on `rustrade + indicators-ta + the public siblings`. |
| **C. Stay in fks-full** | Service binaries, FKS-only configuration, the v1 supervisor plumbing already replaced by `rustrade-supervisor`. Eventually deletable; keep until v2 has parity. |

The headline guarantee: **after this extraction, `rustrade` ships
publicly, the brain ships privately, and neither knows about the other
beyond the `Brain` trait surface.**

---

## Survey results (all 23 sub-crates + lib + services)

Internal dependency graph (from each `Cargo.toml`):

```
indicators       → (none)
regime           → (none)
strategies       → indicators, models, regime
risk             → (none)
models           → (none)
bybit-client     → (none)
compliance       → (none)
health           → (none)
logic            → (none)
common           → (none)
rate-limiter     → (none)
gap-detection    → (none)
memory           → (none)
dsp              → (none)
ltn              → (none)
exchanges        → janus-core, janus-cns
data-quality     → janus-core, gap-detection, cns
ml               → janus-core, data-quality
lob              → janus-core
optimizer        → janus-core, backtest, indicators, strategies, models
cns              → (none)
training         → (none)
questdb-writer   → (none)
registry         → (none)
backtest         → models, indicators, strategies, risk, compliance, regime
neuromorphic     → common (+ fks-proto)
```

**Eighteen sub-crates have zero internal `janus-*` deps.** That's the
loudest signal in this survey: most of janus is *already* loosely
coupled — the framework move is overdue, not premature.

---

## A. Publish as public siblings

These are domain-agnostic and either already work or need only
mechanical decoupling. They join `indicators-ta` and the `rustrade-*`
crates as MIT-licensed publishable crates.

| Crate | Lift verbatim? | Notes |
|---|---|---|
| `janus-rate-limiter` | yes | Token bucket. Rename: `rate-limiter-ta` (or fold into a shared `trading-utils`). Zero deps. |
| `janus-gap-detection` | yes | Time-series gap detection. Generic. |
| `janus-dsp` | yes | FFT + fractal-adaptive filters. Generic; `rustfft`-backed. |
| `janus-lob` | almost | Limit order book simulator. Drop the `janus-core` dep — it's only used for one type alias that has a stdlib equivalent. |
| `janus-memory` | yes | Qdrant vector DB wrapper. Could become `qdrant-trading-utils` or merge with a future `rustrade-memory` for replay buffers. |
| `janus-ltn` | yes | Logic Tensor Networks — a generic ML primitive, not strategy code. |
| `janus-data-quality` | needs decoupling | Drop `janus-core` + `janus-cns` deps. Keep the gap-detection dep. Generic data-quality assertions. |
| `janus-ml` | needs decoupling | Drop `janus-core` + `data-quality` deps OR keep them by making them feature-gated. |
| `janus-bybit-client` | yes | Sibling of `exchange-apiws`. Wrap with a `rustrade-bybit` adapter (mirroring `rustrade-kucoin`). |

**Notable: `janus-indicators` and `janus-regime` overlap `indicators-ta`.**
The published `indicators-ta` already exposes `Indicators`,
`MarketRegime{Tracker}`, `LiquidityProfile`, `ConfluenceEngine`,
`MarketStructure`, `CVDTracker`, `VolatilityPercentile`,
`SignalStreak`, `compute_signal`. Recommendation: **delete
`janus-indicators` and `janus-regime`**, migrate strategies to use
`indicators-ta` (lib name `indicators` already matches — the import
lines don't change). This is the single biggest cleanup.

---

## B. Private janus repo (depends on rustrade)

These are the brain IP. They move to a private repo (e.g.
`github.com/nuniesmith/janus-private`) that depends on `rustrade +
exchange-apiws + indicators-ta + the public siblings`.

| Crate | Why private |
|---|---|
| `janus-strategies` | Concrete strategies (EMA flip, Bollinger squeeze, VWAP, ORB, …). Each becomes a `Brain` impl. Could also be split — some are "common knowledge" patterns that could publish, others are tuned edge. |
| `janus-compliance` | Prop-firm rules. Specific to your prop-firm relationships. |
| `janus-models` | Account / prop-firm / performance types tuned to your accounts. |
| `janus-cns` | Central Nervous System coordination layer. FKS-specific. |
| `janus-logic` | Differentiable Logic Tensor Networks for the neuromorphic brain. Same crate as `ltn`? — needs investigation. If different, this stays private. |
| `janus-training` | Training pipeline tied to your data + prop firm. |
| `janus-optimizer` | Optuna-driven param search. References strategies + backtest — pull it private. |
| `janus-neuromorphic` | The brain itself: cortex, amygdala, basal_ganglia, cerebellum, distributed runtime, GPU code. The single biggest reason janus is private. |

**No shared `Strategy` / `Brain` trait in `crates/strategies/`.**
Each strategy is a concrete struct with its own per-bar API. Private
janus repo will need:

```rust
// In each strategy file (or a shared adapter module):
impl rustrade::Brain for EmaFlipBrain {
    fn name(&self) -> &str { "ema-flip" }
    async fn on_event(&self, event: &MarketDataEvent, position: &Position)
        -> Result<Decision> { ... }
}
```

The wrapping is mechanical — each strategy already has a "given new
candle, output signal" method that maps directly onto
`Brain::on_event`. Estimate: 1 hour per strategy × ~10 strategies = 1
day total.

---

## C. Stay in `fks-full` (eventually deletable)

These are FKS-the-application — service binaries, supervisor
plumbing already replaced by rustrade, FKS-specific health/registry.

| Crate | Why it stays | Action |
|---|---|---|
| `bin/janus`, `bin/backtest-cli` | App binaries | Reshape to use rustrade::Bot like kucoin-v2 did. |
| `services/{api, backward, cns, data, execution, forward, optimizer, registry}` | FKS service binaries | These ARE the FKS app. Keep. |
| `lib/janus-core` | Pre-rustrade supervisor + FKS-specific config | Migrate consumers off `janus-core::supervisor` to `rustrade-supervisor`. Then delete. |
| `lib/janus-api` | FKS HTTP API surface | Keep. |
| `janus-backtest` | Replaced by `rustrade-backtest` | Delete after migrating consumers. |
| `janus-health`, `janus-registry`, `janus-questdb-writer` | FKS service utilities | Keep. |
| `apalis-redis` | Vendored crate | Stays vendored. |

---

## Migration order (low-risk first)

The order minimises broken builds and keeps `kucoin-v2` running at
every step.

### Phase 1 — Cleanup (NOT as low-risk as originally estimated)

> **2026-05-06 revision:** the original phase 1 was 1–2 days; the
> findings above push it to 3–5 days because of the regime-routing,
> IncrementalEma, and ohlcv-loader gaps. The sub-tasks below are
> ordered by independence, so partial completion is fine.

#### 1a. Decouple `janus-data-quality` + `janus-ml` (truly low-risk)

Drop `janus-core` / `janus-cns` deps from `janus-data-quality` and
`janus-ml`, or feature-gate them. **~half day.** No external blockers.

#### 1b. Decide on `janus-regime` (decision-bound)

Pick one of:
- **(a)** Port HMM + router upstream into `indicators-ta` as a new
  module — biggest blast radius, biggest payoff.
- **(b)** Lift `janus-regime` into a new public sibling
  `regime-router-ta` (or similar). Stays MIT-licensed, ~5K LOC
  cleanup needed.
- **(c)** Keep `janus-regime` as a private crate inside the eventual
  janus-private repo.

Recommendation: **(c) for v0** — the router code is tightly
strategy-coupled and not obviously generic. Revisit after a second
strategy stack uses regime routing.

#### 1c. Delete `janus-indicators` (after 1b)

After regime is settled:
1. Inline `IncrementalEma` (and `IncrementalAtr` if also missing
   from `indicators-ta`) into `crates/backtest/src/replay.rs` or a
   new shared utility module — ~30 LOC each.
2. Migrate all `use janus_indicators::*` imports to `use indicators::*`.
   The lib name matches; mostly Cargo.toml + use-statement swaps.
3. Delete `crates/janus/crates/indicators/`.

#### 1d. Migrate the supervisor

`bin/janus/src/main.rs` uses `JanusSupervisor`, `BackoffConfig`,
`ApiModuleAdapter`, `SpawnOptions`, `ModuleAdapter` from
`janus-core::supervisor`. Port it to `rustrade::Bot` like
`kucoin-v2` was ported. **~1 day** (kucoin-v2 was ~115 lines of
new `main.rs`; janus's is similar in scope).

After this lands, delete `crates/janus/lib/janus-core/src/supervisor/`
to prevent drift from `rustrade-supervisor`.

#### 1e. Delete `janus-backtest` (decision-bound)

Pick one of:
- **(a)** Lift `ohlcv_loader.rs` (~1,700 LOC) into `rustrade-backtest`
  behind a feature flag. Then migrate `bin/backtest-cli` and
  `crates/optimizer` to `rustrade-backtest`. Delete `janus-backtest`.
- **(b)** Keep `bin/backtest-cli` running on `janus-backtest` until
  someone needs the ergonomic CLI elsewhere. `janus-backtest` becomes
  a thin private crate; `crates/optimizer` either moves with it or
  rewrites against `rustrade-backtest`.

Recommendation: **(b)** — the CLI is fks-internal tooling. Don't
spend a day migrating it before janus-private even exists.

### Phase 2 — Publish public siblings

For each crate in **A** above:

4. Lift to a top-level `crates/<name>/` directory (alongside
   `crates/indicators-ta/` and `crates/exchange-apiws/`).
5. Make it a standalone workspace (own `[workspace]` block + pinned
   versions, no `workspace = true` inheritance).
6. Add `publish = true`, `repository`, `keywords`, `categories`,
   `description`, `readme`.
7. Add `#![warn(missing_docs)]` and fill any gaps.
8. `cargo publish --dry-run`.

Recommended publish order (smallest to largest blast radius):

   a. `janus-rate-limiter` → publish as e.g. `trading-rate-limiter`
   b. `janus-gap-detection` → `gap-detection-ta`
   c. `janus-dsp` → `trading-dsp`
   d. `janus-lob` → `lob-sim` (or fold into `rustrade-backtest` as a
      feature-gated module)
   e. `janus-memory` → `trading-memory` (or merge into a future
      `rustrade-memory` for replay buffers)
   f. `janus-ltn` → standalone publishable
   g. `janus-data-quality` → after phase 1 decoupling
   h. `janus-ml` → after phase 1 decoupling
   i. `janus-bybit-client` + a new `rustrade-bybit` adapter crate

### Phase 3 — Move private janus to its own repo

9. Create `github.com/nuniesmith/janus-private` (or similar).
10. Migrate the **B** crates verbatim — they keep their existing
    structure, just move directories.
11. Update the new repo's `Cargo.toml` to depend on `rustrade +
    indicators-ta + the public siblings` from crates.io (after phase
    2 publishes them).
12. Wrap each strategy with a `Brain` impl. ~1 day total.
13. Re-run kucoin-v2-style ports of any remaining FKS bots that
    consumed the strategies.

### Phase 4 — Archive `crates/janus/`

14. After everything in **C** has migrated to `rustrade-*` consumers,
    delete `crates/janus/` from `fks-full`.
15. The fks-full repo at this point is just: `crates/{rustrade*,
    indicators-ta, exchange-apiws}`, `src/{proto, spawner, kucoin-v2,
    ruby, web}`, infrastructure. Smaller, faster builds.

---

## Effort estimates

| Phase | Effort | Blocking? |
|---|---|---|
| 1a. Decouple data-quality/ml | ~half day | Lands in fks-full, no blockers |
| 1b. Decide regime fate | discussion only | Decision-bound |
| 1c. Delete janus-indicators (after 1b) | ~half day | Needs 1b decision |
| 1d. Migrate `bin/janus` to `rustrade::Bot` | ~1 day | Independent |
| 1e. Decide janus-backtest fate | ~half day to ~1 day | Decision-bound |
| 2. Publish public siblings | 0.5–1 day per crate × 9 = ~1 week of focused time | Each crate independent |
| 3. Private janus repo move + Brain wrappers | 1–2 days | Needs the private repo to exist |
| 4. Archive `crates/janus/` | 1 day | After C migrates |

**Total: 3–4 focused weeks** if done sequentially. Phase 1 is now
3–5 days (was 1–2). Phase 2 is unchanged since the public-sibling
crates are independent of each other.

**The cheapest progress today is sub-task 1a + 1d** (decouple
data-quality/ml + port `bin/janus` to `rustrade::Bot`). Both are
independent of the open decisions and total ~1.5 days of work.

---

## Decisions needed from you (before phase 2 starts)

These are decisions only you can make. Phase 1 doesn't need them; it
can start immediately.

### 1. Crate naming

The public siblings need stable names. The published `indicators-ta`
sets a precedent of "indicators-ta", "exchange-apiws". Options:

- **`-ta` suffix** (matching `indicators-ta`): `dsp-ta`, `lob-ta`,
  `gap-detection-ta`, … — consistent, niche-flavoured.
- **`trading-` prefix**: `trading-dsp`, `trading-lob`,
  `trading-gap-detection` — clearer for crates.io browsers.
- **`rustrade-` prefix** for tightly-tied ones: `rustrade-lob`,
  `rustrade-memory` — brings them under the framework brand.

My pick: a **mix** — DSP/gap-detection/LOB use `-ta` because they're
trading-adjacent but fundamentally generic numeric utilities;
memory/replay-buffer goes `rustrade-` because it's framework-tied.

### 2. Repo strategy

- **Mono-repo** (`github.com/nuniesmith/rustrade` containing all
  framework + adapter crates as a workspace) — easier to develop, one
  git history.
- **Per-crate repos** (`github.com/nuniesmith/{rustrade,
  rustrade-kucoin, indicators-ta, …}`) — each crate has its own
  release cadence; matches the crates.io pattern.

The `indicators-ta` and `exchange-apiws` crates already point at
their own repo URLs in `Cargo.toml`, suggesting per-crate. If you
want the framework crates to follow that, **say so and I can flip
the URLs**. If you want a single `rustrade` mono-repo, also fine —
the workspace structure already supports that.

### 3. Private janus location

- Pre-existing repo somewhere I should know about?
- New private repo on the same `nuniesmith` user/org?
- Or just a different branch of fks-full that's never pushed public?

### 4. License

`rustrade-*` and `indicators-ta` are MIT. Public siblings: also MIT?
Or AGPL the strategies and MIT the primitives?

---

## What I can do without those decisions

Phase 1 (cleanup) is fully independent and unblocks everything else.
Specifically, I can land:

1. Delete `janus-indicators` + `janus-regime`, migrate to
   `indicators-ta`. ~1 day.
2. Decouple `janus-data-quality` + `janus-ml` from
   `janus-core`/`janus-cns`. ~half day.
3. Delete `janus-backtest`, migrate `optimizer` + `bin/backtest-cli`
   to `rustrade-backtest`. ~half day.

That gets `crates/janus/` to a clean separable boundary without
moving any code outside fks-full. After that, your decisions above
gate phase 2.

---

## Risks / open questions

- **`janus-strategies` does NOT use a shared `Strategy` trait.** Each
  strategy is a concrete struct with its own update method. The
  janus-private repo will need a `Brain` wrapper per strategy. Not
  hard, but it's not a copy-paste either.
- **`indicators-ta` is at `0.1.3`; `janus-indicators` may have local
  changes.** Need to diff before deleting. If `janus-indicators` has
  drifted, options are: PR upstream to `indicators-ta`, fork
  `indicators-ta`, or keep `janus-indicators` private as a fork.
- **`fks-proto` is consumed by `services/api/backward/cns/data` and
  by `neuromorphic`.** Those services + neuromorphic stay coupled to
  fks-full's proto layer; private janus can keep `fks-proto` as a
  dep. Or extract `fks-proto` itself into a publishable
  `trading-protos` crate (separate decision).
- **`crates/janus/lib/janus-core/src/supervisor/`** is the *original*
  source of the `rustrade-supervisor` port. After phase 1 it should
  be deleted from `crates/janus/` — keeping two supervisor codebases
  in the tree invites drift.
