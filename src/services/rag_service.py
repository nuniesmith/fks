"""
RAG Service - Enhanced retrieval with LangChain integration.
Provides cosine similarity queries, prompt augmentation, and intelligent retrieval.

Features:
- pgvector cosine similarity search
- LangChain RAG chains for context-aware generation
- Multi-strategy retrieval (semantic + hybrid)
- Performance optimization with caching
- Feedback loop integration
"""

from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# LangChain imports
try:
    from langchain.chains import RetrievalQA
    from langchain.embeddings.base import Embeddings
    from langchain.prompts import PromptTemplate
    from langchain.schema import Document as LangChainDocument
    from langchain.vectorstores import PGVector
    from langchain_community.chat_models import ChatOllama
    from langchain_openai import ChatOpenAI

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print(
        "⚠ LangChain not available. Install with: pip install langchain langchain-community langchain-openai"
    )

from database import Document, DocumentChunk, QueryHistory, Session, TradingInsight
from rag.embeddings import EmbeddingsService
from rag.intelligence import FKSIntelligence
from rag.retrieval import RetrievalService

from framework.config.constants import DATABASE_URL, OPENAI_API_KEY


class FKSEmbeddingsAdapter(Embeddings):
    """Adapter to use FKS EmbeddingsService with LangChain"""

    def __init__(self, embeddings_service: EmbeddingsService):
        self.embeddings_service = embeddings_service

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents"""
        return [
            self.embeddings_service.generate_embedding(text).tolist() for text in texts
        ]

    def embed_query(self, text: str) -> list[float]:
        """Embed a query"""
        return self.embeddings_service.generate_embedding(text).tolist()


class RAGService:
    """
    Enhanced RAG service with LangChain integration.
    Provides intelligent retrieval and augmented generation for trading insights.
    """

    def __init__(
        self,
        use_local: bool = True,
        local_model: str = "llama3.2:3b",
        openai_model: str = "gpt-4o-mini",
        embedding_model: str = "all-MiniLM-L6-v2",
        cache_ttl: int = 300,
    ):
        """
        Initialize RAG service.

        Args:
            use_local: Use local models (Ollama)
            local_model: Local LLM model name
            openai_model: OpenAI model name
            embedding_model: Embedding model name
            cache_ttl: Cache TTL in seconds
        """
        self.use_local = use_local
        self.local_model = local_model
        self.openai_model = openai_model
        self.cache_ttl = cache_ttl

        # Initialize core components
        self.intelligence = FKSIntelligence(
            use_local=use_local,
            local_llm_model=local_model,
            openai_model=openai_model,
            embedding_model=embedding_model,
        )

        self.embeddings_service = self.intelligence.embeddings
        self.retrieval_service = self.intelligence.retrieval

        # Initialize LangChain components if available
        if LANGCHAIN_AVAILABLE:
            self._init_langchain()

    def _init_langchain(self):
        """Initialize LangChain components"""
        try:
            # Create embeddings adapter
            self.lc_embeddings = FKSEmbeddingsAdapter(self.embeddings_service)

            # Initialize LLM
            if self.use_local:
                self.llm = ChatOllama(model=self.local_model, temperature=0.3)
            else:
                self.llm = ChatOpenAI(
                    model=self.openai_model, temperature=0.3, api_key=OPENAI_API_KEY
                )

            # Create custom prompt template
            self.prompt_template = self._create_prompt_template()

            print("✓ LangChain RAG chain initialized")

        except Exception as e:
            print(f"⚠ LangChain initialization failed: {e}")
            self.llm = None

    def _create_prompt_template(self) -> PromptTemplate:
        """Create custom prompt template for trading insights"""
        template = """You are FKS Intelligence, an expert trading assistant with access to historical trading data, backtest results, and market insights.

Context from knowledge base:
{context}

User Question: {question}

Instructions:
1. Analyze the provided context carefully
2. Focus on actionable trading insights
3. Reference specific data points from the context
4. Consider risk management and market conditions
5. If context is insufficient, say so clearly

Provide a detailed, professional answer:"""

        return PromptTemplate(
            template=template, input_variables=["context", "question"]
        )

    def query_with_cosine_similarity(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.6,
        filters: dict[str, Any] | None = None,
        session: Session | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query knowledge base using pgvector cosine similarity.

        Args:
            query: Natural language query
            top_k: Number of results to retrieve
            similarity_threshold: Minimum similarity score (0-1)
            filters: Optional filters (symbol, doc_type, date_range)
            session: SQLAlchemy session

        Returns:
            List of relevant chunks with similarity scores
        """
        # Generate query embedding
        query_embedding = self.embeddings_service.generate_embedding(query)

        # Perform semantic search with cosine similarity
        results = self.embeddings_service.semantic_search(
            query_embedding=query_embedding,
            limit=top_k,
            similarity_threshold=similarity_threshold,
            filters=filters,
            session=session,
        )

        return results

    def augment_prompt_with_context(
        self, query: str, top_k: int = 5, filters: dict[str, Any] | None = None
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Retrieve context and augment prompt for generation.

        Args:
            query: User query
            top_k: Number of context chunks
            filters: Optional filters

        Returns:
            Tuple of (augmented_prompt, sources)
        """
        # Retrieve relevant context
        context_chunks = self.query_with_cosine_similarity(
            query=query, top_k=top_k, filters=filters
        )

        if not context_chunks:
            return query, []

        # Build context string
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            similarity = chunk.get("similarity_score", 0)
            content = chunk.get("content", "")
            metadata = chunk.get("metadata", {})

            context_part = f"[Source {i}] (Relevance: {similarity:.2%})\n{content}"
            if metadata.get("symbol"):
                context_part += f"\nSymbol: {metadata['symbol']}"
            if metadata.get("doc_type"):
                context_part += f"\nType: {metadata['doc_type']}"

            context_parts.append(context_part)

        # Create augmented prompt
        context_text = "\n\n".join(context_parts)
        augmented_prompt = self.prompt_template.format(
            context=context_text, question=query
        )

        return augmented_prompt, context_chunks

    def query_with_rag(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        include_sources: bool = True,
        session: Session | None = None,
    ) -> dict[str, Any]:
        """
        Query using full RAG pipeline with LangChain.

        Args:
            query: Natural language query
            top_k: Number of context chunks to retrieve
            filters: Optional filters
            include_sources: Include source documents in response
            session: SQLAlchemy session

        Returns:
            Dict with answer, sources, and metadata
        """
        start_time = datetime.now()

        # Retrieve context and augment prompt
        augmented_prompt, sources = self.augment_prompt_with_context(
            query=query, top_k=top_k, filters=filters
        )

        # Generate response
        if LANGCHAIN_AVAILABLE and self.llm:
            try:
                # Use LangChain for generation
                response = self.llm.invoke(augmented_prompt)
                answer = (
                    response.content if hasattr(response, "content") else str(response)
                )
            except Exception as e:
                print(f"⚠ LangChain generation failed: {e}")
                # Fallback to FKS Intelligence
                result = self.intelligence.query(query, top_k=top_k, session=session)
                answer = result.get("answer", "Error generating response")
        else:
            # Use FKS Intelligence directly
            result = self.intelligence.query(query, top_k=top_k, session=session)
            answer = result.get("answer", "Error generating response")

        # Calculate response time
        response_time = (datetime.now() - start_time).total_seconds()

        # Log query
        self._log_query(query, answer, len(sources), response_time, session)

        # Build response
        response = {
            "answer": answer,
            "query": query,
            "num_sources": len(sources),
            "response_time": response_time,
            "model": self.local_model if self.use_local else self.openai_model,
        }

        if include_sources:
            response["sources"] = sources

        return response

    def predict_trend(
        self, symbol: str, timeframe: str = "1h", lookback_days: int = 30
    ) -> dict[str, Any]:
        """
        Predict trend for a symbol using RAG insights.

        Example: "Based on history, predict SOLUSDT trend"

        Args:
            symbol: Trading pair (e.g., "SOLUSDT")
            timeframe: Timeframe for analysis
            lookback_days: Days of historical data to consider

        Returns:
            Dict with prediction, reasoning, and confidence
        """
        # Build query
        query = f"Based on recent {lookback_days}-day history, what is the trend prediction for {symbol} on {timeframe} timeframe?"

        # Add filters for symbol and recency
        filters = {
            "symbol": symbol,
            "date_range": {
                "start": datetime.now() - timedelta(days=lookback_days),
                "end": datetime.now(),
            },
        }

        # Query with RAG
        result = self.query_with_rag(
            query=query, top_k=10, filters=filters  # More context for predictions
        )

        # Extract prediction confidence from sources
        sources = result.get("sources", [])
        avg_similarity = (
            np.mean([s.get("similarity_score", 0) for s in sources]) if sources else 0
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "prediction": result["answer"],
            "confidence": avg_similarity,
            "sources_count": len(sources),
            "response_time": result["response_time"],
        }

    def suggest_strategy(
        self,
        symbol: str,
        market_condition: str | None = None,
        risk_level: str = "medium",
    ) -> dict[str, Any]:
        """
        Get strategy suggestions based on historical performance.

        Args:
            symbol: Trading pair
            market_condition: Current market condition (trending, ranging, volatile)
            risk_level: Risk tolerance (low, medium, high)

        Returns:
            Strategy recommendations with reasoning
        """
        # Build context-aware query
        query_parts = [f"What trading strategy works best for {symbol}"]

        if market_condition:
            query_parts.append(f"in {market_condition} market conditions")

        query_parts.append(f"with {risk_level} risk tolerance?")
        query = " ".join(query_parts)

        # Add filters
        filters = {
            "symbol": symbol,
            "doc_type": ["backtest_result", "trade_analysis", "strategy_insight"],
        }

        # Query with RAG
        result = self.query_with_rag(query=query, top_k=7, filters=filters)

        return {
            "symbol": symbol,
            "market_condition": market_condition,
            "risk_level": risk_level,
            "strategy": result["answer"],
            "sources_count": result["num_sources"],
            "response_time": result["response_time"],
        }

    def analyze_trade_outcome(
        self,
        symbol: str,
        outcome: str,
        pnl: float,
        strategy: str,
        market_condition: str,
        notes: str | None = None,
    ) -> int:
        """
        Store trade outcome as learning feedback.

        This creates a feedback loop where trade results are ingested
        into the knowledge base for future reference.

        Args:
            symbol: Trading pair
            outcome: "win" or "loss"
            pnl: Profit/loss amount
            strategy: Strategy used
            market_condition: Market condition during trade
            notes: Additional observations

        Returns:
            Document ID
        """
        # Build feedback document
        content = f"""Trade Outcome Analysis
Symbol: {symbol}
Outcome: {outcome.upper()}
P&L: ${pnl:.2f} ({'+' if pnl > 0 else ''}{pnl:.2%})
Strategy: {strategy}
Market Condition: {market_condition}
Date: {datetime.now().isoformat()}

Observations:
{notes or 'No additional notes'}

Learning: {'This strategy performed well' if pnl > 0 else 'Strategy needs adjustment'} in {market_condition} conditions for {symbol}.
"""

        # Ingest into knowledge base
        doc_id = self.intelligence.ingest_document(
            content=content,
            doc_type="trade_outcome",
            title=f"{outcome.upper()}: {symbol} - {strategy}",
            symbol=symbol,
            metadata={
                "outcome": outcome,
                "pnl": pnl,
                "strategy": strategy,
                "market_condition": market_condition,
                "feedback_type": "trade_result",
            },
        )

        print(f"✓ Trade outcome logged (Doc ID: {doc_id})")
        return doc_id

    def store_backtest_feedback(
        self,
        strategy: str,
        symbol: str,
        timeframe: str,
        metrics: dict[str, Any],
        insights: str,
    ) -> int:
        """
        Store backtest results as structured feedback.

        Args:
            strategy: Strategy name
            symbol: Trading pair
            timeframe: Timeframe tested
            metrics: Performance metrics dict
            insights: Key insights and learnings

        Returns:
            Document ID
        """
        # Format metrics
        metrics_text = "\n".join([f"- {k}: {v}" for k, v in metrics.items()])

        content = f"""Backtest Results: {strategy}
Symbol: {symbol}
Timeframe: {timeframe}
Date: {datetime.now().isoformat()}

Performance Metrics:
{metrics_text}

Key Insights:
{insights}

Conclusion: {"Strong performance" if metrics.get('win_rate', 0) > 0.6 else "Needs optimization"}
"""

        # Ingest
        doc_id = self.intelligence.ingest_document(
            content=content,
            doc_type="backtest_result",
            title=f"Backtest: {strategy} - {symbol}",
            symbol=symbol,
            timeframe=timeframe,
            metadata={
                "strategy": strategy,
                "metrics": metrics,
                "feedback_type": "backtest",
            },
        )

        return doc_id

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        session: Session | None = None,
    ) -> list[dict[str, Any]]:
        """
        Hybrid search combining semantic and keyword matching.

        Args:
            query: Search query
            top_k: Number of results
            semantic_weight: Weight for semantic similarity (0-1)
            keyword_weight: Weight for keyword matching (0-1)
            session: SQLAlchemy session

        Returns:
            Ranked results from hybrid search
        """
        should_close = False
        if session is None:
            session = Session()
            should_close = True

        try:
            # 1. Semantic search
            semantic_results = self.query_with_cosine_similarity(
                query=query, top_k=top_k * 2, session=session  # Get more for ranking
            )

            # 2. Keyword search (PostgreSQL full-text search)
            keyword_results = self._keyword_search(query, top_k * 2, session)

            # 3. Combine and rank
            combined = self._hybrid_rank(
                semantic_results, keyword_results, semantic_weight, keyword_weight
            )

            return combined[:top_k]

        finally:
            if should_close:
                session.close()

    def _keyword_search(
        self, query: str, limit: int, session: Session
    ) -> list[dict[str, Any]]:
        """Keyword-based search using PostgreSQL full-text search"""
        from sqlalchemy import String, cast, func

        # Simple keyword matching (can be enhanced with PostgreSQL FTS)
        keywords = query.lower().split()

        results = []
        query_obj = session.query(DocumentChunk).filter(
            not DocumentChunk.is_deleted
        )

        # Match any keyword in content
        for keyword in keywords:
            query_obj = query_obj.filter(
                func.lower(DocumentChunk.content).contains(keyword)
            )

        chunks = query_obj.limit(limit).all()

        for chunk in chunks:
            # Calculate simple keyword score
            content_lower = chunk.content.lower()
            score = sum(1 for kw in keywords if kw in content_lower) / len(keywords)

            results.append(
                {
                    "chunk_id": chunk.id,
                    "content": chunk.content,
                    "keyword_score": score,
                    "metadata": chunk.metadata or {},
                }
            )

        return results

    def _hybrid_rank(
        self,
        semantic_results: list[dict],
        keyword_results: list[dict],
        semantic_weight: float,
        keyword_weight: float,
    ) -> list[dict[str, Any]]:
        """Combine and rank results from semantic and keyword search"""
        # Create score map
        scores = {}

        # Add semantic scores
        for result in semantic_results:
            chunk_id = result.get("chunk_id")
            semantic_score = result.get("similarity_score", 0)
            scores[chunk_id] = {
                "semantic": semantic_score,
                "keyword": 0,
                "data": result,
            }

        # Add keyword scores
        for result in keyword_results:
            chunk_id = result.get("chunk_id")
            keyword_score = result.get("keyword_score", 0)

            if chunk_id in scores:
                scores[chunk_id]["keyword"] = keyword_score
            else:
                scores[chunk_id] = {
                    "semantic": 0,
                    "keyword": keyword_score,
                    "data": result,
                }

        # Calculate hybrid scores
        ranked = []
        for _chunk_id, data in scores.items():
            hybrid_score = (
                data["semantic"] * semantic_weight + data["keyword"] * keyword_weight
            )

            result = data["data"].copy()
            result["hybrid_score"] = hybrid_score
            ranked.append(result)

        # Sort by hybrid score
        ranked.sort(key=lambda x: x["hybrid_score"], reverse=True)

        return ranked

    def _log_query(
        self,
        query: str,
        answer: str,
        num_sources: int,
        response_time: float,
        session: Session | None = None,
    ):
        """Log query for analytics and improvement"""
        should_close = False
        if session is None:
            session = Session()
            should_close = True

        try:
            query_log = QueryHistory(
                query_text=query,
                response=answer,
                num_sources=num_sources,
                response_time=response_time,
                model=self.local_model if self.use_local else self.openai_model,
                timestamp=datetime.now(),
            )
            session.add(query_log)
            session.commit()
        except Exception as e:
            print(f"⚠ Failed to log query: {e}")
            session.rollback()
        finally:
            if should_close:
                session.close()

    def get_query_analytics(
        self, days: int = 7, session: Session | None = None
    ) -> dict[str, Any]:
        """
        Get query analytics for monitoring and improvement.

        Args:
            days: Number of days to analyze
            session: SQLAlchemy session

        Returns:
            Analytics dict with stats and trends
        """
        should_close = False
        if session is None:
            session = Session()
            should_close = True

        try:
            cutoff = datetime.now() - timedelta(days=days)

            queries = (
                session.query(QueryHistory)
                .filter(QueryHistory.timestamp >= cutoff)
                .all()
            )

            if not queries:
                return {"message": "No queries in period"}

            # Calculate stats
            total_queries = len(queries)
            avg_response_time = np.mean([q.response_time for q in queries])
            avg_sources = np.mean([q.num_sources for q in queries])

            # Most common query patterns
            [q.query_text.lower() for q in queries]

            return {
                "period_days": days,
                "total_queries": total_queries,
                "avg_response_time": f"{avg_response_time:.2f}s",
                "avg_sources_per_query": f"{avg_sources:.1f}",
                "model": self.local_model if self.use_local else self.openai_model,
                "queries_per_day": total_queries / days,
            }

        finally:
            if should_close:
                session.close()


# Factory function
def create_rag_service(use_local: bool = True, **kwargs) -> RAGService:
    """
    Create RAG service instance.

    Args:
        use_local: Use local models
        **kwargs: Additional arguments for RAGService

    Returns:
        RAGService instance
    """
    return RAGService(use_local=use_local, **kwargs)


# Singleton instance (optional)
_rag_service_instance = None


def get_rag_service() -> RAGService:
    """Get singleton RAG service instance"""
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = create_rag_service()
    return _rag_service_instance
