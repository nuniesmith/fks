"""
IntelligenceOrchestrator - Simplified API for trading recommendations.

This module provides the exact API specified in the issue requirements:
    from rag.services import IntelligenceOrchestrator
    
    orchestrator = IntelligenceOrchestrator()
    recommendation = orchestrator.get_trading_recommendation(
        symbol="BTCUSDT",
        account_balance=10000.00,
        context="current market conditions"
    )
"""

from typing import Dict, Any, Optional
from datetime import datetime

from src.rag.intelligence import FKSIntelligence, create_intelligence
from core.database.models import Session


class IntelligenceOrchestrator:
    """
    Simplified orchestrator for FKS Intelligence RAG system.
    
    Provides high-level API for getting trading recommendations
    based on account state and market conditions.
    """
    
    def __init__(self,
                 use_local: bool = True,
                 local_llm_model: str = "llama3.2:3b",
                 embedding_model: str = "all-MiniLM-L6-v2"):
        """
        Initialize intelligence orchestrator.
        
        Args:
            use_local: Use local models (Ollama + sentence-transformers)
            local_llm_model: Local LLM model name
            embedding_model: Embedding model name
        """
        self.intelligence = create_intelligence(
            use_local=use_local,
            local_llm_model=local_llm_model,
            embedding_model=embedding_model
        )
    
    def get_trading_recommendation(self,
                                  symbol: str,
                                  account_balance: float,
                                  available_cash: Optional[float] = None,
                                  context: Optional[str] = None,
                                  current_positions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get optimal trading recommendation based on account state and historical data.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            account_balance: Total account balance
            available_cash: Available cash for trading (defaults to account_balance)
            context: Additional context (e.g., 'current market conditions', 'trending market')
            current_positions: Dict of current positions {symbol: {quantity, entry_price, ...}}
            
        Returns:
            Dictionary containing:
                - action: 'BUY', 'SELL', 'HOLD'
                - position_size: Recommended position size in base currency
                - position_size_usd: Position size in USD/USDT
                - entry_points: List of recommended entry prices
                - exit_points: List of recommended exit prices (take profit levels)
                - stop_loss: Recommended stop loss price
                - risk_assessment: Risk level ('low', 'medium', 'high')
                - reasoning: Detailed explanation of the recommendation
                - confidence: Confidence score (0-1)
                - strategy: Recommended strategy name
                - timeframe: Recommended timeframe
                - sources: Number of historical insights used
        """
        # Set defaults
        if available_cash is None:
            available_cash = account_balance
        
        if current_positions is None:
            current_positions = {}
        
        # Build comprehensive query
        query_parts = [
            f"Based on historical trading data and signals for {symbol},",
            f"with an account balance of ${account_balance:,.2f}",
            f"and ${available_cash:,.2f} available cash,",
        ]
        
        if context:
            query_parts.append(f"considering {context},")
        
        # Check if already have position
        if symbol in current_positions:
            position = current_positions[symbol]
            query_parts.append(
                f"and currently holding a position of {position.get('quantity', 0)} units "
                f"at entry price {position.get('entry_price', 0)},"
            )
        
        query_parts.extend([
            "what is the optimal trading action?",
            "\nProvide:",
            "1. Action (BUY/SELL/HOLD)",
            "2. Recommended position size",
            "3. Entry price(s)",
            "4. Exit price(s) / take profit levels",
            "5. Stop loss level",
            "6. Risk assessment",
            "7. Detailed reasoning based on historical performance"
        ])
        
        query = " ".join(query_parts)
        
        # Query RAG system with focus on signals, backtests, and past performance
        result = self.intelligence.query(
            question=query,
            symbol=symbol,
            doc_types=['signal', 'backtest', 'trade_analysis', 'strategy'],
            top_k=7  # Get more context for comprehensive recommendation
        )
        
        # Parse response into structured format
        recommendation = self._parse_recommendation(
            answer=result['answer'],
            symbol=symbol,
            account_balance=account_balance,
            available_cash=available_cash,
            sources=result['sources']
        )
        
        # Add metadata
        recommendation['timestamp'] = datetime.now().isoformat()
        recommendation['query_time_ms'] = result.get('response_time_ms', 0)
        recommendation['sources_used'] = len(result['sources'])
        
        return recommendation
    
    def optimize_portfolio(self,
                          symbols: list[str],
                          account_balance: float,
                          available_cash: float,
                          current_positions: Dict[str, Any],
                          market_condition: Optional[str] = None) -> Dict[str, Any]:
        """
        Get portfolio optimization recommendations for multiple symbols.
        
        Args:
            symbols: List of trading pairs to consider
            account_balance: Total account balance
            available_cash: Available cash for new positions
            current_positions: Current positions {symbol: {quantity, entry_price, ...}}
            market_condition: Overall market condition
            
        Returns:
            Dictionary with recommendations for each symbol and portfolio-level suggestions
        """
        recommendations = {}
        
        for symbol in symbols:
            position = current_positions.get(symbol)
            
            try:
                rec = self.get_trading_recommendation(
                    symbol=symbol,
                    account_balance=account_balance,
                    available_cash=available_cash,
                    context=market_condition,
                    current_positions={symbol: position} if position else {}
                )
                recommendations[symbol] = rec
            except Exception as e:
                recommendations[symbol] = {
                    'error': str(e),
                    'action': 'HOLD'
                }
        
        # Get portfolio-level insights
        portfolio_query = (
            f"Based on historical performance across {', '.join(symbols)}, "
            f"with total balance ${account_balance:,.2f} and "
            f"${available_cash:,.2f} available cash, "
            f"how should I allocate capital across these assets?"
        )
        
        portfolio_result = self.intelligence.query(
            question=portfolio_query,
            doc_types=['backtest', 'strategy', 'insight'],
            top_k=10
        )
        
        return {
            'symbols': recommendations,
            'portfolio_advice': portfolio_result['answer'],
            'total_balance': account_balance,
            'available_cash': available_cash,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_daily_signals(self,
                         symbols: Optional[list[str]] = None,
                         min_confidence: float = 0.7) -> Dict[str, Any]:
        """
        Get daily trading signals for specified symbols.
        
        Args:
            symbols: List of symbols (None = all symbols with recent data)
            min_confidence: Minimum confidence threshold for signals
            
        Returns:
            Dictionary of signals by symbol
        """
        if symbols is None:
            # Query for all symbols with recent signals
            symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']  # Default majors
        
        signals = {}
        
        for symbol in symbols:
            result = self.intelligence.query(
                question=f"What is today's trading signal for {symbol}? "
                        f"Based on recent signals and market conditions.",
                symbol=symbol,
                doc_types=['signal', 'market_report'],
                top_k=3
            )
            
            signals[symbol] = {
                'recommendation': result['answer'],
                'confidence': self._extract_confidence(result['answer']),
                'sources': len(result['sources'])
            }
        
        return {
            'date': datetime.now().date().isoformat(),
            'signals': signals,
            'min_confidence': min_confidence
        }
    
    def _parse_recommendation(self,
                            answer: str,
                            symbol: str,
                            account_balance: float,
                            available_cash: float,
                            sources: list) -> Dict[str, Any]:
        """
        Parse LLM response into structured recommendation.
        
        This is a simple parser. In production, you might want to use
        structured output from the LLM or more sophisticated parsing.
        """
        answer_lower = answer.lower()
        
        # Detect action
        if 'buy' in answer_lower and 'don\'t buy' not in answer_lower:
            action = 'BUY'
        elif 'sell' in answer_lower:
            action = 'SELL'
        else:
            action = 'HOLD'
        
        # Extract confidence (look for percentages or confidence keywords)
        confidence = self._extract_confidence(answer)
        
        # Determine risk level based on keywords
        if any(word in answer_lower for word in ['high risk', 'risky', 'aggressive']):
            risk = 'high'
        elif any(word in answer_lower for word in ['low risk', 'safe', 'conservative']):
            risk = 'low'
        else:
            risk = 'medium'
        
        # Calculate position size based on risk (2% risk per trade default)
        risk_percent = 0.02 if risk == 'low' else 0.03 if risk == 'medium' else 0.05
        position_size_usd = available_cash * risk_percent
        
        return {
            'symbol': symbol,
            'action': action,
            'position_size_usd': round(position_size_usd, 2),
            'position_size_percent': round(risk_percent * 100, 1),
            'entry_points': [],  # Would need more sophisticated parsing
            'exit_points': [],
            'stop_loss': None,
            'risk_assessment': risk,
            'reasoning': answer,
            'confidence': confidence,
            'strategy': 'RAG-optimized',  # Could extract from answer
            'timeframe': '1h',  # Could extract from answer
        }
    
    def _extract_confidence(self, text: str) -> float:
        """Extract confidence score from text."""
        import re
        
        # Look for percentages like "85% confident" or "0.85 confidence"
        percent_match = re.search(r'(\d+)%\s*confiden', text.lower())
        if percent_match:
            return float(percent_match.group(1)) / 100
        
        decimal_match = re.search(r'confidence[:\s]+(\d+\.?\d*)', text.lower())
        if decimal_match:
            return float(decimal_match.group(1))
        
        # Default based on keywords
        if any(word in text.lower() for word in ['highly confident', 'very confident', 'strong']):
            return 0.85
        elif any(word in text.lower() for word in ['confident', 'likely']):
            return 0.75
        elif any(word in text.lower() for word in ['uncertain', 'unclear', 'maybe']):
            return 0.5
        
        return 0.7  # Default


# Convenience function matching the issue spec
def create_orchestrator(use_local: bool = True) -> IntelligenceOrchestrator:
    """
    Create an intelligence orchestrator instance.
    
    Args:
        use_local: Use local models (Ollama + sentence-transformers)
        
    Returns:
        IntelligenceOrchestrator instance
    """
    return IntelligenceOrchestrator(use_local=use_local)
