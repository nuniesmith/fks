# indicators-ta — TODO

> **Repo (future):** `github.com/nuniesmith/indicators-ta`
> **Last synced:** 2026-05-10

## P0 — Pre-publish

- [ ] **`cargo publish --dry-run`** — fix anything it complains about.
- [ ] **README polish** — make sure it's self-contained, no `fks-full` path references.
- [ ] **License file** — add `LICENSE` (MIT) at the directory root before the repo carve-out.
- [ ] **CI** — GitHub Actions workflow (`check`, `test`, `clippy`, `fmt`, optional `cargo doc`).

## P1 — Coverage gaps

- [ ] **Doc-tests** on the headline types (EMA, RSI, MACD, Bollinger). One per indicator demonstrating the streaming-update pattern.
- [ ] **Benchmarks** — `criterion` benches for the per-tick hot paths so regressions are visible. Today there are unit tests for correctness but no perf gate.

## P2 — Absorb generic janus indicators

Per `crates/janus/JANUS_EXTRACTION_PLAN.md` Phase 1:
- [ ] Lift `IncrementalEma` (and `IncrementalAtr` if missing) from `crates/janus/crates/indicators/` so the consumers in `crates/janus/crates/backtest/` can switch. Lib name is already `indicators`, so import paths don't change.
- [ ] Decide whether to absorb `janus-regime` (HMM + router, ~5K LOC) here or in a separate `regime-router-ta` crate. Plan recommendation: separate crate; revisit once a second consumer exists.

## P3 — Future

- [ ] **No-std support** behind a `std` feature flag — opens the door to embedded / WASM bot brains. Most indicators are math-only, so the lift should be small.
