"""Metrics module for data quality monitoring.

Phase: AI Enhancement Plan Phase 5.6 - Metrics Integration
"""

from .quality_metrics import (
    # Gauge metrics
    quality_score,
    outlier_score,
    freshness_score,
    completeness_score,
    freshness_age_seconds,
    completeness_percentage,
    
    # Counter metrics
    outlier_count,
    stale_data_detected,
    quality_issues_detected,
    quality_checks_performed,
    
    # Histogram metrics
    quality_check_duration,
    
    # Update functions
    update_quality_metrics,
    update_outlier_metrics,
    update_freshness_metrics,
    update_completeness_metrics,
    record_quality_check_duration,
    
    # Batch update functions
    update_metrics_from_quality_score,
    update_metrics_from_outlier_results,
    update_metrics_from_freshness_result,
    update_metrics_from_completeness_result,
)

__all__ = [
    # Gauge metrics
    'quality_score',
    'outlier_score',
    'freshness_score',
    'completeness_score',
    'freshness_age_seconds',
    'completeness_percentage',
    
    # Counter metrics
    'outlier_count',
    'stale_data_detected',
    'quality_issues_detected',
    'quality_checks_performed',
    
    # Histogram metrics
    'quality_check_duration',
    
    # Update functions
    'update_quality_metrics',
    'update_outlier_metrics',
    'update_freshness_metrics',
    'update_completeness_metrics',
    'record_quality_check_duration',
    
    # Batch update functions
    'update_metrics_from_quality_score',
    'update_metrics_from_outlier_results',
    'update_metrics_from_freshness_result',
    'update_metrics_from_completeness_result',
]
