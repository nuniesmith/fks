"""
Services module for FKS Trading Platform.

This module provides high-level business logic services that orchestrate
multiple components for specific use cases.

Services:
- rag_service: Enhanced RAG with LangChain integration
- feedback_service: Learning and retention loop for trade outcomes
- optimization_service: Strategy optimization with Optuna + RAG insights
"""

from services.rag_service import RAGService, create_rag_service, get_rag_service
from services.feedback_service import FeedbackService, create_feedback_service, get_feedback_service

try:
    from services.optimization_service import (
        OptimizationService, 
        create_optimization_service, 
        get_optimization_service
    )
    OPTIMIZATION_AVAILABLE = True
except ImportError:
    OPTIMIZATION_AVAILABLE = False
    print("⚠ Optimization service requires Optuna: pip install optuna")

__all__ = [
    'RAGService',
    'create_rag_service',
    'get_rag_service',
    'FeedbackService',
    'create_feedback_service',
    'get_feedback_service',
]

if OPTIMIZATION_AVAILABLE:
    __all__.extend([
        'OptimizationService',
        'create_optimization_service',
        'get_optimization_service',
    ])

__version__ = '0.1.0'
