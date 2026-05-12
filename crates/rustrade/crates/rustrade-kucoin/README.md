# rustrade-kucoin

KuCoin Futures `ExchangeClient` adapter for the
[rustrade](https://github.com/nuniesmith/rustrade) trading-bot framework.

Bridges the published [`exchange-apiws`](https://crates.io/crates/exchange-apiws)
KuCoin client into rustrade's narrow [`ExchangeClient`] trait so any
rustrade-based bot can trade KuCoin Futures without depending on KuCoin
specifics directly.

```toml
[dependencies]
rustrade-kucoin = "0.1"
```

## Quick start

```rust,ignore
use std::sync::Arc;
use exchange_apiws::{Credentials, KuCoin, KucoinEnv};
use rustrade_core::ExchangeClient;
use rustrade_kucoin::KucoinExchangeAdapter;

let creds  = Credentials::new(api_key, api_secret, passphrase);
let kucoin = KuCoin::new(creds, KucoinEnv::LiveFutures).rest_client()?;
let leverage = 5;
let adapter: Arc<dyn ExchangeClient> =
    Arc::new(KucoinExchangeAdapter::new(Arc::new(kucoin), leverage));
```

## Design notes

- **Leverage is per-adapter at construction time** — the recommended v0
  design from rustrade's `DESIGN_NOTES.md`. Per-account leverage covers
  95% of strategies. Build a second adapter with different leverage if
  you need both at once.
- **Contract-multiplier table** for major USDT-margined contracts
  (`XBTUSDTM` = 0.001 BTC, `ETHUSDTM` = 0.01 ETH, etc.). Unknown symbols
  log a warning and fall back to `1.0`. Add a missing symbol by
  extending `contract_value_for`.
- **Escape hatch via `.client()`** for service-specific calls outside the
  framework trait surface (stop orders, kline history, account overview).

## License

MIT — see `LICENSE`.
