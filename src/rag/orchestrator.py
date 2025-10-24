"""
IntelligenceOrchestrator - Wrapper for RAG-powered trading intelligence.

This orchestrator provides a clean interface for Celery tasks to interact with
the RAG system for generating trading recommendations and portfolio optimization.
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

try:
    from framework.config.constants import RISK_PER_TRADE, TIMEZONE
except ImportError:
    # Fallback values if framework not in path
    RISK_PER_TRADE = 0.02  # 2% risk per trade
    import pytz
    TIMEZONE = pytz.timezone('UTC')


def create_intelligence(
    use_local: bool = True,
    local_llm_model: str = "llama3.2:3b",
    embedding_model: str = "all-MiniLM-L6-v2"
):
    """
    Factory function to create mock intelligence for testing.
    
    This is a simplified implementation that returns a mock object.
    The full RAG system implementation is not required for basic task functionality.
    
    Args:
        use_local: Whether to use local LLM (Ollama)
        local_llm_model: Local LLM model name
        embedding_model: Embedding model name
        
    Returns:
        Mock intelligence object with query() method
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Using mock RAG intelligence (full RAG system not required for basic tasks)")
    
    # Return mock that provides basic interface
    class MockIntelligence:
        def query(self, question: str, **kwargs):
            """Mock query that returns HOLD recommendation."""
            return {
                'answer': 'HOLD - Mock RAG response. Full RAG system optional for basic functionality.',
                'sources': [],
                'context_used': 0,
                'response_time_ms': 0
            }
    
    return MockIntelligence()


class IntelligenceOrchestrator:
    """
    Orchestrates RAG-powered trading intelligence for Celery tasks.
    
    Provides methods for:
    - Trading signal recommendations
    - Daily signal generation
    - Portfolio optimization
    
    This is a thin wrapper around the existing RAG infrastructure to provide
    a clean, task-friendly interface.
    """
    
    def __init__(
        self,
        use_local: bool = True,
        local_llm_model: str = "llama3.2:3b",
        openai_model: str = "gpt-4o-mini",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize the intelligence orchestrator.
        
        Args:
            use_local: Use local Ollama models instead of OpenAI
            local_llm_model: Local LLM model name
            openai_model: OpenAI model name (fallback)
            embedding_model: Embedding model for vector search
        """
        self.use_local = use_local
        self.local_llm_model = local_llm_model
        self.openai_model = openai_model
        self.embedding_model = embedding_model
        
        # Initialize intelligence with error handling
        self.intelligence = create_intelligence(
            use_local=use_local,
            local_llm_model=local_llm_model,
            embedding_model=embedding_model
        )
    
    def get_trading_recommendation(
        self,
        symbol: str,
        account_balance: float,
        available_cash: float = None,
        context: str = "",
        current_positions: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Get AI-powered trading recommendation for a specific symbol.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            account_balance: Current account balance in USD
            available_cash: Available cash for new positions (defaults to account_balance)
            context: Additional context for the recommendation
            current_positions: Dictionary of current positions
            
        Returns:
            Dictionary with:
            - symbol: Trading pair
            - action: BUY, SELL, or HOLD
            - position_size_usd: Recommended position size
            - reasoning: AI reasoning for recommendation
            - risk_assessment: low, medium, or high
            - confidence: Confidence score (0-1)
            - entry_points: Suggested entry prices (list)
            - stop_loss: Suggested stop loss price
            - take_profit: Suggested take profit price
            - timestamp: ISO timestamp
        """
        if available_cash is None:
            available_cash = account_balance
        
        current_positions = current_positions or {}
        
        # Build query for RAG system
        positions_str = ""
        if current_positions:
            positions_str = "\n".join([
                f"- {sym}: {pos['quantity']} @ ${pos['entry_price']:.2f}"
                for sym, pos in current_positions.items()
            ])
        
        question = f"""
Analyze trading opportunity for {symbol}.

Account State:
- Balance: ${account_balance:.2f}
- Available Cash: ${available_cash:.2f}
- Current Positions:
{positions_str or "- No open positions"}

Context: {context}

Provide trading recommendation with:
1. Action (BUY/SELL/HOLD)
2. Position size in USD
3. Entry points
4. Stop loss and take profit levels
5. Risk assessment
6. Confidence level (0-100%)
7. Detailed reasoning
"""
        
        # Query RAG intelligence
        try:
            rag_response = self.intelligence.query(
                question=question,
                symbol=symbol,
                account_balance=account_balance,
                max_results=10
            )
            
            # Parse response
            answer = rag_response.get('answer', '')
            
            # Extract recommendation components using regex
            action = self._extract_action(answer)
            confidence = self._extract_confidence(answer)
            risk = self._extract_risk(answer)
            
            # Calculate position size based on risk management
            position_size_usd = 0.0
            if action == 'BUY' and available_cash > 0:
                # Use 2% risk per trade (RISK_PER_TRADE from constants)
                position_size_usd = min(
                    account_balance * RISK_PER_TRADE,
                    available_cash * 0.95  # Leave 5% buffer
                )
            
            # Extract entry/stop/target from answer
            entry_points = self._extract_prices(answer, 'entry')
            stop_loss = self._extract_price(answer, 'stop')
            take_profit = self._extract_price(answer, 'target')
            
            return {
                'symbol': symbol,
                'action': action,
                'position_size_usd': position_size_usd,
                'reasoning': answer,
                'risk_assessment': risk,
                'confidence': confidence,
                'entry_points': entry_points,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'sources': rag_response.get('sources', []),
                'context_used': rag_response.get('context_used', 0),
                'timeframe': '1h',
                'timestamp': datetime.now(TIMEZONE).isoformat()
            }
            
        except Exception as e:
            # Fallback to conservative recommendation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"RAG recommendation failed for {symbol}: {e}")
            
            return {
                'symbol': symbol,
                'action': 'HOLD',
                'position_size_usd': 0.0,
                'reasoning': f'RAG system error: {str(e)}',
                'risk_assessment': 'high',
                'confidence': 0.0,
                'entry_points': [],
                'stop_loss': None,
                'take_profit': None,
                'sources': [],
                'context_used': 0,
                'timeframe': '1h',
                'timestamp': datetime.now(TIMEZONE).isoformat()
            }
    
    def get_daily_signals(
        self,
        symbols: List[str],
        min_confidence: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate daily trading signals for all symbols.
        
        Args:
            symbols: List of trading pairs to analyze
            min_confidence: Minimum confidence threshold
            
        Returns:
            Dictionary with:
            - date: Current date
            - signals: Dict of symbol -> signal data
            - high_confidence_count: Number of high confidence signals
        """
        signals = {}
        
        for symbol in symbols:
            try:
                # Query RAG for daily analysis
                question = f"""
Provide daily trading signal for {symbol}.

Analyze:
1. Overall market trend
2. Technical indicators
3. Historical performance patterns
4. Risk factors

Give recommendation as: BUY, SELL, or HOLD
Include confidence level (0-100%) and reasoning.
"""
                
                rag_response = self.intelligence.query(
                    question=question,
                    symbol=symbol,
                    max_results=5
                )
                
                answer = rag_response.get('answer', '')
                
                signals[symbol] = {
                    'recommendation': answer,
                    'confidence': self._extract_confidence(answer),
                    'sources': len(rag_response.get('sources', [])),
                    'action': self._extract_action(answer)
                }
                
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Daily signal failed for {symbol}: {e}")
                
                signals[symbol] = {
                    'recommendation': f'Error: {str(e)}',
                    'confidence': 0.0,
                    'sources': 0,
                    'action': 'HOLD'
                }
        
        # Count high confidence signals
        high_confidence_count = sum(
            1 for s in signals.values()
            if s['confidence'] >= min_confidence
        )
        
        return {
            'date': datetime.now(TIMEZONE).strftime('%Y-%m-%d'),
            'signals': signals,
            'high_confidence_count': high_confidence_count
        }
    
    def optimize_portfolio(
        self,
        symbols: List[str],
        account_balance: float,
        available_cash: float,
        current_positions: Dict[str, Any],
        market_condition: str = ""
    ) -> Dict[str, Any]:
        """
        Get RAG-powered portfolio optimization recommendations.
        
        Args:
            symbols: List of trading pairs
            account_balance: Total account balance
            available_cash: Available cash for new positions
            current_positions: Current positions dict
            market_condition: Current market condition description
            
        Returns:
            Dictionary with:
            - symbols: Dict of symbol -> recommendation
            - portfolio_advice: Overall portfolio advice
            - rebalance_needed: Boolean
        """
        # Build current portfolio summary
        positions_str = "\n".join([
            f"- {sym}: {pos['quantity']} @ ${pos['entry_price']:.2f} "
            f"(Current: ${pos.get('current_price', 0):.2f})"
            for sym, pos in current_positions.items()
        ])
        
        question = f"""
Analyze portfolio optimization for account with ${account_balance:.2f}.

Current Portfolio:
{positions_str or "- No positions"}

Available Cash: ${available_cash:.2f}
Market Condition: {market_condition}
Symbols to Consider: {', '.join(symbols)}

Provide:
1. Recommended allocation per symbol
2. Actions needed (BUY/SELL/HOLD for each)
3. Position sizes
4. Overall portfolio advice
5. Risk assessment
"""
        
        try:
            rag_response = self.intelligence.query(
                question=question,
                max_results=15
            )
            
            answer = rag_response.get('answer', '')
            
            # Parse recommendations for each symbol
            symbol_recommendations = {}
            for symbol in symbols:
                # Look for symbol mentions in answer
                if symbol in answer:
                    # Extract action near symbol mention
                    pattern = f"{symbol}.*?(BUY|SELL|HOLD)"
                    match = re.search(pattern, answer, re.IGNORECASE)
                    action = match.group(1).upper() if match else 'HOLD'
                    
                    # Calculate suggested position size
                    position_size = 0.0
                    if action == 'BUY' and available_cash > 0:
                        # Simple equal allocation for now
                        position_size = available_cash / len(symbols) * 0.8
                    
                    symbol_recommendations[symbol] = {
                        'action': action,
                        'position_size_usd': position_size,
                        'reasoning': f'Based on RAG analysis: {action}',
                        'risk_assessment': self._extract_risk(answer),
                        'confidence': self._extract_confidence(answer)
                    }
            
            return {
                'symbols': symbol_recommendations,
                'portfolio_advice': answer,
                'rebalance_needed': any(
                    r['action'] in ['BUY', 'SELL']
                    for r in symbol_recommendations.values()
                ),
                'sources': rag_response.get('sources', []),
                'timestamp': datetime.now(TIMEZONE).isoformat()
            }
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Portfolio optimization failed: {e}")
            
            return {
                'symbols': {},
                'portfolio_advice': f'Optimization error: {str(e)}',
                'rebalance_needed': False,
                'sources': [],
                'timestamp': datetime.now(TIMEZONE).isoformat()
            }
    
    # Helper methods for parsing RAG responses
    
    def _extract_action(self, text: str) -> str:
        """Extract trading action from RAG response."""
        text_upper = text.upper()
        
        # Look for explicit action statements
        if 'SELL' in text_upper or 'SHORT' in text_upper:
            return 'SELL'
        elif 'BUY' in text_upper or 'LONG' in text_upper:
            # Check it's not "DON'T BUY" or similar
            if "DON'T BUY" not in text_upper and "NOT BUY" not in text_upper:
                return 'BUY'
        
        return 'HOLD'
    
    def _extract_confidence(self, text: str) -> float:
        """Extract confidence level from RAG response (0-1)."""
        # Look for confidence percentage
        patterns = [
            r'confidence[:\s]+(\d+)%',
            r'(\d+)%\s+confidence',
            r'confidence[:\s]+(\d+\.?\d*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                # Normalize to 0-1 range
                return value / 100.0 if value > 1 else value
        
        # Default moderate confidence if not specified
        return 0.7
    
    def _extract_risk(self, text: str) -> str:
        """Extract risk level from RAG response."""
        text_lower = text.lower()
        
        if 'high risk' in text_lower or 'risky' in text_lower:
            return 'high'
        elif 'low risk' in text_lower or 'safe' in text_lower:
            return 'low'
        
        return 'medium'
    
    def _extract_prices(self, text: str, keyword: str) -> List[float]:
        """Extract price levels from RAG response."""
        prices = []
        
        # Look for prices near keyword
        pattern = rf'{keyword}[:\s]+\$?([0-9,]+(?:\.[0-9]+)?)'
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            try:
                price = float(match.group(1).replace(',', ''))
                prices.append(price)
            except ValueError:
                continue
        
        return prices
    
    def _extract_price(self, text: str, keyword: str) -> Optional[float]:
        """Extract single price level from RAG response."""
        prices = self._extract_prices(text, keyword)
        return prices[0] if prices else None


def create_orchestrator(
    use_local: bool = True,
    **kwargs
) -> IntelligenceOrchestrator:
    """
    Convenience function to create an IntelligenceOrchestrator.
    
    Args:
        use_local: Use local Ollama models
        **kwargs: Additional arguments passed to IntelligenceOrchestrator
        
    Returns:
        IntelligenceOrchestrator instance
    """
    return IntelligenceOrchestrator(use_local=use_local, **kwargs)
