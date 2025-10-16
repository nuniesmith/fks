# Phase 4 Progress: Code Migration

## ✅ Completed (Part 1)

### 1. Unified Logging Module (`core/utils/logging.py`)
**Consolidated from:**
- `src/data/app_logging.py` - JSON logging, basicConfig
- `src/worker/fks_logging.py` - StreamHandler wrapper

**Features:**
- JSON and standard logging formatters
- Environment-based configuration (`FKS_JSON_LOGS`, `FKS_LOG_LEVEL`)
- Convenience functions: `log_trade()`, `log_signal()`
- Consistent logging across all apps

**Usage:**
```python
from core.utils.logging import get_logger

logger = get_logger(__name__)
logger.info("Trading signal", extra={"symbol": "BTCUSDT"})
```

### 2. Unified Exceptions Module (`core/exceptions/__init__.py`)
**Consolidated exceptions from:**
- `framework/middleware/error.py` - ApplicationError, HTTP errors
- `framework/middleware/circuit_breaker/exceptions.py` - Circuit breaker errors
- `worker/ensemble.py` - EnsembleError
- Various `shared_python.exceptions` imports

**Exception Hierarchy:**
```
FKSException (base)
├── DataError
│   ├── DataFetchError
│   ├── DataValidationError
│   └── DataStorageError
├── TradingError
│   ├── SignalError
│   ├── StrategyError
│   ├── BacktestError
│   └── OrderError
├── ModelError
│   ├── ModelTrainingError
│   ├── ModelPredictionError
│   └── ModelNotFoundError
├── ConfigError
│   ├── ConfigValidationError
│   └── ConfigNotFoundError
├── ApplicationError (HTTP)
│   ├── BadRequestError (400)
│   ├── UnauthorizedError (401)
│   ├── ForbiddenError (403)
│   ├── NotFoundError (404)
│   └── ConflictError (409)
├── CircuitBreakerError
│   ├── CircuitOpenError
│   └── StateTransitionError
├── TaskError
│   └── EnsembleError
├── RateLimitError
├── DatabaseError
│   ├── ConnectionError
│   └── QueryError
└── AuthenticationError/AuthorizationError
```

**Benefits:**
- Single import point for all exceptions
- Consistent error structure with `.to_dict()` method
- HTTP status codes for API errors
- Rich error context with `details` dict

## 🔄 Next Steps (Part 2)

1. **Copy/Merge Domain Models to Core**
   - Move `domain/trading/` models to `core/models.py`
   - Update imports throughout codebase

2. **Migrate Framework to Config App**
   - Move `framework/config/` to `config_app/`
   - Move `config.py` to `config_app/manager.py`

3. **Consolidate Trading Logic**
   - Move `domain/trading/` to `trading_app/`
   - Move `engine/`, `backtest.py`, `optimizer.py` to `trading_app/`
   - Move indicators to `trading_app/indicators/`

4. **Update All Imports**
   - Replace `from shared_python.exceptions import` with `from core.exceptions import`
   - Replace `from data.app_logging import` with `from core.utils.logging import`
   - Update all other import paths

5. **Test Imports**
   - Verify no circular dependencies
   - Run basic import tests
