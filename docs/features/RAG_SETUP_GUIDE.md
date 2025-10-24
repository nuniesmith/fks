# FKS Intelligence - RAG System Setup Guide

## Overview

FKS Intelligence is a Retrieval-Augmented Generation (RAG) system that provides intelligent querying of your trading knowledge base. It stores trading signals, backtests, trade analyses, and market reports, then allows you to ask questions and get AI-powered insights based on your historical data.

## Features

- **Document Processing**: Automatically chunks and indexes trading documents
- **Semantic Search**: Find relevant trading information using natural language
- **LLM Integration**: GPT-4 powered responses with context from your trading history
- **Trading Insights**: Curated lessons learned and pattern observations
- **Automated Ingestion**: Automatically ingests completed trades and backtests

## Architecture

```
User Query
    ↓
FKS Intelligence
    ↓
Query Embedding (OpenAI)
    ↓
Semantic Search (pgvector)
    ↓
Context Retrieval
    ↓
LLM Generation (GPT-4)
    ↓
Response + Sources
```

## Prerequisites

1. **PostgreSQL with pgvector extension** (already included in TimescaleDB container)
2. **OpenAI API Key** for embeddings and generation
3. **Python dependencies** (see requirements.txt)

## Setup Instructions

### 1. Environment Configuration

Add to your `.env` file:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here
```

### 2. Database Setup

Enable pgvector extension:

```bash
# Run migration
docker exec -it fks_db psql -U postgres -d trading_db -f /docker-entrypoint-initdb.d/migrations/001_add_pgvector.sql
```

Or manually:

```sql
-- Connect to database
docker exec -it fks_db psql -U postgres -d trading_db

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Create tables (run from Python)
python -c "from database import init_db; init_db()"
```

### 3. Install Dependencies

Dependencies are already in `requirements.txt`:
- pgvector>=0.3.6
- tiktoken>=0.9.0
- langchain and related packages

```bash
# If needed, reinstall
docker-compose exec web pip install -r requirements.txt
```

### 4. Initialize Knowledge Base

```python
from rag.intelligence import create_intelligence
from database import Session

# Create intelligence instance
intelligence = create_intelligence()

# Test ingestion
session = Session()
doc_id = intelligence.ingest_document(
    content="Bitcoin shows strong support at 40k level with RSI indicating oversold conditions.",
    doc_type="market_report",
    title="BTC Market Analysis",
    symbol="BTCUSDT",
    timeframe="1h",
    session=session
)
session.close()

print(f"Document ingested with ID: {doc_id}")
```

### 5. Ingest Historical Data

```python
from rag.ingestion import create_ingestion_pipeline

# Create pipeline
pipeline = create_ingestion_pipeline()

# Batch ingest recent trades (last 30 days)
count = pipeline.batch_ingest_recent_trades(days=30)
print(f"Ingested {count} trades")
```

## Usage Examples

### Basic Query

```python
from rag.intelligence import create_intelligence

intelligence = create_intelligence()

# Ask a question
result = intelligence.query(
    question="What strategy works best for BTCUSDT?",
    symbol="BTCUSDT"
)

print(f"Answer: {result['answer']}")
print(f"Sources: {len(result['sources'])} relevant documents")
```

### Strategy Suggestion

```python
# Get strategy recommendation
result = intelligence.suggest_strategy(
    symbol="ETHUSDT",
    market_condition="trending"
)

print(result['answer'])
```

### Analyze Past Performance

```python
# Analyze trading history
result = intelligence.analyze_past_trades(symbol="BTCUSDT")

print(result['answer'])
```

### Explain Signal

```python
# Get context for current signal
result = intelligence.explain_signal(
    symbol="SOLUSDT",
    current_indicators={
        'rsi': 32.5,
        'macd': -1.2,
        'sma_20': 145.30
    }
)

print(result['answer'])
```

### Ingest New Documents

```python
from rag.ingestion import create_ingestion_pipeline

pipeline = create_ingestion_pipeline()

# Ingest a signal
signal_data = {
    'symbol': 'BTCUSDT',
    'action': 'BUY',
    'timeframe': '1h',
    'timestamp': '2025-10-16T10:30:00',
    'price': 42500,
    'indicators': {
        'rsi': 35,
        'macd': -0.5
    },
    'reasoning': 'RSI oversold, MACD showing bullish divergence'
}

doc_id = pipeline.ingest_signal(signal_data)

# Ingest backtest results
backtest_data = {
    'strategy_name': 'RSI Mean Reversion',
    'symbol': 'ETHUSDT',
    'timeframe': '15m',
    'total_return': 15.5,
    'win_rate': 65.2,
    'sharpe_ratio': 1.8,
    'max_drawdown': -8.3,
    'total_trades': 145,
    'parameters': {
        'rsi_period': 14,
        'oversold': 30,
        'overbought': 70
    }
}

doc_id = pipeline.ingest_backtest_result(backtest_data)
```

## API Reference

### FKSIntelligence

Main RAG orchestrator class.

**Methods:**

- `query(question, symbol=None, doc_types=None, top_k=5)` - Query knowledge base
- `suggest_strategy(symbol, market_condition=None)` - Get strategy recommendation
- `analyze_past_trades(symbol=None)` - Analyze trading history
- `explain_signal(symbol, current_indicators)` - Explain trading signal
- `ingest_document(content, doc_type, title, symbol, timeframe, metadata)` - Add document

### DataIngestionPipeline

Automated data ingestion pipeline.

**Methods:**

- `ingest_completed_trade(trade_id)` - Ingest single trade
- `ingest_backtest_result(backtest_data)` - Ingest backtest
- `ingest_signal(signal_data)` - Ingest trading signal
- `ingest_market_analysis(analysis_text, symbol, timeframe)` - Ingest analysis
- `batch_ingest_recent_trades(days=30)` - Batch ingest trades

## Document Types

- `signal` - Trading signals
- `backtest` - Backtest results
- `trade_analysis` - Completed trade analyses
- `market_report` - Market analysis reports
- `strategy` - Strategy descriptions
- `insight` - Curated trading insights
- `log` - System logs
- `other` - Other documents

## Database Schema

### documents
- `id` - Document ID
- `doc_type` - Document type
- `title` - Document title
- `content` - Full content
- `symbol` - Trading pair
- `timeframe` - Timeframe
- `metadata` - JSON metadata
- `created_at` - Creation timestamp

### document_chunks
- `id` - Chunk ID
- `document_id` - Parent document
- `chunk_index` - Order in document
- `content` - Chunk text
- `embedding` - Vector embedding (1536 dimensions)
- `token_count` - Number of tokens
- `metadata` - JSON metadata

### query_history
- `id` - Query ID
- `query` - User question
- `response` - AI response
- `retrieved_chunks` - JSON array of chunk info
- `model_used` - LLM model
- `response_time_ms` - Response time
- `created_at` - Query timestamp

### trading_insights
- `id` - Insight ID
- `insight_type` - Type of insight
- `title` - Insight title
- `content` - Insight content
- `symbol` - Related symbol
- `impact` - Impact level (high/medium/low)
- `category` - Category
- `tags` - Array of tags

## Performance Optimization

### Embedding Generation
- Batch size: 100 texts per API call
- Model: text-embedding-3-small (1536 dimensions)
- Cost: ~$0.02 per 1M tokens

### Vector Search
- Index: HNSW (fast approximate nearest neighbor)
- Similarity: Cosine distance
- Typical query time: <100ms for 10k documents

### Context Window
- Max tokens per query: 4000 tokens (~16,000 characters)
- Default chunks retrieved: 5
- Chunk size: 512 tokens with 50 token overlap

## Monitoring

### Query Performance

```python
from database import Session, QueryHistory

session = Session()

# Get recent queries
queries = session.query(QueryHistory).order_by(
    QueryHistory.created_at.desc()
).limit(10).all()

for q in queries:
    print(f"{q.query[:50]}... - {q.response_time_ms}ms")
```

### Document Statistics

```python
from database import Session, Document
from sqlalchemy import func

session = Session()

# Count by type
stats = session.query(
    Document.doc_type,
    func.count(Document.id)
).group_by(Document.doc_type).all()

for doc_type, count in stats:
    print(f"{doc_type}: {count} documents")
```

## Troubleshooting

### pgvector Extension Not Found

```sql
-- Verify extension
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Install if missing
CREATE EXTENSION vector;
```

### Slow Query Performance

```sql
-- Check if index exists
SELECT indexname FROM pg_indexes WHERE tablename = 'document_chunks';

-- Rebuild index if needed
REINDEX INDEX idx_document_chunks_embedding_hnsw;
```

### OpenAI API Errors

- Check API key in `.env`
- Verify API quota/billing
- Monitor rate limits

## Cost Estimation

### Embeddings
- 1000 documents × 2 chunks avg = 2000 chunks
- 2000 chunks × 512 tokens = 1,024,000 tokens
- Cost: ~$0.02

### LLM Queries
- 100 queries/day × 1500 tokens avg = 150,000 tokens/day
- Using GPT-4o-mini: ~$0.15/day
- Monthly: ~$4.50

## Next Steps

1. **Automated Ingestion**: Set up Celery task to auto-ingest new trades
2. **UI Integration**: Add intelligence queries to Django views
3. **Insights Curation**: Create trading insights from patterns
4. **Advanced Features**: Multi-modal search, time-aware retrieval

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review query history in database
3. Test with simple queries first
