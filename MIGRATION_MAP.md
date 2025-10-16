# Phase 4: Detailed Migration Map

## Migration Strategy

### Step 1: Copy Core Registry and Constants
- `assets/registry.py` → `core/registry.py`
- Create `core/constants.py` for shared constants

### Step 2: Migrate Domain to Core & Trading App
**domain/trading/** → **trading_app/**
- `strategies/` → `trading_app/strategies/`
- `indicators/` → `trading_app/indicators/`
- `backtesting/` → `trading_app/backtest/`
- `execution/` → `trading_app/execution/`
- `signals/` → `trading_app/signals/`
- `core/`, `utils/` → `trading_app/utils/`
- `api/` → `api_app/routes/trading/`

**domain/market/** → **core/models/** (market data models)
**domain/analytics/** → **trading_app/analytics/**
**domain/portfolio/** → **trading_app/portfolio/**
**domain/risk/** → **trading_app/risk/**
**domain/ml/** → **trading_app/ml/**

### Step 3: Migrate Framework to Config App & API App
**framework/config/** → **config_app/**
**framework/middleware/** → **api_app/middleware/**
**framework/exceptions/** → Already done (core/exceptions/)
**framework/logging/** → Already done (core/utils/logging.py)
**framework/cache/** → **core/cache/**
**framework/patterns/** → **core/patterns/**
**framework/services/** → **core/services/**

### Step 4: Migrate Engine & Root Files
- `engine/` → `trading_app/engine/`
- `backtest.py` → `trading_app/backtest/engine.py`
- `optimizer.py` → `trading_app/optimizer.py`
- `signals.py` → `trading_app/signals/generator.py`
- `config.py` → `config_app/manager.py`

### Step 5: Keep Data App As-Is (Minor Updates)
- Update imports only
- Already well-structured

### Step 6: Keep Worker App As-Is (Minor Updates)
- Update imports only
- Already well-structured

### Step 7: Update All Imports
- Replace `from domain.` → `from trading_app.` or `from core.`
- Replace `from framework.` → `from core.` or `from config_app.` or `from api_app.`
- Replace `from shared_python.exceptions` → `from core.exceptions`
- Replace `from data.app_logging` → `from core.utils.logging`
- Replace `from worker.fks_logging` → `from core.utils.logging`

## Execution Order

1. ✅ Create core utilities (logging, exceptions) - DONE
2. → Copy registry and constants to core
3. → Migrate framework/config to config_app
4. → Migrate domain/trading to trading_app
5. → Migrate engine and root files to trading_app
6. → Create import update script
7. → Run import updates
8. → Test imports
