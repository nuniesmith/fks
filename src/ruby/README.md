# fks-ruby

**Python trading system for FKS — source code only.**

This repo contains the Python backend that powers the FKS trading platform: market data ingestion, signal generation, CNN model training, execution routing, paper trading, and FastAPI REST/SSE APIs. Infrastructure (Docker, compose, CI/CD) lives in [fks](https://github.com/nuniesmith/fks).

---

## What's here

| Package | Role |
|---------|------|
| `src/ml/` | CNN training pipeline, feature engineering, labeling, inference |
| `src/analysis/` | ICT structure, CVD, confluence, regime detection, sentiment |
| `src/indicators/` | EMA, RSI, VWAP, ATR, Bollinger, volume profile, candle patterns |
| `src/trading/` | RB breakout strategy, swing detector, daily bias, multi-TP |
| `src/integrations/` | Kraken, Rithmic, MassiveAPI, TradingView, Pine script generator, Grok |
| `src/model/` | Ensemble, deep (LSTM/TFT/NN), statistical (GARCH/HMM/ARIMA), prediction |
| `src/data/` | Data factory: gap scanner, backfill manager, chain monitor, news pipeline, dataset generator |
| `src/services/` | Execution gate, risk engine, Redis store, config loader, circuit breaker |
| `src/core/` | Asset registry (29 assets + source routing), contracts, schema, formatters |
| `src/workers/` | Per-asset async workers |
| `src/web/` | Futures bot HTMX app (pending API-only split — see FUTURES-MERGE in todo) |
| `sql/` | Postgres migrations (001–008) |
| `tests/` | 5,351+ tests across all modules |

## Architecture

Ruby runs as three supervised processes inside a single container (`supervisord`):

```
fks_ruby
├── data service   :8000  — market data, factory, chain, news, asset registry
├── engine service :8050  — signals, pipeline, trades, execution, sessions
└── web service    :8080  — futures bot API (being converted to API-only)
```

All three expose FastAPI REST + SSE endpoints. No UI is served from this repo — the WebUI lives in [fks-web](https://github.com/nuniesmith/fks-web).

**Signal flow (Ruby's role):**
```
Alertmanager → AlertmanagerSignalMonitor (Ruby)
    ├── prop-firm → WebUI only (manual execution)
    ├── personal-crypto → Kraken API (auto)
    └── hardware-wallet → monitor only
```

**Champion model:** CNN v10 — 93.5% accuracy, 37 features, 6 CME symbols combined.

**Training assets:** `MGC SIL MES MNQ M2K MYM` + crypto expansion in progress.

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -x -q

# Run a specific service locally (needs .env)
python -m src.services.data.main
python -m src.services.engine.main

# Generate Pine Script indicator
python -m src.integrations.pine.main
```

Required env vars are documented in [fks/.env.example](https://github.com/nuniesmith/fks/blob/main/.env.example).

## Key design principles

- **Janus never executes.** Ruby is the only execution layer. Janus generates signals → Alertmanager → Ruby decides what to do.
- **No autonomous prop-firm orders.** All Rithmic execution requires manual confirmation in the WebUI.
- **Data factory always runs.** Gap scanner, backfill manager, and dataset generator run continuously so the trainer always has fresh data.
- **Source of truth for asset routing.** The asset registry in `src/core/asset_registry.py` defines which data source backs each symbol and is queried by Janus, the data factory, charting, and execution.

## Deployment

Deployed via [fks](https://github.com/nuniesmith/fks). The Dockerfile in that repo clones this repo at build time and builds from source. No Docker config lives here.

## Stats

- ~296K lines of Python
- 5,351+ tests
- 499 `.py` files
- 60+ FastAPI route files
- 8 Postgres migrations
