#!/usr/bin/env python3
"""
Test script for quality monitoring pipeline.

This script tests the complete quality monitoring pipeline:
1. Generate sample market data
2. Run quality checks with QualityCollector
3. Verify Prometheus metrics are updated
4. Verify TimescaleDB storage (if enabled)
5. Query continuous aggregates

Usage:
    python scripts/test_quality_pipeline.py
    
Environment variables:
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, '/app/src')

def create_sample_data(symbol='BTCUSDT', rows=100):
    """Create sample OHLCV data for testing."""
    import numpy as np
    
    print(f"\n📊 Creating sample data for {symbol} ({rows} rows)...")
    
    # Create realistic sample data
    base_price = 50000.0
    timestamps = pd.date_range(end=datetime.now(), periods=rows, freq='1min')
    
    # Generate realistic price movements
    np.random.seed(42)
    price_changes = np.random.normal(0, 100, rows)
    closes = base_price + np.cumsum(price_changes)
    
    data = pd.DataFrame({
        'timestamp': timestamps,
        'open': closes + np.random.normal(0, 20, rows),
        'high': closes + np.abs(np.random.normal(50, 30, rows)),
        'low': closes - np.abs(np.random.normal(50, 30, rows)),
        'close': closes,
        'volume': np.random.uniform(100, 1000, rows)
    })
    
    print(f"✅ Created {len(data)} rows")
    print(f"   Time range: {data['timestamp'].min()} to {data['timestamp'].max()}")
    print(f"   Columns: {list(data.columns)}")
    print(f"\nSample data:")
    print(data.head(3))
    
    return data


def test_quality_check(data):
    """Test quality check with QualityCollector."""
    try:
        from metrics.quality_collector import create_quality_collector
        
        print("\n\n🔍 Running quality checks...")
        
        # Create collector with storage disabled for now
        collector = create_quality_collector(enable_storage=False)
        
        # Run quality check
        quality_score = collector.check_quality('BTCUSDT', data)
        
        print(f"\n✅ Quality Check Complete!")
        print(f"   Overall Score: {quality_score.overall_score:.2f}/100")
        print(f"   Status: {quality_score.status}")
        
        if hasattr(quality_score, 'component_scores'):
            print(f"\n   Component Scores:")
            for component, score in quality_score.component_scores.items():
                print(f"      {component}: {score:.2f}")
        
        # Check for issues
        if hasattr(quality_score, 'issues') and quality_score.issues:
            print(f"\n   Issues Detected ({len(quality_score.issues)}):")
            for issue in quality_score.issues[:5]:  # Show first 5
                print(f"      - {issue}")
        
        # Check for recommendations
        if hasattr(quality_score, 'recommendations') and quality_score.recommendations:
            print(f"\n   Recommendations ({len(quality_score.recommendations)}):")
            for rec in quality_score.recommendations[:3]:  # Show first 3
                print(f"      - {rec}")
        
        return quality_score
        
    except Exception as e:
        print(f"❌ Error running quality check: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_with_storage(data):
    """Test quality check with TimescaleDB storage enabled."""
    try:
        from metrics.quality_collector import create_quality_collector
        
        print("\n\n💾 Testing with TimescaleDB storage...")
        
        # Create collector with storage enabled
        collector = create_quality_collector(enable_storage=True)
        
        # Run quality check
        quality_score = collector.check_quality('BTCUSDT', data)
        
        print(f"✅ Quality check completed and stored")
        print(f"   Overall Score: {quality_score.overall_score:.2f}/100")
        
        # Query the stored data
        print("\n📊 Querying stored data...")
        
        from database.connection import (
            get_latest_quality_score,
            get_quality_history,
            get_quality_statistics
        )
        
        # Get latest score
        latest = get_latest_quality_score('BTCUSDT')
        if latest:
            print(f"\n   Latest Score in DB: {latest.get('overall_score', 'N/A'):.2f}")
            print(f"   Timestamp: {latest.get('time', 'N/A')}")
            print(f"   Status: {latest.get('status', 'N/A')}")
        else:
            print("   ⚠️  No data found in database (storage may have failed)")
        
        # Get recent history
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)
        history = get_quality_history('BTCUSDT', start_time=start_time, limit=10)
        print(f"\n   Recent history (last hour): {len(history)} records")
        
        # Get statistics
        stats = get_quality_statistics('BTCUSDT', start_time=start_time)
        if stats:
            print(f"\n   Statistics (last hour):")
            print(f"      Avg Score: {stats.get('avg_score', 'N/A'):.2f}")
            print(f"      Min Score: {stats.get('min_score', 'N/A'):.2f}")
            print(f"      Max Score: {stats.get('max_score', 'N/A'):.2f}")
            print(f"      Count: {stats.get('count', 'N/A')}")
        
        return quality_score
        
    except Exception as e:
        print(f"❌ Error with storage test: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_prometheus_metrics():
    """Check if Prometheus metrics are being exposed."""
    try:
        from prometheus_client import REGISTRY
        
        print("\n\n📈 Checking Prometheus Metrics...")
        
        # Get all metrics
        metrics = list(REGISTRY.collect())
        
        quality_metrics = [m for m in metrics if 'quality' in m.name]
        
        print(f"   Total metrics registered: {len(metrics)}")
        print(f"   Quality-related metrics: {len(quality_metrics)}")
        
        if quality_metrics:
            print(f"\n   Quality Metrics:")
            for metric in quality_metrics[:10]:  # Show first 10
                print(f"      - {metric.name}")
                # Show sample values
                for sample in list(metric.samples)[:2]:
                    print(f"        {sample.name} = {sample.value}")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Could not check metrics: {e}")
        return False


def main():
    """Run the complete pipeline test."""
    print("=" * 60)
    print("Quality Monitoring Pipeline Test")
    print("=" * 60)
    
    # Step 1: Create sample data
    data = create_sample_data(symbol='BTCUSDT', rows=100)
    if data is None:
        print("\n❌ Pipeline test failed: Could not create data")
        return 1
    
    # Step 2: Run quality check (no storage)
    quality_score = test_quality_check(data)
    if quality_score is None:
        print("\n❌ Pipeline test failed: Quality check failed")
        return 1
    
    # Step 3: Check Prometheus metrics
    check_prometheus_metrics()
    
    # Step 4: Test with storage (optional - may fail if DB not available)
    try:
        test_with_storage(data)
    except Exception as e:
        print(f"\n⚠️  Storage test skipped (DB may not be available): {e}")
    
    print("\n" + "=" * 60)
    print("✅ Pipeline Test Complete!")
    print("=" * 60)
    
    return 0


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
