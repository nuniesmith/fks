# Phase 6 Deployment Guide - Multi-Agent AI Service

**Quick Reference**: Deploy fks_ai with LangGraph multi-agent system

---

## Prerequisites

- Docker & Docker Compose installed
- NVIDIA GPU with CUDA support (for Ollama)
- `.env` file configured with API keys

---

## Deployment Steps

### 1. Standard Deployment (CPU-only, for testing)

```bash
# Build and start fks_ai service
docker-compose build fks_ai
docker-compose up -d fks_ai

# Check logs
docker-compose logs -f fks_ai

# Verify health
curl http://localhost:8006/health
```

**Note**: Without Ollama, agents will fail. Use GPU deployment for production.

---

### 2. GPU Deployment with Ollama (Recommended)

```bash
# Build and start fks_ai + ollama with GPU support
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml build fks_ai ollama
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d fks_ai ollama

# Pull Ollama model (inside ollama container)
docker-compose exec ollama ollama pull llama3.2:3b

# Verify model loaded
docker-compose exec ollama ollama list

# Check fks_ai logs
docker-compose logs -f fks_ai
```

**Expected output**:
```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8006
```

---

## Testing the API

### 1. Health Check

```bash
curl http://localhost:8006/health
```

**Response**:
```json
{
  "status": "healthy",
  "service": "fks_ai",
  "version": "1.0.0",
  "timestamp": "2025-10-31T..."
}
```

### 2. Agent Status

```bash
curl http://localhost:8006/ai/agents/status
```

**Response** (all agents healthy):
```json
{
  "status": "healthy",
  "agents": {
    "technical": {"status": "healthy"},
    "sentiment": {"status": "healthy"},
    "macro": {"status": "healthy"},
    "risk": {"status": "healthy"},
    "bull": {"status": "healthy"},
    "bear": {"status": "healthy"},
    "manager": {"status": "healthy"}
  },
  "memory_status": {"status": "healthy"},
  "uptime_ms": 1234.56
}
```

### 3. Full Analysis

```bash
curl -X POST http://localhost:8006/ai/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "market_data": {
      "price": 67234.50,
      "rsi": 58.5,
      "macd": 150.2,
      "macd_signal": 125.8,
      "bb_upper": 68000.0,
      "bb_middle": 67000.0,
      "bb_lower": 66000.0,
      "atr": 400.0,
      "volume": 1234567890,
      "regime": "bull"
    }
  }'
```

**Response**:
```json
{
  "symbol": "BTCUSDT",
  "timestamp": "2025-10-31T...",
  "analysts": {
    "technical": "Technical analysis: BUY signal...",
    "sentiment": "Sentiment analysis: Bullish...",
    "macro": "Macro analysis: Favorable...",
    "risk": "Risk assessment: Moderate..."
  },
  "debate": {
    "bull": "Bull case: Strong momentum...",
    "bear": "Bear case: Overbought conditions..."
  },
  "final_decision": "RECOMMENDATION: BUY...",
  "trading_signal": {
    "action": "BUY",
    "position_size": 0.05,
    "stop_loss": 66834.50,
    "take_profit": 68434.50,
    "confidence": 0.72
  },
  "confidence": 0.72,
  "regime": "bull",
  "execution_time_ms": 3456.78
}
```

### 4. API Documentation

```bash
# Open Swagger UI in browser
open http://localhost:8006/docs

# Or ReDoc
open http://localhost:8006/redoc
```

---

## Running Tests

### Unit Tests (70 tests, no Ollama needed)

```bash
# Run all unit tests
docker-compose exec fks_ai pytest tests/unit/ -v

# Run specific test module
docker-compose exec fks_ai pytest tests/unit/test_signal_processor.py -v

# With coverage
docker-compose exec fks_ai pytest tests/unit/ --cov=. --cov-report=term-missing
```

**Expected**: All 70 tests pass (mocked dependencies)

### Integration Tests (18 tests, requires Ollama)

```bash
# Run E2E graph tests
docker-compose exec fks_ai pytest tests/integration/test_e2e.py -v -s

# Run API tests
docker-compose exec fks_ai pytest tests/integration/test_api.py -v -s

# Run all integration tests
docker-compose exec fks_ai pytest tests/integration/ -v -s
```

**Expected** (with live Ollama):
- Graph execution <5s
- Debate contrast >70%
- Signal quality validation passes
- API endpoints return 200 status

---

## Troubleshooting

### Issue: Import errors when starting container

**Symptom**:
```
ModuleNotFoundError: No module named 'langchain'
```

**Solution**:
```bash
# Rebuild with updated requirements
docker-compose build --no-cache fks_ai
docker-compose up -d fks_ai
```

### Issue: Ollama connection refused

**Symptom**:
```
requests.exceptions.ConnectionError: HTTPConnectionPool(host='ollama', port=11434)
```

**Solution**:
```bash
# Check Ollama is running
docker-compose ps ollama

# If not running, start it
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d ollama

# Wait for model pull to complete
docker-compose exec ollama ollama pull llama3.2:3b
```

### Issue: ChromaDB persistence errors

**Symptom**:
```
chromadb.errors.Error: Collection not found
```

**Solution**:
```bash
# ChromaDB creates collections automatically on first add_insight()
# Just run analyze endpoint once to initialize
curl -X POST http://localhost:8006/ai/analyze -H "Content-Type: application/json" -d '...'
```

### Issue: Slow response times (>10s)

**Symptom**: Analysis takes longer than expected

**Solutions**:
1. **Check GPU**: Ensure Ollama is using GPU acceleration
   ```bash
   docker-compose exec ollama nvidia-smi
   ```

2. **Reduce model size**: Use smaller model
   ```bash
   docker-compose exec ollama ollama pull llama3.2:1b  # Faster but less accurate
   ```

3. **Increase timeout**: In API calls, increase timeout to 30s

---

## Integration with fks_app

### Python Client Example

```python
# In fks_app/src/integrations/ai_client.py
import httpx
from typing import Dict, Any

async def get_ai_analysis(symbol: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
    """Get multi-agent analysis from fks_ai service"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://fks_ai:8006/ai/analyze",
            json={"symbol": symbol, "market_data": market_data},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()

# Usage in strategy
async def execute_strategy(symbol: str):
    # Get market data from fks_data
    market_data = await get_market_data(symbol)
    
    # Get AI analysis
    ai_result = await get_ai_analysis(symbol, market_data)
    
    # Extract trading signal
    signal = ai_result['trading_signal']
    
    if signal['action'] != 'HOLD' and ai_result['confidence'] > 0.6:
        # Execute via fks_execution
        await execute_trade(signal)
```

---

## Monitoring

### Prometheus Metrics (Future)

Add to `fks_ai/src/api/routes.py`:
```python
from prometheus_client import Counter, Histogram

# Request metrics
request_count = Counter('fks_ai_requests_total', 'Total requests', ['endpoint', 'status'])
request_duration = Histogram('fks_ai_request_duration_seconds', 'Request duration', ['endpoint'])

# Agent metrics
agent_latency = Histogram('fks_ai_agent_latency_seconds', 'Agent response time', ['agent'])
debate_contrast = Gauge('fks_ai_debate_contrast', 'Bull/Bear debate divergence')
```

### Grafana Dashboard

Create dashboard with:
- Request rate (requests/sec)
- Average latency per endpoint
- Agent uptime (healthy/unhealthy)
- Signal confidence distribution
- Debate contrast over time

---

## Next Steps

1. **Week 1**: Container deployment + Ollama setup (Tasks 2, 15)
2. **Week 2**: fks_app integration + paper trading
3. **Week 3**: Monitoring + Grafana dashboards
4. **Week 4**: Live validation + performance tuning

---

**Status**: Phase 6 - 93% complete (14/15 tasks)  
**Remaining**: Ollama setup + live validation (requires GPU deployment)

*Ready for deployment! 🚀*
