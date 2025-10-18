# FKS Intelligence RAG System - Setup Guide

Complete guide to setting up and using the FKS Intelligence RAG (Retrieval-Augmented Generation) system for AI-powered trading recommendations.

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Database Setup](#database-setup)
- [Ollama Setup](#ollama-setup)
- [Quick Start](#quick-start)
- [Usage Examples](#usage-examples)
- [Celery Integration](#celery-integration)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

The FKS Intelligence RAG system provides:
- AI-powered trading recommendations based on historical data
- Semantic search over signals, backtests, and trade analyses
- Local LLM support (Ollama) with GPU acceleration
- Automatic data ingestion via Celery tasks
- OpenAI API fallback

**Architecture:**
```
Trading Data → Document Processor → Embeddings → pgvector (PostgreSQL)
                                                        ↓
User Query → Retrieval Service → Context + LLM → Trading Insights
```

## 📦 Prerequisites

### Required
- Python 3.10+
- PostgreSQL 15+ with pgvector extension
- Redis (for Celery)
- Docker & Docker Compose (recommended)

### Optional but Recommended
- CUDA-capable GPU (for acceleration)
- Ollama (for local LLM)
- 8GB+ RAM (16GB+ for local LLM)

## 🔧 Installation

### 1. Install Python Dependencies

All dependencies are in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Key packages:
- `sentence-transformers` - Local embeddings
- `ollama` - Local LLM client
- `torch` - CUDA support
- `openai` - OpenAI API
- `tiktoken` - Token counting
- `transformers` - Model support

### 2. Verify Installation

```bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
python -c "import sentence_transformers; print('✓ sentence-transformers installed')"
python -c "import ollama; print('✓ ollama client installed')"
```

## 🗄️ Database Setup

### 1. Enable pgvector Extension

Connect to your PostgreSQL database:

```bash
psql -U postgres -d trading_db
```

Enable pgvector:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Verify:

```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### 2. Run Migrations

```bash
# From project root
psql -U postgres -d trading_db -f sql/migrations/001_add_pgvector.sql
```

This creates:
- Vector indexes (HNSW for fast similarity search)
- Composite indexes for filtering
- GIN indexes for JSONB metadata

### 3. Verify Tables

```bash
psql -U postgres -d trading_db -c "\dt"
```

Should show:
- `documents` - Source documents
- `document_chunks` - Chunks with embeddings
- `query_history` - Query logs
- `trading_insights` - Curated insights

## 🤖 Ollama Setup

Ollama provides free local LLM inference with GPU acceleration.

### 1. Install Ollama

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:**
```bash
brew install ollama
```

**Windows:**
Download from https://ollama.com/download

### 2. Start Ollama Server

```bash
ollama serve
```

Keep this running in a terminal.

### 3. Pull a Model

Recommended models:

```bash
# Small & fast (3B parameters) - Recommended
ollama pull llama3.2:3b

# Tiny & very fast (1B parameters)
ollama pull llama3.2:1b

# Better quality (7B parameters)
ollama pull mistral:7b

# Balanced (3.8B parameters)
ollama pull phi3:mini
```

### 4. Test Ollama

```bash
ollama run llama3.2:3b "What is a good trading strategy?"
```

Press Ctrl+D to exit.

## 🚀 Quick Start

### 1. Initialize Intelligence Service

```python
from web.rag.services import IntelligenceOrchestrator

# Create orchestrator (uses local models by default)
orchestrator = IntelligenceOrchestrator()
```

### 2. Ingest Trading Data

```python
from web.rag.ingestion import DataIngestionPipeline

pipeline = DataIngestionPipeline()

# Ingest a signal
signal = {
    'symbol': 'BTCUSDT',
    'action': 'BUY',
    'price': 42000.00,
    'timeframe': '1h',
    'indicators': {'rsi': 35.5, 'macd': -50.2},
    'confidence': 0.85,
    'reasoning': 'RSI oversold + MACD divergence'
}
doc_id = pipeline.ingest_signal(signal)
print(f"Ingested signal as document {doc_id}")

# Batch ingest recent trades
count = pipeline.batch_ingest_recent_trades(days=30)
print(f"Ingested {count} trades")
```

### 3. Get Trading Recommendations

```python
# Get recommendation for a symbol
recommendation = orchestrator.get_trading_recommendation(
    symbol="BTCUSDT",
    account_balance=10000.00,
    available_cash=5000.00,
    context="current market conditions"
)

print(f"Action: {recommendation['action']}")
print(f"Position Size: ${recommendation['position_size_usd']:.2f}")
print(f"Risk: {recommendation['risk_assessment']}")
print(f"Confidence: {recommendation['confidence']:.0%}")
print(f"\nReasoning:\n{recommendation['reasoning']}")
```

## 📚 Usage Examples

### Example 1: Daily Signals

```python
# Get daily signals for multiple symbols
signals = orchestrator.get_daily_signals(
    symbols=['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
    min_confidence=0.7
)

for symbol, signal in signals['signals'].items():
    print(f"{symbol}: {signal['recommendation'][:100]}...")
    print(f"  Confidence: {signal['confidence']:.0%}\n")
```

### Example 2: Portfolio Optimization

```python
# Get portfolio recommendations
portfolio = orchestrator.optimize_portfolio(
    symbols=['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
    account_balance=10000.00,
    available_cash=5000.00,
    current_positions={
        'BTCUSDT': {'quantity': 0.5, 'entry_price': 41000.00}
    },
    market_condition='trending'
)

print("Portfolio Allocation:")
for symbol, rec in portfolio['symbols'].items():
    print(f"  {symbol}: {rec['action']} (Risk: {rec['risk_assessment']})")

print(f"\nPortfolio Advice:\n{portfolio['portfolio_advice']}")
```

### Example 3: Query Knowledge Base

```python
from web.rag.intelligence import create_intelligence

intelligence = create_intelligence(use_local=True)

# Ask a question
result = intelligence.query(
    "What are the best entry points for Bitcoin based on past signals?",
    symbol='BTCUSDT',
    top_k=5
)

print(f"Answer:\n{result['answer']}\n")
print(f"Sources used: {result['context_used']}")
print(f"Response time: {result['response_time_ms']}ms")
```

## 🔄 Celery Integration

### 1. Start Celery Worker

```bash
# From project root
celery -A src.web.django worker -l info
```

### 2. Start Celery Beat (Scheduler)

```bash
celery -A src.web.django beat -l info
```

### 3. Use Tasks

```python
from trading.tasks import (
    ingest_signal,
    ingest_backtest_result,
    ingest_completed_trade,
    ingest_recent_trades
)

# Trigger ingestion asynchronously
ingest_signal.delay(signal_data)
ingest_backtest_result.delay(backtest_data)
ingest_completed_trade.delay(trade_id=123)

# Batch ingest recent trades
ingest_recent_trades.delay(days=7)
```

### 4. Schedule Periodic Tasks

Add to `src/web/django/celery.py`:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'ingest-recent-trades-daily': {
        'task': 'trading.tasks.ingest_recent_trades',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
        'args': (7,)  # Last 7 days
    },
}
```

## 🧪 Testing

### Run Example Scripts

```bash
# Comprehensive test suite
python scripts/test_rag_system.py

# Simple usage examples
python scripts/rag_example.py
```

### Run Unit Tests

```bash
# All RAG tests
pytest tests/unit/test_rag/ -v

# Specific test file
pytest tests/unit/test_rag/test_orchestrator.py -v

# With coverage
pytest tests/unit/test_rag/ --cov=web.rag --cov-report=html
```

### Test CUDA Availability

```python
from web.rag.local_llm import check_cuda_availability

cuda_info = check_cuda_availability()
print(f"CUDA Available: {cuda_info['cuda_available']}")
if cuda_info['cuda_available']:
    print(f"GPU: {cuda_info['devices'][0]['name']}")
    print(f"VRAM: {cuda_info['devices'][0]['total_memory_gb']:.1f} GB")
```

## 🐛 Troubleshooting

### Issue: Ollama Not Connecting

**Error:** `OllamaConnectionError` or `Connection refused`

**Solution:**
```bash
# Make sure Ollama is running
ollama serve

# Test connection
ollama list

# Check if model is installed
ollama pull llama3.2:3b
```

### Issue: pgvector Extension Not Found

**Error:** `extension "vector" is not available`

**Solution:**
```bash
# Install pgvector (Ubuntu/Debian)
sudo apt install postgresql-15-pgvector

# Or build from source
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Enable in database
psql -U postgres -d trading_db -c "CREATE EXTENSION vector;"
```

### Issue: CUDA Not Available

**Error:** `CUDA available: False`

**Solution:**
```bash
# Check NVIDIA driver
nvidia-smi

# Install CUDA toolkit (Ubuntu)
sudo apt install nvidia-cuda-toolkit

# Reinstall PyTorch with CUDA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### Issue: Out of Memory (GPU)

**Error:** `CUDA out of memory`

**Solution:**
1. Use smaller models:
   ```bash
   ollama pull llama3.2:1b  # Instead of 3b
   ```

2. Use CPU instead:
   ```python
   orchestrator = IntelligenceOrchestrator(use_local=False)  # Use OpenAI
   ```

3. Reduce batch size:
   ```python
   embeddings.generate_embeddings_batch(texts, batch_size=16)  # Instead of 32
   ```

### Issue: Slow Semantic Search

**Error:** Queries taking >1 second

**Solution:**
```sql
-- Check if HNSW index exists
SELECT indexname FROM pg_indexes 
WHERE tablename = 'document_chunks' 
AND indexname LIKE '%embedding%';

-- Create if missing
CREATE INDEX idx_document_chunks_embedding_hnsw 
ON document_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Analyze table
VACUUM ANALYZE document_chunks;
```

### Issue: Import Errors

**Error:** `ModuleNotFoundError: No module named 'web.rag'`

**Solution:**
```bash
# Make sure you're in project root
cd /path/to/fks

# Add src to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"

# Or use absolute imports
from src.web.rag.services import IntelligenceOrchestrator
```

## 📊 Performance Tips

1. **Use GPU acceleration** - 3-5x faster embeddings and LLM
2. **Batch operations** - Process multiple documents at once
3. **Cache frequent queries** - Use Redis for common questions
4. **Tune HNSW parameters** - Adjust `m` and `ef_construction` for your data size
5. **Use smaller models** - llama3.2:1b for faster responses
6. **Index metadata** - Add indexes for frequently filtered fields

## 🔗 Additional Resources

- [RAG Module README](../src/web/rag/README.md) - Detailed API documentation
- [Project Architecture](./ARCHITECTURE.md) - System design
- [Ollama Documentation](https://github.com/ollama/ollama) - Model management
- [pgvector Documentation](https://github.com/pgvector/pgvector) - Vector operations

## 💡 Best Practices

1. **Start with small models** (llama3.2:1b) and scale up if needed
2. **Ingest data incrementally** - Don't load everything at once
3. **Monitor query performance** - Log slow queries in `query_history`
4. **Keep embeddings model consistent** - Don't mix different embedding dimensions
5. **Use appropriate doc_types** - Helps with filtering and relevance
6. **Test with mock data first** - Before ingesting production data
7. **Set up scheduled ingestion** - Keep knowledge base up-to-date

## 🎉 You're Ready!

The RAG system is now set up and ready to use. Start with the example scripts and explore the API:

```bash
# Run comprehensive tests
python scripts/test_rag_system.py

# Try simple examples
python scripts/rag_example.py

# Or use the API directly
python -c "from web.rag.services import IntelligenceOrchestrator; print('✓ Ready!')"
```

Happy trading! 🚀
