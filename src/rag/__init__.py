"""
RAG (Retrieval-Augmented Generation) system for FKS Trading Intelligence.

This module provides the orchestration layer for AI-powered trading recommendations.
"""

from src.rag.orchestrator import IntelligenceOrchestrator, create_orchestrator

__all__ = ['IntelligenceOrchestrator', 'create_orchestrator']
