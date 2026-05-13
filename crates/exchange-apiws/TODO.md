# exchange-apiws — TODO

> **Repo (future):** `github.com/nuniesmith/exchange-apiws`
> **Last synced:** 2026-05-13

## P0 — Pre-publish

- [ ] **`cargo publish --dry-run`** — runs cleanly today per the `cargo package` smoke in `PRE_PUBLISH_AUDIT.md` (26 files, 73 KiB compressed after PR #29's `[package].exclude`). Actual `cargo publish` is the next step — needs the crates.io token.
- [ ] **Verify version `0.1.10` is still claimable** (or the next one is) — `cargo search exchange-apiws` before publish. If a previous upload exists, bump to `0.1.11`.
- [ ] **README split** — `README.md` is ~655 lines. Trim the headline to overview + quickstart, move full KuCoin REST reference to `docs/KUCOIN.md`. Not strictly a blocker, but the long README will be the first impression on crates.io.

## P1 — Coverage gaps

- [ ] **Mocked tests** for every REST endpoint and WS subscription. `wiremock` for HTTP, in-memory channels for WS. Today some endpoints are exercised live during dev; that's not OK for a published crate.
- [ ] **Error type audit** — every public function should return `Result<_, exchange_apiws::Error>` (one enum). Avoid `anyhow::Result` in library surface.

## P1 — Second venue

- [ ] **Bybit module** — port the relevant bits of `crates/janus/crates/bybit-client/` into `src/bybit/`. Same shape as `src/kucoin/`. Then `crates/janus/crates/bybit-client/` becomes deletable.

## P2 — Quality of life

- [ ] **Rate-limiter integration** — today the client makes a single attempt per call. A shared rate-limiter (token bucket per venue) is a natural fit at this layer.
- [ ] **Re-connect policy for WS** — currently the consumer (e.g. `rustrade-kucoin`) handles reconnect. Consider an opt-in `auto_reconnect` flag on the WS client.

## P3 — Future

- [ ] **Trait-ify** — abstract `RestClient` + `WsClient` traits so consumers can be venue-agnostic. Today the consumer picks a concrete `KuCoin` and works with it directly.

---

## ✅ Recently shipped

- `LICENSE` and `README.md` already present at crate root.
- `[workspace]` block added in PR #22 so this crate is its own workspace root (cargo no longer hunts the parent tree).
- Per-workspace CI job in `.github/workflows/rust.yml` (PR #23) — passing.
- Auto-formatted by `cargo fmt` in PR #24's CI green-up (the `HeaderValue::from_str` `From` impl rewrite).
- `[package].exclude` added in PR #29 to slim the published tarball (31 → 26 files).
- README references verified `fks-full`-free in PR #29 prep.
