# Phase 6 Quick Start - Multi-Agent AI System

**One-Page Guide**: Get the Phase 6 multi-agent system running in 5 minutes

---

## 🚀 Quick Deploy (GPU)

```bash
# 1. Build containers (first time only)
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml build fks_ai ollama

# 2. Start services
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d fks_ai ollama

# 3. Pull Ollama model
docker-compose exec ollama ollama pull llama3.2:3b

# 4. Verify
curl http://localhost:8006/health
```

**Expected**: `{"status": "healthy", "service": "fks_ai", ...}`

---

## 🧪 Quick Test

```bash
# Unit tests (70 tests, <3s)
docker-compose exec fks_ai pytest tests/unit/ -v

# Integration tests (18 tests, requires Ollama)
docker-compose exec fks_ai pytest tests/integration/ -v -s

# API docs
open http://localhost:8006/docs
```

---

## 📊 Quick API Call

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

**Expected**: JSON with analysts, debate, final_decision, trading_signal (~3-5s response)

---

## 📁 Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `src/services/ai/src/api/routes.py` | FastAPI endpoints | 419 |
| `src/services/ai/src/graph/trading_graph.py` | StateGraph orchestration | 120 |
| `src/services/ai/src/agents/analysts/*.py` | 4 analyst agents | 450 |
| `src/services/ai/src/agents/debaters/*.py` | 3 debate agents | 375 |
| `src/services/ai/tests/unit/` | 70 unit tests | 1,586 |
| `src/services/ai/tests/integration/` | 18 integration tests | 637 |

---

## 🛠️ Quick Troubleshooting

**Container won't start?**
```bash
docker-compose logs fks_ai  # Check logs
docker-compose build --no-cache fks_ai  # Rebuild
```

**Ollama connection error?**
```bash
docker-compose ps ollama  # Check running
docker-compose exec ollama ollama list  # Verify model
```

**Import errors?**
```bash
docker-compose exec fks_ai pip list | grep langchain  # Check deps
```

---

## 📚 Full Documentation

- **Deployment Guide**: `docs/PHASE_6_DEPLOYMENT.md` (392 lines)
- **Architecture**: `docs/PHASE_6_FINAL_SUMMARY.md` (448 lines)
- **Progress Tracker**: `docs/PHASE_6_PROGRESS.md` (364 lines)
- **Copilot Instructions**: `.github/copilot-instructions.md` (Phase 6 section)

---

## ✅ What You Get

- **7 Agents**: 4 analysts (Technical, Sentiment, Macro, Risk) + 3 debaters (Bull, Bear, Manager)
- **StateGraph**: LangGraph orchestration with conditional routing
- **ChromaDB Memory**: Persistent decision storage with semantic search
- **Risk Management**: Position sizing, stop-loss, take-profit calculation
- **REST API**: 4 endpoints (analyze, debate, memory, status)
- **88 Tests**: 70 unit + 18 integration (>80% coverage)

---

## 🎯 Phase 6 Status

**Complete**: 14/15 tasks (93%)  
**Remaining**: Live Ollama validation (30 min after deployment)  
**Code**: 4,936 lines (2,321 production + 2,223 tests + 392 docs)

---

**Ready to deploy!** Run the Quick Deploy commands above ⬆️
