"""
API Routes for Multi-Agent Trading System

Endpoints:
- POST /ai/analyze - Full multi-agent analysis with trading signals
- POST /ai/debate - Bull/Bear debate only (no final decision)
- GET /ai/memory/query - Query similar past decisions
- GET /ai/agents/status - Health check for all agents
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import logging

# Import Phase 6 components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from graph.trading_graph import analyze_symbol, trading_graph
from agents.state import create_initial_state
from agents.analysts.technical import technical_analyst
from agents.analysts.sentiment import sentiment_analyst
from agents.analysts.macro import macro_analyst
from agents.analysts.risk import risk_analyst
from agents.debaters.bull import bull_agent
from agents.debaters.bear import bear_agent
from agents.debaters.manager import manager_agent
from memory.memory_manager import TradingMemory
from processors.signal_processor import SignalProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="FKS AI Service",
    description="Multi-Agent Trading Intelligence API",
    version="1.0.0"
)

# Initialize global components
try:
    trading_memory = TradingMemory()
    signal_processor = SignalProcessor()
    logger.info("Initialized TradingMemory and SignalProcessor")
except Exception as e:
    logger.error(f"Failed to initialize components: {e}")
    trading_memory = None
    signal_processor = None


# Request/Response Models
class AnalyzeRequest(BaseModel):
    """Request model for full multi-agent analysis"""
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    market_data: Dict[str, Any] = Field(..., description="OHLCV and indicators")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "BTCUSDT",
                "market_data": {
                    "price": 67234.50,
                    "rsi": 58.5,
                    "macd": 150.2,
                    "macd_signal": 125.8,
                    "bb_upper": 68000.0,
                    "bb_middle": 67000.0,
                    "bb_lower": 66000.0,
                    "atr": 400.0,
                    "volume": 1234567890,
                    "regime": "bull"
                }
            }
        }


class DebateRequest(BaseModel):
    """Request model for Bull/Bear debate"""
    symbol: str = Field(..., description="Trading symbol")
    market_data: Dict[str, Any] = Field(..., description="OHLCV and indicators")


class MemoryQueryRequest(BaseModel):
    """Request model for memory similarity search"""
    query: str = Field(..., description="Search query text")
    n_results: int = Field(default=5, ge=1, le=20, description="Number of results")
    filter_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Filter by metadata")


class AnalyzeResponse(BaseModel):
    """Response model for analysis endpoint"""
    symbol: str
    timestamp: datetime
    analysts: Dict[str, str]
    debate: Dict[str, str]
    final_decision: str
    trading_signal: Dict[str, Any]
    confidence: float
    regime: str
    execution_time_ms: float


class DebateResponse(BaseModel):
    """Response model for debate endpoint"""
    symbol: str
    timestamp: datetime
    bull_argument: str
    bear_argument: str
    execution_time_ms: float


class MemoryQueryResponse(BaseModel):
    """Response model for memory query endpoint"""
    results: List[Dict[str, Any]]
    count: int


class AgentStatusResponse(BaseModel):
    """Response model for agent status endpoint"""
    status: str
    agents: Dict[str, Dict[str, Any]]
    memory_status: Dict[str, Any]
    uptime_ms: float


# API Endpoints

@app.post("/ai/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Full multi-agent analysis with trading signals.
    
    Executes complete StateGraph:
    1. Technical, Sentiment, Macro, Risk analysts
    2. Bull/Bear debate
    3. Manager synthesis
    4. Signal generation with risk management
    5. Reflection and memory storage
    
    Returns:
    - Analyst insights
    - Debate arguments
    - Final decision
    - Executable trading signal
    - Confidence score
    """
    start_time = asyncio.get_event_loop().time()
    
    try:
        # Execute full graph analysis
        logger.info(f"Starting analysis for {request.symbol}")
        final_state = await analyze_symbol(request.symbol, request.market_data)
        
        # Extract results
        analysts_output = {
            "technical": final_state.get('messages', [{}])[0].get('content', '') if final_state.get('messages') else '',
            "sentiment": final_state.get('messages', [{}])[1].get('content', '') if len(final_state.get('messages', [])) > 1 else '',
            "macro": final_state.get('messages', [{}])[2].get('content', '') if len(final_state.get('messages', [])) > 2 else '',
            "risk": final_state.get('messages', [{}])[3].get('content', '') if len(final_state.get('messages', [])) > 3 else ''
        }
        
        debate_output = {
            "bull": final_state.get('debates', [''])[0] if final_state.get('debates') else '',
            "bear": final_state.get('debates', ['', ''])[1] if len(final_state.get('debates', [])) > 1 else ''
        }
        
        # Process signal if signal_processor available
        trading_signal = {}
        if signal_processor and final_state.get('final_decision'):
            trading_signal = signal_processor.process_decision(
                final_state['final_decision'],
                request.market_data
            )
        
        execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return AnalyzeResponse(
            symbol=request.symbol,
            timestamp=datetime.utcnow(),
            analysts=analysts_output,
            debate=debate_output,
            final_decision=final_state.get('final_decision', ''),
            trading_signal=trading_signal,
            confidence=final_state.get('confidence', 0.5),
            regime=final_state.get('regime', 'unknown'),
            execution_time_ms=execution_time
        )
        
    except Exception as e:
        logger.error(f"Analysis failed for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/ai/debate", response_model=DebateResponse)
async def debate(request: DebateRequest):
    """
    Bull/Bear debate only (no manager synthesis).
    
    Runs adversarial debate between Bull and Bear agents without
    final decision. Useful for exploring contrasting viewpoints.
    
    Returns:
    - Bull agent's optimistic argument
    - Bear agent's pessimistic argument
    - Execution time
    """
    start_time = asyncio.get_event_loop().time()
    
    try:
        # Create minimal state for debate
        state = create_initial_state(request.symbol, request.market_data)
        
        # Run Bull and Bear agents in parallel
        logger.info(f"Starting debate for {request.symbol}")
        bull_result, bear_result = await asyncio.gather(
            bull_agent.ainvoke(state),
            bear_agent.ainvoke(state)
        )
        
        execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
        
        return DebateResponse(
            symbol=request.symbol,
            timestamp=datetime.utcnow(),
            bull_argument=bull_result.get('content', '') if isinstance(bull_result, dict) else str(bull_result),
            bear_argument=bear_result.get('content', '') if isinstance(bear_result, dict) else str(bear_result),
            execution_time_ms=execution_time
        )
        
    except Exception as e:
        logger.error(f"Debate failed for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Debate failed: {str(e)}")


@app.get("/ai/memory/query", response_model=MemoryQueryResponse)
async def query_memory(
    query: str = Query(..., description="Search query text"),
    n_results: int = Query(default=5, ge=1, le=20, description="Number of results"),
    symbol: Optional[str] = Query(default=None, description="Filter by symbol"),
    min_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0, description="Minimum confidence")
):
    """
    Query similar past decisions from ChromaDB memory.
    
    Performs semantic similarity search across historical agent decisions.
    Supports filtering by symbol and confidence threshold.
    
    Returns:
    - List of similar decisions with metadata
    - Result count
    """
    if not trading_memory:
        raise HTTPException(status_code=503, detail="Memory system not initialized")
    
    try:
        # Build filter metadata
        filter_metadata = {}
        if symbol:
            filter_metadata['symbol'] = symbol
        if min_confidence is not None:
            filter_metadata['confidence'] = {'$gte': min_confidence}
        
        # Query memory
        logger.info(f"Querying memory: query='{query}', n={n_results}, filters={filter_metadata}")
        results = trading_memory.query_similar(
            query=query,
            n_results=n_results,
            filter_metadata=filter_metadata if filter_metadata else None
        )
        
        return MemoryQueryResponse(
            results=results,
            count=len(results)
        )
        
    except Exception as e:
        logger.error(f"Memory query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Memory query failed: {str(e)}")


@app.get("/ai/agents/status", response_model=AgentStatusResponse)
async def agent_status():
    """
    Health check for all agents and system components.
    
    Tests connectivity to:
    - Ollama LLM service
    - ChromaDB memory
    - All 7 agents (4 analysts + 3 debaters)
    
    Returns:
    - Overall status (healthy/degraded/unhealthy)
    - Individual agent status
    - Memory system status
    - Uptime
    """
    start_time = asyncio.get_event_loop().time()
    
    agents_status = {}
    overall_status = "healthy"
    
    # Test all agents with minimal state
    test_state = create_initial_state("BTCUSDT", {
        "price": 50000.0,
        "rsi": 50.0,
        "macd": 0.0,
        "regime": "neutral"
    })
    
    # Test analyst agents
    analyst_agents = {
        "technical": technical_analyst,
        "sentiment": sentiment_analyst,
        "macro": macro_analyst,
        "risk": risk_analyst
    }
    
    for name, agent in analyst_agents.items():
        try:
            result = await asyncio.wait_for(agent.ainvoke(test_state), timeout=5.0)
            agents_status[name] = {"status": "healthy", "response_type": type(result).__name__}
        except asyncio.TimeoutError:
            agents_status[name] = {"status": "timeout", "error": "Response timeout"}
            overall_status = "degraded"
        except Exception as e:
            agents_status[name] = {"status": "unhealthy", "error": str(e)}
            overall_status = "unhealthy"
    
    # Test debate agents
    debate_agents = {
        "bull": bull_agent,
        "bear": bear_agent,
        "manager": manager_agent
    }
    
    for name, agent in debate_agents.items():
        try:
            result = await asyncio.wait_for(agent.ainvoke(test_state), timeout=5.0)
            agents_status[name] = {"status": "healthy", "response_type": type(result).__name__}
        except asyncio.TimeoutError:
            agents_status[name] = {"status": "timeout", "error": "Response timeout"}
            overall_status = "degraded"
        except Exception as e:
            agents_status[name] = {"status": "unhealthy", "error": str(e)}
            overall_status = "unhealthy"
    
    # Test memory system
    memory_status = {}
    if trading_memory:
        try:
            # Try to query memory
            test_results = trading_memory.query_similar("test", n_results=1)
            memory_status = {
                "status": "healthy",
                "collections": "trading_decisions",
                "can_query": True
            }
        except Exception as e:
            memory_status = {
                "status": "unhealthy",
                "error": str(e)
            }
            overall_status = "unhealthy"
    else:
        memory_status = {"status": "not_initialized"}
        overall_status = "degraded"
    
    uptime = (asyncio.get_event_loop().time() - start_time) * 1000
    
    return AgentStatusResponse(
        status=overall_status,
        agents=agents_status,
        memory_status=memory_status,
        uptime_ms=uptime
    )


@app.get("/health")
async def health_check():
    """Simple health check endpoint for Docker/Kubernetes"""
    return JSONResponse(
        content={
            "status": "healthy",
            "service": "fks_ai",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.get("/")
async def root():
    """API root with documentation links"""
    return JSONResponse(
        content={
            "service": "FKS AI - Multi-Agent Trading System",
            "version": "1.0.0",
            "docs": "/docs",
            "redoc": "/redoc",
            "endpoints": {
                "analyze": "POST /ai/analyze - Full multi-agent analysis",
                "debate": "POST /ai/debate - Bull/Bear debate only",
                "memory": "GET /ai/memory/query - Query past decisions",
                "status": "GET /ai/agents/status - Agent health check"
            }
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
