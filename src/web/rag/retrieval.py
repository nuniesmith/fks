"""
Retrieval service for RAG system.
Handles context retrieval and ranking for generating responses.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from core.database import Session, Document, DocumentChunk, TradingInsight
from web.rag.embeddings import EmbeddingsService


class RetrievalService:
    """Retrieve relevant context for RAG queries"""
    
    def __init__(self, embeddings_service: Optional[EmbeddingsService] = None):
        """
        Initialize retrieval service.
        
        Args:
            embeddings_service: EmbeddingsService instance
        """
        self.embeddings = embeddings_service or EmbeddingsService()
    
    def retrieve_context(self,
                        query: str,
                        top_k: int = 5,
                        filters: Optional[Dict[str, Any]] = None,
                        session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context for a query.
        
        Args:
            query: User query
            top_k: Number of results to return
            filters: Optional filters (symbol, doc_type, date range, etc.)
            session: SQLAlchemy session
            
        Returns:
            List of relevant chunks with metadata
        """
        # Generate query embedding
        query_embedding = self.embeddings.generate_embedding(query)
        
        # Perform semantic search
        results = self.embeddings.semantic_search(
            query_embedding=query_embedding,
            limit=top_k,
            similarity_threshold=0.6,  # Adjustable threshold
            filters=filters,
            session=session
        )
        
        return results
    
    def retrieve_trading_insights(self,
                                  query: str,
                                  symbol: Optional[str] = None,
                                  category: Optional[str] = None,
                                  limit: int = 5,
                                  session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Retrieve curated trading insights.
        
        Args:
            query: Search query
            symbol: Filter by symbol
            category: Filter by category
            limit: Maximum number of results
            session: SQLAlchemy session
            
        Returns:
            List of trading insights
        """
        should_close = False
        if session is None:
            session = Session()
            should_close = True
        
        try:
            query_obj = session.query(TradingInsight)
            
            # Apply filters
            if symbol:
                query_obj = query_obj.filter(TradingInsight.symbol == symbol)
            
            if category:
                query_obj = query_obj.filter(TradingInsight.category == category)
            
            # Order by impact and recency
            query_obj = query_obj.order_by(
                TradingInsight.impact.desc(),
                TradingInsight.created_at.desc()
            ).limit(limit)
            
            insights = query_obj.all()
            
            return [
                {
                    'id': insight.id,
                    'type': insight.insight_type,
                    'title': insight.title,
                    'content': insight.content,
                    'symbol': insight.symbol,
                    'impact': insight.impact,
                    'category': insight.category,
                    'tags': insight.tags,
                    'created_at': insight.created_at.isoformat() if insight.created_at else None
                }
                for insight in insights
            ]
        finally:
            if should_close:
                session.close()
    
    def retrieve_recent_signals(self,
                               symbol: Optional[str] = None,
                               days: int = 7,
                               limit: int = 10,
                               session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Retrieve recent trading signals from knowledge base.
        
        Args:
            symbol: Filter by symbol
            days: Number of days to look back
            limit: Maximum number of results
            session: SQLAlchemy session
            
        Returns:
            List of recent signals
        """
        filters = {'doc_type': 'signal'}
        
        if symbol:
            filters['symbol'] = symbol
        
        should_close = False
        if session is None:
            session = Session()
            should_close = True
        
        try:
            # Query documents
            query_obj = session.query(Document).filter(
                Document.doc_type == 'signal',
                Document.created_at >= datetime.now() - timedelta(days=days)
            )
            
            if symbol:
                query_obj = query_obj.filter(Document.symbol == symbol)
            
            signals = query_obj.order_by(
                Document.created_at.desc()
            ).limit(limit).all()
            
            return [
                {
                    'id': signal.id,
                    'title': signal.title,
                    'content': signal.content,
                    'symbol': signal.symbol,
                    'metadata': signal.metadata,
                    'created_at': signal.created_at.isoformat() if signal.created_at else None
                }
                for signal in signals
            ]
        finally:
            if should_close:
                session.close()
    
    def retrieve_backtest_results(self,
                                  strategy: Optional[str] = None,
                                  symbol: Optional[str] = None,
                                  min_return: Optional[float] = None,
                                  limit: int = 5,
                                  session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Retrieve backtest results from knowledge base.
        
        Args:
            strategy: Filter by strategy name
            symbol: Filter by symbol
            min_return: Minimum return percentage
            limit: Maximum number of results
            session: SQLAlchemy session
            
        Returns:
            List of backtest results
        """
        should_close = False
        if session is None:
            session = Session()
            should_close = True
        
        try:
            query_obj = session.query(Document).filter(
                Document.doc_type == 'backtest'
            )
            
            if symbol:
                query_obj = query_obj.filter(Document.symbol == symbol)
            
            # Get results
            results = query_obj.order_by(
                Document.created_at.desc()
            ).limit(limit * 2).all()  # Get more to filter by return
            
            # Filter by metadata if needed
            filtered_results = []
            for result in results:
                metadata = result.metadata or {}
                
                # Check strategy filter
                if strategy and metadata.get('strategy_name') != strategy:
                    continue
                
                # Check return filter
                if min_return is not None and metadata.get('total_return', 0) < min_return:
                    continue
                
                filtered_results.append({
                    'id': result.id,
                    'title': result.title,
                    'content': result.content,
                    'symbol': result.symbol,
                    'timeframe': result.timeframe,
                    'metadata': metadata,
                    'created_at': result.created_at.isoformat() if result.created_at else None
                })
                
                if len(filtered_results) >= limit:
                    break
            
            return filtered_results
        finally:
            if should_close:
                session.close()
    
    def rerank_results(self,
                      query: str,
                      results: List[Dict[str, Any]],
                      method: str = 'similarity') -> List[Dict[str, Any]]:
        """
        Re-rank retrieval results.
        
        Args:
            query: Original query
            results: List of results from retrieval
            method: Ranking method ('similarity', 'recency', 'hybrid')
            
        Returns:
            Re-ranked results
        """
        if method == 'similarity':
            # Already sorted by similarity from semantic search
            return results
        
        elif method == 'recency':
            # Sort by creation date
            return sorted(
                results,
                key=lambda x: x.get('created_at', ''),
                reverse=True
            )
        
        elif method == 'hybrid':
            # Combine similarity and recency
            # Normalize scores and create weighted combination
            if not results:
                return results
            
            max_sim = max(r.get('similarity', 0) for r in results)
            
            for result in results:
                sim_score = result.get('similarity', 0) / max_sim if max_sim > 0 else 0
                # Simple recency score (newer = higher)
                recency_score = 0.5  # Default if no date
                
                # Combined score (60% similarity, 40% recency)
                result['combined_score'] = 0.6 * sim_score + 0.4 * recency_score
            
            return sorted(results, key=lambda x: x.get('combined_score', 0), reverse=True)
        
        return results
    
    def format_context_for_prompt(self, 
                                  results: List[Dict[str, Any]],
                                  max_tokens: int = 4000) -> str:
        """
        Format retrieval results into a context string for LLM prompt.
        
        Args:
            results: Retrieved chunks
            max_tokens: Maximum tokens for context (rough estimate)
            
        Returns:
            Formatted context string
        """
        if not results:
            return "No relevant context found."
        
        context_parts = []
        total_length = 0
        max_chars = max_tokens * 4  # Rough estimate: 1 token ≈ 4 chars
        
        for i, result in enumerate(results, 1):
            # Format each result
            doc_type = result.get('doc_type', 'document')
            symbol = result.get('symbol', 'N/A')
            similarity = result.get('similarity', 0)
            content = result.get('content', '')
            
            part = f"\n[Context {i} - {doc_type.upper()} - {symbol} - Relevance: {similarity:.2f}]\n{content}\n"
            
            # Check if adding this would exceed limit
            if total_length + len(part) > max_chars:
                context_parts.append("\n[Additional context truncated due to length...]")
                break
            
            context_parts.append(part)
            total_length += len(part)
        
        return '\n'.join(context_parts)


# Convenience function
def create_retrieval_service(embeddings_service: Optional[EmbeddingsService] = None) -> RetrievalService:
    """Create retrieval service with embeddings service"""
    return RetrievalService(embeddings_service=embeddings_service)
