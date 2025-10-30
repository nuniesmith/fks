"""
Quality Collector - Wrapper for QualityScorer with Prometheus Metrics

This module provides a collector that wraps the QualityScorer and automatically
updates Prometheus metrics after each quality check. It includes:
- Timer decorator for measuring quality check duration
- Batch collection for multiple symbols
- Automatic metric updates for all validator results
- Integration with TimescaleDB for historical analysis

Usage:
    from metrics.quality_collector import QualityCollector
    
    collector = QualityCollector()
    result = await collector.check_quality('BTCUSDT', market_data)
    # Metrics are automatically updated
    
    # Batch collection
    results = await collector.check_quality_batch(['BTCUSDT', 'ETHUSDT'], data_dict)
"""

import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from validators.quality_scorer import QualityScorer
from validators.outlier_detector import OutlierDetector
from validators.freshness_monitor import FreshnessMonitor
from validators.completeness_validator import CompletenessValidator
from validators.models import QualityScore, OutlierResult, FreshnessResult, CompletenessResult

from metrics.quality_metrics import (
    update_metrics_from_quality_score,
    update_metrics_from_outlier_results,  # Takes List[OutlierResult]
    update_metrics_from_freshness_result,
    update_metrics_from_completeness_result,
    record_quality_check_duration,
    update_outlier_metrics,  # For single outlier updates
)

logger = logging.getLogger(__name__)


class QualityCollector:
    """
    Collector that wraps QualityScorer and automatically updates Prometheus metrics.
    
    This class:
    - Wraps the QualityScorer from Phase 5.5
    - Automatically updates Prometheus metrics after each quality check
    - Records duration metrics for performance monitoring
    - Supports batch collection for multiple symbols
    - Provides integration points for TimescaleDB storage
    
    Attributes:
        quality_scorer (QualityScorer): The wrapped quality scorer
        outlier_detector (OutlierDetector): Outlier detection validator
        freshness_monitor (FreshnessMonitor): Freshness monitoring validator
        completeness_validator (CompletenessValidator): Completeness validation validator
        enable_metrics (bool): Whether to update Prometheus metrics
        enable_storage (bool): Whether to store results in TimescaleDB
    """
    
    def __init__(
        self,
        outlier_threshold: float = 3.0,
        freshness_threshold: timedelta = timedelta(minutes=15),
        completeness_threshold: float = 0.9,
        enable_metrics: bool = True,
        enable_storage: bool = False
    ):
        """
        Initialize the QualityCollector.
        
        Args:
            outlier_threshold: Z-score threshold for outlier detection
            freshness_threshold: Maximum data age before considered stale
            completeness_threshold: Minimum completeness percentage
            enable_metrics: Whether to update Prometheus metrics
            enable_storage: Whether to store results in TimescaleDB
        """
        self.outlier_detector = OutlierDetector(z_threshold=outlier_threshold)
        self.freshness_monitor = FreshnessMonitor(max_age=freshness_threshold)
        self.completeness_validator = CompletenessValidator(threshold=completeness_threshold)
        
        self.quality_scorer = QualityScorer(
            outlier_detector=self.outlier_detector,
            freshness_monitor=self.freshness_monitor,
            completeness_validator=self.completeness_validator
        )
        
        self.enable_metrics = enable_metrics
        self.enable_storage = enable_storage
        
        logger.info(
            "QualityCollector initialized: outlier_threshold=%.2f, "
            "freshness_threshold=%s, completeness_threshold=%.2f, "
            "metrics=%s, storage=%s",
            outlier_threshold,
            freshness_threshold,
            completeness_threshold,
            enable_metrics,
            enable_storage
        )
    
    def check_quality(
        self,
        symbol: str,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ) -> QualityScore:
        """
        Check data quality for a single symbol and update metrics.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            data: Market data dictionary with OHLCV fields
            timestamp: Data timestamp (defaults to now)
        
        Returns:
            QualityScore: Comprehensive quality assessment
        
        Side Effects:
            - Updates Prometheus metrics if enable_metrics=True
            - Stores results in TimescaleDB if enable_storage=True
        """
        start_time = time.time()
        
        try:
            # Run quality check
            result = self.quality_scorer.check_quality(symbol, data, timestamp)
            
            # Record duration
            duration = time.time() - start_time
            if self.enable_metrics:
                record_quality_check_duration(symbol, duration)
            
            # Update Prometheus metrics
            if self.enable_metrics:
                self._update_all_metrics(symbol, result)
            
            # Store in TimescaleDB
            if self.enable_storage:
                self._store_result(symbol, result)
            
            logger.debug(
                "Quality check completed: symbol=%s, score=%.2f, duration=%.3fs",
                symbol, result.score, duration
            )
            
            return result
            
        except Exception as e:
            logger.error("Quality check failed for %s: %s", symbol, e, exc_info=True)
            raise
    
    async def check_quality_batch(
        self,
        symbols: List[str],
        data_dict: Dict[str, Dict[str, Any]],
        timestamp: Optional[datetime] = None
    ) -> Dict[str, QualityScore]:
        """
        Check data quality for multiple symbols in batch.
        
        Args:
            symbols: List of trading pair symbols
            data_dict: Dictionary mapping symbol -> market data
            timestamp: Data timestamp (defaults to now)
        
        Returns:
            Dictionary mapping symbol -> QualityScore
        
        Side Effects:
            - Updates Prometheus metrics for all symbols if enable_metrics=True
            - Stores all results in TimescaleDB if enable_storage=True
        """
        results = {}
        
        for symbol in symbols:
            if symbol not in data_dict:
                logger.warning("No data for symbol %s, skipping", symbol)
                continue
            
            try:
                result = self.check_quality(symbol, data_dict[symbol], timestamp)
                results[symbol] = result
            except Exception as e:
                logger.error("Batch quality check failed for %s: %s", symbol, e)
                # Continue with other symbols
                continue
        
        logger.info(
            "Batch quality check completed: %d/%d symbols processed",
            len(results), len(symbols)
        )
        
        return results
    
    def check_outliers(
        self,
        symbol: str,
        data: Dict[str, Any]
    ) -> OutlierResult:
        """
        Check for outliers and update metrics.
        
        Args:
            symbol: Trading pair symbol
            data: Market data dictionary
        
        Returns:
            OutlierResult: Outlier detection results
        """
        result = self.outlier_detector.detect_outliers(symbol, data)
        
        if self.enable_metrics and result.has_outliers:
            # Update metrics for each outlier field
            for field in result.outlier_fields:
                # Handle both enum and string severity
                severity_value = result.severity.value if hasattr(result.severity, 'value') else result.severity
                update_outlier_metrics(
                    symbol=symbol,
                    field=field,
                    severity=severity_value
                )
        
        return result
    
    def check_freshness(
        self,
        symbol: str,
        timestamp: datetime,
        current_time: Optional[datetime] = None
    ) -> FreshnessResult:
        """
        Check data freshness and update metrics.
        
        Args:
            symbol: Trading pair symbol
            timestamp: Data timestamp
            current_time: Current time (defaults to now)
        
        Returns:
            FreshnessResult: Freshness check results
        """
        result = self.freshness_monitor.check_freshness(symbol, timestamp, current_time)
        
        if self.enable_metrics:
            update_metrics_from_freshness_result(symbol, result)
        
        return result
    
    def check_completeness(
        self,
        symbol: str,
        data: Dict[str, Any]
    ) -> CompletenessResult:
        """
        Check data completeness and update metrics.
        
        Args:
            symbol: Trading pair symbol
            data: Market data dictionary
        
        Returns:
            CompletenessResult: Completeness validation results
        """
        result = self.completeness_validator.validate_completeness(symbol, data)
        
        if self.enable_metrics:
            update_metrics_from_completeness_result(symbol, result)
        
        return result
    
    def _update_all_metrics(self, symbol: str, result: QualityScore) -> None:
        """
        Update all Prometheus metrics from a QualityScore.
        
        Args:
            symbol: Trading pair symbol
            result: Quality score to update metrics from
        """
        # Update overall quality score (pass just the object)
        update_metrics_from_quality_score(result)
        
        # Update individual component metrics
        if result.outlier_result and result.outlier_result.has_outliers:
            # Update metrics for each outlier field
            for field in result.outlier_result.outlier_fields:
                # Handle both enum and string severity
                severity_value = (result.outlier_result.severity.value 
                                if hasattr(result.outlier_result.severity, 'value') 
                                else result.outlier_result.severity)
                update_outlier_metrics(
                    symbol=symbol,
                    field=field,
                    severity=severity_value
                )
        
        if result.freshness_result:
            update_metrics_from_freshness_result(result.freshness_result)
        
        if result.completeness_result:
            update_metrics_from_completeness_result(result.completeness_result)
    
    def _store_result(self, symbol: str, result: QualityScore) -> None:
        """
        Store quality check result in TimescaleDB.
        
        Args:
            symbol: Trading pair symbol
            result: Quality score to store
        
        Note:
            This is a placeholder for TimescaleDB integration.
            Will be implemented in Phase 5.6 Task 3 (Pipeline Integration).
        """
        # TODO: Implement TimescaleDB storage in Phase 5.6 Task 3
        logger.debug("TimescaleDB storage not yet implemented (placeholder)")
        pass


def create_quality_collector(
    outlier_threshold: float = 3.0,
    freshness_minutes: int = 15,
    completeness_threshold: float = 0.9,
    enable_metrics: bool = True,
    enable_storage: bool = False
) -> QualityCollector:
    """
    Factory function to create a QualityCollector with standard settings.
    
    Args:
        outlier_threshold: Z-score threshold for outliers (default: 3.0)
        freshness_minutes: Maximum data age in minutes (default: 15)
        completeness_threshold: Minimum completeness percentage (default: 0.9)
        enable_metrics: Whether to update Prometheus metrics (default: True)
        enable_storage: Whether to store in TimescaleDB (default: False)
    
    Returns:
        QualityCollector: Configured collector instance
    
    Example:
        >>> collector = create_quality_collector(freshness_minutes=30)
        >>> result = collector.check_quality('BTCUSDT', market_data)
    """
    return QualityCollector(
        outlier_threshold=outlier_threshold,
        freshness_threshold=timedelta(minutes=freshness_minutes),
        completeness_threshold=completeness_threshold,
        enable_metrics=enable_metrics,
        enable_storage=enable_storage
    )
