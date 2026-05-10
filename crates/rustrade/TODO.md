# rustrade — TODO

> **Repo (future):** `github.com/nuniesmith/rustrade`
> **Last synced:** 2026-05-10
>
> Open work for the open-source trading framework. See `NEXT_STEPS.md`
> for the historical phased build plan and `CONTRIBUTING.md` for the
> design invariants every PR has to respect.

---

## P0 — Pre-publish blockers

> Must be true before any `cargo publish` happens.

- [ ] **Convert remaining `workspace = true` deps to explicit versions** in every crate that ships to crates.io. `rustrade-supervisor` is already done. `rustrade-core`, `-risk`, `-backtest`, `-notify`, `-kucoin`, and the facade `rustrade` need the same treatment.
- [ ] **Audit each crate's `Cargo.toml` for crates.io readiness**:
  - `description`, `license`, `repository`, `keywords`, `categories` populated
  - `publish = true` set (or remove `publish = false` if present)
  - No `path = "..."` deps on anything that won't be on crates.io
  - README path resolves
- [ ] **Bollard 0.19 deprecation migration** in `rustrade-kucoin` (and anywhere else it pops up). Replace `bollard::container::*Options` with the `bollard::query_parameters::*OptionsBuilder` types. Mechanical change, ~half day, but it removes the `#![allow(deprecated)]` shim.
- [ ] **CI** — add a GitHub Actions workflow that runs `cargo check --workspace`, `cargo test --workspace`, `cargo fmt --check`, `cargo clippy --workspace -- -D warnings` on every PR. Doesn't exist yet because the workspace lived inside `fks-full`.

## P1 — Repo split prep

- [ ] **Self-contained README** — the current `README.md` references neighbouring `fks-full` paths in a few places. Audit and either remove or replace with public-repo equivalents.
- [ ] **Verify `cargo check --workspace` from a fresh clone** of just `crates/rustrade/` (after the split) works — no dangling parent-workspace references.
- [ ] **Pick a license headline** — `MIT` is in every `Cargo.toml` but there's no top-level `LICENSE` file in this directory. Add one before the repo carve-out.
- [ ] **Decide on `rustrade-kucoin`'s home** — publish from inside the rustrade workspace, or extract to its own `rustrade-kucoin` repo. Recommendation: publish from rustrade for v0.1; extract later if it grows.

## P1 — Framework gaps

- [ ] **Phase 1 sub-task 1c from `JANUS_EXTRACTION_PLAN.md`** — once `janus-regime` is decided on (port HMM/router upstream, lift to public sibling, or keep private), absorb whatever pieces are generic enough into the framework.
- [ ] **More exchange adapters** — `rustrade-bybit`, `rustrade-binance`, mirroring `rustrade-kucoin`. Each is ~270 LOC including tests + docs. Pattern documented in `CONTRIBUTING.md`.

## P2 — Quality of life

- [ ] **`rustrade-prometheus` feature** — opt-in Prometheus registry for `SupervisorMetrics`. Today, downstream binaries read the atomic counters and publish themselves (see how `fks-full/crates/janus/bin/janus/` does it). A small feature-gated module here would save duplication once we have 3+ downstream binaries.
- [ ] **Example that exercises the full risk layer** — `rustrade-risk` has 13 tests but no example binary that walks through circuit-breaker + session-PnL + sizing together. A "demo bot under stress" example would document the contract better than the tests.
- [ ] **Doc-test the `Brain` trait** — every example should appear as a doctest so `cargo test --doc` catches drift.

## P3 — Future

- [ ] **Multi-exchange routing** in `ExecutionService` — fan out one decision to multiple adapters per the routing rules. Today `ExecutionService` owns a single `Arc<dyn ExchangeClient>`.
- [ ] **`rustrade-memory`** — replay buffer + Qdrant-backed embedding storage for ML brains. Discussed in `JANUS_EXTRACTION_PLAN.md` Phase 2.
- [ ] **Polars-backed OHLCV loaders** in `rustrade-backtest` behind a `polars` feature flag. Today the backtest engine takes `Vec<Candle>` and the loaders live elsewhere.

---

## ✅ Recently shipped (PRs #1–#10 in `fks-full`)

- Supervisor port + `rustrade-supervisor` skeleton (PR #1)
- Facade crate `rustrade` + `noop-bot` example (PR #2)
- `ExchangeClient::contract_value()` + first concrete adapter (`rustrade-kucoin`) (PR #3)
- `kucoin-v2` production-shaped example (PR #4)
- `rustrade-backtest` replay engine + sim exchange + metrics (PR #5)
- Doc-coverage pass — `#![warn(missing_docs)]` on every framework crate (PR #6)
- `JANUS_EXTRACTION_PLAN.md` (PR #7) + reality-check (#9)
- `rustrade-notify` — Discord webhooks as supervised services (PR #8)
- `CONTRIBUTING.md` with the 5 design invariants (PR #10)
- `fks-bot-example` reference image for the FKS spawner (PR #17)
- `rustrade-supervisor` dep-pinning (in #19 / "Janus port") so it works as a cross-workspace path dep
