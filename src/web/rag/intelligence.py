"""
FKS Intelligence - Main RAG orchestrator for trading knowledge base.
Combines document processing, embeddings, retrieval, and LLM generation.
Supports both OpenAI API and local CUDA-accelerated models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from core.database.models import Session, Document, DocumentChunk, QueryHistory
from web.rag.document_processor import DocumentProcessor
from web.rag.embeddings import EmbeddingsService
from web.rag.retrieval import RetrievalService
from framework.config.constants import OPENAI_API_KEY


class FKSIntelligence:
    """Main RAG system for FKS trading intelligence"""

    def __init__(
        self,
        openai_model: str = "gpt-4o-mini",
        embedding_model: str = "all-MiniLM-L6-v2",
        use_local: bool = True,
        local_llm_model: str = "llama3.2:3b",
    ):
        """
        Initialize FKS Intelligence.

        Args:
            openai_model: OpenAI model for generation (fallback)
            embedding_model: Model for embeddings (local or OpenAI)
            use_local: Use local models instead of OpenAI API
            local_llm_model: Local LLM model name for Ollama
        """
        self.openai_model = openai_model
        self.use_local = use_local
        self.local_llm_model = local_llm_model

        # Initialize RAG components
        self.processor = DocumentProcessor()
        self.embeddings = EmbeddingsService(model=embedding_model, use_local=use_local)
        self.retrieval = RetrievalService(embeddings_service=self.embeddings)

        # Initialize LLM
        if use_local:
            self._init_local_llm()
        else:
            self._init_openai()

    def _init_local_llm(self):
        """Initialize local LLM"""
        try:
            from web.rag.local_llm import create_local_llm
            
            self.llm = create_local_llm(
                model_name=self.local_llm_model, backend="ollama"
            )
            print(f"✓ Using local LLM: {self.local_llm_model}")

        except Exception as e:
            print(f"⚠ Local LLM not available: {e}")
            print("  Falling back to OpenAI...")
            self.use_local = False
            self._init_openai()

    def _init_openai(self):
        """Initialize OpenAI client"""
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key not set and local LLM not available")

        self.client = OpenAI(api_key=OPENAI_API_KEY)
        print(f"✓ Using OpenAI: {self.openai_model}")

    def ingest_document(
        self,
        content: str,
        doc_type: str,
        title: Optional[str] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        metadata: dict[str, Any] | None = None,
        session: Optional[Session] = None,
    ) -> int:
        """
        Ingest a document into the knowledge base.

        Args:
            content: Document content
            doc_type: Type of document
            title: Document title
            symbol: Trading pair
            timeframe: Timeframe
            metadata: Additional metadata
            session: SQLAlchemy session

        Returns:
            Document ID
        """
        should_close = False
        if session is None:
            session = Session()
            should_close = True

        try:
            # Create document
            doc = Document(
                doc_type=doc_type,
                title=title
                or f"{doc_type} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                content=content,
                symbol=symbol,
                timeframe=timeframe,
                metadata=metadata or {},
            )
            session.add(doc)
            session.flush()  # Get document ID

            # Chunk document
            chunks = self.processor.chunk_text(content, metadata={"doc_id": doc.id})

            # Create chunk records and generate embeddings
            chunk_texts = []
            chunk_records = []

            for chunk in chunks:
                chunk_record = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    metadata=chunk.metadata,
                )
                session.add(chunk_record)
                chunk_records.append(chunk_record)
                chunk_texts.append(chunk.content)

            session.flush()  # Get chunk IDs

            # Generate embeddings in batch
            embeddings = self.embeddings.generate_embeddings_batch(chunk_texts)

            # Store embeddings
            for chunk_record, embedding in zip(chunk_records, embeddings, strict=False):
                self.embeddings.store_chunk_embedding(
                    chunk_id=chunk_record.id, embedding=embedding, session=session
                )

            session.commit()
            return doc.id

        except Exception as e:
            print(f"Error ingesting document: {e}")
            session.rollback()
            raise
        finally:
            if should_close:
                session.close()

    def query(
        self,
        question: str,
        symbol: Optional[str] = None,
        doc_types: list[str] | None = None,
        top_k: int = 5,
        session: Optional[Session] = None,
    ) -> dict[str, Any]:
        """
        Query the knowledge base and generate a response.

        Args:
            question: User question
            symbol: Filter by trading pair
            doc_types: Filter by document types
            top_k: Number of context chunks to retrieve
            session: SQLAlchemy session

        Returns:
            Response dictionary with answer, sources, and metadata
        """
        start_time = datetime.now()

        should_close = False
        if session is None:
            session = Session()
            should_close = True

        try:
            # Build filters
            filters = {}
            if symbol:
                filters["symbol"] = symbol

            # Retrieve context
            all_results = []

            if doc_types:
                for doc_type in doc_types:
                    filters["doc_type"] = doc_type
                    results = self.retrieval.retrieve_context(
                        query=question, top_k=top_k, filters=filters, session=session
                    )
                    all_results.extend(results)
            else:
                all_results = self.retrieval.retrieve_context(
                    query=question, top_k=top_k, filters=filters, session=session
                )

            # Re-rank results
            ranked_results = self.retrieval.rerank_results(
                query=question, results=all_results, method="hybrid"
            )[:top_k]

            # Format context
            context = self.retrieval.format_context_for_prompt(ranked_results)

            # Generate response
            response = self._generate_response(question, context)

            # Calculate response time
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)

            # Log query
            self._log_query(
                query=question,
                response=response,
                retrieved_chunks=ranked_results,
                response_time=response_time,
                session=session,
            )

            return {
                "answer": response,
                "sources": ranked_results,
                "context_used": len(ranked_results),
                "response_time_ms": response_time,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"Error processing query: {e}")
            return {
                "answer": f"Error processing query: {str(e)}",
                "sources": [],
                "context_used": 0,
                "response_time_ms": 0,
                "timestamp": datetime.now().isoformat(),
            }
        finally:
            if should_close:
                session.close()

    def suggest_strategy(
        self,
        symbol: str,
        market_condition: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> dict[str, Any]:
        """
        Suggest trading strategy based on historical data.

        Args:
            symbol: Trading pair
            market_condition: Current market condition (e.g., 'trending', 'ranging')
            session: SQLAlchemy session

        Returns:
            Strategy suggestion with reasoning
        """
        # Build query
        query = f"Suggest a trading strategy for {symbol}"
        if market_condition:
            query += f" in {market_condition} market conditions"
        query += " based on past performance and signals."

        # Use specialized doc types
        return self.query(
            question=query,
            symbol=symbol,
            doc_types=["backtest", "signal", "strategy", "trade_analysis"],
            top_k=7,
            session=session,
        )

    def analyze_past_trades(
        self, symbol: Optional[str] = None, session: Optional[Session] = None
    ) -> dict[str, Any]:
        """
        Analyze past trading performance.

        Args:
            symbol: Trading pair to analyze
            session: SQLAlchemy session

        Returns:
            Analysis with insights
        """
        query = "What patterns and insights can you identify from past trades"
        if symbol:
            query += f" for {symbol}"
        query += "? What mistakes were made and what strategies worked well?"

        return self.query(
            question=query,
            symbol=symbol,
            doc_types=["trade_analysis", "backtest", "insight"],
            top_k=10,
            session=session,
        )

    def explain_signal(
        self,
        symbol: str,
        current_indicators: dict[str, float],
        session: Optional[Session] = None,
    ) -> dict[str, Any]:
        """
        Explain a trading signal based on historical context.

        Args:
            symbol: Trading pair
            current_indicators: Current technical indicators
            session: SQLAlchemy session

        Returns:
            Signal explanation with context
        """
        # Format indicators
        indicators_str = ", ".join(
            [f"{k}={v:.2f}" for k, v in current_indicators.items()]
        )

        query = f"For {symbol}, given current indicators: {indicators_str}, "
        query += "what trading action is recommended based on historical signals and performance?"

        return self.query(
            question=query,
            symbol=symbol,
            doc_types=["signal", "backtest", "strategy"],
            top_k=5,
            session=session,
        )

    def _generate_response(self, question: str, context: str) -> str:
        """
        Generate response using local LLM or OpenAI with retrieved context.

        Args:
            question: User question
            context: Retrieved context

        Returns:
            Generated response
        """
        system_prompt = """You are FKS Intelligence, an expert AI trading assistant with deep knowledge of crypto trading strategies, technical analysis, and risk management.

Your role is to provide actionable trading insights based on historical data, past signals, backtest results, and trading lessons learned.

Guidelines:
- Base your answers on the provided context
- Be specific and reference actual data when available
- Acknowledge uncertainty when context is limited
- Provide actionable recommendations
- Consider risk management in all suggestions
- Explain your reasoning clearly

Format your responses with:
1. Direct answer to the question
2. Supporting evidence from historical data
3. Actionable recommendations
4. Risk considerations"""

        user_prompt = f"""Context from FKS Knowledge Base:
{context}

Question: {question}

Please provide a comprehensive answer based on the context above."""

        if self.use_local:
            return self._generate_local(user_prompt, system_prompt)
        else:
            return self._generate_openai(user_prompt, system_prompt)

    def _generate_local(self, prompt: str, system_prompt: str) -> str:
        """Generate response using local LLM"""
        try:
            response = self.llm.generate(
                prompt=prompt, system_prompt=system_prompt, max_tokens=1000
            )
            return response
        except Exception as e:
            return f"Error generating response: {str(e)}"

    def _generate_openai(self, prompt: str, system_prompt: str) -> str:
        """Generate response using OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=1000,
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"Error generating response: {str(e)}"

    def _log_query(
        self,
        query: str,
        response: str,
        retrieved_chunks: list[dict[str, Any]],
        response_time: int,
        session: Session,
    ):
        """Log query to database"""
        try:
            log_entry = QueryHistory(
                query=query,
                response=response,
                retrieved_chunks={
                    "chunks": [
                        {
                            "chunk_id": chunk.get("chunk_id"),
                            "similarity": chunk.get("similarity"),
                            "doc_type": chunk.get("doc_type"),
                        }
                        for chunk in retrieved_chunks
                    ]
                },
                model_used=self.openai_model,
                response_time_ms=response_time,
            )
            session.add(log_entry)
            session.commit()
        except Exception as e:
            print(f"Error logging query: {e}")


# Convenience function
def create_intelligence(
    use_local: bool = True,
    local_llm_model: str = "llama3.2:3b",
    embedding_model: str = "all-MiniLM-L6-v2",
) -> FKSIntelligence:
    """
    Create FKS Intelligence instance with local or OpenAI models.

    Args:
        use_local: Use local CUDA-accelerated models (default: True)
        local_llm_model: Ollama model name (e.g., "llama3.2:3b", "mistral:7b")
        embedding_model: Embedding model name

    Returns:
        FKSIntelligence instance
    """
    return FKSIntelligence(
        use_local=use_local,
        local_llm_model=local_llm_model,
        embedding_model=embedding_model,
    )
