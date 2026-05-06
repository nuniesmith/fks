# Janus Extraction Plan

> **Status:** plan only — no code moved yet. Companion to
> `crates/rustrade/NEXT_STEPS.md` step 5.

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

### Phase 1 — Cleanup (low-risk, can land in fks-full first)

1. **Delete `janus-indicators` + `janus-regime`.** Migrate
   `crates/strategies/`, `crates/backtest/`, `crates/optimizer/`, and
   the bin to `indicators-ta`. The lib name `indicators` already
   matches; mostly just `Cargo.toml` swaps.
2. **Decouple `janus-data-quality` and `janus-ml`** from `janus-core`
   / `janus-cns`. Either drop the deps or feature-gate them.
3. **Delete `janus-backtest`.** Migrate `optimizer` + the CLI to
   `rustrade-backtest`. Reshape `crates/backtest-cli/src/main.rs`.

After phase 1: `crates/janus/` has a clean separable boundary. No code
has moved repos yet.

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
| 1. Cleanup (`indicators` migration, decouple data-quality/ml, delete janus-backtest) | 1–2 days | Lands in fks-full |
| 2. Publish public siblings | 0.5–1 day per crate × 9 = ~1 week of focused time | Each crate independent — can park between |
| 3. Private janus repo move + Brain wrappers | 1–2 days | Needs the private repo to exist |
| 4. Archive `crates/janus/` | 1 day | After C migrates |

**Total: 2–3 focused weeks** if done sequentially. Most of phase 2
can run in parallel since the public siblings are independent crates.

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
