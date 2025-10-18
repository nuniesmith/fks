"""
RAG Services - Public API

This module provides the public API for the FKS Intelligence RAG system,
matching the interface specified in the issue requirements.

Example from issue:
    from rag.services import IntelligenceOrchestrator
    
    orchestrator = IntelligenceOrchestrator()
    recommendation = orchestrator.get_trading_recommendation(
        symbol="BTCUSDT",
        account_balance=10000.00,
        context="current market conditions"
    )
"""

# Export the main orchestrator class
from web.rag.orchestrator import IntelligenceOrchestrator, create_orchestrator

# Export other useful classes
from web.rag.intelligence import FKSIntelligence, create_intelligence
from web.rag.ingestion import DataIngestionPipeline
from web.rag.embeddings import EmbeddingsService
from web.rag.retrieval import RetrievalService
from web.rag.document_processor import DocumentProcessor

__all__ = [
    'IntelligenceOrchestrator',
    'create_orchestrator',
    'FKSIntelligence',
    'create_intelligence',
    'DataIngestionPipeline',
    'EmbeddingsService',
    'RetrievalService',
    'DocumentProcessor',
]
