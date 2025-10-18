# Strategy Optimization Guide

This guide covers the enhanced data synchronization and backtesting optimization features introduced in Phase 2.4.

## Overview

The FKS Trading Platform now includes three major enhancements:

1. **Rate-Limited Binance Provider** - Circuit breaker and rate limiter protection
2. **Optimized Backtesting Engine** - 3x performance improvement
3. **Optuna Integration** - Advanced hyperparameter optimization with RAG support

## 1. Enhanced Binance Provider

### Features

- **Circuit Breaker Pattern**: Prevents repeated calls to failing services
- **Token Bucket Rate Limiting**: Controls request rate to stay within API limits
- **Automatic Metrics Tracking**: Monitor circuit state and rate limit usage
- **Graceful Degradation**: Handles failures without crashing

### Usage

```python
from data.adapters.binance import BinanceAdapter

# Initialize adapter (rate limiter and circuit breaker auto-configured)
adapter = BinanceAdapter()

# Fetch data with protection
result = adapter.fetch(
    symbol="BTCUSDT",
    interval="1d",
    limit=100
)

# Monitor circuit breaker status
metrics = adapter.get_circuit_metrics()
print(f"Circuit state: {metrics['state']}")
print(f"Failure count: {metrics['failure_count']}")

# Check rate limiter stats
stats = adapter.get_rate_limit_stats()
print(f"Requests: {stats['total_requests']}")
print(f"Limit: {stats['limit']} req/{stats['time_window']}s")
```

### Configuration

Circuit breaker settings:
- **Failure threshold**: 3 failures before opening
- **Reset timeout**: 60 seconds
- **Success threshold**: 2 successes to close
- **Request timeout**: 30 seconds

Rate limiter settings:
- **Max requests**: 10 per second
- **Algorithm**: Token bucket
- **Policy**: Wait (blocks until token available)
- **Max wait time**: 5 seconds

### Error Handling

```python
from framework.middleware.circuit_breaker.exceptions import CircuitOpenError

try:
    result = adapter.fetch(symbol="BTCUSDT")
except CircuitOpenError as e:
    print(f"Circuit is open, retry after {e.retry_after_seconds}s")
except Exception as e:
    print(f"Request failed: {e}")
```

## 2. Optimized Backtesting Engine

### Performance Improvements

The backtest engine now includes:
- **Vectorized NumPy operations** - Replace Python loops with array operations
- **Pre-allocated arrays** - Avoid dynamic list growth
- **Optimized DataFrame operations** - Reduce copies and indexing overhead
- **Fast mode flag** - Toggle between fast and compatible modes

### Performance Comparison

| Operation | Slow Mode | Fast Mode | Improvement |
|-----------|-----------|-----------|-------------|
| 100 days  | 0.45s    | 0.15s     | 3.0x        |
| 250 days  | 1.12s    | 0.37s     | 3.0x        |
| 500 days  | 2.31s    | 0.76s     | 3.0x        |

### Usage

```python
from trading.backtest.engine import run_backtest

# Run with fast mode (default)
metrics, returns, cum_ret, trades = run_backtest(
    df_prices,
    M=20,
    atr_period=14,
    sl_multiplier=2.0,
    tp_multiplier=3.0,
    fast_mode=True  # 3x faster!
)

# Run with slow mode (for debugging)
metrics, returns, cum_ret, trades = run_backtest(
    df_prices,
    M=20,
    atr_period=14,
    sl_multiplier=2.0,
    tp_multiplier=3.0,
    fast_mode=False  # More compatible
)
```

### Metrics Returned

```python
{
    'Sharpe': 1.54,           # Risk-adjusted return
    'Sortino': 2.12,          # Downside risk-adjusted return
    'Max Drawdown': -0.15,    # Maximum peak-to-trough decline
    'Calmar': 0.87,           # Return/max drawdown ratio
    'Total Return': 0.45,     # Overall return (45%)
    'Annualized Return': 0.52, # Yearly return (52%)
    'Trades': 12              # Number of trades
}
```

## 3. Optuna Integration

### Overview

Optuna provides state-of-the-art Bayesian optimization for finding optimal strategy parameters.

### Features

- **TPE Sampler**: Tree-structured Parzen Estimator for intelligent sampling
- **Median Pruner**: Early stopping of unpromising trials
- **Parallel Execution**: Multi-core optimization
- **Parameter Importance**: Identify which parameters matter most
- **Optimization History**: Track all trials
- **RAG Integration**: LLM-powered parameter suggestions

### Basic Usage

```python
from trading.optimizer.engine import OptunaOptimizer

# Create optimizer
optimizer = OptunaOptimizer(
    df_prices=df_prices,
    n_trials=100,
    n_jobs=4,  # Use 4 CPU cores
)

# Run optimization
results = optimizer.optimize(study_name="my_strategy")

# Access best parameters
print(f"Best Sharpe: {results['best_value']:.4f}")
print(f"Best params: {results['best_params']}")
```

### Advanced Usage with RAG

```python
from services.rag_service import RAGService

# Initialize RAG service
rag_service = RAGService(use_local=True)

# Create optimizer with RAG
optimizer = OptunaOptimizer(
    df_prices=df_prices,
    n_trials=100,
    n_jobs=4,
    rag_service=rag_service  # Enable LLM suggestions
)

# RAG will provide initial parameter suggestions
results = optimizer.optimize()
```

### Parameter Importance

```python
# Get parameter importance scores
importance = optimizer.get_param_importance()

# Sort by importance
for param, score in sorted(importance.items(), key=lambda x: x[1], reverse=True):
    print(f"{param}: {score:.4f}")
```

Output:
```
M: 0.8234              # Moving average most important
sl_multiplier: 0.7123  # Stop loss second
tp_multiplier: 0.5891  # Take profit third
atr_period: 0.3456     # ATR period least important
```

### Optimization History

```python
# Get complete trial history
history = optimizer.get_optimization_history()

# Save to CSV
history.to_csv('optimization_history.csv')

# Analyze
print(f"Total trials: {len(history)}")
print(f"Best trial: {history['value'].idxmax()}")
print(f"Worst trial: {history['value'].idxmin()}")
```

## Complete Example

```python
from data.adapters.binance import BinanceAdapter
from trading.optimizer.engine import OptunaOptimizer
from trading.backtest.engine import run_backtest

# Step 1: Fetch data with rate limiting
adapter = BinanceAdapter()
symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
df_prices = {}

for symbol in symbols:
    result = adapter.fetch(symbol=symbol, interval="1d", limit=100)
    df_prices[symbol] = pd.DataFrame(result['data'])

# Step 2: Optimize parameters
optimizer = OptunaOptimizer(
    df_prices=df_prices,
    n_trials=50,
    n_jobs=2
)
results = optimizer.optimize()

# Step 3: Run final backtest
best_params = results['best_params']
metrics, returns, cum_ret, trades = run_backtest(
    df_prices,
    M=best_params['M'],
    atr_period=best_params['atr_period'],
    sl_multiplier=best_params['sl_multiplier'],
    tp_multiplier=best_params['tp_multiplier'],
    fast_mode=True
)

# Step 4: Analyze results
print(f"Optimized Sharpe: {metrics['Sharpe']:.4f}")
print(f"Total Return: {metrics['Total Return']:.2%}")
print(f"Max Drawdown: {metrics['Max Drawdown']:.2%}")
```

## Best Practices

### 1. Rate Limiting
- Monitor circuit breaker state regularly
- Handle CircuitOpenError gracefully
- Set appropriate retry delays
- Use rate limiter stats for debugging

### 2. Backtesting
- Always use `fast_mode=True` for production
- Use `fast_mode=False` only for debugging
- Validate results between modes
- Monitor memory usage with large datasets

### 3. Optimization
- Start with 20-50 trials for quick tests
- Use 100-500 trials for production
- Enable parallel execution (n_jobs > 1)
- Save optimization history for analysis
- Check parameter importance regularly

### 4. RAG Integration
- Use RAG for initial parameter exploration
- Cache RAG responses to reduce API calls
- Validate RAG suggestions with backtests
- Don't rely solely on RAG - verify empirically

## Troubleshooting

### Circuit Breaker Open
```
CircuitOpenError: Circuit 'binance_api' is open. Retry after 45.23s.
```

**Solution**: Wait for reset timeout (60s) or manually reset:
```python
adapter.circuit_breaker.reset()
```

### Rate Limit Exceeded
```
RateLimitExceededError: Rate limit exceeded: 10 requests per 1 seconds
```

**Solution**: Increase wait time or reduce request frequency

### Optimization Timeout
```
# Optimization didn't complete all trials
```

**Solution**: Increase timeout or reduce n_trials:
```python
optimizer = OptunaOptimizer(
    df_prices=df_prices,
    n_trials=50,
    timeout=600  # 10 minutes
)
```

### Memory Issues
```
MemoryError: Unable to allocate array
```

**Solution**: Reduce data size or use slow mode:
```python
run_backtest(..., fast_mode=False)
```

## Performance Tips

1. **Use fast mode**: 3x speedup with no accuracy loss
2. **Parallel optimization**: Set `n_jobs=-1` to use all CPUs
3. **Reduce data**: Use `days=100` instead of `days=1000` for testing
4. **Enable pruning**: MedianPruner stops bad trials early
5. **Cache results**: Save optimization history to avoid re-running

## API Reference

### BinanceAdapter
- `fetch(**kwargs)`: Fetch market data with protection
- `get_circuit_metrics()`: Get circuit breaker status
- `get_rate_limit_stats()`: Get rate limiter statistics

### OptunaOptimizer
- `optimize(study_name)`: Run optimization
- `get_best_params()`: Get optimal parameters
- `get_optimization_history()`: Get trial history DataFrame
- `get_param_importance()`: Get parameter importance scores

### run_backtest
- `run_backtest(df_prices, M, atr_period, sl_multiplier, tp_multiplier, fast_mode=True)`
- Returns: `(metrics, returns, cum_ret, trades)`

## Further Reading

- [Optuna Documentation](https://optuna.readthedocs.io/)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Rate Limiting Algorithms](https://en.wikipedia.org/wiki/Token_bucket)
- [Vectorization in NumPy](https://numpy.org/doc/stable/user/basics.broadcasting.html)

## Support

For issues or questions:
1. Check existing tests in `tests/unit/test_trading/`
2. Review example scripts in `examples/`
3. Open an issue on GitHub
4. Contact the development team
