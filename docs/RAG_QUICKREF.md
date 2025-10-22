# RAG Foundation Quick Reference

Quick reference for FKS Intelligence RAG system (Phase 1).

## Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up database
python scripts/setup_rag_foundation.py

# 3. Validate setup
python scripts/validate_rag_foundation.py
```

## Basic Usage

### Import the RAG System

```python
from web.rag.services import IntelligenceOrchestrator
from web.rag.intelligence import create_intelligence
from web.rag.embeddings import create_embeddings_service
```

### Initialize

```python
# Option 1: Simple orchestrator (recommended)
orchestrator = IntelligenceOrchestrator()

# Option 2: Full intelligence system
intelligence = create_intelligence(
    use_local=True,  # Use local models (sentence-transformers)
    embedding_model="all-MiniLM-L6-v2"  # Fast, 384-dim embeddings
)
```

### Ingest Documents

```python
# Ingest a trading signal
doc_id = intelligence.ingest_document(
    content="BTCUSDT bullish momentum building. RSI: 65, MACD: positive",
    doc_type="signal",
    title="BTCUSDT Buy Signal",
    symbol="BTCUSDT",
    metadata={
        'timeframe': '1h',
        'indicators': {'rsi': 65, 'macd': 'bullish'},
        'confidence': 0.85
    }
)
```

### Query the Knowledge Base

```python
# General query
result = intelligence.query(
    question="What are good entry points for Bitcoin?",
    symbol='BTCUSDT',
    top_k=5
)
print(result['answer'])

# Get trading recommendation
recommendation = orchestrator.get_trading_recommendation(
    symbol="BTCUSDT",
    account_balance=10000.00,
    context="current market conditions"
)
```

### Semantic Search

```python
from web.rag.retrieval import create_retrieval_service

retrieval = create_retrieval_service()

results = retrieval.retrieve_context(
    query="Bitcoin support levels",
    top_k=5,
    filters={'symbol': 'BTCUSDT', 'doc_type': 'signal'}
)

for result in results:
    print(f"[{result['similarity']:.2f}] {result['content']}")
```

## Database Schema

### Tables

- **documents** - Source documents (signals, backtests, analyses)
- **document_chunks** - Text chunks with embeddings
- **query_history** - RAG query/response history
- **trading_insights** - Curated insights

### Example Queries

```python
from core.database.models import Session, Document, DocumentChunk

session = Session()

# Find all signals for BTCUSDT
signals = session.query(Document).filter(
    Document.doc_type == 'signal',
    Document.symbol == 'BTCUSDT'
).all()

# Get recent insights
from datetime import datetime, timedelta
recent = session.query(TradingInsight).filter(
    TradingInsight.created_at >= datetime.now() - timedelta(days=7)
).all()

session.close()
```

## Configuration

### Environment Variables

```bash
# Required
DATABASE_URL=postgresql://user:pass@localhost:5432/trading_db

# Optional (for OpenAI embeddings/LLM)
OPENAI_API_KEY=sk-...

# Optional (for local LLM via Ollama)
OLLAMA_HOST=http://localhost:11434
```

### Model Options

**Embeddings:**
- `all-MiniLM-L6-v2` - Fast, 384 dim (default)
- `all-mpnet-base-v2` - Better quality, 768 dim
- `text-embedding-3-small` - OpenAI, 1536 dim

**LLM (Ollama):**
- `llama3.2:3b` - Fast, good quality
- `llama3.2:1b` - Very fast, smaller
- `mistral:7b` - Better quality, slower

## Testing

```bash
# Run validation
python scripts/validate_rag_foundation.py

# Run unit tests
pytest tests/unit/test_rag/ -v

# Run specific test
pytest tests/unit/test_rag/test_embeddings_mocked.py -v

# With coverage
pytest tests/unit/test_rag/ -v --cov=src/web/rag
```

## Common Tasks

### Check pgvector Installation

```bash
# Connect to database
psql -U postgres -d trading_db

# Check if extension exists
SELECT * FROM pg_extension WHERE extname = 'vector';

# Enable if not present
CREATE EXTENSION IF NOT EXISTS vector;
```

### Verify Vector Indexes

```sql
-- Check if HNSW index exists
SELECT indexname FROM pg_indexes 
WHERE tablename = 'document_chunks' 
AND indexname LIKE '%embedding%';
```

### Reset RAG Tables

```bash
# WARNING: This deletes all RAG data
psql -U postgres -d trading_db -c "
DROP TABLE IF EXISTS query_history CASCADE;
DROP TABLE IF EXISTS trading_insights CASCADE;
DROP TABLE IF EXISTS document_chunks CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
"

# Then recreate
python scripts/setup_rag_foundation.py
```

## Troubleshooting

### Import Errors

```python
# Ensure correct path
import sys
sys.path.insert(0, 'src')

# Or set PYTHONPATH
export PYTHONPATH=/path/to/fks/src:$PYTHONPATH
```

### pgvector Not Found

```bash
# Install pgvector
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Enable in database
psql -U postgres -d trading_db -c "CREATE EXTENSION vector;"
```

### Slow Semantic Search

```sql
-- Create HNSW index for fast similarity search
CREATE INDEX idx_document_chunks_embedding_hnsw 
ON document_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

## Files Reference

### SQL Migrations
- `sql/migrations/000_create_rag_tables.sql` - Create RAG tables
- `sql/migrations/001_add_pgvector.sql` - Enable pgvector

### Python Modules
- `src/web/rag/embeddings.py` - Embedding generation
- `src/web/rag/document_processor.py` - Text chunking
- `src/web/rag/retrieval.py` - Semantic search
- `src/web/rag/intelligence.py` - Main orchestrator
- `src/web/rag/ingestion.py` - Data pipeline
- `src/web/rag/services.py` - Public API

### Scripts
- `scripts/setup_rag_foundation.py` - Setup script
- `scripts/validate_rag_foundation.py` - Validation script
- `scripts/test_rag_system.py` - Test suite
- `scripts/rag_example.py` - Usage examples

### Documentation
- `docs/RAG_PHASE1.md` - Full Phase 1 documentation
- `src/web/rag/README.md` - RAG system README

## Next Steps

After Phase 1 setup:
1. Phase 2: Auto-ingestion pipeline
2. Phase 3: LLM integration
3. Phase 4: Trading recommendations
4. Phase 5: Continuous learning

## Support

See full documentation:
- `docs/RAG_PHASE1.md` - Phase 1 complete guide
- `src/web/rag/README.md` - RAG system guide
- `docs/ARCHITECTURE.md` - Project architecture
