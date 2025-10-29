"""
RAG (Retrieval-Augmented Generation) module for FKS Trading Platform.

This module provides intelligent knowledge base capabilities for trading insights,
including document processing, semantic search, and LLM-powered query responses.

Components:
- document_processor: Chunk documents for embedding
- embeddings: Generate and store OpenAI embeddings with pgvector
- retrieval: Semantic search and context retrieval
- intelligence: Main RAG orchestrator (FKS Intelligence)
- ingestion: Automated data pipeline for trading data

Usage:
    from rag.intelligence import FKSIntelligence

    intelligence = FKSIntelligence()

    # Query knowledge base
    result = intelligence.query("What strategy works best for BTCUSDT?")
    print(result['answer'])

    # Ingest trading data
    intelligence.ingest_document(
        content="Trade analysis...",
        doc_type="trade_analysis",
        symbol="BTCUSDT"
    )
"""

from src.rag.document_processor import DocumentProcessor, create_processor
from src.rag.embeddings import EmbeddingsService, create_embeddings_service
from src.rag.ingestion import DataIngestionPipeline, create_ingestion_pipeline
from src.rag.intelligence import FKSIntelligence, create_intelligence
from src.rag.retrieval import RetrievalService, create_retrieval_service

__all__ = [
    "FKSIntelligence",
    "create_intelligence",
    "DocumentProcessor",
    "create_processor",
    "EmbeddingsService",
    "create_embeddings_service",
    "RetrievalService",
    "create_retrieval_service",
    "DataIngestionPipeline",
    "create_ingestion_pipeline",
]

__version__ = "0.1.0"
