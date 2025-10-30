"""Feature engineering module for FKS trading platform.

This module provides comprehensive feature engineering capabilities for trading strategies,
including technical indicators, statistical features, and market microstructure features.
"""

from .feature_processor import FeatureProcessor, create_feature_matrix

__all__ = ["FeatureProcessor", "create_feature_matrix"]