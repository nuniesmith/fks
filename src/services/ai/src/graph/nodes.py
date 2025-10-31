"""
Graph Nodes for Multi-Agent Trading System

Implements the execution logic for each node in the StateGraph.
"""

from typing import Dict, Any
from ..agents.state import AgentState
from ..agents.analysts import (
    analyze_technical,
    analyze_sentiment, 
    analyze_macro,
    analyze_risk
)
from ..agents.debaters import (
    generate_bull_case,
    generate_bear_case,
    synthesize_debate
)
from ..memory import TradingMemory
import asyncio


async def run_analysts(state: AgentState) -> AgentState:
    """
    Run all 4 analyst agents in parallel.
    
    Args:
        state: Current agent state with market_data
        
    Returns:
        Updated state with analyst insights in messages
    """
    # Extract data for each analyst
    market_data = state['market_data']
    symbol = state['symbol']
    
    # Prepare analyst-specific data
    technical_data = {
        'symbol': symbol,
        'close': market_data.get('close'),
        'rsi': market_data.get('rsi'),
        'macd': market_data.get('macd'),
        'bb_upper': market_data.get('bb_upper'),
        'bb_lower': market_data.get('bb_lower'),
        'volume': market_data.get('volume'),
        'atr': market_data.get('atr')
    }
    
    sentiment_data = {
        'symbol': symbol,
        'fear_greed_index': market_data.get('fear_greed_index', 50),
        'social_volume': market_data.get('social_volume', 'medium'),
        'news_sentiment': market_data.get('news_sentiment', 'neutral'),
        'whale_activity': market_data.get('whale_activity', 'unknown')
    }
    
    macro_data = {
        'symbol': symbol,
        'cpi_yoy': market_data.get('cpi_yoy'),
        'fed_funds_rate': market_data.get('fed_funds_rate'),
        'dxy': market_data.get('dxy'),
        'spx_correlation': market_data.get('spx_correlation'),
        'gold_correlation': market_data.get('gold_correlation')
    }
    
    risk_data = {
        'symbol': symbol,
        'entry_price': market_data.get('close'),
        'direction': 'LONG',  # Will be determined by debate
        'confidence': 0.5,  # Initial placeholder
        'account_size': market_data.get('account_size', 100000),
        'current_positions': market_data.get('current_positions', 0),
        'volatility': market_data.get('volatility', 0.02),
        'current_drawdown': market_data.get('current_drawdown', 0)
    }
    
    # Run all analysts in parallel
    results = await asyncio.gather(
        analyze_technical(technical_data),
        analyze_sentiment(sentiment_data),
        analyze_macro(macro_data),
        analyze_risk(risk_data)
    )
    
    # Add results to messages
    for result in results:
        state['messages'].append({
            'role': result['agent'],
            'content': result['analysis']
        })
    
    return state


async def debate_node(state: AgentState) -> AgentState:
    """
    Run Bull vs Bear debate based on analyst insights.
    
    Args:
        state: State with analyst messages
        
    Returns:
        Updated state with bull/bear debates
    """
    # Extract analyst insights
    analyst_insights = [
        msg['content'] for msg in state['messages']
        if msg['role'] in ['technical_analyst', 'sentiment_analyst', 'macro_analyst', 'risk_analyst']
    ]
    
    # Run bull and bear in parallel
    bull_result, bear_result = await asyncio.gather(
        generate_bull_case(analyst_insights),
        generate_bear_case(analyst_insights)
    )
    
    # Store debates
    state['debates'] = [
        bull_result['argument'],
        bear_result['argument']
    ]
    
    # Add to messages
    state['messages'].append({
        'role': 'bull',
        'content': bull_result['argument']
    })
    state['messages'].append({
        'role': 'bear',
        'content': bear_result['argument']
    })
    
    return state


async def manager_decision_node(state: AgentState) -> AgentState:
    """
    Manager synthesizes debate into final decision.
    
    Args:
        state: State with bull/bear debates
        
    Returns:
        Updated state with final_decision
    """
    if len(state['debates']) < 2:
        raise ValueError("Need both bull and bear arguments")
    
    bull_argument = state['debates'][0]
    bear_argument = state['debates'][1]
    
    # Synthesize debate
    result = await synthesize_debate(
        bull_argument=bull_argument,
        bear_argument=bear_argument,
        market_regime=state.get('regime', 'unknown'),
        additional_context=state.get('market_data', {})
    )
    
    # Store decision
    state['final_decision'] = {
        'decision': result['decision'],
        'inputs': result['inputs']
    }
    
    # Add to messages
    state['messages'].append({
        'role': 'manager',
        'content': result['decision']
    })
    
    return state


async def reflection_node(state: AgentState) -> AgentState:
    """
    Store decision in ChromaDB and retrieve similar past insights.
    
    Args:
        state: State with final_decision
        
    Returns:
        Updated state with memory context
    """
    memory = TradingMemory()
    
    # Create insight text
    decision = state['final_decision']
    insight_text = f"""
    Symbol: {state['symbol']}
    Decision: {decision}
    Debates: {state['debates']}
    Timestamp: {state['timestamp']}
    """
    
    # Store in memory
    memory.add_insight(
        text=insight_text,
        metadata={
            'symbol': state['symbol'],
            'timestamp': state['timestamp'],
            'regime': state.get('regime', 'unknown'),
            'confidence': state.get('confidence', 0.5)
        }
    )
    
    # Query similar decisions
    similar = memory.query_similar(
        query=f"Trading {state['symbol']} in {state.get('regime', 'unknown')} regime",
        n_results=3
    )
    
    # Add to state
    state['memory'] = [s['text'] for s in similar]
    
    return state


def should_execute_trade(state: AgentState) -> str:
    """
    Conditional edge: Decide if we should execute trade.
    
    Args:
        state: State with final_decision
        
    Returns:
        'execute' or 'skip'
    """
    decision = state.get('final_decision', {})
    decision_text = decision.get('decision', '').upper()
    
    # Check if decision is BUY or SELL (not HOLD)
    if 'BUY' in decision_text or 'SELL' in decision_text:
        # Check confidence threshold
        confidence = state.get('confidence', 0.0)
        if confidence > 0.6:  # 60% confidence threshold
            return 'execute'
    
    return 'skip'
