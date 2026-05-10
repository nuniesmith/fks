# exchange-apiws — TODO

> **Repo (future):** `github.com/nuniesmith/exchange-apiws`
> **Last synced:** 2026-05-10

## P0 — Pre-publish

- [ ] **`cargo publish --dry-run`** — fix anything it complains about.
- [ ] **README split** — `README.md` is ~655 lines. Trim the headline to overview + quickstart, move full KuCoin REST reference to `docs/KUCOIN.md`.
- [ ] **License file** — add `LICENSE` (MIT) at the directory root before the repo carve-out.
- [ ] **CI** — `cargo check / test / clippy / fmt` workflow.

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
