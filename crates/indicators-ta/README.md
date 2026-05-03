# indicators-ta

[![Crates.io](https://img.shields.io/crates/v/indicators-ta.svg)](https://crates.io/crates/indicators-ta)
[![Docs.rs](https://docs.rs/indicators-ta/badge.svg)](https://docs.rs/indicators-ta)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Technical analysis indicators and market regime detection for algorithmic trading, written in Rust.

## Features

- **Batch functions** — `ema()`, `sma()`, `atr()`, `rsi()`, `macd()` over price slices
- **Incremental structs** — O(1) per-tick `EMA` and `ATR` with SMA warm-up
- **11-layer signal engine** — VWAP, EMA, ML SuperTrend, Trend Speed, Liquidity Profile, Confluence, Market Structure, CVD, Awesome Oscillator, Hurst exponent, Price Acceleration
- **Market regime detection** — indicator-based, Hidden Markov Model (HMM), and ensemble methods
- **Strategy router** — maps detected regime to a recommended trading strategy

## Quick Start — Batch Indicators

```rust
use indicators::{ema, rsi, atr};

let closes = vec![22.27, 22.19, 22.08, 22.17, 22.18, 22.10, 22.65];
let ema9   = ema(&closes, 9)?;

let highs  = vec![22.50, 22.40, 22.30, 22.40, 22.45, 22.30, 22.80];
let lows   = vec![22.10, 22.00, 21.90, 22.00, 22.05, 21.95, 22.50];
let atr14  = atr(&highs, &lows, &closes, 14)?;
```

## Quick Start — Signal Engine

```rust
use indicators::{
    Indicators, ConfluenceEngine, LiquidityProfile, MarketStructure,
    CVDTracker, VolatilityPercentile, SignalStreak, compute_signal,
};

let mut ind    = Indicators::new(&s);
let mut liq    = LiquidityProfile::new(s.liq_period, s.liq_bins);
let mut conf   = ConfluenceEngine::new(s.conf_ema_fast, s.conf_ema_slow,
                                       s.conf_ema_trend, s.conf_rsi_len, s.conf_adx_len);
let mut ms     = MarketStructure::new(s.struct_swing_len, s.struct_atr_mult);
let mut cvd    = CVDTracker::new(s.cvd_slope_bars, s.cvd_div_lookback);
let mut vol    = VolatilityPercentile::new(200);
let mut streak = SignalStreak::new(s.signal_confirm_bars);

// Per-candle update loop
// for candle in candles {
//     ind.update(&candle);
//     liq.update(&candle);
//     conf.update(&candle);
//     ms.update(&candle);
//     cvd.update(&candle);
//     vol.update(ind.atr);
//     let (raw, _) = compute_signal(candle.close, &ind, &liq, &conf, &ms, &s, Some(&cvd), Some(&vol));
//     if streak.update(raw) { /* confirmed signal — act */ }
// }
```

## Quick Start — Regime Detection

```rust
use indicators::EnsembleRegimeDetector;

let mut det = EnsembleRegimeDetector::default_config();

// for (high, low, close) in bars {
//     det.update(high, low, close);
//     if det.is_ready() {
//         println!("{}", det.regime());
//     }
// }
```

## Regime Types

| Regime          | Recommended Strategy |
|-----------------|----------------------|
| `Trending`      | Trend Following      |
| `MeanReverting` | Mean Reversion       |
| `Volatile`      | Reduced Exposure     |
| `Uncertain`     | Stay Cash            |

## Signal Modes

The signal engine supports three aggregation modes via `BotSettings::signal_mode`:

- **`"majority"`** — Core layers must agree; at least 2 extended layers confirm *(default)*
- **`"strict"`** — All core and extended layers must align
- **`"any"`** — Core layers only, no extended confirmation required

## License

MIT — see [LICENSE](LICENSE).
