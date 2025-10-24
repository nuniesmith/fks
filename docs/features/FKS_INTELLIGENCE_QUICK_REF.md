# FKS Intelligence - Quick Reference

## Services Quick Access

### RAG Service
```python
from services import get_rag_service
rag = get_rag_service()

# Query knowledge base
result = rag.query_with_rag("What works for BTCUSDT?", top_k=5)

# Predict trend
pred = rag.predict_trend("SOLUSDT", "1h", lookback_days=30)

# Suggest strategy
strat = rag.suggest_strategy("BTCUSDT", market_condition="trending")

# Hybrid search
results = rag.hybrid_search("RSI signals", top_k=10)

# Analytics
analytics = rag.get_query_analytics(days=7)
```

### Feedback Service
```python
from services import get_feedback_service
feedback = get_feedback_service()

# Log trade
feedback.log_trade_outcome(
    symbol="BTCUSDT", strategy="RSI", outcome="win",
    entry_price=45000, exit_price=46500, position_size=0.1,
    pnl=150, pnl_pct=3.33, market_condition="trending", timeframe="1h"
)

# Log backtest
feedback.log_backtest_result(
    strategy="EMA", symbol="ETHUSDT", timeframe="4h",
    start_date=datetime(2025,1,1), end_date=datetime(2025,10,1),
    metrics={'win_rate': 0.65, 'profit_factor': 1.8},
    parameters={'fast': 12, 'slow': 26},
    insights="Strong in trending markets"
)

# Analyze performance
analysis = feedback.analyze_strategy_performance("RSI", lookback_days=90)

# Learn from losses
loss_analysis = feedback.learn_from_losses("ETHUSDT", lookback_days=30)
```

### Optimization Service
```python
from services import get_optimization_service
optimizer = get_optimization_service()

# Get RAG ranges
ranges = optimizer.get_rag_suggested_ranges(
    "RSI_Strategy", "BTCUSDT", ['rsi_period', 'overbought']
)

# Optimize
def objective(trial, **params):
    return run_backtest(**params)

results = optimizer.optimize_strategy(
    strategy="MACD", symbol="BTCUSDT", timeframe="1h",
    objective_function=objective, parameters=['fast', 'slow'],
    n_trials=100, use_rag_ranges=True
)

# Compare strategies
comparison = optimizer.compare_strategies(
    ["RSI", "MACD", "EMA"], "BTCUSDT", metric="sharpe_ratio"
)
```

## Streamlit Intelligence Tab

### Navigation
```
app.py → Tab 8: "🧠 Intelligence"
```

### Features
1. **Query Interface**
   - Natural language questions
   - 6 quick question templates
   - Advanced filters (symbol, doc type, top-k)

2. **Specialized Analysis**
   - Strategy suggestions (symbol + market condition)
   - Trend predictions (symbol + timeframe + lookback)

3. **History & Analytics**
   - Query history (last 10 queries)
   - System analytics (7-day stats)
   - Database statistics

### Example Queries
```
- "What strategy works best for BTCUSDT?"
- "Analyze my recent losing trades"
- "What are the best entry indicators for SOLUSDT?"
- "Compare RSI and MACD strategies"
- "Predict trend for AVAXUSDT based on history"
```

## Django REST API Endpoints

### Query Knowledge Base
```bash
POST /api/intelligence/query/
{
  "query": "What strategy works for BTCUSDT?",
  "top_k": 5,
  "include_sources": true
}
```

### Strategy Suggestions
```bash
POST /api/intelligence/strategy/
{
  "symbol": "BTCUSDT",
  "market_condition": "trending",
  "risk_level": "medium"
}
```

### Analyze Trades
```bash
GET /api/intelligence/trades/BTCUSDT/?days=30&min_trades=5
```

### Explain Signal
```bash
POST /api/intelligence/signal/
{
  "symbol": "BTCUSDT",
  "indicators": {"rsi": 35, "macd": -0.5}
}
```

### Manual Ingestion
```bash
POST /api/intelligence/ingest/
{
  "type": "all",
  "days": 30,
  "limit": 100
}
```

### System Stats
```bash
GET /api/intelligence/stats/
```

### Health Check
```bash
GET /api/intelligence/health/
```

## CLI Commands

### Start Services
```bash
make up                    # Standard startup
make gpu-up                # With GPU support
make logs-celery           # View Celery logs
```

### Test RAG
```bash
chmod +x scripts/test_rag_integration.sh
./scripts/test_rag_integration.sh
```

### Database
```bash
# Enable pgvector
docker exec fks_db psql -U postgres -d trading_db \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Check indexes
docker exec fks_db psql -U postgres -d trading_db \
  -c "SELECT * FROM pg_indexes WHERE tablename='document_chunks';"
```

### Celery
```bash
# Check scheduled tasks
docker-compose exec celery_worker celery -A fks_project inspect scheduled

# View active tasks
docker-compose exec celery_worker celery -A fks_project inspect active

# Flower UI
open http://localhost:5555
```

## Configuration

### Environment Variables
```bash
# .env file
OPENAI_API_KEY=sk-...           # OpenAI API (optional)
DATABASE_URL=postgresql://...    # PostgreSQL
REDIS_HOST=redis                 # Redis host
REDIS_PORT=6379                  # Redis port
```

### Model Selection
```python
# Use local models (default)
rag = RAGService(use_local=True, local_model="llama3.2:3b")

# Use OpenAI
rag = RAGService(use_local=False, openai_model="gpt-4o-mini")
```

### Performance Tuning
```python
# Adjust top-k for speed vs. context
result = rag.query_with_rag(query, top_k=3)  # Faster

# Use hybrid search
results = rag.hybrid_search(
    query, 
    semantic_weight=0.8,  # Prioritize semantic
    keyword_weight=0.2
)

# Set similarity threshold
results = rag.query_with_cosine_similarity(
    query,
    similarity_threshold=0.7  # Higher = stricter
)
```

## Common Patterns

### Pattern 1: Trade Logging Workflow
```python
# 1. Execute trade
trade_result = execute_trade(symbol, strategy, params)

# 2. Log outcome
feedback.log_trade_outcome(
    symbol=trade_result['symbol'],
    strategy=strategy,
    outcome='win' if trade_result['pnl'] > 0 else 'loss',
    entry_price=trade_result['entry'],
    exit_price=trade_result['exit'],
    position_size=trade_result['size'],
    pnl=trade_result['pnl'],
    pnl_pct=trade_result['pnl_pct'],
    market_condition=detect_market_condition(),
    timeframe=timeframe
)

# 3. Query for insights
insights = feedback.analyze_strategy_performance(strategy)
```

### Pattern 2: Strategy Optimization
```python
# 1. Get RAG-suggested ranges
ranges = optimizer.get_rag_suggested_ranges(strategy, symbol, params)

# 2. Define objective
def objective(trial, **params):
    return backtest_strategy(symbol, timeframe, **params)

# 3. Optimize
results = optimizer.optimize_strategy(
    strategy, symbol, timeframe, objective, params,
    n_trials=100, use_rag_ranges=True
)

# 4. Store results (automatic)
# 5. Apply best parameters
apply_parameters(results['best_parameters'])
```

### Pattern 3: Loss Analysis Loop
```python
# 1. Detect losing streak
recent_losses = get_recent_trades(outcome='loss', days=7)

if len(recent_losses) >= 3:
    # 2. Analyze patterns
    analysis = feedback.learn_from_losses(symbol, lookback_days=30)
    
    # 3. Get suggestions
    suggestions = feedback.get_optimization_suggestions(
        strategy, symbol, current_params
    )
    
    # 4. Alert user
    send_notification(f"Loss pattern detected: {analysis['loss_analysis']}")
    send_notification(f"Suggestions: {suggestions['suggestions']}")
```

## Troubleshooting

### Issue: Slow queries
```python
# Solution 1: Reduce top_k
result = rag.query_with_rag(query, top_k=3)

# Solution 2: Add filters
result = rag.query_with_rag(
    query, 
    filters={'symbol': 'BTCUSDT', 'doc_type': 'trade_outcome'}
)

# Solution 3: Check indexes
# See Database section above
```

### Issue: Low confidence
```python
# Solution 1: Increase top_k
result = rag.query_with_rag(query, top_k=15)

# Solution 2: Broaden search
result = rag.hybrid_search(query, semantic_weight=0.5, keyword_weight=0.5)

# Solution 3: Ingest more data
feedback.log_backtest_result(...)  # Add more context
```

### Issue: No results
```python
# Solution 1: Check filters
results = rag.query_with_cosine_similarity(
    query,
    similarity_threshold=0.3  # Lower threshold
)

# Solution 2: Verify data exists
from database import Session, Document
session = Session()
count = session.query(Document).filter(
    Document.symbol == 'BTCUSDT'
).count()
print(f"Documents for BTCUSDT: {count}")
```

## Performance Benchmarks

### Query Response Times
- Simple query (top_k=5): ~1-2s
- Complex query (top_k=15): ~2-4s
- Hybrid search (top_k=10): ~2-3s
- Trend prediction: ~3-5s
- Strategy suggestion: ~2-4s

### Optimization Times
- 50 trials: ~5-15 min (depends on objective)
- 100 trials: ~10-30 min
- 200 trials: ~20-60 min

### Ingestion Rates
- Trade outcome: ~0.1s per document
- Backtest result: ~0.2s per document
- Bulk ingestion (100 docs): ~30-60s

## Resources

- **Documentation**: `docs/PHASE3_COMPLETE.md`
- **API Reference**: `docs/PHASE2_COMPLETE.md`
- **Testing**: `scripts/test_rag_integration.sh`
- **LangChain**: https://python.langchain.com/docs/
- **Optuna**: https://optuna.readthedocs.io/
- **pgvector**: https://github.com/pgvector/pgvector

---

**Quick Tip**: Start with `get_rag_service()` for querying, `get_feedback_service()` for logging, and `get_optimization_service()` for tuning. All services are singleton instances that share the same knowledge base.
