"""Caching infrastructure for FKS app service.

This module provides Redis-based caching for:
- Engineered features (from FeatureProcessor)
- API responses (EODHD fundamentals data)
- Market data queries
- ML model predictions

Phase: AI Enhancement Plan Phase 5.4 - Redis Caching Layer
"""

from .feature_cache import FeatureCache, get_cache_instance

__all__ = ["FeatureCache", "get_cache_instance"]
