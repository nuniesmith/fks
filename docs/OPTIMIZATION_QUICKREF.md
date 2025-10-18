# Optimization Quick Reference

Fast reference for Phase 2.4 optimization features.

## 🚀 Quick Start

```python
# 1. Fetch data with protection
from data.adapters.binance import BinanceAdapter
adapter = BinanceAdapter()
result = adapter.fetch(symbol="BTCUSDT", interval="1d", limit=100)

# 2. Optimize parameters
from trading.optimizer.engine import OptunaOptimizer
optimizer = OptunaOptimizer(df_prices, n_trials=50, n_jobs=2)
results = optimizer.optimize()

# 3. Run fast backtest
from trading.backtest.engine import run_backtest
metrics, returns, cum_ret, trades = run_backtest(
    df_prices, fast_mode=True, **results['best_params']
)
```

## 📊 Circuit Breaker States

| State | Description | Next State |
|-------|-------------|------------|
| CLOSED | Normal operation | OPEN (after 3 failures) |
| OPEN | Blocking requests | HALF_OPEN (after 60s) |
| HALF_OPEN | Testing recovery | CLOSED (2 successes) or OPEN (1 failure) |

## 🎯 Key Metrics

### Backtest Metrics
```python
{
    'Sharpe': 1.54,           # > 1 is good, > 2 is excellent
    'Sortino': 2.12,          # Higher is better
    'Max Drawdown': -0.15,    # -15%, lower magnitude is better
    'Calmar': 0.87,           # Return / |MaxDD|
    'Total Return': 0.45,     # 45%
    'Annualized Return': 0.52, # 52%
    'Trades': 12              # Number of round trips
}
```

### Circuit Breaker Metrics
```python
metrics = adapter.get_circuit_metrics()
{
    'name': 'binance_api',
    'state': 'closed',        # closed, open, or half_open
    'failure_count': 0,
    'success_count': 5,
    'config': {
        'failure_threshold': 3,
        'reset_timeout': 60,
        'success_threshold': 2
    }
}
```

### Rate Limiter Stats
```python
stats = adapter.get_rate_limit_stats()
{
    'name': 'binance_rate_limit',
    'limit': 10,              # requests
    'time_window': 1,         # seconds
    'total_requests': 150,
    'allowed_requests': 148,
    'rejected_requests': 2
}
```

## ⚙️ Configuration Cheatsheet

### Binance Adapter
```python
# Default configuration (auto-applied)
circuit_breaker:
  failure_threshold: 3      # failures before opening
  reset_timeout: 60        # seconds to wait
  success_threshold: 2     # successes to close
  timeout: 30             # request timeout

rate_limiter:
  max_requests: 10        # requests
  time_window: 1          # seconds
  policy: "wait"          # wait for token
  max_wait_time: 5.0      # seconds
```

### OptunaOptimizer
```python
OptunaOptimizer(
    df_prices=df_prices,
    n_trials=100,           # optimization trials
    n_jobs=4,               # parallel workers (-1 = all CPUs)
    timeout=600,            # seconds (None = unlimited)
    rag_service=None,       # optional RAG integration
)
```

### Backtest Engine
```python
run_backtest(
    df_prices,
    M=20,                   # moving average period (5-200)
    atr_period=14,          # ATR period (5-30)
    sl_multiplier=2.0,      # stop loss multiplier (1-5)
    tp_multiplier=3.0,      # take profit multiplier (1-10)
    fast_mode=True          # 3x speedup
)
```

## 🔥 Common Patterns

### Pattern 1: Quick Optimization
```python
# For rapid testing
optimizer = OptunaOptimizer(df_prices, n_trials=20, n_jobs=2)
results = optimizer.optimize()
```

### Pattern 2: Production Optimization
```python
# For production deployment
optimizer = OptunaOptimizer(
    df_prices, 
    n_trials=500, 
    n_jobs=-1,  # all CPUs
    timeout=3600  # 1 hour
)
results = optimizer.optimize()
importance = optimizer.get_param_importance()
```

### Pattern 3: RAG-Enhanced Optimization
```python
# With LLM suggestions
from services.rag_service import RAGService
rag = RAGService(use_local=True)
optimizer = OptunaOptimizer(df_prices, n_trials=100, rag_service=rag)
results = optimizer.optimize()
```

### Pattern 4: Safe Data Fetching
```python
# With error handling
from framework.middleware.circuit_breaker.exceptions import CircuitOpenError

adapter = BinanceAdapter()
try:
    result = adapter.fetch(symbol="BTCUSDT")
except CircuitOpenError as e:
    print(f"Circuit open, retry in {e.retry_after_seconds}s")
    time.sleep(e.retry_after_seconds)
    result = adapter.fetch(symbol="BTCUSDT")
```

## 🐛 Troubleshooting

### Circuit Breaker Won't Close
```python
# Manually reset
adapter.circuit_breaker.reset()
```

### Rate Limit Exceeded
```python
# Check current stats
stats = adapter.get_rate_limit_stats()
print(f"Used: {stats['total_requests']}/{stats['limit']}")

# Wait for window to reset
time.sleep(stats['time_window'])
```

### Optimization Too Slow
```python
# Reduce trials or increase parallelization
optimizer = OptunaOptimizer(
    df_prices,
    n_trials=20,  # fewer trials
    n_jobs=-1     # max parallelization
)
```

### Backtest Out of Memory
```python
# Use slow mode
run_backtest(..., fast_mode=False)

# Or reduce data size
df_prices = {k: v.tail(100) for k, v in df_prices.items()}
```

## 📈 Performance Tips

| Scenario | Recommendation | Expected Speedup |
|----------|---------------|------------------|
| Small dataset (< 100 days) | fast_mode=True | 2-3x |
| Large dataset (> 500 days) | fast_mode=True | 3-4x |
| Quick test | n_trials=20 | Complete in < 1 min |
| Production | n_trials=500, n_jobs=-1 | Best parameters |
| Memory constrained | fast_mode=False | Use slow mode |

## 🎓 Parameter Ranges

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| M | 5-200 | 20 | Moving average period |
| atr_period | 5-30 | 14 | ATR calculation period |
| sl_multiplier | 1.0-5.0 | 2.0 | Stop loss multiplier |
| tp_multiplier | 1.0-10.0 | 3.0 | Take profit multiplier |

**Typical Good Values**:
- Trending markets: M=50-100, sl=2.5, tp=5.0
- Range-bound: M=10-20, sl=1.5, tp=2.0
- High volatility: M=30-60, atr=20, sl=3.0

## 📝 Quick Commands

```bash
# Run example script
python examples/optimize_strategy.py

# Run tests
pytest tests/unit/test_trading/test_binance_rate_limiting.py -v
pytest tests/unit/test_trading/test_backtest_optimization.py -v
pytest tests/unit/test_trading/test_optuna_optimizer.py -v

# Check imports work
python -c "from data.adapters.binance import BinanceAdapter; print('OK')"
python -c "from trading.optimizer.engine import OptunaOptimizer; print('OK')"
```

## 🔗 Quick Links

- Full Guide: `docs/OPTIMIZATION_GUIDE.md`
- Examples: `examples/optimize_strategy.py`
- Tests: `tests/unit/test_trading/`
- Optuna Docs: https://optuna.readthedocs.io/

## 💡 Pro Tips

1. **Start small**: Test with n_trials=20 before running 500 trials
2. **Use fast_mode**: 3x speedup with no accuracy loss
3. **Monitor circuit**: Check `get_circuit_metrics()` regularly
4. **Save history**: `optimizer.get_optimization_history().to_csv()`
5. **Check importance**: See which parameters matter most
6. **Parallel optimization**: Set n_jobs=-1 for all CPUs
7. **RAG is optional**: Works fine without LLM suggestions

## ⚡ One-Liners

```python
# Quick fetch
adapter = BinanceAdapter(); data = adapter.fetch(symbol="BTCUSDT")

# Quick optimize
results = OptunaOptimizer(df_prices, n_trials=20).optimize()

# Quick backtest
metrics, *_ = run_backtest(df_prices, M=20, atr_period=14, fast_mode=True)

# Quick importance
importance = optimizer.get_param_importance()
```

## 🎯 Success Checklist

Before deploying:
- [ ] Tested with n_trials=20
- [ ] Reviewed parameter importance
- [ ] Validated with backtest
- [ ] Checked Sharpe > 1.0
- [ ] Max drawdown acceptable
- [ ] Circuit breaker works
- [ ] Rate limiting works
- [ ] Saved optimization history
- [ ] Documented parameters
- [ ] Tested error handling

---

**Version**: 2.4.0  
**Updated**: October 2025  
**Status**: Production Ready ✅
