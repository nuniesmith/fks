# Phase 1: RAG Foundation Setup

This document describes the basic RAG (Retrieval-Augmented Generation) infrastructure setup for the FKS Trading Platform.

## Overview

Phase 1 establishes the foundation for the FKS Intelligence system by setting up:

1. **Vector Database**: PostgreSQL with pgvector extension for semantic search
2. **Database Schema**: Tables for documents, chunks, queries, and insights
3. **Embeddings Service**: Support for both local (sentence-transformers) and OpenAI embeddings
4. **Document Processing**: Text chunking and tokenization for RAG
5. **Retrieval Service**: Semantic search and context retrieval

## What's Included

### Database Tables

- **`documents`**: Stores source documents (signals, backtests, trade analyses, etc.)
- **`document_chunks`**: Document chunks with embeddings for semantic search
- **`query_history`**: Tracks RAG queries and responses
- **`trading_insights`**: Curated trading insights and lessons learned

### Python Modules

Located in `src/web/rag/`:

- **`embeddings.py`**: Embedding generation and storage with pgvector
- **`document_processor.py`**: Document chunking and tokenization
- **`retrieval.py`**: Semantic search and context retrieval
- **`intelligence.py`**: Main RAG orchestrator
- **`ingestion.py`**: Data ingestion pipeline
- **`orchestrator.py`**: Simplified API for trading recommendations
- **`local_llm.py`**: Local LLM support (Ollama/transformers)
- **`services.py`**: Public API exports

### SQL Migrations

Located in `sql/migrations/`:

1. **`000_create_rag_tables.sql`**: Creates all RAG tables
2. **`001_add_pgvector.sql`**: Enables pgvector and creates vector indexes

## Setup Instructions

### Prerequisites

1. **PostgreSQL 12+** with pgvector extension
2. **Python 3.12+**
3. **Required packages** (in `requirements.txt`):
   - `sqlalchemy>=2.0.0`
   - `psycopg2-binary>=2.9.0`
   - `openai>=1.0.0` (optional, for OpenAI embeddings)
   - `sentence-transformers>=2.0.0` (optional, for local embeddings)
   - `tiktoken>=0.5.0`
   - `numpy>=1.24.0`

### Quick Start

#### Option 1: Using the Setup Script (Recommended)

```bash
# Run the automated setup script
python scripts/setup_rag_foundation.py

# With custom database URL
python scripts/setup_rag_foundation.py --db-url postgresql://user:pass@host:5432/dbname

# Skip functionality tests
python scripts/setup_rag_foundation.py --no-test
```

The script will:
1. Check database connectivity
2. Enable pgvector extension
3. Create RAG tables
4. Create vector indexes
5. Run basic functionality tests

#### Option 2: Manual Setup

```bash
# 1. Install pgvector (if not already installed)
# See: https://github.com/pgvector/pgvector

# 2. Connect to your database
psql -U postgres -d trading_db

# 3. Run migrations in order
\i sql/migrations/000_create_rag_tables.sql
\i sql/migrations/001_add_pgvector.sql
```

### Verify Installation

```python
from web.rag.services import IntelligenceOrchestrator
from core.database.models import Session, Document

# Test database connectivity
session = Session()
docs = session.query(Document).all()
print(f"Found {len(docs)} documents")
session.close()

# Test embeddings service (requires dependencies)
from web.rag.embeddings import create_embeddings_service

service = create_embeddings_service(use_local=True)
embedding = service.generate_embedding("Test text")
print(f"Generated {len(embedding)}-dimensional embedding")
```

## Usage Examples

### Basic Document Ingestion

```python
from web.rag.intelligence import create_intelligence

# Initialize RAG system
intelligence = create_intelligence(use_local=True)

# Ingest a trading signal
doc_id = intelligence.ingest_document(
    content="BTCUSDT showing bullish momentum. RSI: 65, MACD: positive crossover",
    doc_type="signal",
    title="BTCUSDT Bullish Signal",
    symbol="BTCUSDT",
    metadata={
        'timeframe': '1h',
        'indicators': {'rsi': 65, 'macd': 'bullish'},
        'confidence': 0.85
    }
)
```

### Semantic Search

```python
from web.rag.retrieval import create_retrieval_service

# Create retrieval service
retrieval = create_retrieval_service()

# Search for relevant context
results = retrieval.retrieve_context(
    query="What are good entry points for Bitcoin?",
    top_k=5,
    filters={'symbol': 'BTCUSDT'}
)

for result in results:
    print(f"[{result['similarity']:.2f}] {result['content'][:100]}...")
```

### Trading Recommendations

```python
from web.rag.services import IntelligenceOrchestrator

# Create orchestrator
orchestrator = IntelligenceOrchestrator()

# Get trading recommendation
recommendation = orchestrator.get_trading_recommendation(
    symbol="BTCUSDT",
    account_balance=10000.00,
    context="current market conditions"
)

print(recommendation['recommendation'])
```

## Architecture

### Data Flow

```
Trading Data → Document Processor → Embeddings → pgvector (PostgreSQL)
                                                        ↓
User Query → Retrieval Service → Context + LLM → Trading Insights
```

### Components

1. **Document Processor**
   - Chunks documents into processable segments
   - Handles token counting and overlap
   - Preserves metadata across chunks

2. **Embeddings Service**
   - Generates embeddings (local or OpenAI)
   - Stores vectors in pgvector
   - Supports batch processing

3. **Retrieval Service**
   - Performs semantic search using cosine similarity
   - Applies filters (symbol, doc_type, timeframe)
   - Ranks and reranks results

4. **Intelligence Orchestrator**
   - Combines retrieval + LLM generation
   - Provides high-level API
   - Manages conversation context

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/trading_db

# OpenAI (optional, for OpenAI embeddings/LLM)
OPENAI_API_KEY=sk-...

# Ollama (optional, for local LLM)
OLLAMA_HOST=http://localhost:11434
```

### Model Selection

**Embedding Models:**
- `all-MiniLM-L6-v2`: Fast, 384 dimensions (default local)
- `all-mpnet-base-v2`: Better quality, 768 dimensions
- `text-embedding-3-small`: OpenAI, 1536 dimensions

**LLM Models (Ollama):**
- `llama3.2:3b`: Small, fast (3B parameters)
- `llama3.2:1b`: Tiny, very fast (1B parameters)
- `mistral:7b`: Good quality (7B parameters)

## Testing

### Run Unit Tests

```bash
# All RAG tests
pytest tests/unit/test_rag/ -v

# Specific test file
pytest tests/unit/test_rag/test_embeddings_mocked.py -v

# With coverage
pytest tests/unit/test_rag/ -v --cov=src/web/rag
```

### Run Integration Tests

```bash
# Example usage script
python scripts/rag_example.py

# Comprehensive test suite
python scripts/test_rag_system.py
```

## Troubleshooting

### pgvector not found

```bash
# Install pgvector
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Enable in database
psql -U postgres -d trading_db -c "CREATE EXTENSION vector;"
```

### Permission denied creating extension

```bash
# Connect as superuser
psql -U postgres -d trading_db

# Grant necessary permissions
GRANT ALL ON DATABASE trading_db TO your_user;
```

### Import errors

```python
# Ensure you're running from project root with correct PYTHONPATH
import sys
sys.path.insert(0, 'src')

# Or set PYTHONPATH
export PYTHONPATH=/path/to/fks/src:$PYTHONPATH
```

### Slow semantic search

```sql
-- Check if HNSW index exists
SELECT indexname FROM pg_indexes 
WHERE tablename = 'document_chunks' 
AND indexname LIKE '%embedding%';

-- Create if missing (from pgvector migration)
CREATE INDEX idx_document_chunks_embedding_hnsw 
ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

## Next Steps

After completing Phase 1, you're ready for:

- **Phase 2**: Auto-ingestion pipeline for trading data
- **Phase 3**: LLM integration for intelligent responses
- **Phase 4**: Trading recommendation engine
- **Phase 5**: Continuous learning and optimization

## Files Modified/Created

### New Files
- `sql/migrations/000_create_rag_tables.sql` - RAG database schema
- `scripts/setup_rag_foundation.py` - Automated setup script
- `docs/RAG_PHASE1.md` - This documentation

### Modified Files
- `src/web/rag/__init__.py` - Fixed import paths
- `src/web/rag/embeddings.py` - Fixed duplicate Session import
- `src/web/rag/intelligence.py` - Fixed database imports
- `src/web/rag/ingestion.py` - Fixed database imports
- `src/web/rag/orchestrator.py` - Fixed database imports
- `src/web/rag/retrieval.py` - Fixed database imports
- `sql/migrations/001_add_pgvector.sql` - Enhanced pgvector setup

## References

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [Sentence Transformers](https://www.sbert.net/)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [Project Architecture](../ARCHITECTURE.md)
- [RAG System README](../src/web/rag/README.md)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review test files in `tests/unit/test_rag/`
3. Consult the main project documentation
4. Open an issue on GitHub
