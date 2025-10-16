# FKS Project Improvement Plan

## Executive Summary

This document outlines a comprehensive plan to fix issues and integrate the RAG-based FKS Intelligence system into the trading platform. The plan addresses code quality, structural improvements, and feature additions.

## Phase 1: Core Issues and RAG Integration (✅ COMPLETED)

### 1.1 RAG System Implementation (✅ DONE)

**Completed:**
- ✅ Added `pgvector>=0.3.6` to requirements.txt
- ✅ Updated docker-compose.yml to enable pgvector in TimescaleDB
- ✅ Created RAG database models (Document, DocumentChunk, QueryHistory, TradingInsight)
- ✅ Implemented DocumentProcessor for chunking with sliding window
- ✅ Created EmbeddingsService with OpenAI integration
- ✅ Built RetrievalService for semantic search
- ✅ Developed FKSIntelligence orchestrator
- ✅ Created DataIngestionPipeline for automated data ingestion
- ✅ Added SQL migration for pgvector setup
- ✅ Created comprehensive documentation (RAG_SETUP_GUIDE.md)

**Files Created:**
- `src/rag/document_processor.py` - Document chunking (512 tokens, 50 overlap)
- `src/rag/embeddings.py` - OpenAI embeddings + pgvector storage
- `src/rag/retrieval.py` - Semantic search and context retrieval
- `src/rag/intelligence.py` - Main RAG orchestrator
- `src/rag/ingestion.py` - Automated ingestion pipeline
- `src/rag/__init__.py` - Module initialization
- `sql/migrations/001_add_pgvector.sql` - Database migration
- `docs/RAG_SETUP_GUIDE.md` - Complete setup guide

**Database Models Added:**
```python
Document          # Source documents
DocumentChunk     # Chunks with embeddings (vector)
QueryHistory      # Query logs and analytics
TradingInsight    # Curated lessons learned
```

### 1.2 Dependencies Updated

**Added to requirements.txt:**
- pgvector>=0.3.6 - PostgreSQL vector extension
- tiktoken>=0.9.0 - Token counting

**Already Present:**
- langchain, langchain-openai - RAG framework
- openai - Embeddings and LLM
- sentence-transformers - Alternative embeddings

## Phase 2: Integration and UI (NEXT STEPS)

### 2.1 Django Views Integration (TODO)

Create RAG API endpoints:

```python
# src/trading/views/intelligence.py

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from rag.intelligence import create_intelligence

@require_http_methods(["POST"])
def query_knowledge_base(request):
    """Query FKS Intelligence"""
    data = json.loads(request.body)
    intelligence = create_intelligence()
    
    result = intelligence.query(
        question=data['question'],
        symbol=data.get('symbol'),
        doc_types=data.get('doc_types')
    )
    
    return JsonResponse(result)

@require_http_methods(["POST"])
def suggest_strategy(request):
    """Get strategy suggestion"""
    data = json.loads(request.body)
    intelligence = create_intelligence()
    
    result = intelligence.suggest_strategy(
        symbol=data['symbol'],
        market_condition=data.get('market_condition')
    )
    
    return JsonResponse(result)
```

**URL Routing:**
```python
# src/trading/urls.py

urlpatterns = [
    path('intelligence/query/', query_knowledge_base, name='intelligence_query'),
    path('intelligence/suggest/', suggest_strategy, name='intelligence_suggest'),
    path('intelligence/analyze/', analyze_trades, name='intelligence_analyze'),
]
```

### 2.2 UI Components (TODO)

**Option A: Django Template**
```html
<!-- templates/trading/intelligence.html -->
<div class="intelligence-panel">
  <h3>🧠 FKS Intelligence</h3>
  <form id="query-form">
    <textarea name="question" placeholder="Ask about your trading..."></textarea>
    <select name="symbol">
      <option value="">All Symbols</option>
      <option value="BTCUSDT">BTCUSDT</option>
      <option value="ETHUSDT">ETHUSDT</option>
    </select>
    <button type="submit">Ask</button>
  </form>
  <div id="response"></div>
</div>
```

**Option B: Streamlit Integration**
```python
# Add to src/app.py

import streamlit as st
from rag.intelligence import create_intelligence

# Add intelligence tab
tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Signals", "Intelligence", "Settings"])

with tab3:
    st.header("🧠 FKS Intelligence")
    
    question = st.text_area("Ask about your trading history:")
    symbol = st.selectbox("Symbol (optional)", ["All"] + SYMBOLS)
    
    if st.button("Query"):
        with st.spinner("Thinking..."):
            intelligence = create_intelligence()
            result = intelligence.query(
                question=question,
                symbol=symbol if symbol != "All" else None
            )
            
            st.success("Answer:")
            st.write(result['answer'])
            
            with st.expander("Sources"):
                for i, source in enumerate(result['sources'], 1):
                    st.write(f"{i}. {source['doc_type']} - {source['similarity']:.2f}")
                    st.code(source['content'][:200])
```

### 2.3 Automated Ingestion (TODO)

Create Celery task for automatic ingestion:

```python
# src/fks_project/celery.py (add task)

from celery import shared_task
from rag.ingestion import create_ingestion_pipeline

@shared_task
def ingest_recent_trades():
    """Automatically ingest completed trades"""
    pipeline = create_ingestion_pipeline()
    count = pipeline.batch_ingest_recent_trades(days=1)
    return f"Ingested {count} trades"

# Schedule in celery beat
app.conf.beat_schedule = {
    'ingest-trades-daily': {
        'task': 'fks_project.celery.ingest_recent_trades',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
}
```

## Phase 3: Code Quality and Structure (TODO)

### 3.1 Directory Consolidation

**Current Issues:**
- Multiple `domain/` directories: `src/data/domain`, `src/engine/domain`, etc.
- Deep nesting in some areas

**Proposed Structure:**
```
src/
├── rag/              # RAG system (✅ DONE)
├── trading/          # Django app (✅ EXISTS)
├── fks_project/      # Django project (✅ EXISTS)
├── domain/           # Unified domain models
│   ├── entities/     # Core entities
│   ├── strategies/   # Trading strategies
│   └── services/     # Business logic
├── data/             # Data fetching
├── engine/           # Trading engine
└── utils/            # Shared utilities
```

**Action Items:**
1. Merge all `domain/` subdirectories into single `src/domain/`
2. Move `trading/strategies/` to `domain/strategies/`
3. Consolidate utilities into `src/utils/`

### 3.2 Linting and Type Checking

**Run ruff:**
```bash
# Check code
docker-compose exec web ruff check src/

# Auto-fix
docker-compose exec web ruff check --fix src/
```

**Run mypy:**
```bash
# Type checking
docker-compose exec web mypy src/
```

**Common Issues to Fix:**
- Missing type hints
- Unused imports
- Long lines (>100 chars)
- Missing docstrings

### 3.3 Testing

**Create RAG Tests:**
```python
# src/rag/tests/test_intelligence.py

import pytest
from rag.intelligence import FKSIntelligence

def test_document_ingestion():
    intelligence = FKSIntelligence()
    doc_id = intelligence.ingest_document(
        content="Test signal",
        doc_type="signal",
        symbol="BTCUSDT"
    )
    assert doc_id > 0

def test_query():
    intelligence = FKSIntelligence()
    result = intelligence.query("What is the best strategy?")
    assert 'answer' in result
    assert 'sources' in result
```

**Run Tests:**
```bash
docker-compose exec web pytest src/rag/tests/
```

## Phase 4: Assets and Improvements (TODO)

### 4.1 Add Missing Assets

**Logo and Branding:**
- Add logo to `src/static/images/logo.png`
- Update templates with branding

**Favicon:**
```html
<!-- Add to base template -->
<link rel="icon" href="{% static 'images/favicon.ico' %}" type="image/x-icon">
```

### 4.2 Enhanced Analytics

**Trading Insights Dashboard:**
- Visualize query patterns
- Show knowledge base statistics
- Display top insights

```python
# src/trading/views/analytics.py

def intelligence_analytics(request):
    """Show RAG analytics"""
    session = Session()
    
    # Query statistics
    total_queries = session.query(QueryHistory).count()
    avg_response_time = session.query(func.avg(QueryHistory.response_time_ms)).scalar()
    
    # Document statistics
    doc_stats = session.query(
        Document.doc_type,
        func.count(Document.id)
    ).group_by(Document.doc_type).all()
    
    return render(request, 'trading/intelligence_analytics.html', {
        'total_queries': total_queries,
        'avg_response_time': avg_response_time,
        'doc_stats': doc_stats
    })
```

## Implementation Timeline

### Week 1-2: RAG Foundation (✅ COMPLETED)
- ✅ Database models and migrations
- ✅ Core RAG services
- ✅ Document processing
- ✅ Embeddings and retrieval
- ✅ Documentation

### Week 3: Integration (IN PROGRESS)
- [ ] Django views and URLs
- [ ] Celery tasks for auto-ingestion
- [ ] Initial data ingestion

### Week 4: UI and Testing
- [ ] Streamlit UI components
- [ ] Django templates
- [ ] Unit tests
- [ ] End-to-end testing

### Week 5: Code Quality
- [ ] Run ruff/mypy
- [ ] Fix linting issues
- [ ] Consolidate directories
- [ ] Add type hints

### Week 6: Polish and Deploy
- [ ] Assets and branding
- [ ] Analytics dashboard
- [ ] Performance optimization
- [ ] Production deployment

## Success Metrics

### Technical Metrics
- [ ] All RAG tests passing
- [ ] Query response time <500ms
- [ ] Zero linting errors
- [ ] Type coverage >80%

### Feature Metrics
- [ ] 1000+ documents ingested
- [ ] 100+ queries processed
- [ ] 90%+ query satisfaction

### Code Quality
- [ ] Consolidated directory structure
- [ ] No duplicate domain folders
- [ ] Full documentation
- [ ] CI/CD pipeline

## Next Immediate Actions

1. **Setup Database** (5 min)
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec db psql -U postgres -d trading_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```

2. **Add OpenAI Key** (2 min)
   ```bash
   echo "OPENAI_API_KEY=sk-..." >> .env
   ```

3. **Test RAG System** (10 min)
   ```python
   from rag.intelligence import create_intelligence
   intelligence = create_intelligence()
   result = intelligence.query("Test query")
   print(result)
   ```

4. **Ingest Sample Data** (15 min)
   ```python
   from rag.ingestion import create_ingestion_pipeline
   pipeline = create_ingestion_pipeline()
   pipeline.batch_ingest_recent_trades(days=30)
   ```

5. **Add UI Integration** (1-2 hours)
   - Create intelligence views
   - Add to URL routing
   - Update templates

## Conclusion

The RAG system foundation is complete and ready for integration. The next phase focuses on connecting it to the Django web interface and Streamlit dashboard, followed by code quality improvements and testing.

**Status:** Phase 1 Complete ✅ | Phase 2 Ready to Start 🚀
