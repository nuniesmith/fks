# Quick Start: Creating AI Architecture Issues

## Step 1: Authorize GitHub CLI

If you haven't already, authorize the GitHub CLI with project permissions:

```bash
# In WSL terminal where gh auth is waiting
# Press Enter and follow the prompts to authorize
# Use code: E10D-4411
```

## Step 2: Verify GitHub Project Access

```bash
# After authorization, verify you can access projects
gh project list --owner nuniesmith

# If successful, you should see a list of projects
```

## Step 3: Create GitHub Issues (Manual)

Since the Python script has syntax issues with multi-line strings, let's create the issues manually using gh CLI. I've created the detailed architecture in `docs/AI_ARCHITECTURE.md`.

### Create [AI-1] - Base Layer

```bash
gh issue create --repo nuniesmith/fks \
  --title "[AI-1] Implement Base Layer - Ollama Embeddings" \
  --label "🟡 high" \
  --label "✨ feature" \
  --label "effort:medium" \
  --label "phase:2-core" \
  --label "⚡ performance" \
  --body "## Overview

Implement the **Base Layer** of the AI architecture using Ollama embeddings (BGE-M3) for RAG data ingestion and semantic search.

**Parent Issue**: #9 (P2.2 - Complete RAG System)  
**Layer**: Base (Embeddings)  
**Priority**: 🟡 High  
**Effort**: Medium (~10 hours)

## Goals

- Install Ollama + BGE-M3 embedding model
- Implement OllamaEmbeddingService
- Integrate with pgvector
- Test embedding generation and similarity search

## Key Tasks

1. Docker infrastructure (Ollama service in docker-compose.gpu.yml)
2. BGE-M3 model installation
3. Embedding service implementation (src/rag/embeddings.py)
4. pgvector integration
5. Testing (unit + integration)

## Acceptance Criteria

- Ollama running with GPU support
- BGE-M3 generating 1024-dim embeddings
- Semantic search functional (>0.7 similarity threshold)
- Performance: <100ms per embedding, ~1000 tokens/sec

## References

- Architecture Doc: docs/AI_ARCHITECTURE.md
- Parent Issue: #9

**Time Estimate**: ~10 hours  
**Status**: Ready to start after Phase 1"
```

### Create [AI-2] - Middle Layer

```bash
gh issue create --repo nuniesmith/fks \
  --title "[AI-2] Implement Middle Layer - Reasoning/Coding Models" \
  --label "🟡 high" \
  --label "✨ feature" \
  --label "effort:high" \
  --label "phase:2-core" \
  --label "⚡ performance" \
  --body "## Overview

Implement the **Middle Layer** using Qwen3 and Mathstral for math-heavy calculations, backtesting logic, and strategy code generation.

**Parent Issue**: #9 (P2.2 - Complete RAG System)  
**Layer**: Middle (Reasoning/Coding)  
**Priority**: 🟡 High  
**Effort**: High (~14 hours)

## Goals

- Install Qwen3:30b and Mathstral models
- Implement TradingReasoningEngine
- Generate trading calculations (ATR, position sizing, R:R ratios)
- Test math accuracy and code generation

## Key Tasks

1. Install Qwen3:30b + Mathstral models
2. Implement TradingReasoningEngine class (src/trading/intelligence/reasoning.py)
3. Math calculations module (ATR, position sizing, R:R)
4. Strategy code generation
5. Integration with RAG layer
6. Testing (20+ test cases)

## Acceptance Criteria

- Both models installed and functional
- Math calculations accurate (within 1% of manual)
- Code generation produces valid Python
- Performance: <2s per inference, ~50 tokens/sec

## Dependencies

- **Requires**: [AI-1] Base Layer implementation

## References

- Architecture Doc: docs/AI_ARCHITECTURE.md
- Parent Issue: #9

**Time Estimate**: ~14 hours  
**Status**: Blocked by [AI-1]"
```

### Create [AI-3] - Top Layer

```bash
gh issue create --repo nuniesmith/fks \
  --title "[AI-3] Implement Top Layer - Agentic Orchestration" \
  --label "🟡 high" \
  --label "✨ feature" \
  --label "effort:high" \
  --label "phase:2-core" \
  --label "⚡ performance" \
  --body "## Overview

Implement the **Top Layer** using Llama4:scout for high-level orchestration, tool calling, and autonomous trading decisions.

**Parent Issue**: #9 (P2.2 - Complete RAG System)  
**Layer**: Top (Agentic/Tools)  
**Priority**: 🟡 High  
**Effort**: High (~16 hours)

## Goals

- Install Llama4:scout agentic model
- Implement IntelligenceOrchestrator coordinating all layers
- Add tool/function calling for API integrations
- Generate end-to-end trading recommendations

## Key Tasks

1. Install Llama4:scout model
2. Implement IntelligenceOrchestrator (src/rag/intelligence.py)
3. Function/tool calling (execute_trade, fetch_market_data, etc.)
4. Decision-making logic with confidence scoring
5. Integration with Celery tasks
6. Testing (15+ test cases)

## Acceptance Criteria

- Llama4:scout functional with tool calling
- Orchestrator coordinates all 3 layers successfully
- Recommendations include entry/exit/sizing/reasoning
- Performance: <5s end-to-end latency
- Decision accuracy >60%

## Dependencies

- **Requires**: [AI-1] Base Layer, [AI-2] Middle Layer

## References

- Architecture Doc: docs/AI_ARCHITECTURE.md
- Parent Issue: #9

**Time Estimate**: ~16 hours  
**Status**: Blocked by [AI-1], [AI-2]"
```

### Create [AI-4] - Integration Testing

```bash
gh issue create --repo nuniesmith/fks \
  --title "[AI-4] Integration Testing & Performance Optimization" \
  --label "🟡 high" \
  --label "🧪 tests" \
  --label "effort:medium" \
  --label "phase:2-core" \
  --label "⚡ performance" \
  --body "## Overview

End-to-end integration testing and performance optimization of the complete 3-layer AI architecture.

**Parent Issue**: #9 (P2.2 - Complete RAG System)  
**Priority**: 🟡 High  
**Effort**: Medium (~10 hours)

## Goals

- Test complete layered AI flow
- Optimize performance (latency, VRAM usage)
- Add monitoring and observability
- Implement production safeguards

## Key Tasks

1. End-to-end integration tests (20+ scenarios)
2. Performance optimization (caching, model swapping)
3. Monitoring & observability (Grafana dashboard)
4. Production safeguards (confidence thresholds, circuit breaker)
5. Documentation & examples

## Acceptance Criteria

- All integration tests passing
- Performance meets targets (<5s end-to-end)
- Monitoring dashboard operational
- System tested with 7+ days of real market data

## Dependencies

- **Requires**: [AI-1], [AI-2], [AI-3] complete

## References

- Architecture Doc: docs/AI_ARCHITECTURE.md
- Parent Issue: #9

**Time Estimate**: ~10 hours  
**Status**: Blocked by [AI-1], [AI-2], [AI-3]"
```

## Step 4: Update Issue #9

```bash
gh issue edit 9 --repo nuniesmith/fks \
  --title "[P2.2] Complete RAG System - AI-Powered Trading Intelligence (UPDATED)" \
  --body "## Overview

**UPDATED**: This issue has been expanded with detailed AI architecture implementation tasks.

Complete the RAG system with **3-layer AI architecture** using Ollama models for intelligent trading insights.

**Phase**: 2 - Core Development  
**Priority**: 🟡 High  
**Effort**: High (~50+ hours total across sub-issues)

## Architecture

The FKS Intelligence system uses a layered AI approach:
- TOP LAYER: Agentic/Tools (Llama4:scout) - Issue [AI-3]
- MIDDLE LAYER: Reasoning/Coding (Qwen3, Mathstral) - Issue [AI-2]
- BASE LAYER: Embeddings (BGE-M3) - Issue [AI-1]

## Implementation Sub-Issues

- **[AI-1]** Implement Ollama Embeddings (~10 hours)
- **[AI-2]** Implement Reasoning/Coding Models (~14 hours)
- **[AI-3]** Implement Agentic Orchestration (~16 hours)
- **[AI-4]** Integration Testing & Optimization (~10 hours)

## Timeline

- Weeks 1-2: Base Layer ([AI-1])
- Weeks 3-4: Middle Layer ([AI-2])
- Weeks 5-6: Top Layer ([AI-3])
- Week 7: Integration ([AI-4])

**Total**: 7 weeks, ~50 hours

## Documentation

**Primary Reference**: docs/AI_ARCHITECTURE.md

This document contains complete model recommendations, implementation guides, Docker/Django configuration, testing strategies, and performance optimization tips.

## Progress Tracking

- [ ] [AI-1] Base Layer - Embeddings (0%)
- [ ] [AI-2] Middle Layer - Reasoning (0%)
- [ ] [AI-3] Top Layer - Agentic (0%)
- [ ] [AI-4] Integration & Optimization (0%)

**Status**: Planning complete - Ready to start [AI-1]"
```

## Step 5: Add Issues to Project

After creating all issues, add them to your Project board:

```bash
# List your projects to get the project number
gh project list --owner nuniesmith

# Add issues to project (replace PROJECT_NUMBER with actual number)
gh project item-add PROJECT_NUMBER --owner nuniesmith --url https://github.com/nuniesmith/fks/issues/14
gh project item-add PROJECT_NUMBER --owner nuniesmith --url https://github.com/nuniesmith/fks/issues/15
gh project item-add PROJECT_NUMBER --owner nuniesmith --url https://github.com/nuniesmith/fks/issues/16
gh project item-add PROJECT_NUMBER --owner nuniesmith --url https://github.com/nuniesmith/fks/issues/17
```

## Step 6: Organize on Project Board

1. Visit https://github.com/nuniesmith/fks/projects
2. Move [AI-1] to "Backlog" (start after Phase 1 complete)
3. Move [AI-2], [AI-3], [AI-4] to "Backlog"
4. Add dependencies in issue descriptions

## Done!

Your AI architecture implementation is now tracked in GitHub Issues with:
- ✅ Detailed task breakdowns
- ✅ Time estimates
- ✅ Proper labeling
- ✅ Clear dependencies
- ✅ Comprehensive documentation (docs/AI_ARCHITECTURE.md)

## Next Steps

1. Complete Phase 1 issues (#5, #6, #7) first
2. Then start [AI-1] (Base Layer - Embeddings)
3. Follow the 7-week timeline
4. Reference docs/AI_ARCHITECTURE.md for implementation details
