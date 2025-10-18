"""
Data ingestion pipeline for RAG system.
Automatically ingests trading signals, backtests, and analyses into knowledge base.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json

from core.database import Session, Trade, Position, Document
from web.rag.intelligence import FKSIntelligence


class DataIngestionPipeline:
    """Automated pipeline for ingesting trading data into RAG knowledge base"""
    
    def __init__(self, intelligence: Optional[FKSIntelligence] = None):
        """
        Initialize ingestion pipeline.
        
        Args:
            intelligence: FKSIntelligence instance
        """
        self.intelligence = intelligence or FKSIntelligence()
    
    def ingest_completed_trade(self,
                              trade_id: int,
                              session: Optional[Session] = None) -> Optional[int]:
        """
        Ingest a completed trade into knowledge base.
        
        Args:
            trade_id: Trade ID
            session: SQLAlchemy session
            
        Returns:
            Document ID if successful
        """
        should_close = False
        if session is None:
            session = Session()
            should_close = True
        
        try:
            # Get trade
            trade = session.query(Trade).filter(Trade.id == trade_id).first()
            
            if not trade:
                print(f"Trade {trade_id} not found")
                return None
            
            # Format trade analysis
            content = self._format_trade_for_ingestion(trade)
            
            # Create metadata
            metadata = {
                'trade_id': trade.id,
                'pnl': float(trade.realized_pnl) if trade.realized_pnl else 0,
                'pnl_percent': self._calculate_pnl_percent(trade),
                'duration_hours': self._calculate_trade_duration(trade),
                'strategy': trade.strategy_name
            }
            
            # Ingest
            doc_id = self.intelligence.ingest_document(
                content=content,
                doc_type='trade_analysis',
                title=f"Trade Analysis: {trade.symbol} - {trade.position_side}",
                symbol=trade.symbol,
                metadata=metadata,
                session=session
            )
            
            print(f"Ingested trade {trade_id} as document {doc_id}")
            return doc_id
            
        except Exception as e:
            print(f"Error ingesting trade: {e}")
            return None
        finally:
            if should_close:
                session.close()
    
    def ingest_backtest_result(self,
                               backtest_data: Dict[str, Any],
                               session: Optional[Session] = None) -> Optional[int]:
        """
        Ingest backtest results into knowledge base.
        
        Args:
            backtest_data: Backtest results dictionary
            session: SQLAlchemy session
            
        Returns:
            Document ID if successful
        """
        try:
            # Format backtest
            content = self._format_backtest_for_ingestion(backtest_data)
            
            # Extract metadata
            metadata = {
                'total_return': backtest_data.get('total_return', 0),
                'win_rate': backtest_data.get('win_rate', 0),
                'sharpe_ratio': backtest_data.get('sharpe_ratio', 0),
                'max_drawdown': backtest_data.get('max_drawdown', 0),
                'total_trades': backtest_data.get('total_trades', 0),
                'strategy_name': backtest_data.get('strategy_name', 'Unknown'),
                'parameters': backtest_data.get('parameters', {})
            }
            
            # Ingest
            doc_id = self.intelligence.ingest_document(
                content=content,
                doc_type='backtest',
                title=f"Backtest: {backtest_data.get('strategy_name')} - {backtest_data.get('symbol')}",
                symbol=backtest_data.get('symbol'),
                timeframe=backtest_data.get('timeframe'),
                metadata=metadata,
                session=session
            )
            
            print(f"Ingested backtest as document {doc_id}")
            return doc_id
            
        except Exception as e:
            print(f"Error ingesting backtest: {e}")
            return None
    
    def ingest_signal(self,
                     signal_data: Dict[str, Any],
                     session: Optional[Session] = None) -> Optional[int]:
        """
        Ingest trading signal into knowledge base.
        
        Args:
            signal_data: Signal dictionary
            session: SQLAlchemy session
            
        Returns:
            Document ID if successful
        """
        try:
            # Format signal
            content = self._format_signal_for_ingestion(signal_data)
            
            # Ingest
            doc_id = self.intelligence.ingest_document(
                content=content,
                doc_type='signal',
                title=f"Signal: {signal_data.get('symbol')} - {signal_data.get('action')}",
                symbol=signal_data.get('symbol'),
                timeframe=signal_data.get('timeframe'),
                metadata=signal_data,
                session=session
            )
            
            print(f"Ingested signal as document {doc_id}")
            return doc_id
            
        except Exception as e:
            print(f"Error ingesting signal: {e}")
            return None
    
    def ingest_market_analysis(self,
                               analysis_text: str,
                               symbol: str,
                               timeframe: str,
                               metadata: Optional[Dict[str, Any]] = None,
                               session: Optional[Session] = None) -> Optional[int]:
        """
        Ingest market analysis into knowledge base.
        
        Args:
            analysis_text: Analysis content
            symbol: Trading pair
            timeframe: Timeframe
            metadata: Additional metadata
            session: SQLAlchemy session
            
        Returns:
            Document ID if successful
        """
        try:
            doc_id = self.intelligence.ingest_document(
                content=analysis_text,
                doc_type='market_report',
                title=f"Market Analysis: {symbol} {timeframe}",
                symbol=symbol,
                timeframe=timeframe,
                metadata=metadata or {},
                session=session
            )
            
            print(f"Ingested market analysis as document {doc_id}")
            return doc_id
            
        except Exception as e:
            print(f"Error ingesting market analysis: {e}")
            return None
    
    def batch_ingest_recent_trades(self,
                                   days: int = 30,
                                   session: Optional[Session] = None) -> int:
        """
        Batch ingest recent completed trades.
        
        Args:
            days: Number of days to look back
            session: SQLAlchemy session
            
        Returns:
            Number of trades ingested
        """
        should_close = False
        if session is None:
            session = Session()
            should_close = True
        
        try:
            # Get recent trades
            cutoff = datetime.now() - timedelta(days=days)
            trades = session.query(Trade).filter(
                Trade.time >= cutoff,
                Trade.realized_pnl.isnot(None)  # Only completed trades
            ).all()
            
            # Check what's already ingested
            existing_docs = session.query(Document).filter(
                Document.doc_type == 'trade_analysis',
                Document.created_at >= cutoff
            ).all()
            
            existing_trade_ids = set()
            for doc in existing_docs:
                if doc.metadata and 'trade_id' in doc.metadata:
                    existing_trade_ids.add(doc.metadata['trade_id'])
            
            # Ingest new trades
            count = 0
            for trade in trades:
                if trade.id not in existing_trade_ids:
                    if self.ingest_completed_trade(trade.id, session):
                        count += 1
            
            print(f"Batch ingested {count} trades")
            return count
            
        except Exception as e:
            print(f"Error in batch ingestion: {e}")
            return 0
        finally:
            if should_close:
                session.close()
    
    def _format_trade_for_ingestion(self, trade: Trade) -> str:
        """Format trade as natural language"""
        lines = [
            f"Trade Analysis: {trade.symbol}",
            f"Position: {trade.position_side or 'N/A'}",
            f"Type: {trade.trade_type}",
            f"Quantity: {trade.quantity}",
            f"Price: {trade.price}",
            f"Time: {trade.time.isoformat() if trade.time else 'N/A'}",
        ]
        
        if trade.realized_pnl:
            pnl_percent = self._calculate_pnl_percent(trade)
            lines.append(f"Realized P&L: {trade.realized_pnl} ({pnl_percent:.2f}%)")
        
        if trade.strategy_name:
            lines.append(f"Strategy: {trade.strategy_name}")
        
        if trade.notes:
            lines.append(f"Notes: {trade.notes}")
        
        if trade.trade_metadata:
            lines.append(f"Additional Info: {json.dumps(trade.trade_metadata, indent=2)}")
        
        # Add performance summary
        if trade.realized_pnl:
            outcome = "Profitable" if float(trade.realized_pnl) > 0 else "Loss"
            lines.append(f"\nOutcome: {outcome} trade")
        
        return '\n'.join(lines)
    
    def _format_backtest_for_ingestion(self, backtest: Dict[str, Any]) -> str:
        """Format backtest as natural language"""
        lines = [
            f"Backtest Results: {backtest.get('strategy_name', 'Unknown Strategy')}",
            f"Symbol: {backtest.get('symbol', 'N/A')}",
            f"Timeframe: {backtest.get('timeframe', 'N/A')}",
            f"Period: {backtest.get('start_date', 'N/A')} to {backtest.get('end_date', 'N/A')}",
            "",
            "Performance Metrics:",
            f"  Total Return: {backtest.get('total_return', 0):.2f}%",
            f"  Win Rate: {backtest.get('win_rate', 0):.2f}%",
            f"  Sharpe Ratio: {backtest.get('sharpe_ratio', 0):.2f}",
            f"  Max Drawdown: {backtest.get('max_drawdown', 0):.2f}%",
            f"  Total Trades: {backtest.get('total_trades', 0)}",
        ]
        
        if 'parameters' in backtest:
            lines.append("\nStrategy Parameters:")
            for key, value in backtest['parameters'].items():
                lines.append(f"  {key}: {value}")
        
        if 'insights' in backtest:
            lines.append(f"\nKey Insights:\n{backtest['insights']}")
        
        return '\n'.join(lines)
    
    def _format_signal_for_ingestion(self, signal: Dict[str, Any]) -> str:
        """Format signal as natural language"""
        lines = [
            f"Trading Signal: {signal.get('symbol', 'Unknown')}",
            f"Action: {signal.get('action', 'HOLD')}",
            f"Timeframe: {signal.get('timeframe', 'N/A')}",
            f"Timestamp: {signal.get('timestamp', datetime.now().isoformat())}",
        ]
        
        if 'price' in signal:
            lines.append(f"Price: {signal['price']}")
        
        if 'indicators' in signal:
            lines.append("\nTechnical Indicators:")
            for indicator, value in signal['indicators'].items():
                lines.append(f"  {indicator}: {value}")
        
        if 'stop_loss' in signal:
            lines.append(f"\nStop Loss: {signal['stop_loss']}")
        
        if 'take_profit' in signal:
            lines.append(f"Take Profit: {signal['take_profit']}")
        
        if 'confidence' in signal:
            lines.append(f"Confidence: {signal['confidence']}")
        
        if 'reasoning' in signal:
            lines.append(f"\nReasoning:\n{signal['reasoning']}")
        
        return '\n'.join(lines)
    
    def _calculate_pnl_percent(self, trade: Trade) -> float:
        """Calculate P&L percentage"""
        if not trade.realized_pnl or not trade.price or not trade.quantity:
            return 0.0
        
        cost_basis = float(trade.price) * float(trade.quantity)
        if cost_basis == 0:
            return 0.0
        
        return (float(trade.realized_pnl) / cost_basis) * 100
    
    def _calculate_trade_duration(self, trade: Trade) -> float:
        """Calculate trade duration in hours"""
        # This would need additional data (entry/exit times)
        # Simplified version for now
        return 0.0


# Convenience function
def create_ingestion_pipeline() -> DataIngestionPipeline:
    """Create data ingestion pipeline"""
    return DataIngestionPipeline()
