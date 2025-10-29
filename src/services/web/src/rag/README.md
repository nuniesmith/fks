# FKS Intelligence - RAG System

AI-powered trading intelligence using Retrieval-Augmented Generation (RAG) with local LLM support and GPU acceleration.

## 🎯 Overview

The FKS Intelligence RAG system provides:
- **Semantic search** over trading signals, backtests, and historical trades
- **AI-powered recommendations** based on past performance
- **Context-aware analysis** using local LLMs (Ollama) or OpenAI
- **Automatic ingestion** of trading data via Celery tasks
- **GPU acceleration** for embeddings and LLM inference

## 📁 Architecture

```
Trading Data → Document Processor → Embeddings → pgvector (PostgreSQL)
                                                        ↓
User Query → Retrieval Service → Context + LLM → Trading Insights
```

### Components

1. **document_processor.py** - Chunks trading data into processable segments
2. **embeddings.py** - Generates embeddings (local or OpenAI) and stores in pgvector
3. **local_llm.py** - Local LLM support (Ollama/llama.cpp) with CUDA acceleration
4. **retrieval.py** - Semantic search and context retrieval
5. **intelligence.py** - Main orchestrator combining all components
6. **ingestion.py** - Auto-ingestion pipeline for trading data

## 🚀 Quick Start

### 1. Initialize Intelligence Service

```python
from web.rag.intelligence import create_intelligence

# Use local models (recommended)
intelligence = create_intelligence(
    use_local=True,
    local_llm_model="llama3.2:3b",
    embedding_model="all-MiniLM-L6-v2"
)

# Or use OpenAI (requires API key)
intelligence = create_intelligence(use_local=False)
```

### 2. Ingest Trading Data

```python
from web.rag.ingestion import DataIngestionPipeline

pipeline = DataIngestionPipeline()

# Ingest a trading signal
signal_data = {
    'symbol': 'BTCUSDT',
    'action': 'BUY',
    'price': 42000.00,
    'timeframe': '1h',
    'indicators': {'rsi': 35.5, 'macd': -50.2},
    'confidence': 0.85,
    'reasoning': 'RSI oversold + MACD divergence'
}
doc_id = pipeline.ingest_signal(signal_data)

# Ingest backtest results
backtest_data = {
    'strategy_name': 'RSI Reversal',
    'symbol': 'ETHUSDT',
    'total_return': 45.2,
    'win_rate': 68.5,
    'sharpe_ratio': 2.1
}
doc_id = pipeline.ingest_backtest_result(backtest_data)

# Batch ingest recent trades
count = pipeline.batch_ingest_recent_trades(days=30)
```

### 3. Query the Knowledge Base

```python
# General query
result = intelligence.query(
    "What are good entry points for Bitcoin?",
    symbol='BTCUSDT',
    top_k=5
)
print(result['answer'])

# Get strategy recommendation
result = intelligence.suggest_strategy(
    symbol='BTCUSDT',
    market_condition='trending'
)

# Explain current indicators
result = intelligence.explain_signal(
    symbol='BTCUSDT',
    current_indicators={'rsi': 35.5, 'macd': -50.2}
)
```

## 🔧 Setup

### Prerequisites

1. **PostgreSQL with pgvector**
   ```bash
   # Enable pgvector extension
   psql -U postgres -d trading_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```

2. **Run migrations**
   ```bash
   psql -U postgres -d trading_db -f sql/migrations/001_add_pgvector.sql
   ```

3. **Install Ollama (for local LLM)**
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Pull a model
   ollama pull llama3.2:3b
   
   # Start Ollama server
   ollama serve
   ```

4. **Python Dependencies**
   All required packages are in `requirements.txt`:
   - `sentence-transformers` - Local embeddings
   - `ollama` - Local LLM client
   - `torch` - CUDA support
   - `openai` - OpenAI API (fallback)
   - `tiktoken` - Token counting
   - `transformers` - Additional model support

### GPU Acceleration

If you have a CUDA-capable GPU:

```python
from web.rag.local_llm import check_cuda_availability

cuda_info = check_cuda_availability()
if cuda_info['cuda_available']:
    print(f"✓ GPU: {cuda_info['devices'][0]['name']}")
    print(f"✓ VRAM: {cuda_info['devices'][0]['total_memory_gb']:.1f} GB")
```

The system automatically uses GPU when available for:
- Embedding generation (sentence-transformers)
- LLM inference (Ollama with CUDA)

## 📊 Database Schema

### documents
```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    doc_type VARCHAR(50) NOT NULL,  -- 'signal', 'backtest', 'trade_analysis', etc.
    title VARCHAR(500),
    content TEXT NOT NULL,
    symbol VARCHAR(20),
    timeframe VARCHAR(10),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### document_chunks
```sql
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),  -- or 1536 for OpenAI
    token_count INTEGER,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast similarity search
CREATE INDEX idx_document_chunks_embedding_hnsw 
ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

### query_history
```sql
CREATE TABLE query_history (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    response TEXT,
    retrieved_chunks JSONB,
    model_used VARCHAR(50),
    response_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### trading_insights
```sql
CREATE TABLE trading_insights (
    id SERIAL PRIMARY KEY,
    insight_type VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    symbol VARCHAR(20),
    impact VARCHAR(20),  -- 'high', 'medium', 'low'
    category VARCHAR(50),
    tags TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 🔄 Celery Auto-Ingestion

The RAG system integrates with Celery for automatic data ingestion.

### Available Tasks

```python
from trading.tasks import (
    ingest_signal,
    ingest_backtest_result,
    ingest_completed_trade,
    ingest_market_analysis,
    ingest_recent_trades
)

# Trigger via Celery
ingest_signal.delay(signal_data)
ingest_backtest_result.delay(backtest_data)
ingest_completed_trade.delay(trade_id)
ingest_recent_trades.delay(days=7)
```

### Scheduled Tasks (Beat)

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

### Run Tests

```bash
# All RAG tests
pytest tests/unit/test_core/test_rag_system.py -v

# Specific test
pytest tests/unit/test_core/test_rag_system.py::TestLocalEmbeddings -v
```

### Example Scripts

```bash
# Comprehensive test suite
python scripts/test_rag_system.py

# Simple usage examples
python scripts/rag_example.py
```

## 🎛️ Configuration

### Environment Variables

```bash
# OpenAI (fallback)
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=postgresql://user:pass@host:5432/trading_db

# Optional: Custom model paths
LLAMA_MODEL_PATH=/path/to/models/
```

### Model Selection

**Embedding Models:**
- `all-MiniLM-L6-v2` - Fast, 384 dim (default)
- `all-mpnet-base-v2` - Better quality, 768 dim
- `text-embedding-3-small` - OpenAI, 1536 dim

**LLM Models (Ollama):**
- `llama3.2:3b` - Small, fast (default)
- `llama3.2:1b` - Tiny, very fast
- `mistral:7b` - Good quality
- `phi3:mini` - Balanced

## 📈 Performance

### Benchmarks (M1 Mac / RTX 3090)

| Operation | Time (CPU) | Time (GPU) |
|-----------|-----------|-----------|
| Embedding (single) | ~30ms | ~10ms |
| Embedding (batch 32) | ~500ms | ~150ms |
| LLM generation (100 tokens) | ~5s | ~1.5s |
| Semantic search (top 5) | ~20ms | ~20ms |

### Optimization Tips

1. **Use batch operations** when ingesting multiple documents
2. **Enable GPU acceleration** for embeddings and LLM
3. **Tune HNSW index parameters** (m=16, ef_construction=64) for your dataset size
4. **Cache frequent queries** in Redis
5. **Use smaller models** (llama3.2:1b) for faster responses

## 🔍 Troubleshooting

### Ollama Connection Error
```python
# Make sure Ollama is running
$ ollama serve

# Check if model exists
$ ollama list
```

### GPU Not Detected
```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda}")
```

### pgvector Not Found
```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Slow Semantic Search
```sql
-- Check if HNSW index exists
SELECT indexname FROM pg_indexes 
WHERE tablename = 'document_chunks' 
AND indexname LIKE '%embedding%';

-- Create if missing
CREATE INDEX idx_document_chunks_embedding_hnsw 
ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

## 📚 API Reference

### FKSIntelligence

Main RAG orchestrator class.

```python
class FKSIntelligence:
    def __init__(self, 
                 openai_model: str = "gpt-4o-mini",
                 embedding_model: str = "all-MiniLM-L6-v2",
                 use_local: bool = True,
                 local_llm_model: str = "llama3.2:3b")
    
    def query(self,
             question: str,
             symbol: Optional[str] = None,
             doc_types: Optional[List[str]] = None,
             top_k: int = 5) -> Dict[str, Any]
    
    def suggest_strategy(self,
                        symbol: str,
                        market_condition: Optional[str] = None) -> Dict[str, Any]
    
    def explain_signal(self,
                      symbol: str,
                      current_indicators: Dict[str, float]) -> Dict[str, Any]
    
    def analyze_past_trades(self,
                           symbol: Optional[str] = None) -> Dict[str, Any]
```

### DataIngestionPipeline

Auto-ingestion pipeline for trading data.

```python
class DataIngestionPipeline:
    def ingest_signal(self,
                     signal_data: Dict[str, Any]) -> Optional[int]
    
    def ingest_backtest_result(self,
                              backtest_data: Dict[str, Any]) -> Optional[int]
    
    def ingest_completed_trade(self,
                              trade_id: int) -> Optional[int]
    
    def ingest_market_analysis(self,
                              analysis_text: str,
                              symbol: str,
                              timeframe: str) -> Optional[int]
    
    def batch_ingest_recent_trades(self,
                                   days: int = 30) -> int
```

## 🤝 Contributing

When adding new features:

1. **Document new doc_types** in `Document` model
2. **Update chunking logic** in `document_processor.py` if needed
3. **Add tests** for new functionality
4. **Update this README** with examples

## 📄 License

MIT License - See main project LICENSE file.

## 🔗 Related Documentation

- [Project Architecture](../../../docs/ARCHITECTURE.md)
- [Celery Tasks](../../trading/tasks.py)
- [Database Schema](../../../sql/init.sql)
- [Docker GPU Setup](../../../docker-compose.gpu.yml)
