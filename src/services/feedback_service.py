"""
Feedback Service - Learning and retention loop for FKS Intelligence.

This service implements a continuous learning system that:
1. Captures trade outcomes (wins/losses)
2. Stores backtest results with detailed metrics
3. Learns from market patterns
4. Provides insights for strategy optimization
5. Integrates with Optuna for parameter tuning

Features:
- Automated feedback ingestion
- Trade outcome analysis
- Pattern recognition
- Performance tracking
- Integration with RAG knowledge base
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

from database import Session, Document, TradingInsight
from services.rag_service import RAGService, get_rag_service


class OutcomeType(Enum):
    """Trade outcome types"""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class MarketCondition(Enum):
    """Market condition types"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"


class FeedbackService:
    """
    Service for learning from trade outcomes and backtests.
    Implements a retention loop that improves strategy selection over time.
    """
    
    def __init__(self, rag_service: Optional[RAGService] = None):
        """
        Initialize feedback service.
        
        Args:
            rag_service: RAGService instance (creates new if None)
        """
        self.rag = rag_service or get_rag_service()
    
    def log_trade_outcome(self,
                         symbol: str,
                         strategy: str,
                         outcome: str,
                         entry_price: float,
                         exit_price: float,
                         position_size: float,
                         pnl: float,
                         pnl_pct: float,
                         market_condition: str,
                         timeframe: str,
                         indicators: Optional[Dict[str, float]] = None,
                         notes: Optional[str] = None) -> int:
        """
        Log a completed trade for learning.
        
        Args:
            symbol: Trading pair
            strategy: Strategy name
            outcome: "win", "loss", or "breakeven"
            entry_price: Entry price
            exit_price: Exit price
            position_size: Position size
            pnl: Profit/loss amount
            pnl_pct: P&L percentage
            market_condition: Market condition during trade
            timeframe: Trading timeframe
            indicators: Technical indicators at entry
            notes: Additional observations
            
        Returns:
            Document ID
        """
        # Format indicators
        indicators_text = ""
        if indicators:
            indicators_text = "\n".join([f"- {k}: {v}" for k, v in indicators.items()])
        
        # Build detailed content
        content = f"""Trade Outcome Report
{'='*50}

Symbol: {symbol}
Strategy: {strategy}
Outcome: {outcome.upper()}
Timeframe: {timeframe}

Entry & Exit:
- Entry Price: ${entry_price:.4f}
- Exit Price: ${exit_price:.4f}
- Position Size: {position_size}

Performance:
- P&L: ${pnl:.2f}
- P&L %: {pnl_pct:+.2f}%
- Outcome: {outcome.upper()}

Market Context:
- Condition: {market_condition}
- Date: {datetime.now().isoformat()}

Technical Indicators at Entry:
{indicators_text or 'No indicators recorded'}

Trader Notes:
{notes or 'No additional notes'}

Analysis:
This {outcome} trade on {symbol} using {strategy} in {market_condition} market conditions 
resulted in {pnl_pct:+.2f}% P&L. {'Strategy performed well' if pnl > 0 else 'Strategy underperformed'} 
for this setup. Consider {'repeating' if pnl > 0 else 'avoiding'} similar entries in {market_condition} conditions.
"""
        
        # Ingest into RAG
        doc_id = self.rag.intelligence.ingest_document(
            content=content,
            doc_type='trade_outcome',
            title=f"{outcome.upper()}: {symbol} - {strategy} ({pnl_pct:+.2f}%)",
            symbol=symbol,
            timeframe=timeframe,
            metadata={
                'outcome': outcome,
                'strategy': strategy,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'position_size': position_size,
                'market_condition': market_condition,
                'indicators': indicators or {},
                'feedback_type': 'trade_outcome',
                'timestamp': datetime.now().isoformat()
            }
        )
        
        # Also store as TradingInsight for quick retrieval
        self._store_trading_insight(
            symbol=symbol,
            category='trade_outcome',
            content=f"{strategy} {outcome} in {market_condition}: {pnl_pct:+.2f}%",
            impact=abs(pnl_pct) / 10,  # Normalize impact score
            metadata={
                'strategy': strategy,
                'outcome': outcome,
                'pnl_pct': pnl_pct
            }
        )
        
        print(f"✓ Trade outcome logged: {symbol} {outcome} ({pnl_pct:+.2f}%) - Doc ID: {doc_id}")
        return doc_id
    
    def log_backtest_result(self,
                           strategy: str,
                           symbol: str,
                           timeframe: str,
                           start_date: datetime,
                           end_date: datetime,
                           metrics: Dict[str, Any],
                           parameters: Dict[str, Any],
                           insights: str,
                           trades_data: Optional[List[Dict]] = None) -> int:
        """
        Log backtest results for strategy evaluation.
        
        Args:
            strategy: Strategy name
            symbol: Trading pair
            timeframe: Timeframe tested
            start_date: Backtest start date
            end_date: Backtest end date
            metrics: Performance metrics
            parameters: Strategy parameters used
            insights: Key insights and learnings
            trades_data: Optional list of all trades
            
        Returns:
            Document ID
        """
        # Format metrics
        metrics_text = "\n".join([f"- {k}: {v}" for k, v in metrics.items()])
        
        # Format parameters
        params_text = "\n".join([f"- {k}: {v}" for k, v in parameters.items()])
        
        # Calculate period
        period_days = (end_date - start_date).days
        
        # Performance assessment
        win_rate = metrics.get('win_rate', 0)
        profit_factor = metrics.get('profit_factor', 0)
        sharpe_ratio = metrics.get('sharpe_ratio', 0)
        
        if win_rate >= 0.6 and profit_factor >= 1.5:
            performance = "EXCELLENT"
        elif win_rate >= 0.5 and profit_factor >= 1.2:
            performance = "GOOD"
        elif win_rate >= 0.4:
            performance = "FAIR"
        else:
            performance = "POOR"
        
        # Build content
        content = f"""Backtest Results Report
{'='*50}

Strategy: {strategy}
Symbol: {symbol}
Timeframe: {timeframe}

Test Period:
- Start: {start_date.strftime('%Y-%m-%d')}
- End: {end_date.strftime('%Y-%m-%d')}
- Duration: {period_days} days

Strategy Parameters:
{params_text}

Performance Metrics:
{metrics_text}

Overall Assessment: {performance}

Key Insights:
{insights}

Conclusion:
This backtest of {strategy} on {symbol} ({timeframe}) over {period_days} days shows {performance} performance.
Win rate: {win_rate:.1%}, Profit Factor: {profit_factor:.2f}, Sharpe Ratio: {sharpe_ratio:.2f}.
{'Recommended for live trading with proper risk management.' if performance in ['EXCELLENT', 'GOOD'] else 'Requires further optimization before live trading.'}
"""
        
        # Ingest
        doc_id = self.rag.intelligence.ingest_document(
            content=content,
            doc_type='backtest_result',
            title=f"Backtest: {strategy} - {symbol} ({performance})",
            symbol=symbol,
            timeframe=timeframe,
            metadata={
                'strategy': strategy,
                'metrics': metrics,
                'parameters': parameters,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'performance': performance,
                'feedback_type': 'backtest',
                'timestamp': datetime.now().isoformat()
            }
        )
        
        # Store insight
        self._store_trading_insight(
            symbol=symbol,
            category='backtest',
            content=f"{strategy} backtest: {performance} - WR:{win_rate:.1%} PF:{profit_factor:.2f}",
            impact=(win_rate * profit_factor) / 2,  # Combined impact
            metadata={
                'strategy': strategy,
                'performance': performance,
                'metrics': metrics
            }
        )
        
        print(f"✓ Backtest logged: {strategy} on {symbol} - {performance} - Doc ID: {doc_id}")
        return doc_id
    
    def analyze_strategy_performance(self,
                                    strategy: str,
                                    lookback_days: int = 90,
                                    session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Analyze historical performance of a strategy using RAG.
        
        Args:
            strategy: Strategy name
            lookback_days: Days to analyze
            session: SQLAlchemy session
            
        Returns:
            Performance analysis dict
        """
        query = f"Analyze the performance of {strategy} strategy over the last {lookback_days} days. What are the win rate, profit factor, and key learnings?"
        
        filters = {
            'doc_type': ['trade_outcome', 'backtest_result'],
            'date_range': {
                'start': datetime.now() - timedelta(days=lookback_days),
                'end': datetime.now()
            }
        }
        
        # Search for strategy-specific content
        result = self.rag.query_with_rag(
            query=query,
            top_k=15,
            filters=filters,
            session=session
        )
        
        return {
            'strategy': strategy,
            'lookback_days': lookback_days,
            'analysis': result['answer'],
            'sources_count': result['num_sources'],
            'response_time': result['response_time']
        }
    
    def get_best_strategy_for_condition(self,
                                       symbol: str,
                                       market_condition: str,
                                       lookback_days: int = 60) -> Dict[str, Any]:
        """
        Determine best strategy for given market condition using historical data.
        
        Args:
            symbol: Trading pair
            market_condition: Market condition
            lookback_days: Days of history to consider
            
        Returns:
            Strategy recommendation with reasoning
        """
        query = f"Based on recent performance data, what strategy performs best for {symbol} in {market_condition} market conditions?"
        
        filters = {
            'symbol': symbol,
            'doc_type': ['trade_outcome', 'backtest_result'],
            'date_range': {
                'start': datetime.now() - timedelta(days=lookback_days),
                'end': datetime.now()
            }
        }
        
        result = self.rag.query_with_rag(
            query=query,
            top_k=10,
            filters=filters
        )
        
        return {
            'symbol': symbol,
            'market_condition': market_condition,
            'recommendation': result['answer'],
            'confidence': result['num_sources'] / 10,  # Normalize to 0-1
            'sources_count': result['num_sources']
        }
    
    def learn_from_losses(self,
                         symbol: Optional[str] = None,
                         lookback_days: int = 30) -> Dict[str, Any]:
        """
        Analyze losing trades to identify patterns and avoid future losses.
        
        Args:
            symbol: Optional symbol filter
            lookback_days: Days to analyze
            
        Returns:
            Loss analysis with patterns and recommendations
        """
        query_base = f"Analyze the losing trades"
        if symbol:
            query_base += f" for {symbol}"
        query = query_base + f" in the last {lookback_days} days. What patterns led to losses and how can they be avoided?"
        
        filters = {
            'doc_type': 'trade_outcome',
            'date_range': {
                'start': datetime.now() - timedelta(days=lookback_days),
                'end': datetime.now()
            }
        }
        
        if symbol:
            filters['symbol'] = symbol
        
        result = self.rag.query_with_rag(
            query=query,
            top_k=20,  # More context for pattern recognition
            filters=filters
        )
        
        return {
            'symbol': symbol or 'ALL',
            'lookback_days': lookback_days,
            'loss_analysis': result['answer'],
            'sources_analyzed': result['num_sources']
        }
    
    def get_optimization_suggestions(self,
                                    strategy: str,
                                    symbol: str,
                                    current_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get parameter optimization suggestions using RAG insights.
        
        This can be used with Optuna to guide the search space.
        
        Args:
            strategy: Strategy name
            symbol: Trading pair
            current_params: Current strategy parameters
            
        Returns:
            Optimization suggestions
        """
        params_str = ", ".join([f"{k}={v}" for k, v in current_params.items()])
        
        query = f"The {strategy} strategy for {symbol} currently uses parameters: {params_str}. Based on historical performance, what parameter adjustments would likely improve results?"
        
        filters = {
            'symbol': symbol,
            'doc_type': ['backtest_result', 'trade_outcome']
        }
        
        result = self.rag.query_with_rag(
            query=query,
            top_k=12,
            filters=filters
        )
        
        return {
            'strategy': strategy,
            'symbol': symbol,
            'current_params': current_params,
            'suggestions': result['answer'],
            'confidence': result['num_sources'] / 12
        }
    
    def _store_trading_insight(self,
                              symbol: str,
                              category: str,
                              content: str,
                              impact: float,
                              metadata: Optional[Dict] = None,
                              session: Optional[Session] = None):
        """Store curated trading insight for quick retrieval"""
        should_close = False
        if session is None:
            session = Session()
            should_close = True
        
        try:
            insight = TradingInsight(
                symbol=symbol,
                category=category,
                content=content,
                impact=min(impact, 10.0),  # Cap at 10
                metadata=metadata or {},
                created_at=datetime.now()
            )
            session.add(insight)
            session.commit()
        except Exception as e:
            print(f"⚠ Failed to store insight: {e}")
            session.rollback()
        finally:
            if should_close:
                session.close()
    
    def get_recent_insights(self,
                           symbol: Optional[str] = None,
                           category: Optional[str] = None,
                           limit: int = 10,
                           session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Get recent high-impact trading insights.
        
        Args:
            symbol: Optional symbol filter
            category: Optional category filter
            limit: Maximum results
            session: SQLAlchemy session
            
        Returns:
            List of insights
        """
        should_close = False
        if session is None:
            session = Session()
            should_close = True
        
        try:
            query = session.query(TradingInsight)
            
            if symbol:
                query = query.filter(TradingInsight.symbol == symbol)
            
            if category:
                query = query.filter(TradingInsight.category == category)
            
            insights = query.order_by(
                TradingInsight.impact.desc(),
                TradingInsight.created_at.desc()
            ).limit(limit).all()
            
            return [
                {
                    'id': insight.id,
                    'symbol': insight.symbol,
                    'category': insight.category,
                    'content': insight.content,
                    'impact': insight.impact,
                    'metadata': insight.metadata,
                    'created_at': insight.created_at.isoformat()
                }
                for insight in insights
            ]
            
        finally:
            if should_close:
                session.close()


# Factory function
def create_feedback_service(rag_service: Optional[RAGService] = None) -> FeedbackService:
    """
    Create feedback service instance.
    
    Args:
        rag_service: RAGService instance
        
    Returns:
        FeedbackService instance
    """
    return FeedbackService(rag_service=rag_service)


# Singleton
_feedback_service_instance = None

def get_feedback_service() -> FeedbackService:
    """Get singleton feedback service instance"""
    global _feedback_service_instance
    if _feedback_service_instance is None:
        _feedback_service_instance = create_feedback_service()
    return _feedback_service_instance
