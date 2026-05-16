# rustrade — TODO

> **Repo (future):** `github.com/nuniesmith/rustrade`
> **Last synced:** 2026-05-13
>
> Open work for the open-source trading framework. See `NEXT_STEPS.md`
> for the historical phased build plan and `CONTRIBUTING.md` for the
> design invariants every PR has to respect.

---

## P0 — Pre-publish blockers

> Must be true before any `cargo publish` happens. See the root
> `PRE_PUBLISH_AUDIT.md` for the per-crate publishability matrix and
> the dependency-ordered `cargo publish` execution script.

- [ ] **Convert remaining `workspace = true` deps to explicit versions** in every crate that ships to crates.io. `rustrade-supervisor` is already done (PR series merged into `main` before #23). `rustrade-core`, `-risk`, `-backtest`, `-notify`, `-kucoin`, and the facade `rustrade` need the same treatment **only if** they're consumed from a foreign workspace. If they're only consumed from inside the rustrade workspace + crates.io, the workspace inheritance is fine — cargo resolves `version = "0.1.0"` from the rustrade-* crates' published versions at publish time.
- [ ] **`cargo publish --dry-run` per crate**, in dependency order. Blocked on the upstream crate being live for downstream dry-runs; see the chicken-and-egg note in `PRE_PUBLISH_AUDIT.md`.

## P1 — Framework gaps

- [ ] **Phase 1 sub-task 1c from `JANUS_EXTRACTION_PLAN.md`** — once `janus-regime` is decided on (port HMM/router upstream, lift to public sibling, or keep private), absorb whatever pieces are generic enough into the framework.
- [ ] **More exchange adapters** — `rustrade-bybit`, `rustrade-binance`, mirroring `rustrade-kucoin`. Each is ~270 LOC including tests + docs. Pattern documented in `CONTRIBUTING.md`.

## P2 — Quality of life

- [ ] **`rustrade-prometheus` feature** — opt-in Prometheus registry for `SupervisorMetrics`. Today, downstream binaries read the atomic counters and publish themselves (see `crates/janus/bin/janus/` for the pattern). A small feature-gated module here would save duplication once we have 3+ downstream binaries.
- [ ] **Example that exercises the full risk layer** — `rustrade-risk` has 13 tests but no example binary that walks through circuit-breaker + session-PnL + sizing together. A "demo bot under stress" example would document the contract better than the tests.
- [ ] **Doc-test the `Brain` trait** — every example should appear as a doctest so `cargo test --doc` catches drift.

## P3 — Future

- [ ] **Multi-exchange routing** in `ExecutionService` — fan out one decision to multiple adapters per the routing rules. Today `ExecutionService` owns a single `Arc<dyn ExchangeClient>`.
- [ ] **`rustrade-memory`** — replay buffer + Qdrant-backed embedding storage for ML brains. Discussed in `JANUS_EXTRACTION_PLAN.md` Phase 2.
- [ ] **Polars-backed OHLCV loaders** in `rustrade-backtest` behind a `polars` feature flag. Today the backtest engine takes `Vec<Candle>` and the loaders live elsewhere.

---

## ✅ Recently shipped

The 0.1 framework arc — PRs #1–#10 in `fks-full`:

- Supervisor port + `rustrade-supervisor` (PR #1)
- Facade crate `rustrade` + `noop-bot` example (PR #2)
- `ExchangeClient::contract_value()` + first concrete adapter (`rustrade-kucoin`) (PR #3)
- `kucoin-v2` production-shaped example (PR #4)
- `rustrade-backtest` replay engine + sim exchange + metrics (PR #5)
- Doc-coverage pass — `#![warn(missing_docs)]` on every framework crate (PR #6)
- `JANUS_EXTRACTION_PLAN.md` (PR #7) + reality-check (#9)
- `rustrade-notify` — Discord webhooks as supervised services (PR #8)
- `CONTRIBUTING.md` with the 5 design invariants (PR #10)

Plus the publish-readiness arc — PRs #11–#29 in `fks-full`:

- `fks-bot-example` reference image for the FKS spawner (PR #17)
- `rustrade-supervisor` dep-pinning so it works as a cross-workspace path dep
- **PR #22:** `[workspace]` block added to `indicators-ta` + `exchange-apiws` so they're standalone workspaces; root `TODO.md` refresh
- **PR #23:** `.github/workflows/rust.yml` — per-workspace `check / test / clippy / fmt` matrix
- **PR #24:** CI green-up — `--locked` gated per workspace, clippy soft-failed, broken `indicators-ta` test fixed, fmt drift applied
- **PR #25:** `PRE_PUBLISH_AUDIT.md` (per-crate publishability matrix) [not merged — superseded by PR #27]
- **PR #26:** Per-crate `README.md` + `LICENSE` for every `rustrade-*` crate
- **PR #27:** `PRE_PUBLISH_AUDIT.md` with `cargo package` findings + chicken-and-egg explanation
- **PR #28:** `paths-ignore` on `rust.yml` so doc-only PRs skip the matrix
- **PR #29:** `[package].exclude` on `indicators-ta` + `exchange-apiws` to slim publishable tarballs

The workspace-level `LICENSE` and the missing `readme = "README.md"` lines flagged in earlier versions of this TODO were closed by PR #26. The `fks-full` README references were verified clean in PR #29's prep grep. The bollard 0.19 migration item that used to live here was misattributed — bollard is `crates/spawner/`'s dep, not `rustrade-kucoin`'s, so that work belongs in `crates/spawner/TODO.md`.
