# Phase 6: Multi-Agent Foundation - Kickoff Plan

**Status**: Ready to Begin  
**Duration**: 4 weeks (Weeks 1-4 of AI Enhancement Plan)  
**Goal**: Establish LangGraph infrastructure for AI-powered trading decisions  
**Start Date**: October 31, 2025

---

## 📋 Phase 6 Overview

Transform FKS into an intelligent multi-agent system where specialized AI agents collaborate to make trading decisions through adversarial debate and consensus-building.

### Success Criteria
- [ ] Ollama serving llama3.2:3b on fks_ai (port 8006)
- [ ] All 7 agents operational (4 analysts + 3 debate agents)
- [ ] Graph execution <5 seconds
- [ ] Signal quality >60% accuracy on validation set
- [ ] ChromaDB memory with >1000 trading insights

### Expected Outcomes
- Multi-agent debate system generating contrasting views
- Regime-aware decision making
- Self-improving through reflection loops
- Foundation for Phases 7-11 (advanced AI features)

---

## 🗓️ 3-Week Implementation Plan

### Week 1: Phase 6.1 - Agentic Foundation (5-7 days)

**Objective**: Setup LangGraph + Ollama + ChromaDB infrastructure

#### Day 1-2: Environment Setup
- [ ] Install LangChain/LangGraph dependencies
- [ ] Configure Ollama with llama3.2:3b model
- [ ] Setup ChromaDB for agent memory
- [ ] Verify GPU acceleration working

**Files to Create**:
```
src/services/ai/requirements-langgraph.txt
src/services/ai/src/config/agent_config.py
src/services/ai/src/memory/chroma_client.py
docker/Dockerfile.ai (update for LangGraph)
```

**Commands**:
```bash
# Install dependencies
docker-compose exec fks_ai pip install langchain langgraph chromadb

# Pull Ollama model
docker-compose exec fks_ai ollama pull llama3.2:3b

# Verify setup
docker-compose exec fks_ai python -c "import langchain; import langgraph; import chromadb; print('All imports successful')"
```

**Acceptance Criteria**:
- [ ] LangGraph installed and importable
- [ ] Ollama responding to test prompts (<3s latency)
- [ ] ChromaDB creating collections successfully

---

#### Day 3-4: AgentState Schema & Base Agent

**Objective**: Define data structures for agent communication

**Files to Create**:
```
src/services/ai/src/agents/state.py         # AgentState TypedDict
src/services/ai/src/agents/base.py          # Base agent factory
src/services/ai/src/agents/__init__.py
```

**AgentState Schema** (`state.py`):
```python
from typing import TypedDict, List, Annotated, Optional, Dict, Any
from langgraph.graph import add_messages

class AgentState(TypedDict):
    """Shared state for all agents in the graph"""
    messages: Annotated[List, add_messages]  # Conversation history
    market_data: Dict[str, Any]  # OHLCV, indicators, features
    signals: List[Dict]  # Generated trading signals
    debates: List[str]  # Bull/Bear arguments
    memory: List[str]  # ChromaDB retrieval context
    regime: Optional[str]  # Market regime (bull/bear/sideways)
    confidence: float  # Overall confidence (0-1)
    final_decision: Optional[Dict]  # Manager's final output
```

**Base Agent Factory** (`base.py`):
```python
from langchain_ollama import ChatOllama
from langchain.prompts import ChatPromptTemplate

def create_agent(
    role: str,
    system_prompt: str,
    model: str = "llama3.2:3b",
    temperature: float = 0.7
):
    """Factory for creating specialized agents"""
    llm = ChatOllama(model=model, temperature=temperature)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}")
    ])
    
    return prompt | llm
```

**Acceptance Criteria**:
- [ ] AgentState schema handles all required fields
- [ ] Base agent factory creates working agents
- [ ] Test agent responds to simple prompts

---

#### Day 5-7: ChromaDB Memory Integration

**Objective**: Persistent memory for agent context and learning

**Files to Create**:
```
src/services/ai/src/memory/chroma_client.py
src/services/ai/src/memory/memory_manager.py
src/services/ai/tests/test_memory.py
```

**ChromaDB Client** (`chroma_client.py`):
```python
import chromadb
from chromadb.config import Settings
from typing import List, Dict

class TradingMemory:
    def __init__(self, persist_directory: str = "./chroma_data"):
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False
        ))
        self.collection = self.client.get_or_create_collection(
            name="trading_insights",
            metadata={"description": "Multi-agent trading decisions"}
        )
    
    def add_insight(self, text: str, metadata: Dict):
        """Store trading insight with metadata"""
        self.collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[f"insight_{len(self.collection.get()['ids'])}"]
        )
    
    def query_similar(self, query: str, n_results: int = 5) -> List[str]:
        """Retrieve similar past insights"""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results['documents'][0]
```

**Acceptance Criteria**:
- [ ] ChromaDB storing insights successfully
- [ ] Semantic search returning relevant results
- [ ] Memory persists across restarts
- [ ] Test suite passing (10+ tests)

---

### Week 2: Phase 6.2 - Multi-Agent Debate (7-10 days)

**Objective**: Build 7 specialized agents with debate system

#### Day 8-10: Analyst Agents (4 types)

**Files to Create**:
```
src/services/ai/src/agents/analysts/technical.py
src/services/ai/src/agents/analysts/sentiment.py
src/services/ai/src/agents/analysts/macro.py
src/services/ai/src/agents/analysts/risk.py
src/services/ai/tests/test_analysts.py
```

**Technical Analyst** (`technical.py`):
```python
from ..base import create_agent

TECHNICAL_PROMPT = """You are a Technical Analyst specializing in chart patterns, 
indicators (RSI, MACD, Bollinger Bands), and price action.

Current market data: {market_data}

Analyze:
1. Trend direction and strength
2. Support/resistance levels
3. Indicator signals (overbought/oversold)
4. Volume patterns

Provide: BUY, SELL, or HOLD with confidence (0-1) and reasoning."""

technical_agent = create_agent(
    role="Technical Analyst",
    system_prompt=TECHNICAL_PROMPT
)
```

**Similar structure for**:
- **Sentiment Analyst**: News, social media, fear/greed index
- **Macro Analyst**: CPI, interest rates, correlations, economic indicators
- **Risk Analyst**: VaR, MDD, position sizing, exposure limits

**Acceptance Criteria**:
- [ ] All 4 analysts generating different perspectives
- [ ] Outputs include confidence scores
- [ ] Reasoning is fact-based and specific

---

#### Day 11-13: Debate Agents (Bull/Bear/Manager)

**Files to Create**:
```
src/services/ai/src/agents/debaters/bull.py
src/services/ai/src/agents/debaters/bear.py
src/services/ai/src/agents/debaters/manager.py
src/services/ai/tests/test_debate.py
```

**Bull Agent** (`bull.py`):
```python
BULL_PROMPT = """You are the Bull Agent, advocating for LONG positions.

Analyst insights: {analyst_insights}
Bear argument: {bear_argument}

Your role:
1. Find bullish signals and opportunities
2. Counter bearish arguments with data
3. Emphasize upside potential
4. Acknowledge but minimize risks

Generate: Persuasive LONG case with confidence and refutations."""

bull_agent = create_agent(role="Bull", system_prompt=BULL_PROMPT)
```

**Manager Agent** (`manager.py`):
```python
MANAGER_PROMPT = """You are the Manager, synthesizing Bull and Bear debates.

Bull argument: {bull_argument}
Bear argument: {bear_argument}
Market regime: {regime}

Your role:
1. Evaluate both arguments objectively
2. Consider market regime context
3. Weigh confidence levels
4. Make final BUY/SELL/HOLD decision

Output: Final decision with reasoning and position size (% of capital)."""

manager_agent = create_agent(role="Manager", system_prompt=MANAGER_PROMPT, temperature=0.3)
```

**Acceptance Criteria**:
- [ ] Bull/Bear generating contrasting views
- [ ] Manager synthesizing debates objectively
- [ ] Decisions include position sizing

---

#### Day 14-15: Trader Personas + Judge

**Files to Create**:
```
src/services/ai/src/agents/traders/conservative.py
src/services/ai/src/agents/traders/moderate.py
src/services/ai/src/agents/traders/aggressive.py
src/services/ai/src/agents/traders/judge.py
```

**Judge Agent** (`judge.py`):
```python
JUDGE_PROMPT = """You are the Judge, selecting optimal trader persona.

Market volatility: {volatility}
Confidence: {confidence}
Account size: {account_size}

Personas:
- Conservative: Tight stops, 1-2% risk, high certainty only
- Moderate: Balanced, 2-5% risk, normal conditions
- Aggressive: Wide stops, 5-10% risk, high conviction

Select persona based on: volatility, confidence, regime."""

judge_agent = create_agent(role="Judge", system_prompt=JUDGE_PROMPT)
```

**Acceptance Criteria**:
- [ ] Judge selecting personas correctly (>70% accuracy on test data)
- [ ] Personas adjusting position size appropriately
- [ ] Risk limits enforced

---

### Week 3: Phase 6.3 - Graph Orchestration (7-10 days)

**Objective**: Build end-to-end StateGraph with reflection

#### Day 16-18: StateGraph Construction

**Files to Create**:
```
src/services/ai/src/graph/trading_graph.py
src/services/ai/src/graph/nodes.py
src/services/ai/src/graph/edges.py
```

**Trading Graph** (`trading_graph.py`):
```python
from langgraph.graph import StateGraph, END
from ..agents.state import AgentState
from .nodes import (
    run_analysts,
    debate_node,
    manager_decision,
    select_trader,
    reflection_node
)
from .edges import route_to_trader

def build_trading_graph():
    """Construct multi-agent trading graph"""
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("analysts", run_analysts)
    graph.add_node("debate", debate_node)
    graph.add_node("manager", manager_decision)
    graph.add_node("trader", select_trader)
    graph.add_node("reflect", reflection_node)
    
    # Add edges
    graph.add_edge("analysts", "debate")
    graph.add_edge("debate", "manager")
    graph.add_conditional_edges(
        "manager",
        route_to_trader,  # Check if confidence > threshold
        {"execute": "trader", "skip": END}
    )
    graph.add_edge("trader", "reflect")
    graph.add_edge("reflect", END)
    
    # Set entry point
    graph.set_entry_point("analysts")
    
    return graph.compile()
```

**Nodes Implementation** (`nodes.py`):
```python
from typing import Dict
from ..agents.analysts import technical, sentiment, macro, risk
from ..agents.debaters import bull, bear, manager

async def run_analysts(state: AgentState) -> AgentState:
    """Run all 4 analyst agents in parallel"""
    insights = []
    
    for agent in [technical, sentiment, macro, risk]:
        result = await agent.ainvoke({
            "input": f"Analyze {state['market_data']['symbol']}"
        })
        insights.append(result.content)
    
    state['messages'].extend(insights)
    return state

async def debate_node(state: AgentState) -> AgentState:
    """Bull vs Bear debate"""
    bull_arg = await bull.ainvoke({"analyst_insights": state['messages']})
    bear_arg = await bear.ainvoke({"analyst_insights": state['messages']})
    
    state['debates'] = [bull_arg.content, bear_arg.content]
    return state

async def manager_decision(state: AgentState) -> AgentState:
    """Manager synthesizes debate"""
    decision = await manager.ainvoke({
        "bull_argument": state['debates'][0],
        "bear_argument": state['debates'][1],
        "regime": state.get('regime', 'unknown')
    })
    
    state['final_decision'] = parse_decision(decision.content)
    return state
```

**Acceptance Criteria**:
- [ ] Graph executes full pipeline
- [ ] All nodes processing correctly
- [ ] State passing between nodes
- [ ] Conditional routing working

---

#### Day 19-20: Signal Processor

**Files to Create**:
```
src/services/ai/src/processors/signal_processor.py
src/services/ai/tests/test_processor.py
```

**Signal Processor** (`signal_processor.py`):
```python
from typing import Dict, List

class SignalProcessor:
    """Convert agent decisions to executable signals"""
    
    def process(self, agent_decision: Dict) -> Dict:
        """Transform agent output to signal format"""
        return {
            "symbol": agent_decision['symbol'],
            "action": agent_decision['action'],  # BUY/SELL/HOLD
            "confidence": agent_decision['confidence'],
            "position_size": self._calculate_size(agent_decision),
            "stop_loss": self._calculate_stop(agent_decision),
            "take_profit": self._calculate_target(agent_decision),
            "reasoning": agent_decision['reasoning'],
            "timestamp": datetime.now()
        }
    
    def _calculate_size(self, decision: Dict) -> float:
        """Position size based on confidence and persona"""
        base_size = 0.02  # 2% default
        confidence_multiplier = decision['confidence']
        persona_multiplier = {
            'conservative': 0.5,
            'moderate': 1.0,
            'aggressive': 2.0
        }[decision.get('persona', 'moderate')]
        
        return base_size * confidence_multiplier * persona_multiplier
```

**Acceptance Criteria**:
- [ ] Signals have all required fields
- [ ] Position sizing within risk limits
- [ ] Stop-loss/take-profit calculated correctly

---

#### Day 21-22: Reflection Node

**Files to Create**:
```
src/services/ai/src/graph/reflection.py
src/services/ai/tests/test_reflection.py
```

**Reflection Node** (`reflection.py`):
```python
from ..memory import TradingMemory

async def reflection_node(state: AgentState) -> AgentState:
    """Analyze decision and update memory"""
    memory = TradingMemory()
    
    # Store decision with metadata
    memory.add_insight(
        text=f"Decision: {state['final_decision']} | Reasoning: {state['messages']}",
        metadata={
            "symbol": state['market_data']['symbol'],
            "action": state['final_decision']['action'],
            "confidence": state['final_decision']['confidence'],
            "regime": state.get('regime'),
            "timestamp": datetime.now().isoformat()
        }
    )
    
    # Retrieve similar past decisions
    similar = memory.query_similar(
        query=f"Trading {state['market_data']['symbol']} in {state['regime']} regime",
        n_results=3
    )
    
    state['memory'] = similar
    return state
```

**Acceptance Criteria**:
- [ ] Decisions stored in ChromaDB
- [ ] Memory retrieval working
- [ ] Insights accumulating over time

---

## 🧪 Testing Strategy

### Unit Tests (40+ tests)
```bash
# Test individual agents
pytest src/services/ai/tests/test_analysts.py -v
pytest src/services/ai/tests/test_debate.py -v

# Test memory
pytest src/services/ai/tests/test_memory.py -v

# Test graph nodes
pytest src/services/ai/tests/test_graph.py -v
```

### Integration Tests (10+ tests)
```bash
# End-to-end graph execution
pytest src/services/ai/tests/integration/test_e2e_graph.py -v

# Signal quality validation
pytest src/services/ai/tests/integration/test_signal_quality.py -v
```

### Performance Benchmarks
- Graph execution latency: <5 seconds
- Ollama response time: <3 seconds per agent
- ChromaDB query time: <100ms

---

## 📊 Validation Plan

### Signal Quality Metrics
```python
# Test on historical data (BTC/ETH 2024)
validation_metrics = {
    "accuracy": 0.65,  # Target >60%
    "precision": 0.70,
    "recall": 0.60,
    "f1_score": 0.65
}
```

### Debate Quality Checks
- Bull/Bear arguments must be contrasting (>70% different)
- Manager decisions must reference both arguments
- Confidence scores correlate with actual outcomes

---

## 🚀 Deployment Checklist

- [ ] All 40+ unit tests passing
- [ ] 10+ integration tests passing
- [ ] Graph execution <5 seconds
- [ ] Signal quality >60% on validation set
- [ ] ChromaDB memory >1000 insights
- [ ] Ollama stable under load
- [ ] Documentation complete
- [ ] API endpoints created for fks_app integration

---

## 📝 Documentation Requirements

**Files to Create**:
```
docs/PHASE_6_ARCHITECTURE.md     # System design
docs/PHASE_6_API.md               # API reference
docs/PHASE_6_COMPLETE.md          # Completion report
```

**API Endpoints** (for fks_app integration):
```
POST /ai/analyze              # Run full graph
POST /ai/debate              # Bull vs Bear only
GET  /ai/memory/query        # Query ChromaDB
GET  /ai/agents/status       # Health check
```

---

## 🎯 Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Graph Latency | <5s | Time full pipeline execution |
| Signal Accuracy | >60% | Validate on BTC/ETH 2024 data |
| Debate Quality | >70% contrast | Semantic similarity between Bull/Bear |
| Memory Size | >1000 insights | ChromaDB collection count |
| Agent Uptime | >99% | Ollama availability checks |

---

## 💡 Next Steps After Phase 6

Once Phase 6 is complete, proceed to:
- **Phase 7**: Evaluation Framework (confusion matrices, LLM-judge)
- **Phase 8**: Hybrid Models (CNN-LSTM + LLM vetoes, WFO, MDD protection)
- **Phase 9**: Markov Integration (state transitions, steady-state probabilities)

---

**Ready to Start?** Begin with Day 1-2 (Environment Setup) tomorrow (Oct 31, 2025).

**First Command**:
```bash
docker-compose exec fks_ai pip install langchain langgraph chromadb
```

---
*Generated: October 30, 2025*  
*Phase 6 Duration: 3 weeks (21-22 days)*  
*Complexity: High | Dependencies: Ollama, LangGraph, ChromaDB*
