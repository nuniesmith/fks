---
title: "Ruby — Python Trading System"
category: "ruby"
tags: ["python", "fastapi", "trading", "execution", "indicators", "cnn"]
---

# Ruby — Python Trading System

Ruby is the Python layer of the FKS stack. It handles market data ingestion,
indicator computation, CNN model inference, trade execution, and the HTMX
terminal dashboard. It runs inside `fks_ruby` under `supervisord` with four
supervised programs.

## Programs

| Program | Port | Role |
|---------|------|------|
| `data` | `:8000` | FastAPI REST + SSE + execution engine |
| `engine` | — | ML inference, regime detection, risk, scheduler |
| `factory` | — | Data pipeline, news feed, on-chain data |
| `web` | `:8080` | HTMX terminal dashboard (served by FastAPI) |

## Source Layout

```
src/ruby/
├── entrypoints/          # Supervisord entry points per program
│   ├── data/             # FastAPI data service
│   ├── engine/           # Trading engine
│   ├── training/         # Model training runner
│   └── web/              # Web dashboard
├── lib/
│   ├── analysis/         # Strategy analysis and scoring
│   ├── core/             # DB layer, migration, config, core utilities
│   ├── data_factory/     # Data pipeline: bars, ticks, news, on-chain
│   ├── indicators/       # Technical indicators (EMA, RSI, ATR, etc.)
│   ├── integrations/     # Exchange clients (Kraken, Rithmic, MassiveAPI)
│   ├── model/            # CNN model loader, registry, inference
│   ├── services/         # Service modules (data, engine, web)
│   ├── trading/          # Execution engine, position management, signals
│   └── utils/            # Shared utilities
├── scripts/              # Maintenance and migration scripts
└── tests/                # pytest test suite
```

## Documents in This Directory

| File | Description |
|------|-------------|
| [architecture.md](architecture.md) | Service layout, data flow, and component interactions |
| [STRATEGY_PLAN.md](STRATEGY_PLAN.md) | Asset strategy plan and breakout system design |
| [logging.md](logging.md) | Logging standards and structured log format |
| [news.md](news.md) | News feed integration and sentiment processing |
| [rithmic_notes.md](rithmic_notes.md) | Rithmic integration notes (historical comparison) |
| [rithmic_massive_integration.md](rithmic_massive_integration.md) | Rithmic + MassiveAPI data integration design |

## Data Hierarchy

```
Rithmic (primary — CME L1/L2)
  → MassiveAPI (CME REST beta)
    → Yahoo Finance (fallback)
      → Kraken (crypto)
```

## Execution Model

- **Prop firms (Rithmic):** Signal display only — trader presses "SEND ALL" manually
- **Personal crypto:** Automated execution via Kraken / crypto.com API
- **Hardware wallets:** Monitor-only (xpub balance, no private keys)

All Rithmic orders carry `MANUAL` flag + 200–800 ms humanized delay. No
autonomous orders on prop accounts — ever.

## Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection string (production) |
| `DB_PATH` | `futures_journal.db` | SQLite fallback path (dev/tests only) |
| `DATA_DIR` | `/tmp/fks` | Root for model registry and data artifacts |
| `DISABLE_REDIS` | `0` | Set to `1` to skip Redis in tests |
| `RITHMIC_LIVE_DATA` | `0` | Enable live Rithmic market data feed |

## Related Docs

- [Architecture overview](../architecture/ARCHITECTURE.md)
- [Janus (Rust engine)](../janus/README.md)
- [Exchange integrations](../exchanges/README.md)
- [Testing guides](../testing/README.md)