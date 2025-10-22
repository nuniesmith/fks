# FKS Trading Platform - Layered AI Architecture

**Date**: October 22, 2025  
**Status**: ✅ **PRODUCTION READY** - RAG Fully Integrated  
**Related Issues**: #9 (P2.2 - Complete RAG System) - ✅ COMPLETE

---

## ✅ RAG Integration Status - COMPLETE

**As of October 22, 2025**, the RAG system is **fully integrated** with FKS trading logic:

### Integration Points

1. **Core Signal Generation** (`src/trading/signals/generator.py`) ✅
   - `get_current_signal()` enhanced with RAG recommendations
   - Technical indicators (RSI, MACD, BB) passed as context
   - Position size boost for high-confidence signals (≥80%)
   - Graceful degradation if RAG unavailable

2. **Celery Tasks** (`src/trading/tasks.py`) ✅
   - `generate_signals_task()` - Uses RAG for signal generation
   - `optimize_portfolio_task()` - RAG-powered portfolio optimization
   - `generate_daily_rag_signals_task()` - Daily AI recommendations
   - Auto-ingestion tasks for signals, trades, backtests

3. **Auto-Ingestion Pipeline** (`src/web/rag/ingestion.py`) ✅
   - Automatic indexing of trading signals
   - Backtest results ingestion
   - Completed trades analysis
   - Market insights storage

### Performance Metrics

- **Query Latency**: ~250ms per symbol (mocked tests)
- **Target**: < 500ms in production
- **Graceful Degradation**: Yes - falls back to technical indicators
- **Test Coverage**: 60+ unit tests, 8 integration tests, 16 performance benchmarks

### Usage Example

```python
from trading.signals.generator import get_current_signal

# RAG-enhanced signal generation
signal, suggestions = get_current_signal(
    df_prices=price_data,
    best_params=strategy_params,
    account_size=10000.0,
    use_rag=True,  # Enable RAG
    available_cash=8000.0,
    current_positions={'BTCUSDT': {'quantity': 0.1, 'entry_price': 39500}}
)

# Each suggestion includes RAG insights
for suggestion in suggestions:
    if suggestion.get('rag_enhanced'):
        print(f"Confidence: {suggestion['rag_confidence']:.0%}")
        print(f"Reasoning: {suggestion['rag_reasoning']}")
        print(f"Risk: {suggestion['rag_risk_assessment']}")
```

### Documentation

- **Integration Guide**: [RAG_INTEGRATION_COMPLETE.md](RAG_INTEGRATION_COMPLETE.md)
- **Setup Guide**: [RAG_SETUP_GUIDE.md](RAG_SETUP_GUIDE.md)
- **API Reference**: `src/web/rag/README.md`

---

## Overview

This document defines the **layered AI architecture** for the FKS Trading Platform using Ollama models for local inference. The architecture employs specialized models at each layer to optimize for efficiency, privacy, and trading-specific capabilities.

### Architecture Goals

1. **Cost Efficiency**: Zero API costs via local Ollama inference
2. **Privacy**: Sensitive trading data never leaves local infrastructure
3. **Performance**: Layer-specific model optimization (small → large)
4. **Scalability**: GPU-accelerated inference with CUDA support
5. **Intelligence**: AI-powered trading insights via RAG system

---

## Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  TOP LAYER: Agentic/Tools (Orchestration)                   │
│  Models: Llama4, GPT-OSS, Mistral-Small3.2                  │
│  Purpose: High-level reasoning, tool calls, API integration  │
│  VRAM: 24GB+ | Context: 128K+ tokens                         │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│  MIDDLE LAYER: Reasoning/Coding (Insights)                   │
│  Models: Qwen3, DeepSeek-V3.1, Mathstral                    │
│  Purpose: Math calculations, backtesting, strategy code      │
│  VRAM: 8-16GB | Context: 32K+ tokens                         │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│  BASE LAYER: Embeddings (RAG)                                │
│  Models: BGE-M3, Qwen3-Embedding, Nomic-Embed-Text          │
│  Purpose: Data vectorization, semantic search in pgvector    │
│  VRAM: 2-4GB | Context: 8K+ tokens                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Base - Embeddings for RAG

### Purpose
Vectorize trading data (OHLCV, reports, signals, trades) for semantic search in PostgreSQL with pgvector extension.

### Recommended Models

#### Primary: BGE-M3 (567M parameters)
**Ollama command**: `ollama pull bge-m3`

**Strengths**:
- Multi-functionality: Dense/sparse/multi-vector retrieval
- 100+ languages (useful for global market news)
- 8192 token context (handles long financial reports)
- #1 on MTEB multilingual leaderboard (score ~70+)

**Use Cases**:
- Embedding trading signals for similarity search
- Vectorizing market reports and financial PDFs
- Semantic search across historical trades
- Document ingestion in `rag/document_processor.py`

**Integration**:
```python
# In src/rag/embeddings.py
from ollama import Client

client = Client(host='http://ollama:11434')

def generate_embedding(text: str) -> list[float]:
    """Generate embedding using BGE-M3."""
    response = client.embeddings(
        model='bge-m3',
        prompt=text
    )
    return response['embedding']
```

#### Alternative: Qwen3-Embedding (0.6B / 4B / 8B)
**Ollama command**: `ollama pull qwen3-embedding:8b`

**Strengths**:
- Flexible dimensions (32-4096)
- Strong in text/code retrieval (MTEB: 70.58 for 8B)
- User-defined instructions for domain-specific embeddings

**Use Cases**:
- Code-aware embeddings (for strategy files)
- Multilingual financial data
- Scalable sizes for layered efficiency

#### Alternative: Nomic-Embed-Text (137M - 335M)
**Ollama command**: `ollama pull nomic-embed-text`

**Strengths**:
- Large context (8192+ tokens)
- Outperforms OpenAI ada-002 on long tasks
- Extremely low resource usage

**Use Cases**:
- Extended trading histories
- Long-form market analysis
- News article embeddings

### Implementation in FKS

**File**: `src/rag/embeddings.py`

```python
from typing import List, Optional
from ollama import Client
from django.conf import settings

class OllamaEmbeddingService:
    """Embedding service using Ollama BGE-M3."""
    
    def __init__(self):
        self.client = Client(host=settings.OLLAMA_HOST)
        self.model = 'bge-m3'
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents."""
        return [self.embed(text) for text in texts]
    
    def embed(self, text: str) -> List[float]:
        """Embed single document."""
        response = self.client.embeddings(
            model=self.model,
            prompt=text
        )
        return response['embedding']
    
    def embed_query(self, query: str) -> List[float]:
        """Embed search query."""
        return self.embed(query)
```

**Integration with pgvector**:
```python
# In src/rag/vector_store.py
from pgvector.psycopg2 import register_vector

def store_embedding(text: str, metadata: dict):
    """Store embedding in PostgreSQL with pgvector."""
    embedding = embedding_service.embed(text)
    
    cursor.execute(
        """
        INSERT INTO document_embeddings (content, embedding, metadata)
        VALUES (%s, %s, %s)
        """,
        (text, embedding, json.dumps(metadata))
    )
```

### Performance Characteristics

| Model | Params | VRAM | Speed (tokens/sec) | Context | MTEB Score |
|-------|--------|------|-------------------|---------|------------|
| BGE-M3 | 567M | 2GB | ~1000 | 8192 | 70+ |
| Qwen3-Embedding:8b | 8B | 4GB | ~800 | 8192 | 70.58 |
| Nomic-Embed-Text | 137M | 1GB | ~1200 | 8192 | 65-70 |

---

## Layer 2: Middle - Reasoning and Coding

### Purpose
Handle math-heavy calculations, backtesting logic, strategy optimization, and code generation for trading strategies.

### Recommended Models

#### Primary: Qwen3 (30B-235B MoE recommended)
**Ollama command**: `ollama pull qwen3:30b`

**Strengths**:
- Strong math/code/reasoning (90.6+ on MGSM math benchmark)
- Agent tools with thinking/non-thinking modes
- Competitive with o1/Grok-3 on mathematical reasoning
- MoE variants (30B-A3B activates only 3B) for efficiency

**Use Cases**:
- Backtesting calculations (Sharpe ratio, drawdown, etc.)
- Risk management math (position sizing, ATR calculations)
- Strategy code generation
- Portfolio optimization algorithms

**Integration**:
```python
# In src/trading/signals/ai_analyzer.py
from ollama import Client

def analyze_market_math(data: dict) -> dict:
    """Use Qwen3 for mathematical trading analysis."""
    client = Client(host='http://ollama:11434')
    
    prompt = f"""
    Analyze this trading data and calculate:
    1. Optimal position size (ATR-based)
    2. Risk-reward ratio
    3. Expected value
    
    Data: {data}
    """
    
    response = client.chat(
        model='qwen3:30b',
        messages=[{'role': 'user', 'content': prompt}]
    )
    return parse_analysis(response['message']['content'])
```

#### Alternative: DeepSeek-V3.1 (671B MoE, 37B active)
**Ollama command**: `ollama pull deepseek-v3.1`

**Strengths**:
- Hybrid thinking/non-thinking modes
- Enhanced code/search agents
- Approaches o3-mini/Gemini 2.5 Pro in reasoning

**Use Cases**:
- Complex trading logic reasoning
- Code agents for Celery task automation
- Multi-step strategy optimization

#### Specialized: Mathstral (7B)
**Ollama command**: `ollama pull mathstral`

**Strengths**:
- Specialized math reasoning (70-73 on MathVista)
- Efficient for quantitative tasks
- Outperforms similar sizes in logic/math

**Use Cases**:
- ATR, SMA, EMA calculations
- Statistical analysis of trades
- Risk metrics (VaR, CVaR)

### Implementation in FKS

**File**: `src/trading/intelligence/reasoning.py`

```python
from ollama import Client
from typing import Dict, Any

class TradingReasoningEngine:
    """AI-powered reasoning for trading decisions."""
    
    def __init__(self):
        self.client = Client(host='http://ollama:11434')
        self.model = 'qwen3:30b'
    
    def analyze_trade_setup(
        self, 
        symbol: str, 
        market_data: dict,
        strategy: str
    ) -> Dict[str, Any]:
        """Analyze trade setup with AI reasoning."""
        
        prompt = f"""
        You are an expert quantitative trader. Analyze this setup:
        
        Symbol: {symbol}
        Strategy: {strategy}
        Current Price: {market_data['price']}
        ATR: {market_data['atr']}
        Volume: {market_data['volume']}
        
        Calculate:
        1. Optimal entry price
        2. Stop loss (2x ATR)
        3. Take profit targets (R:R 1:2, 1:3)
        4. Position size (2% risk)
        5. Expected value
        
        Return as JSON.
        """
        
        response = self.client.chat(
            model=self.model,
            messages=[{'role': 'user', 'content': prompt}],
            format='json'
        )
        
        return json.loads(response['message']['content'])
    
    def generate_backtest_code(self, strategy_description: str) -> str:
        """Generate Python code for backtest strategy."""
        
        prompt = f"""
        Generate Python code for this trading strategy:
        {strategy_description}
        
        Use our backtesting framework:
        - Class inheriting from BaseStrategy
        - Implement calculate_signals() method
        - Use pandas for indicators
        - Follow existing code patterns
        """
        
        response = self.client.chat(
            model=self.model,
            messages=[{'role': 'user', 'content': prompt}]
        )
        
        return response['message']['content']
```

### Performance Characteristics

| Model | Params | VRAM | Speed (tok/s) | Context | MGSM Score | LiveCodeBench |
|-------|--------|------|---------------|---------|------------|---------------|
| Qwen3:30b | 30B MoE | 16GB | ~50 | 32K | 90.6% | High |
| DeepSeek-V3.1 | 671B/37B | 24GB | ~40 | 64K | ~88% | High |
| Mathstral | 7B | 8GB | ~100 | 16K | 70-73% | Medium |

---

## Layer 3: Top - Agentic/Tools for Orchestration

### Purpose
High-level orchestration, tool calling, API integrations, multi-turn reasoning, and autonomous trading decisions.

### Recommended Models

#### Primary: Llama4 Scout (109B MoE, 17B active)
**Ollama command**: `ollama pull llama4:scout`

**Strengths**:
- Multimodal (text + image) - can analyze charts
- Native tool/function calling
- Strong agentic capabilities (MMMU 69-73)
- Multilingual support

**Use Cases**:
- Orchestrating RAG → Reasoning → Action workflows
- Tool calls to CCXT (exchange APIs)
- Chart analysis via screenshots
- Multi-agent coordination

**Integration**:
```python
# In src/rag/intelligence.py
from ollama import Client

class IntelligenceOrchestrator:
    """Top-level AI orchestration."""
    
    def __init__(self):
        self.client = Client(host='http://ollama:11434')
        self.model = 'llama4:scout'
    
    def get_trading_recommendation(
        self,
        symbol: str,
        account_balance: float,
        context: str
    ) -> dict:
        """Get AI-powered trading recommendation."""
        
        # 1. Retrieve context via RAG (Base Layer)
        relevant_docs = self.rag_retrieval(symbol)
        
        # 2. Reason about setup (Middle Layer)
        analysis = self.reasoning_engine.analyze_trade_setup(
            symbol, market_data, strategy
        )
        
        # 3. Orchestrate decision (Top Layer)
        prompt = f"""
        You are the FKS Trading Intelligence system.
        
        Context from RAG: {relevant_docs}
        Analysis: {analysis}
        Account Balance: ${account_balance}
        
        Available tools:
        - fetch_market_data(symbol: str)
        - calculate_position_size(risk_pct: float, atr: float)
        - execute_trade(symbol: str, side: str, size: float)
        
        Should we take this trade? If yes, specify:
        1. Entry price
        2. Position size
        3. Stop loss
        4. Take profit targets
        5. Reasoning
        """
        
        response = self.client.chat(
            model=self.model,
            messages=[{'role': 'user', 'content': prompt}],
            tools=[
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
                                'size': {'type': 'number'}
                            }
                        }
                    }
                }
            ]
        )
        
        return self.process_recommendation(response)
```

#### Alternative: GPT-OSS (20B / 120B)
**Ollama command**: `ollama pull gpt-oss:20b`

**Strengths**:
- Competitive with GPT-4o in function calling
- Strong reasoning/agentic capabilities
- Versatile for development tasks

**Use Cases**:
- Intelligence orchestration in `rag/intelligence.py`
- Complex multi-turn strategy discussions
- API integration coordination

#### Alternative: Mistral-Small3.2 (24B)
**Ollama command**: `ollama pull mistral-small3.2`

**Strengths**:
- Improved function calling
- 128K context (long trading histories)
- Less repetition in responses

**Use Cases**:
- Multi-turn strategy refinement
- Long-context portfolio analysis
- Tool-based automation

### Implementation in FKS

**File**: `src/rag/intelligence.py` (full orchestrator)

```python
from typing import Dict, List, Any, Optional
from ollama import Client
from .embeddings import OllamaEmbeddingService
from .vector_store import VectorStore
from src.trading.intelligence.reasoning import TradingReasoningEngine

class IntelligenceOrchestrator:
    """
    FKS Trading Intelligence - Top-level AI orchestration.
    
    Coordinates:
    1. Base Layer: RAG retrieval (embeddings + vector search)
    2. Middle Layer: Mathematical/coding reasoning
    3. Top Layer: Agentic decision-making with tool calls
    """
    
    def __init__(self):
        self.client = Client(host='http://ollama:11434')
        self.agentic_model = 'llama4:scout'
        self.embedding_service = OllamaEmbeddingService()
        self.vector_store = VectorStore()
        self.reasoning_engine = TradingReasoningEngine()
    
    def get_trading_recommendation(
        self,
        symbol: str,
        account_balance: float,
        available_cash: float,
        context: str = "current market conditions"
    ) -> Dict[str, Any]:
        """
        Generate optimal trading recommendation using layered AI.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            account_balance: Total account balance
            available_cash: Cash available for trading
            context: Additional context for decision
        
        Returns:
            dict: Trading recommendation with entry/exit/sizing
        """
        
        # LAYER 1: RAG Retrieval
        query_embedding = self.embedding_service.embed_query(
            f"Trading analysis for {symbol} {context}"
        )
        
        relevant_docs = self.vector_store.similarity_search(
            embedding=query_embedding,
            limit=5,
            filters={'symbol': symbol}
        )
        
        # LAYER 2: Reasoning
        market_data = self._fetch_market_data(symbol)
        analysis = self.reasoning_engine.analyze_trade_setup(
            symbol=symbol,
            market_data=market_data,
            strategy='trend_following'
        )
        
        # LAYER 3: Agentic Orchestration
        recommendation = self._orchestrate_decision(
            symbol=symbol,
            relevant_docs=relevant_docs,
            analysis=analysis,
            account_balance=account_balance,
            available_cash=available_cash,
            context=context
        )
        
        return recommendation
    
    def _orchestrate_decision(
        self,
        symbol: str,
        relevant_docs: List[dict],
        analysis: dict,
        account_balance: float,
        available_cash: float,
        context: str
    ) -> Dict[str, Any]:
        """Use agentic model to make final decision."""
        
        rag_context = "\n".join([
            f"- {doc['content']} (similarity: {doc['score']:.2f})"
            for doc in relevant_docs
        ])
        
        prompt = f"""
        You are the FKS Trading Intelligence system. Make a trading decision.
        
        === CONTEXT FROM RAG ===
        {rag_context}
        
        === MATHEMATICAL ANALYSIS ===
        {json.dumps(analysis, indent=2)}
        
        === PORTFOLIO STATE ===
        Account Balance: ${account_balance:,.2f}
        Available Cash: ${available_cash:,.2f}
        Symbol: {symbol}
        Context: {context}
        
        === YOUR TASK ===
        Decide if we should take this trade. Consider:
        1. Risk/reward ratio from analysis
        2. Historical context from RAG
        3. Portfolio constraints (available cash)
        4. Current market conditions
        
        If YES, provide:
        - Entry price and reasoning
        - Position size (% of available cash)
        - Stop loss (ATR-based)
        - Take profit targets (1:2 and 1:3 R:R)
        - Confidence score (0-100)
        
        If NO, explain why.
        
        Return as JSON: {{"decision": "YES/NO", "entry_price": float, ...}}
        """
        
        response = self.client.chat(
            model=self.agentic_model,
            messages=[{'role': 'user', 'content': prompt}],
            format='json',
            options={
                'temperature': 0.3,  # Lower for consistent decisions
                'top_p': 0.9
            }
        )
        
        recommendation = json.loads(response['message']['content'])
        
        # Add metadata
        recommendation['model'] = self.agentic_model
        recommendation['timestamp'] = datetime.utcnow().isoformat()
        recommendation['symbol'] = symbol
        
        # Store recommendation in DB for learning
        self._store_recommendation(recommendation)
        
        return recommendation
    
    def _fetch_market_data(self, symbol: str) -> dict:
        """Fetch current market data."""
        # Implementation in src/data/adapters/binance.py
        pass
    
    def _store_recommendation(self, recommendation: dict):
        """Store recommendation for future RAG retrieval."""
        text = f"""
        Trading Recommendation for {recommendation['symbol']}
        Decision: {recommendation['decision']}
        Entry: {recommendation.get('entry_price', 'N/A')}
        Reasoning: {recommendation.get('reasoning', '')}
        """
        
        embedding = self.embedding_service.embed(text)
        self.vector_store.add_document(
            content=text,
            embedding=embedding,
            metadata={
                'type': 'recommendation',
                'symbol': recommendation['symbol'],
                'decision': recommendation['decision'],
                'timestamp': recommendation['timestamp']
            }
        )
```

### Performance Characteristics

| Model | Params | VRAM | Speed (tok/s) | Context | MMMU | Function Calling |
|-------|--------|------|---------------|---------|------|------------------|
| Llama4:scout | 109B/17B | 24GB | ~30 | 128K | 69-73% | Excellent |
| GPT-OSS:20b | 20B | 16GB | ~50 | 64K | ~GPT-4o | Excellent |
| Mistral-Small3.2 | 24B | 16GB | ~45 | 128K | High | Improved |

---

## Integration with FKS Architecture

### Docker Services

**File**: `docker-compose.gpu.yml`

```yaml
services:
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
    command: serve

  rag_service:
    build:
      context: .
      dockerfile: docker/Dockerfile.gpu
    container_name: fks_rag
    depends_on:
      - ollama
      - db
      - redis
    environment:
      - OLLAMA_HOST=http://ollama:11434
      - DATABASE_URL=${DATABASE_URL}
    ports:
      - "8001:8001"
    networks:
      - fks_network
    restart: unless-stopped

volumes:
  ollama_data:
```

### Django Settings

**File**: `src/web/django/settings.py`

```python
# Ollama Configuration
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://ollama:11434')

# Model Selection
OLLAMA_MODELS = {
    'embedding': 'bge-m3',           # Base layer
    'reasoning': 'qwen3:30b',        # Middle layer
    'agentic': 'llama4:scout',       # Top layer
    'math': 'mathstral',             # Specialized math
}

# RAG Configuration
RAG_CONFIG = {
    'vector_dim': 1024,  # BGE-M3 embedding dimension
    'top_k': 5,          # Number of similar docs to retrieve
    'similarity_threshold': 0.7,
}
```

### Celery Tasks

**File**: `src/trading/tasks.py`

```python
from celery import shared_task
from src.rag.intelligence import IntelligenceOrchestrator

@shared_task(name='trading.generate_daily_signals')
def generate_daily_signals():
    """
    Generate optimal trading signals using AI.
    
    Uses layered AI:
    1. Retrieves historical context via RAG
    2. Analyzes math/risk with Qwen3
    3. Makes decision with Llama4
    """
    orchestrator = IntelligenceOrchestrator()
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    
    for symbol in symbols:
        account = Account.objects.get(name='main')
        
        recommendation = orchestrator.get_trading_recommendation(
            symbol=symbol,
            account_balance=float(account.balance),
            available_cash=float(account.available_cash),
            context="daily signal generation"
        )
        
        if recommendation['decision'] == 'YES':
            # Create signal
            Signal.objects.create(
                symbol=symbol,
                signal_type='BUY',
                entry_price=recommendation['entry_price'],
                stop_loss=recommendation['stop_loss'],
                take_profit=recommendation['take_profit'],
                position_size=recommendation['position_size'],
                confidence=recommendation['confidence'],
                reasoning=recommendation['reasoning'],
                source='ai_orchestrator'
            )
            
            logger.info(f"AI Signal: {symbol} - {recommendation}")
```

---

## Model Installation and Setup

### Initial Setup Script

**File**: `scripts/setup_ollama_models.sh`

```bash
#!/bin/bash
# Setup Ollama models for FKS Trading Platform

set -e

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"

echo "🤖 FKS Trading Platform - Ollama Model Setup"
echo "=============================================="

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama service..."
until curl -s "$OLLAMA_HOST/api/tags" > /dev/null; do
    sleep 2
done
echo "✅ Ollama is ready"

# Base Layer: Embeddings
echo ""
echo "📦 Installing Base Layer (Embeddings)..."
ollama pull bge-m3
echo "✅ BGE-M3 installed (567M params)"

# Optional: Alternative embeddings
# ollama pull qwen3-embedding:8b
# ollama pull nomic-embed-text

# Middle Layer: Reasoning/Coding
echo ""
echo "🧠 Installing Middle Layer (Reasoning)..."
ollama pull qwen3:30b
echo "✅ Qwen3:30b installed (30B params)"

ollama pull mathstral
echo "✅ Mathstral installed (7B params)"

# Optional: DeepSeek for advanced reasoning
# ollama pull deepseek-v3.1

# Top Layer: Agentic
echo ""
echo "🎯 Installing Top Layer (Agentic)..."
ollama pull llama4:scout
echo "✅ Llama4:scout installed (109B MoE)"

# Optional: Alternatives
# ollama pull gpt-oss:20b
# ollama pull mistral-small3.2

echo ""
echo "=============================================="
echo "✅ All models installed successfully!"
echo ""
echo "Installed models:"
ollama list

echo ""
echo "Next steps:"
echo "1. Verify models: ollama list"
echo "2. Test embedding: ollama run bge-m3"
echo "3. Test reasoning: ollama run qwen3:30b"
echo "4. Test agentic: ollama run llama4:scout"
echo ""
echo "See docs/AI_ARCHITECTURE.md for integration details"
```

### Makefile Commands

**File**: `Makefile`

```makefile
# Ollama/AI commands
.PHONY: ollama-setup ollama-test ollama-logs

ollama-setup:
	@echo "Setting up Ollama models..."
	bash scripts/setup_ollama_models.sh

ollama-test:
	@echo "Testing Ollama models..."
	pytest src/tests/test_ai/ -v -m ollama

ollama-logs:
	@echo "Showing Ollama logs..."
	docker-compose -f docker-compose.gpu.yml logs -f ollama
```

---

## Testing Strategy

### Unit Tests

**File**: `src/tests/test_ai/test_embeddings.py`

```python
import pytest
from src.rag.embeddings import OllamaEmbeddingService

@pytest.fixture
def embedding_service():
    return OllamaEmbeddingService()

def test_embed_single_document(embedding_service):
    """Test single document embedding."""
    text = "BTCUSDT price analysis: bullish trend confirmed"
    embedding = embedding_service.embed(text)
    
    assert isinstance(embedding, list)
    assert len(embedding) == 1024  # BGE-M3 dimension
    assert all(isinstance(x, float) for x in embedding)

def test_embed_multiple_documents(embedding_service):
    """Test batch embedding."""
    texts = [
        "BTC analysis",
        "ETH trading signal",
        "Market sentiment bearish"
    ]
    embeddings = embedding_service.embed_documents(texts)
    
    assert len(embeddings) == 3
    assert all(len(emb) == 1024 for emb in embeddings)

def test_similarity_search(embedding_service, vector_store):
    """Test semantic similarity search."""
    # Store some docs
    docs = [
        "Bitcoin bullish breakout above $50k",
        "Ethereum upgrade successful",
        "BTC bearish pattern forming"
    ]
    for doc in docs:
        embedding = embedding_service.embed(doc)
        vector_store.add_document(doc, embedding)
    
    # Search
    query = "Bitcoin price movement"
    query_embedding = embedding_service.embed_query(query)
    results = vector_store.similarity_search(query_embedding, limit=2)
    
    assert len(results) == 2
    assert "Bitcoin" in results[0]['content'] or "BTC" in results[0]['content']
```

### Integration Tests

**File**: `src/tests/test_ai/test_intelligence_orchestrator.py`

```python
import pytest
from src.rag.intelligence import IntelligenceOrchestrator

@pytest.fixture
def orchestrator():
    return IntelligenceOrchestrator()

@pytest.mark.integration
@pytest.mark.slow
def test_full_recommendation_flow(orchestrator):
    """Test complete layered AI recommendation."""
    
    recommendation = orchestrator.get_trading_recommendation(
        symbol='BTCUSDT',
        account_balance=10000.00,
        available_cash=5000.00,
        context="test scenario"
    )
    
    assert 'decision' in recommendation
    assert recommendation['decision'] in ['YES', 'NO']
    
    if recommendation['decision'] == 'YES':
        assert 'entry_price' in recommendation
        assert 'position_size' in recommendation
        assert 'stop_loss' in recommendation
        assert 'take_profit' in recommendation
        assert 'confidence' in recommendation
        assert 'reasoning' in recommendation

@pytest.mark.integration
def test_rag_retrieval(orchestrator):
    """Test RAG context retrieval."""
    # Add some test documents
    orchestrator.vector_store.add_document(
        content="BTC hit resistance at $52k",
        embedding=orchestrator.embedding_service.embed("BTC resistance $52k"),
        metadata={'symbol': 'BTCUSDT', 'type': 'analysis'}
    )
    
    # Query
    query_embedding = orchestrator.embedding_service.embed_query("Bitcoin resistance levels")
    results = orchestrator.vector_store.similarity_search(query_embedding, limit=1)
    
    assert len(results) > 0
    assert "52k" in results[0]['content']
```

---

## Performance Benchmarks

### Expected Performance (on RTX 4090 24GB VRAM)

| Layer | Model | VRAM | Tokens/sec | Latency | Throughput |
|-------|-------|------|------------|---------|------------|
| Base | BGE-M3 | 2GB | ~1000 | <100ms | ~100 embeds/sec |
| Middle | Qwen3:30b | 16GB | ~50 | ~2s | ~25 inferences/min |
| Top | Llama4:scout | 24GB | ~30 | ~3s | ~20 decisions/min |

### Optimization Strategies

1. **Quantization**: Use 4-bit quantization via Ollama (automatic)
2. **Batching**: Batch embeddings for efficiency
3. **Caching**: Cache embeddings in Redis for repeated queries
4. **Model Swapping**: Load/unload models based on demand
5. **Parallel Inference**: Run base + middle layers simultaneously

---

## Monitoring and Observability

### Prometheus Metrics

**File**: `src/rag/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge

# Embedding metrics
embedding_requests = Counter(
    'ollama_embedding_requests_total',
    'Total embedding requests',
    ['model']
)

embedding_duration = Histogram(
    'ollama_embedding_duration_seconds',
    'Embedding generation duration',
    ['model']
)

# Inference metrics
inference_requests = Counter(
    'ollama_inference_requests_total',
    'Total inference requests',
    ['layer', 'model']
)

inference_duration = Histogram(
    'ollama_inference_duration_seconds',
    'Inference duration',
    ['layer', 'model']
)

# Model status
model_loaded = Gauge(
    'ollama_model_loaded',
    'Whether model is loaded',
    ['model']
)
```

### Grafana Dashboard

**File**: `monitoring/grafana/dashboards/ai-performance.json`

Panels:
- Embedding requests/sec
- Inference latency (p50, p95, p99)
- Model VRAM usage
- Token generation speed
- Cache hit rates

---

## Migration from OpenAI

If currently using OpenAI API:

### Before (OpenAI)
```python
from openai import OpenAI

client = OpenAI()
response = client.embeddings.create(
    input="text",
    model="text-embedding-ada-002"
)
```

### After (Ollama)
```python
from ollama import Client

client = Client(host='http://ollama:11434')
response = client.embeddings(
    model='bge-m3',
    prompt="text"
)
```

### Cost Savings
- **OpenAI**: $0.0001 per 1K tokens = $100/million tokens
- **Ollama**: $0 (local inference)
- **Annual savings** (estimated): $10K-$50K depending on volume

---

## Risks and Mitigation

### Risk 1: Hallucination in Financial Decisions
**Impact**: AI makes incorrect trading recommendations  
**Mitigation**:
- Implement fact-checking chains
- Require human approval for large trades
- Set confidence thresholds (e.g., only act on >80% confidence)
- Monitor recommendation accuracy

### Risk 2: Model Drift
**Impact**: Model performance degrades over time  
**Mitigation**:
- Continuous evaluation on held-out test set
- Track decision accuracy vs actual outcomes
- Retrain/fine-tune quarterly

### Risk 3: GPU Resource Exhaustion
**Impact**: Models fail to load or run slowly  
**Mitigation**:
- Implement model swapping (load on-demand)
- Use smaller models during high load
- Scale horizontally (multiple GPU nodes)

### Risk 4: Inference Latency
**Impact**: Slow recommendations miss trading opportunities  
**Mitigation**:
- Cache frequent queries
- Use smaller models for time-sensitive tasks
- Pre-compute embeddings overnight
- Implement timeout fallbacks

---

## Roadmap

### Phase 1: Base Layer (Weeks 1-2)
- ✅ Research and document models (this doc)
- ⏳ Install Ollama + BGE-M3
- ⏳ Implement `OllamaEmbeddingService`
- ⏳ Integrate with pgvector
- ⏳ Test embedding generation and search

### Phase 2: Middle Layer (Weeks 3-4)
- ⏳ Install Qwen3:30b + Mathstral
- ⏳ Implement `TradingReasoningEngine`
- ⏳ Test math calculations (ATR, position sizing)
- ⏳ Generate backtest code with AI
- ⏳ Validate reasoning accuracy

### Phase 3: Top Layer (Weeks 5-6)
- ⏳ Install Llama4:scout
- ⏳ Implement `IntelligenceOrchestrator`
- ⏳ Connect all three layers
- ⏳ Test full recommendation flow
- ⏳ Add function calling for tool use

### Phase 4: Integration (Weeks 7-8)
- ⏳ Integrate with Celery tasks
- ⏳ Connect to live trading (with safeguards)
- ⏳ Add monitoring/metrics
- ⏳ Performance optimization
- ⏳ Production deployment

### Phase 5: Optimization (Weeks 9-12)
- ⏳ Fine-tune on historical trades
- ⏳ Implement caching strategies
- ⏳ Add model swapping logic
- ⏳ Scale to multiple symbols
- ⏳ Continuous learning loop

---

## References

### Research Citations

1. **Choosing Ollama Models: The Complete 2025 Guide**  
   https://collabnix.com/choosing-ollama-models-the-complete-2025-guide-for-developers-and-enterprises/

2. **The 11 Best Open-Source LLMs for 2025**  
   https://blog.n8n.io/open-source-llm/

3. **The Latest Ollama Models in 2025 Update**  
   https://www.elightwalk.com/blog/latest-ollama-models

4. **10 Open-Source AI Models for Home Labs (August 2025)**  
   https://www.virtualizationhowto.com/2025/08/10-open-source-ai-models-you-should-try-in-your-home-lab-august-2025/

5. **Top 5 Local LLM Tools and Models in 2025**  
   https://pinggy.io/blog/top_5_local_llm_tools_and_models_2025/

6. **Best Ollama Models: Top AI Models in 2025**  
   https://www.byteplus.com/en/topic/398259

7. **Phi-4 and Ollama in PostgreSQL**  
   https://www.tigerdata.com/blog/best-open-source-ai-model-experimenting-with-phi-4-and-ollama-in-postgresql

### Internal Documentation

- `docs/ARCHITECTURE.md` - Overall system architecture
- `docs/features/RAG_SYSTEM.md` - RAG implementation details
- `src/rag/README.md` - RAG module documentation
- `src/trading/README.md` - Trading system overview

---

**Last Updated**: October 17, 2025  
**Status**: Planning Complete - Ready for Implementation  
**Next Action**: Create GitHub issues for Phases 1-5
