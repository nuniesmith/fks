#!/usr/bin/env python3
"""
Import AI Architecture issues into GitHub.
Expands Issue #9 (Complete RAG System) with detailed implementation tasks.
"""

import json
import subprocess
import sys
from typing import List, Dict

class AIArchitectureImporter:
    """Import AI architecture implementation issues."""
    
    def __init__(self, repo: str = "nuniesmith/fks", dry_run: bool = False):
        self.repo = repo
        self.dry_run = dry_run
    
    def get_issues(self) -> List[Dict]:
        """Define all AI architecture issues."""
        
        return [
            # Phase 2.2.1: Base Layer - Embeddings
            {
                "title": "[AI-1] Implement Base Layer - Ollama Embeddings",
                "body": """## Overview
Implement the **Base Layer** of the AI architecture using Ollama embeddings (BGE-M3) for RAG data ingestion and semantic search.

**Parent Issue**: #9 (P2.2 - Complete RAG System)  
**Layer**: Base (Embeddings)  
**Priority**: 🟡 High  
**Effort**: Medium (~8-10 hours)

---

## Goals
- ✅ Install and configure Ollama with BGE-M3 embedding model
- ✅ Implement `OllamaEmbeddingService` for document embeddings
- ✅ Integrate with pgvector for semantic search
- ✅ Test embedding generation and similarity search

---

## Tasks

### 1. Docker & Infrastructure Setup (2 hours)
- [ ] 1.1 Update `docker-compose.gpu.yml` to include Ollama service
- [ ] 1.2 Configure Ollama with CUDA/GPU support
- [ ] 1.3 Create `scripts/setup_ollama_models.sh` installation script
- [ ] 1.4 Add Ollama health checks to monitoring stack
- [ ] 1.5 Update `.env.example` with `OLLAMA_HOST` variable

### 2. Install BGE-M3 Model (1 hour)
- [ ] 2.1 Pull BGE-M3 model via Ollama: `ollama pull bge-m3`
- [ ] 2.2 Verify model installation: `ollama list`
- [ ] 2.3 Test basic embedding generation
- [ ] 2.4 Document model parameters (567M, 1024-dim embeddings)

### 3. Implement OllamaEmbeddingService (3 hours)
- [ ] 3.1 Create `src/rag/embeddings.py` module
- [ ] 3.2 Implement `OllamaEmbeddingService` class
  - `embed(text: str) -> List[float]`
  - `embed_documents(texts: List[str]) -> List[List[float]]`
  - `embed_query(query: str) -> List[float]`
- [ ] 3.3 Add connection pooling for Ollama client
- [ ] 3.4 Implement error handling and retries
- [ ] 3.5 Add Prometheus metrics (embedding_requests, embedding_duration)

### 4. pgvector Integration (2 hours)
- [ ] 4.1 Update `src/rag/vector_store.py` to use Ollama embeddings
- [ ] 4.2 Create `document_embeddings` table with vector column
- [ ] 4.3 Implement `add_document()` with embedding generation
- [ ] 4.4 Implement `similarity_search()` using pgvector
- [ ] 4.5 Add metadata filtering support

### 5. Testing (2 hours)
- [ ] 5.1 Create `src/tests/test_ai/test_embeddings.py`
- [ ] 5.2 Unit tests for single/batch embedding generation
- [ ] 5.3 Integration tests for similarity search
- [ ] 5.4 Performance benchmarks (tokens/sec, latency)
- [ ] 5.5 Test with trading data (signals, trades, reports)

---

## Technical Details

### Ollama Service (docker-compose.gpu.yml)
```yaml
ollama:
  image: ollama/ollama:latest
  container_name: fks_ollama
  ports:
    - "11434:11434"
  volumes:
    - ollama_data:/root/.ollama
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
  networks:
    - fks_network
  restart: unless-stopped
```

### Django Settings
```python
# src/web/django/settings.py
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://ollama:11434')
OLLAMA_MODELS = {
    'embedding': 'bge-m3',
}
RAG_CONFIG = {
    'vector_dim': 1024,  # BGE-M3 dimension
    'top_k': 5,
    'similarity_threshold': 0.7,
}
```

### Implementation Example
```python
# src/rag/embeddings.py
from ollama import Client
from typing import List

class OllamaEmbeddingService:
    def __init__(self):
        self.client = Client(host=settings.OLLAMA_HOST)
        self.model = 'bge-m3'
    
    def embed(self, text: str) -> List[float]:
        response = self.client.embeddings(
            model=self.model,
            prompt=text
        )
        return response['embedding']
```

---

## Acceptance Criteria
- ✅ Ollama service running in docker-compose.gpu.yml
- ✅ BGE-M3 model installed and functional
- ✅ OllamaEmbeddingService generates 1024-dim embeddings
- ✅ Embeddings stored in pgvector successfully
- ✅ Similarity search returns relevant results (>0.7 threshold)
- ✅ All tests passing (unit + integration)
- ✅ Performance: <100ms per embedding, ~1000 tokens/sec

---

## Dependencies
- Docker with NVIDIA GPU support
- PostgreSQL with pgvector extension
- Ollama CLI
- Python packages: `ollama`, `pgvector`

---

## Documentation
- ✅ Update `docs/AI_ARCHITECTURE.md` with implementation notes
- ✅ Create `src/rag/README.md` for module documentation
- ✅ Add usage examples to docstrings

---

## References
- Ollama Documentation: https://ollama.ai/
- BGE-M3 Model Card: https://huggingface.co/BAAI/bge-m3
- pgvector Docs: https://github.com/pgvector/pgvector
- AI Architecture Doc: `docs/AI_ARCHITECTURE.md`

---

**Time Estimate**: ~10 hours  
**Assignee**: @nuniesmith  
**Phase**: 2.2 (Complete RAG System)  
**Status**: Ready to start after Phase 1 completion
""",
                "labels": ["🟡 high", "✨ feature", "effort:medium", "phase:2-core", "⚡ performance"],
            },
            
            # Phase 2.2.2: Middle Layer - Reasoning
            {
                "title": "[AI-2] Implement Middle Layer - Reasoning/Coding Models",
                "body": """## Overview
Implement the **Middle Layer** using Qwen3 and Mathstral for math-heavy calculations, backtesting logic, and strategy code generation.

**Parent Issue**: #9 (P2.2 - Complete RAG System)  
**Layer**: Middle (Reasoning/Coding)  
**Priority**: 🟡 High  
**Effort**: High (~12-14 hours)

---

## Goals
- ✅ Install Qwen3:30b and Mathstral models
- ✅ Implement `TradingReasoningEngine` for quantitative analysis
- ✅ Generate trading calculations (ATR, position sizing, R:R ratios)
- ✅ Test math accuracy and reasoning quality

---

## Tasks

### 1. Model Installation (1 hour)
- [ ] 1.1 Pull Qwen3:30b: `ollama pull qwen3:30b`
- [ ] 1.2 Pull Mathstral: `ollama pull mathstral`
- [ ] 1.3 Verify models loaded: `ollama list`
- [ ] 1.4 Test basic inference with sample prompts
- [ ] 1.5 Document model capabilities and parameters

### 2. Implement TradingReasoningEngine (4 hours)
- [ ] 2.1 Create `src/trading/intelligence/reasoning.py`
- [ ] 2.2 Implement `TradingReasoningEngine` class
  - `analyze_trade_setup()` - Full trade analysis
  - `calculate_position_size()` - ATR-based sizing
  - `calculate_risk_reward()` - R:R ratio computation
  - `generate_backtest_code()` - Strategy code generation
- [ ] 2.3 Add model selection logic (Qwen3 vs Mathstral)
- [ ] 2.4 Implement prompt templates for trading tasks
- [ ] 2.5 Add JSON output parsing with validation

### 3. Math Calculations Module (3 hours)
- [ ] 3.1 Create `src/trading/intelligence/calculations.py`
- [ ] 3.2 Implement AI-powered calculations:
  - ATR-based stop loss
  - Position sizing (2% risk rule)
  - Take profit targets (1:2, 1:3 R:R)
  - Expected value computation
  - Sharpe ratio estimation
- [ ] 3.3 Validate AI outputs against manual calculations
- [ ] 3.4 Add fallback to traditional calculations if AI fails

### 4. Strategy Code Generation (2 hours)
- [ ] 4.1 Implement `generate_strategy_code()` method
- [ ] 4.2 Create prompt templates for different strategy types
- [ ] 4.3 Test code generation for RSI, MACD, Bollinger strategies
- [ ] 4.4 Add code validation (syntax check, imports)
- [ ] 4.5 Integration with backtesting engine

### 5. Integration with RAG (2 hours)
- [ ] 5.1 Connect reasoning engine to embedding layer
- [ ] 5.2 Retrieve historical context for decisions
- [ ] 5.3 Combine RAG context + math reasoning
- [ ] 5.4 Test full flow: Retrieve → Reason → Decide

### 6. Testing & Validation (3 hours)
- [ ] 6.1 Create `src/tests/test_ai/test_reasoning.py`
- [ ] 6.2 Unit tests for each calculation method
- [ ] 6.3 Validate math accuracy (compare vs manual)
- [ ] 6.4 Test code generation quality
- [ ] 6.5 Integration tests with real market data
- [ ] 6.6 Performance benchmarks (inference time, VRAM usage)

---

## Technical Details

### Model Selection Strategy
```python
def _select_model(self, task_type: str) -> str:
    """Select appropriate model for task."""
    if task_type in ['math', 'calculation', 'quantitative']:
        return 'mathstral'  # Specialized math model
    else:
        return 'qwen3:30b'  # General reasoning
```

### Trade Analysis Implementation
```python
# Example implementation (see docs/AI_ARCHITECTURE.md for full code)
def analyze_trade_setup(self, symbol: str, market_data: dict, strategy: str):
    # Returns JSON with entry_price, stop_loss, take_profit, position_size, etc.
    pass
```

---

## Acceptance Criteria
- ✅ Qwen3:30b and Mathstral models installed
- ✅ TradingReasoningEngine functional and tested
- ✅ Math calculations accurate (within 1% of manual)
- ✅ Code generation produces valid Python
- ✅ Integration with RAG layer successful
- ✅ All tests passing (20+ test cases)
- ✅ Performance: <2s per inference, ~50 tokens/sec

---

## Performance Benchmarks

| Model | Task | VRAM | Speed | Accuracy |
|-------|------|------|-------|----------|
| Qwen3:30b | General reasoning | 16GB | ~50 tok/s | 90%+ |
| Mathstral | Math calculations | 8GB | ~100 tok/s | 70-73% |

---

## Dependencies
- **Requires**: [AI-1] Base Layer implementation
- Ollama with GPU support
- Python packages: `ollama`, `json`, `typing`

---

## Documentation
- ✅ Update `docs/AI_ARCHITECTURE.md` with reasoning layer details
- ✅ Create `src/trading/intelligence/README.md`
- ✅ Add calculation examples to docstrings

---

## References
- Qwen3 Model Card: https://ollama.ai/library/qwen3
- Mathstral Model Card: https://ollama.ai/library/mathstral
- MGSM Benchmark: https://github.com/google-research/mgsm
- AI Architecture Doc: `docs/AI_ARCHITECTURE.md`

---

**Time Estimate**: ~14 hours  
**Assignee**: @nuniesmith  
**Phase**: 2.2 (Complete RAG System)  
**Status**: Blocked by [AI-1]
""",
                "labels": ["🟡 high", "✨ feature", "effort:high", "phase:2-core", "⚡ performance"],
            },
            
            # Phase 2.2.3: Top Layer - Agentic
            {
                "title": "[AI-3] Implement Top Layer - Agentic Orchestration",
                "body": """## Overview
Implement the **Top Layer** using Llama4:scout for high-level orchestration, tool calling, and autonomous trading decisions.

**Parent Issue**: #9 (P2.2 - Complete RAG System)  
**Layer**: Top (Agentic/Tools)  
**Priority**: 🟡 High  
**Effort**: High (~14-16 hours)

---

## Goals
- ✅ Install Llama4:scout agentic model
- ✅ Implement `IntelligenceOrchestrator` coordinating all layers
- ✅ Add tool/function calling for API integrations
- ✅ Generate end-to-end trading recommendations

---

## Tasks

### 1. Model Installation (1 hour)
- [ ] 1.1 Pull Llama4:scout: `ollama pull llama4:scout`
- [ ] 1.2 Verify model supports function calling
- [ ] 1.3 Test basic tool call examples
- [ ] 1.4 Document model capabilities (109B MoE, 17B active)

### 2. Implement IntelligenceOrchestrator (5 hours)
- [ ] 2.1 Create `src/rag/intelligence.py` module
- [ ] 2.2 Implement `IntelligenceOrchestrator` class
  - `get_trading_recommendation()` - Main entry point
  - `_rag_retrieval()` - Layer 1 integration
  - `_reasoning_analysis()` - Layer 2 integration
  - `_orchestrate_decision()` - Layer 3 logic
- [ ] 2.3 Connect to embedding service (Base Layer)
- [ ] 2.4 Connect to reasoning engine (Middle Layer)
- [ ] 2.5 Implement layered AI flow: RAG → Reason → Decide

### 3. Function/Tool Calling (3 hours)
- [ ] 3.1 Define tool schemas for:
  - `fetch_market_data(symbol: str)`
  - `calculate_position_size(risk_pct: float, atr: float)`
  - `execute_trade(symbol: str, side: str, size: float)`
  - `get_account_balance()`
- [ ] 3.2 Implement tool execution handlers
- [ ] 3.3 Add safety checks (e.g., max position size)
- [ ] 3.4 Test function calling with Llama4

### 4. Decision-Making Logic (3 hours)
- [ ] 4.1 Implement decision prompt templates
- [ ] 4.2 Add portfolio constraint checks
- [ ] 4.3 Implement confidence scoring (0-100)
- [ ] 4.4 Add reasoning explanation generation
- [ ] 4.5 Store decisions for future RAG retrieval

### 5. Integration with Trading System (2 hours)
- [ ] 5.1 Connect to Celery tasks (generate_daily_signals)
- [ ] 5.2 Create Signal objects from recommendations
- [ ] 5.3 Add Discord notifications for decisions
- [ ] 5.4 Implement dry-run mode (no actual trades)

### 6. Testing & Validation (3 hours)
- [ ] 6.1 Create `src/tests/test_ai/test_orchestrator.py`
- [ ] 6.2 Test full recommendation flow (all 3 layers)
- [ ] 6.3 Test function calling accuracy
- [ ] 6.4 Validate decision quality (backtesting)
- [ ] 6.5 Integration tests with live market data
- [ ] 6.6 Performance benchmarks (end-to-end latency)

---

## Technical Details

### Full Orchestration Flow
```python
class IntelligenceOrchestrator:
    def get_trading_recommendation(
        self,
        symbol: str,
        account_balance: float,
        available_cash: float,
        context: str = "current market conditions"
    ) -> Dict[str, Any]:
        # LAYER 1: RAG Retrieval (Base)
        query_embedding = self.embedding_service.embed_query(
            f"Trading analysis for {symbol} {context}"
        )
        relevant_docs = self.vector_store.similarity_search(
            embedding=query_embedding,
            limit=5
        )
        
        # LAYER 2: Reasoning (Middle)
        market_data = self._fetch_market_data(symbol)
        analysis = self.reasoning_engine.analyze_trade_setup(
            symbol=symbol,
            market_data=market_data,
            strategy='trend_following'
        )
        
        # LAYER 3: Agentic Decision (Top)
        recommendation = self._orchestrate_decision(
            symbol=symbol,
            relevant_docs=relevant_docs,
            analysis=analysis,
            account_balance=account_balance,
            available_cash=available_cash
        )
        
        return recommendation
```

### Tool Schema Example
```python
tools = [
    {
        'type': 'function',
        'function': {
            'name': 'execute_trade',
            'description': 'Execute a trade on Binance',
            'parameters': {
                'type': 'object',
                'properties': {
                    'symbol': {'type': 'string'},
                    'side': {'type': 'string', 'enum': ['BUY', 'SELL']},
                    'size': {'type': 'number', 'minimum': 0}
                },
                'required': ['symbol', 'side', 'size']
            }
        }
    }
]
```

---

## Acceptance Criteria
- ✅ Llama4:scout model installed and functional
- ✅ IntelligenceOrchestrator coordinates all 3 layers
- ✅ Function calling works for all defined tools
- ✅ Recommendations include entry/exit/sizing/reasoning
- ✅ Decisions stored for future RAG retrieval
- ✅ Integration with Celery tasks complete
- ✅ All tests passing (15+ test cases)
- ✅ Performance: <5s end-to-end latency

---

## Safety Mechanisms
- ✅ Confidence threshold (only act on >80%)
- ✅ Position size limits (max 10% portfolio)
- ✅ Human approval for large trades (>$1000)
- ✅ Dry-run mode for testing
- ✅ Circuit breaker on consecutive losses

---

## Performance Benchmarks

| Metric | Target | Actual |
|--------|--------|--------|
| End-to-end latency | <5s | TBD |
| Decision accuracy | >60% | TBD |
| Sharpe ratio | >1.5 | TBD |
| Max drawdown | <20% | TBD |

---

## Dependencies
- **Requires**: [AI-1] Base Layer, [AI-2] Middle Layer
- Ollama with GPU support (24GB VRAM)
- Celery for async tasks
- PostgreSQL for decision storage

---

## Documentation
- ✅ Update `docs/AI_ARCHITECTURE.md` with orchestration details
- ✅ Create `src/rag/README.md` with usage examples
- ✅ Document tool schemas and function calling

---

## References
- Llama4 Model Card: https://ollama.ai/library/llama4
- Function Calling Guide: https://docs.ollama.ai/reference/tools
- AI Architecture Doc: `docs/AI_ARCHITECTURE.md`
- FKS Intelligence System: Issue #9

---

**Time Estimate**: ~16 hours  
**Assignee**: @nuniesmith  
**Phase**: 2.2 (Complete RAG System)  
**Status**: Blocked by [AI-1], [AI-2]
""",
                "labels": ["🟡 high", "✨ feature", "effort:high", "phase:2-core", "⚡ performance"],
            },
            
            # Phase 2.2.4: Integration & Testing
            {
                "title": "[AI-4] Integration Testing & Performance Optimization",
                "body": """## Overview
End-to-end integration testing and performance optimization of the complete 3-layer AI architecture.

**Parent Issue**: #9 (P2.2 - Complete RAG System)  
**Priority**: 🟡 High  
**Effort**: Medium (~8-10 hours)

---

## Goals
- ✅ Test complete layered AI flow
- ✅ Optimize performance (latency, VRAM usage)
- ✅ Add monitoring and observability
- ✅ Implement production safeguards

---

## Tasks

### 1. End-to-End Integration Tests (3 hours)
- [ ] 1.1 Create `src/tests/test_ai/test_integration.py`
- [ ] 1.2 Test full recommendation flow:
  - Embed query → Retrieve docs → Reason → Decide
- [ ] 1.3 Test with multiple symbols (BTC, ETH, BNB)
- [ ] 1.4 Test edge cases (no data, conflicting signals)
- [ ] 1.5 Validate decision quality with backtesting

### 2. Performance Optimization (2 hours)
- [ ] 2.1 Benchmark current performance (latency, VRAM)
- [ ] 2.2 Implement caching for embeddings (Redis)
- [ ] 2.3 Add model swapping logic (load/unload on demand)
- [ ] 2.4 Optimize batch processing for embeddings
- [ ] 2.5 Profile and fix bottlenecks

### 3. Monitoring & Observability (2 hours)
- [ ] 3.1 Add Prometheus metrics:
  - `ollama_embedding_requests_total`
  - `ollama_inference_duration_seconds`
  - `ai_recommendation_confidence`
  - `ai_decision_accuracy`
- [ ] 3.2 Create Grafana dashboard for AI performance
- [ ] 3.3 Add logging for all AI operations
- [ ] 3.4 Implement alerting for failures

### 4. Production Safeguards (2 hours)
- [ ] 4.1 Implement confidence threshold filtering
- [ ] 4.2 Add human approval workflow for large trades
- [ ] 4.3 Create dry-run mode (no actual trades)
- [ ] 4.4 Add circuit breaker on consecutive failures
- [ ] 4.5 Implement rollback mechanism

### 5. Documentation & Examples (1 hour)
- [ ] 5.1 Create usage examples in `docs/AI_ARCHITECTURE.md`
- [ ] 5.2 Document API endpoints and parameters
- [ ] 5.3 Add troubleshooting guide
- [ ] 5.4 Create video/tutorial for using AI system

---

## Performance Targets

| Metric | Current | Target | Optimized |
|--------|---------|--------|-----------|
| Embedding latency | - | <100ms | TBD |
| Reasoning latency | - | <2s | TBD |
| Orchestration latency | - | <3s | TBD |
| End-to-end latency | - | <5s | TBD |
| VRAM usage (all models) | - | <24GB | TBD |
| Throughput | - | 20 decisions/min | TBD |

---

## Monitoring Dashboard

### Grafana Panels
1. **AI Request Rate**: Requests/sec by layer
2. **Inference Latency**: p50, p95, p99 by model
3. **Model VRAM Usage**: Current/max by model
4. **Decision Accuracy**: Hit rate over time
5. **Confidence Distribution**: Histogram of confidence scores
6. **Error Rate**: Errors/min by layer

---

## Acceptance Criteria
- ✅ All integration tests passing (20+ scenarios)
- ✅ Performance meets targets (see table above)
- ✅ Monitoring dashboard operational
- ✅ Production safeguards implemented
- ✅ Documentation complete with examples
- ✅ System tested with real market data (7+ days)

---

## Dependencies
- **Requires**: [AI-1], [AI-2], [AI-3] complete
- Prometheus + Grafana for monitoring
- Redis for caching
- 7+ days of historical market data

---

## Documentation
- ✅ Update `docs/AI_ARCHITECTURE.md` with optimization tips
- ✅ Create `docs/AI_TROUBLESHOOTING.md`
- ✅ Add monitoring guide to `monitoring/README.md`

---

**Time Estimate**: ~10 hours  
**Assignee**: @nuniesmith  
**Phase**: 2.2 (Complete RAG System)  
**Status**: Blocked by [AI-1], [AI-2], [AI-3]
""",
                "labels": ["🟡 high", "🧪 tests", "effort:medium", "phase:2-core", "⚡ performance"],
            },
            
            # Update parent issue #9
            {
                "title": "[P2.2] Complete RAG System - AI-Powered Trading Intelligence (UPDATED)",
                "body": """## Overview
**UPDATED**: This issue has been expanded with detailed AI architecture implementation tasks.

Complete the RAG (Retrieval-Augmented Generation) system with **3-layer AI architecture** using Ollama models for intelligent trading insights.

**Phase**: 2 - Core Development  
**Priority**: 🟡 High  
**Effort**: High (~45+ hours total across sub-issues)

---

## Architecture

The FKS Intelligence system uses a **layered AI approach**:

```
┌─────────────────────────────────────────────────────────────┐
│  TOP LAYER: Agentic/Tools (Llama4:scout)                    │
│  Purpose: High-level orchestration, tool calls               │
│  Issue: [AI-3]                                               │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│  MIDDLE LAYER: Reasoning/Coding (Qwen3, Mathstral)          │
│  Purpose: Math calculations, backtesting, strategy code      │
│  Issue: [AI-2]                                               │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│  BASE LAYER: Embeddings (BGE-M3)                             │
│  Purpose: Data vectorization, semantic search in pgvector    │
│  Issue: [AI-1]                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Sub-Issues

### Phase 1: Base Layer (Weeks 1-2)
- **[AI-1]** Implement Ollama Embeddings (~10 hours)
  - Install BGE-M3 model
  - Create `OllamaEmbeddingService`
  - Integrate with pgvector
  - Testing and validation

### Phase 2: Middle Layer (Weeks 3-4)
- **[AI-2]** Implement Reasoning/Coding Models (~14 hours)
  - Install Qwen3:30b + Mathstral
  - Create `TradingReasoningEngine`
  - Implement math calculations (ATR, position sizing)
  - Generate strategy code with AI

### Phase 3: Top Layer (Weeks 5-6)
- **[AI-3]** Implement Agentic Orchestration (~16 hours)
  - Install Llama4:scout
  - Create `IntelligenceOrchestrator`
  - Add function/tool calling
  - Generate trading recommendations

### Phase 4: Integration (Week 7)
- **[AI-4]** Integration Testing & Optimization (~10 hours)
  - End-to-end testing
  - Performance optimization
  - Monitoring and observability
  - Production safeguards

---

## Original Tasks (Now Expanded into Sub-Issues)

### ~~1. Document Processing (Now [AI-1])~~
- [x] Sub-issue created: [AI-1]
- Auto-ingest signals, backtests, trades, positions
- Document chunking and metadata extraction

### ~~2. Vector Store (Now [AI-1])~~
- [x] Sub-issue created: [AI-1]
- pgvector integration in PostgreSQL
- Embedding generation (sentence-transformers or OpenAI)
- Semantic search implementation

### ~~3. LLM Integration (Now [AI-2] + [AI-3])~~
- [x] Sub-issues created: [AI-2], [AI-3]
- Local LLM via Ollama + llama.cpp
- CUDA acceleration for inference
- Prompt engineering for trading queries

### ~~4. Intelligence Orchestrator (Now [AI-3])~~
- [x] Sub-issue created: [AI-3]
- Query → Retrieval → Context + LLM → Insights
- Trading recommendation generation
- Account balance and cash optimization

### ~~5. Testing (Now [AI-4])~~
- [x] Sub-issue created: [AI-4]
- Integration tests
- Performance benchmarks
- Accuracy validation

---

## Documentation

**Primary Reference**: `docs/AI_ARCHITECTURE.md` (created Oct 17, 2025)

This document contains:
- Complete model recommendations and benchmarks
- Implementation guides for each layer
- Docker/Django configuration
- Testing strategies
- Performance optimization tips
- Cost savings analysis ($10K-$50K annually vs OpenAI)

---

## Dependencies

### Infrastructure
- Docker with NVIDIA GPU support (24GB VRAM recommended)
- PostgreSQL with pgvector extension
- Ollama for local LLM inference
- Redis for caching

### Python Packages
```txt
ollama>=0.1.0
sentence-transformers>=2.2.0
pgvector>=0.2.0
torch>=2.0.0  # CUDA support
```

---

## Acceptance Criteria

### Technical
- ✅ All 3 layers (Base, Middle, Top) implemented
- ✅ End-to-end RAG flow functional
- ✅ Embeddings stored in pgvector
- ✅ AI generates trading recommendations
- ✅ Performance meets targets (<5s end-to-end)

### Business
- ✅ System generates optimal daily signals
- ✅ Tracks all trades with context
- ✅ Optimizes strategy based on portfolio state
- ✅ Learns from historical performance

### Quality
- ✅ All sub-issues ([AI-1] through [AI-4]) completed
- ✅ Integration tests passing
- ✅ Decision accuracy >60%
- ✅ Documentation complete

---

## Timeline

| Week | Phase | Issues | Hours |
|------|-------|--------|-------|
| 1-2 | Base Layer | [AI-1] | 10 |
| 3-4 | Middle Layer | [AI-2] | 14 |
| 5-6 | Top Layer | [AI-3] | 16 |
| 7 | Integration | [AI-4] | 10 |
| **Total** | **7 weeks** | **4 issues** | **~50 hours** |

---

## Progress Tracking

- [ ] [AI-1] Base Layer - Embeddings (0%)
- [ ] [AI-2] Middle Layer - Reasoning (0%)
- [ ] [AI-3] Top Layer - Agentic (0%)
- [ ] [AI-4] Integration & Optimization (0%)

---

## References

### External
- Ollama Models Guide: https://collabnix.com/choosing-ollama-models-the-complete-2025-guide-for-developers-and-enterprises/
- Best Open-Source LLMs: https://blog.n8n.io/open-source-llm/
- Ollama 2025 Update: https://www.elightwalk.com/blog/latest-ollama-models

### Internal
- Architecture Doc: `docs/AI_ARCHITECTURE.md`
- RAG Module: `src/rag/`
- Trading Intelligence: `src/trading/intelligence/`
- Celery Tasks: `src/trading/tasks.py`

---

**Time Estimate**: ~50 hours (across 4 sub-issues)  
**Assignee**: @nuniesmith  
**Phase**: 2.2 (Complete RAG System)  
**Status**: Planning complete - Ready to start [AI-1]
""",
                "labels": ["🟡 high", "✨ feature", "effort:high", "phase:2-core"],
                "update_existing": True,  # Flag to update issue #9
            }
        ]
    
    def create_issue(self, issue: Dict) -> bool:
        """Create a GitHub issue."""
        if self.dry_run:
            print(f"\n[DRY-RUN] Would create issue:")
            print(f"  Title: {issue['title']}")
            print(f"  Labels: {', '.join(issue['labels'])}")
            print(f"  Body length: {len(issue['body'])} chars")
            return True
        
        # Check if this is an update to existing issue
        if issue.get('update_existing'):
            try:
                # Update issue #9
                cmd = [
                    "gh", "issue", "edit", "9",
                    "--repo", self.repo,
                    "--title", issue['title'],
                    "--body", issue['body']
                ]
                
                # Add labels
                for label in issue['labels']:
                    cmd.extend(["--add-label", label])
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"  ✅ Updated: {issue['title']}")
                    return True
                else:
                    print(f"  ❌ Failed: {issue['title']}")
                    print(f"     Error: {result.stderr}")
                    return False
            except Exception as e:
                print(f"  ❌ Error: {e}")
                return False
        else:
            # Create new issue
            try:
                # Build command
                cmd = [
                    "gh", "issue", "create",
                    "--repo", self.repo,
                    "--title", issue['title'],
                    "--body", issue['body']
                ]
                
                # Add labels
                for label in issue['labels']:
                    cmd.extend(["--label", label])
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"  ✅ Created: {issue['title']}")
                    return True
                else:
                    print(f"  ❌ Failed: {issue['title']}")
                    print(f"     Error: {result.stderr}")
                    return False
            except Exception as e:
                print(f"  ❌ Error: {e}")
                return False
    
    def run(self):
        """Import all issues."""
        issues = self.get_issues()
        
        print(f"🤖 FKS Trading Platform - AI Architecture Issues")
        print(f"=" * 60)
        print(f"🎯 Importing {len(issues)} issues to {self.repo}")
        if self.dry_run:
            print(f"🔍 DRY-RUN MODE - No issues will be created")
        print()
        
        success_count = 0
        failed_count = 0
        
        for issue in issues:
            if self.create_issue(issue):
                success_count += 1
            else:
                failed_count += 1
        
        print()
        print(f"=" * 60)
        print(f"✅ Successfully imported: {success_count}/{len(issues)}")
        if failed_count > 0:
            print(f"❌ Failed: {failed_count}/{len(issues)}")
        print()
        
        if not self.dry_run:
            print("Next steps:")
            print("1. View issues: gh issue list --repo nuniesmith/fks")
            print("2. Start with [AI-1]: gh issue view <number>")
            print("3. Add to Project board: https://github.com/nuniesmith/fks/projects")
            print("4. Review AI Architecture: docs/AI_ARCHITECTURE.md")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Import AI Architecture issues into GitHub"
    )
    parser.add_argument(
        "--repo",
        default="nuniesmith/fks",
        help="GitHub repository (default: nuniesmith/fks)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview issues without creating them"
    )
    
    args = parser.parse_args()
    
    importer = AIArchitectureImporter(
        repo=args.repo,
        dry_run=args.dry_run
    )
    importer.run()

if __name__ == "__main__":
    main()
