#!/usr/bin/env python3
"""Run ASMBTR optimization with real market data.

This script loads real market data and runs Optuna optimization to find
the best hyperparameters for the ASMBTR strategy.

Usage:
    python scripts/run_asmbtr_optimization.py --data data/market_data/latest.json --trials 100
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path (works in Docker container)
sys.path.insert(0, '/app/src')

from strategies.asmbtr.optimize import ASMBTROptimizer


def main():
    parser = argparse.ArgumentParser(description='Run ASMBTR optimization with real data')
    parser.add_argument('--data', type=str, required=True,
                       help='Path to market data JSON file')
    parser.add_argument('--trials', type=int, default=100,
                       help='Number of optimization trials (default: 100)')
    parser.add_argument('--metric', type=str, default='calmar_ratio',
                       choices=['calmar_ratio', 'sharpe_ratio', 'total_return_pct'],
                       help='Metric to optimize (default: calmar_ratio)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output JSON file for results (default: docs/asmbtr_real_data_optimization.json)')
    
    args = parser.parse_args()
    
    # Load data
    print(f"📊 Loading market data from {args.data}...")
    with open(args.data, 'r') as f:
        data = json.load(f)
    
    ticks = data['ticks']
    stats = data.get('statistics', {})
    
    # Convert OHLCV format to tick format (close -> last, timestamp str -> datetime)
    print(f"🔄 Converting OHLCV data to tick format...")
    from datetime import datetime as dt
    from decimal import Decimal
    
    converted_ticks = []
    for tick in ticks:
        converted_ticks.append({
            'last': Decimal(str(tick['close'])),  # ASMBTR expects 'last' not 'close'
            'timestamp': dt.fromisoformat(tick['timestamp'])
        })
    
    print(f"✅ Loaded {len(converted_ticks)} ticks")
    print(f"   Symbol: {stats.get('symbol', 'UNKNOWN')}")
    print(f"   Price Range: {stats.get('min_price', 0):.2f} - {stats.get('max_price', 0):.2f}")
    print(f"   Volatility: {stats.get('volatility', 0):.6f}")
    print(f"   Trend: {stats.get('trend', 'UNKNOWN')} ({stats.get('price_change_pct', 0):.2f}%)")
    print(f"   Autocorrelation (lag 1): {stats.get('autocorr_lag1', 0):.3f}")
    
    # Create optimizer
    print(f"\n🔧 Initializing ASMBTROptimizer...")
    print(f"   Trials: {args.trials}")
    print(f"   Metric: {args.metric}")
    
    optimizer = ASMBTROptimizer(
        train_data=converted_ticks,  # Use converted ticks
        n_trials=args.trials,
        optimize_metric=args.metric
    )
    
    # Run optimization
    print(f"\n🚀 Starting optimization (this may take a few minutes)...\n")
    best_params = optimizer.optimize()
    
    # Print results
    print(f"\n{'='*60}")
    print(f"✅ OPTIMIZATION COMPLETE")
    print(f"{'='*60}")
    print(f"\n📈 Best {args.metric}: {best_params['value']:.4f}")
    print(f"\n⚙️  Best Parameters:")
    for param, value in best_params['params'].items():
        print(f"   {param}: {value}")
    
    # Get summary
    summary = optimizer.get_optimization_summary()
    print(f"\n📊 Summary:")
    print(f"   Completed Trials: {summary['completed_trials']}")
    print(f"   Best Trial: #{summary.get('best_trial', 'N/A')}")
    print(f"   Total Runtime: {summary.get('optimization_duration_seconds', 0):.2f}s")
    
    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        docs_dir = Path(__file__).parent.parent / 'docs'
        output_path = docs_dir / 'asmbtr_real_data_optimization.json'
    
    # Export results
    optimizer.export_results(output_path)
    print(f"\n💾 Results saved to: {output_path}")
    
    # Print usage hint
    print(f"\n💡 Next steps:")
    print(f"   1. Review results in {output_path}")
    print(f"   2. Run walk-forward validation")
    print(f"   3. Compare against RSI/MACD baselines")
    print(f"   4. Document findings in docs/ASMBTR_OPTIMIZATION.md")


if __name__ == '__main__':
    main()
