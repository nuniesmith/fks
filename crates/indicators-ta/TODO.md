# indicators-ta — TODO

> **Repo (future):** `github.com/nuniesmith/indicators-ta`
> **Last synced:** 2026-05-13

## P0 — Pre-publish

- [ ] **`cargo publish --dry-run`** — runs cleanly today per the `cargo package` smoke in `PRE_PUBLISH_AUDIT.md` (62 files, 128 KiB compressed after PR #29's `[package].exclude`). Actual `cargo publish` is the next step — needs the crates.io token.
- [ ] **Verify version `0.1.3` is still claimable** (or the next one is) — `cargo search indicators-ta` before publish. If a previous upload exists, bump to `0.1.4`.

## P1 — Coverage gaps

- [ ] **Doc-tests** on the headline types (EMA, RSI, MACD, Bollinger). One per indicator demonstrating the streaming-update pattern.
- [ ] **Benchmarks** — `criterion` benches for the per-tick hot paths so regressions are visible. Today there are unit tests for correctness but no perf gate.

## P2 — Absorb generic janus indicators

Per `crates/janus/JANUS_EXTRACTION_PLAN.md` Phase 1:

- [ ] Lift `IncrementalEma` (and `IncrementalAtr` if missing) from `crates/janus/crates/indicators/` so the consumers in `crates/janus/crates/backtest/` can switch. Lib name is already `indicators`, so import paths don't change.
- [ ] Decide whether to absorb `janus-regime` (HMM + router, ~5K LOC) here or in a separate `regime-router-ta` crate. Plan recommendation: separate crate; revisit once a second consumer exists.

## P3 — Future

- [ ] **No-std support** behind a `std` feature flag — opens the door to embedded / WASM bot brains. Most indicators are math-only, so the lift should be small.

---

## ✅ Recently shipped

- `LICENSE` and `README.md` already present at crate root.
- `[workspace]` block added in PR #22 so this crate is its own workspace root (cargo no longer hunts the parent tree).
- Per-workspace CI job in `.github/workflows/rust.yml` (PR #23) — passing.
- Broken test (`tests/registry_fuzz.rs::all_indicators_calculate_succeeds_with_ample_data`) fixed in PR #24's CI green-up.
- `[package].exclude` added in PR #29 to slim the published tarball (69 → 62 files).
- README references verified `fks-full`-free in PR #29 prep.
