# FKS Trading Examples

This directory contains example scripts demonstrating the usage of FKS Trading Systems features.

## Available Examples

### optimize_strategy.py

A comprehensive example demonstrating:
- **Enhanced Binance data fetching** with rate limiting and circuit breaker protection
- **Strategy optimization** using Optuna for hyperparameter tuning
- **RAG integration** for intelligent parameter suggestions
- **High-performance backtesting** with optimized DataFrame operations

#### Usage

```bash
# Basic usage
python examples/optimize_strategy.py

# With RAG enabled (requires RAG service running)
# Edit the script to set use_rag=True in optimize_strategy()
```

#### Features Demonstrated

1. **Rate-Limited API Calls**
   - Circuit breaker protection against API failures
   - Token bucket rate limiting (10 req/sec)
   - Automatic retry with exponential backoff

2. **Optuna Optimization**
   - Bayesian optimization with TPE sampler
   - Parallel trial execution
   - Parameter importance analysis
   - Optimization history tracking

3. **Fast Backtesting**
   - 3x performance improvement with vectorized operations
   - NumPy array optimizations
   - Reduced memory usage

4. **RAG Integration** (optional)
   - Market-aware parameter suggestions
   - LLM-powered optimization guidance

#### Output Files

The script generates:
- `optimization_history.csv` - Complete trial history
- `backtest_returns.csv` - Daily returns from optimized strategy

#### Configuration

Edit the script to customize:
- `symbols` - Trading pairs to include
- `days` - Historical data period
- `n_trials` - Number of optimization trials
- `use_rag` - Enable/disable RAG suggestions

## Requirements

```bash
# Install required packages
pip install optuna pandas numpy talib loguru

# For RAG integration
pip install langchain sentence-transformers
```

## Running Examples

All examples assume you're running from the repository root:

```bash
cd /path/to/fks
python examples/optimize_strategy.py
```

## Expected Output

```
============================================================
FKS STRATEGY OPTIMIZER
============================================================

[Step 1] Fetching market data...
Fetched 100 bars for BTCUSDT
Fetched 100 bars for ETHUSDT
...

[Step 2] Optimizing strategy parameters...
[I 2025-10-18 14:48:55,123] Starting optimization: 20 trials
[I 2025-10-18 14:49:01,456] Trial 0 finished with value: 1.234
...

============================================================
OPTIMIZATION RESULTS
============================================================
Best Sharpe Ratio: 1.5432
Best Parameters:
  M: 20
  atr_period: 14
  sl_multiplier: 2.0
  tp_multiplier: 3.5

[Step 3] Running backtest with optimized parameters...
============================================================
BACKTEST RESULTS
============================================================
Sharpe Ratio: 1.5432
Sortino Ratio: 2.1234
Max Drawdown: -15.43%
Total Return: 45.67%
Number of Trades: 12
```

## Notes

- **Rate Limiting**: The Binance adapter automatically handles rate limits
- **Circuit Breaker**: After 3 consecutive failures, API calls are blocked for 60 seconds
- **Performance**: Fast mode provides ~3x speedup for backtests
- **Parallel Execution**: Optuna can use multiple CPU cores (set n_jobs parameter)

## Troubleshooting

**Import Errors**:
```bash
# Ensure src is in Python path
export PYTHONPATH="${PYTHONPATH}:/path/to/fks/src"
```

**API Errors**:
- Check internet connection
- Verify Binance API is accessible
- Circuit breaker may be open - wait 60 seconds

**Performance Issues**:
- Reduce `n_trials` for faster optimization
- Use smaller `days` value for less data
- Set `fast_mode=True` in backtests

## Next Steps

After running the example:
1. Review `optimization_history.csv` to see all trials
2. Analyze `backtest_returns.csv` for return distribution
3. Adjust parameters based on your risk tolerance
4. Integrate into your trading workflow
