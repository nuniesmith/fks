# AI Architecture Implementation - GitHub Issues Summary

**Date**: October 17, 2025  
**Parent Issue**: #9 (P2.2 - Complete RAG System)  
**Total Issues**: 4 new + 1 update  
**Total Hours**: ~50 hours across 7 weeks

---

## Issues to Create

### [AI-1] Implement Base Layer - Ollama Embeddings
**Priority**: 🟡 High | **Effort**: Medium (~10 hours) | **Phase**: 2-core

**Summary**:
- Install Ollama + BGE-M3 embedding model
- Implement `OllamaEmbeddingService` in `src/rag/embeddings.py`
- Integrate with pgvector for semantic search
- Test embedding generation and similarity search

**Key Tasks**:
1. Docker infrastructure (Ollama service in docker-compose.gpu.yml)
2. BGE-M3 model installation
3. Embedding service implementation
4. pgvector integration
5. Testing (unit + integration)

**Acceptance Criteria**:
- Ollama running with GPU support
- BGE-M3 generating 1024-dim embeddings
- Semantic search functional (>0.7 similarity threshold)
- Performance: <100ms per embedding, ~1000 tokens/sec

**Labels**: `🟡 high`, `✨ feature`, `effort:medium`, `phase:2-core`, `⚡ performance`

---

### [AI-2] Implement Middle Layer - Reasoning/Coding Models
**Priority**: 🟡 High | **Effort**: High (~14 hours) | **Phase**: 2-core

**Summary**:
- Install Qwen3:30b and Mathstral models
- Implement `TradingReasoningEngine` in `src/trading/intelligence/reasoning.py`
- Generate trading calculations (ATR, position sizing, R:R ratios)
- Test math accuracy and code generation

**Key Tasks**:
1. Install Qwen3:30b + Mathstral models
2. Implement TradingReasoningEngine class
3. Math calculations module (ATR, position sizing, R:R)
4. Strategy code generation
5. Integration with RAG layer
6. Testing (20+ test cases)

**Acceptance Criteria**:
- Both models installed and functional
- Math calculations accurate (within 1% of manual)
- Code generation produces valid Python
- Performance: <2s per inference, ~50 tokens/sec

**Labels**: `🟡 high`, `✨ feature`, `effort:high`, `phase:2-core`, `⚡ performance`

---

### [AI-3] Implement Top Layer - Agentic Orchestration
**Priority**: 🟡 High | **Effort**: High (~16 hours) | **Phase**: 2-core

**Summary**:
- Install Llama4:scout agentic model
- Implement `IntelligenceOrchestrator` in `src/rag/intelligence.py`
- Add tool/function calling for API integrations
- Generate end-to-end trading recommendations

**Key Tasks**:
1. Install Llama4:scout model
2. Implement IntelligenceOrchestrator (coordinates all 3 layers)
3. Function/tool calling (execute_trade, fetch_market_data, etc.)
4. Decision-making logic with confidence scoring
5. Integration with Celery tasks
6. Testing (15+ test cases)

**Acceptance Criteria**:
- Llama4:scout functional with tool calling
- Orchestrator coordinates all 3 layers successfully
- Recommendations include entry/exit/sizing/reasoning
- Performance: <5s end-to-end latency
- Decision accuracy >60%

**Labels**: `🟡 high`, `✨ feature`, `effort:high`, `phase:2-core`, `⚡ performance`

**Dependencies**: Blocked by [AI-1], [AI-2]

---

### [AI-4] Integration Testing & Performance Optimization
**Priority**: 🟡 High | **Effort**: Medium (~10 hours) | **Phase**: 2-core

**Summary**:
- End-to-end integration testing of complete 3-layer AI
- Performance optimization (latency, VRAM usage, caching)
- Add monitoring and observability (Prometheus + Grafana)
- Implement production safeguards

**Key Tasks**:
1. End-to-end integration tests (20+ scenarios)
2. Performance optimization (caching, model swapping)
3. Monitoring & observability (Grafana dashboard)
4. Production safeguards (confidence thresholds, circuit breaker)
5. Documentation & examples

**Acceptance Criteria**:
- All integration tests passing
- Performance meets targets (<5s end-to-end)
- Monitoring dashboard operational
- System tested with 7+ days of real market data

**Labels**: `🟡 high`, `🧪 tests`, `effort:medium`, `phase:2-core`, `⚡ performance`

**Dependencies**: Blocked by [AI-1], [AI-2], [AI-3]

---

### [P2.2] Complete RAG System (UPDATE EXISTING #9)
**Priority**: 🟡 High | **Effort**: High (~50 hours total) | **Phase**: 2-core

**Summary** (updated):
Complete the RAG system with 3-layer AI architecture. This issue has been expanded into 4 detailed sub-issues ([AI-1] through [AI-4]).

**Architecture**:
```
TOP LAYER (Llama4:scout) → [AI-3]
    ↓
MIDDLE LAYER (Qwen3, Mathstral) → [AI-2]
    ↓
BASE LAYER (BGE-M3) → [AI-1]
```

**Timeline**:
- Weeks 1-2: Base Layer ([AI-1]) - 10 hours
- Weeks 3-4: Middle Layer ([AI-2]) - 14 hours
- Weeks 5-6: Top Layer ([AI-3]) - 16 hours
- Week 7: Integration ([AI-4]) - 10 hours
- **Total**: 7 weeks, ~50 hours

**Progress Tracking**:
- [ ] [AI-1] Base Layer - Embeddings (0%)
- [ ] [AI-2] Middle Layer - Reasoning (0%)
- [ ] [AI-3] Top Layer - Agentic (0%)
- [ ] [AI-4] Integration & Optimization (0%)

**Labels**: `🟡 high`, `✨ feature`, `effort:high`, `phase:2-core`

---

## Implementation Order

1. **Start Here**: [AI-1] Base Layer (no dependencies)
2. **Then**: [AI-2] Middle Layer (requires [AI-1])
3. **Next**: [AI-3] Top Layer (requires [AI-1], [AI-2])
4. **Finally**: [AI-4] Integration (requires all previous)

---

## GitHub Commands to Create Issues

### Create [AI-1]
```bash
gh issue create --repo nuniesmith/fks \
  --title "[AI-1] Implement Base Layer - Ollama Embeddings" \
  --label "🟡 high" --label "✨ feature" --label "effort:medium" --label "phase:2-core" --label "⚡ performance" \
  --body-file scripts/ai-1-body.md
```

### Create [AI-2]
```bash
gh issue create --repo nuniesmith/fks \
  --title "[AI-2] Implement Middle Layer - Reasoning/Coding Models" \
  --label "🟡 high" --label "✨ feature" --label "effort:high" --label "phase:2-core" --label "⚡ performance" \
  --body-file scripts/ai-2-body.md
```

### Create [AI-3]
```bash
gh issue create --repo nuniesmith/fks \
  --title "[AI-3] Implement Top Layer - Agentic Orchestration" \
  --label "🟡 high" --label "✨ feature" --label "effort:high" --label "phase:2-core" --label "⚡ performance" \
  --body-file scripts/ai-3-body.md
```

### Create [AI-4]
```bash
gh issue create --repo nuniesmith/fks \
  --title "[AI-4] Integration Testing & Performance Optimization" \
  --label "🟡 high" --label "🧪 tests" --label "effort:medium" --label "phase:2-core" --label "⚡ performance" \
  --body-file scripts/ai-4-body.md
```

### Update #9
```bash
gh issue edit 9 --repo nuniesmith/fks \
  --title "[P2.2] Complete RAG System - AI-Powered Trading Intelligence (UPDATED)" \
  --body-file scripts/issue-9-update.md
```

---

## Next Steps

1. **Authorize GitHub CLI**: Press Enter in terminal where it's waiting for auth
2. **Create individual body files**: Split the detailed issue bodies into separate markdown files
3. **Run gh commands**: Execute the commands above to create all issues
4. **Add to Project**: Once created, add issues to your GitHub Project board
5. **Start Implementation**: Begin with [AI-1] (Base Layer)

---

## References

- **Full Architecture Doc**: `docs/AI_ARCHITECTURE.md` (36KB, 1040 lines)
- **Model Recommendations**: See table in architecture doc
- **Cost Savings**: $10K-$50K annually vs OpenAI APIs
- **Performance Targets**: <5s end-to-end, >60% accuracy

---

## Model Summary

| Layer | Model | Params | VRAM | Purpose |
|-------|-------|--------|------|---------|
| Base | BGE-M3 | 567M | 2GB | Embeddings for RAG |
| Middle | Qwen3:30b | 30B MoE | 16GB | Math & reasoning |
| Middle | Mathstral | 7B | 8GB | Specialized math |
| Top | Llama4:scout | 109B/17B | 24GB | Agentic orchestration |

---

**Status**: Ready to create issues  
**Total Effort**: ~50 hours  
**Timeline**: 7 weeks  
**Dependencies**: Complete Phase 1 first (#5, #6, #7)
