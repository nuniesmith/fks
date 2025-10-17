"""
Simple standalone test to verify the backtest_engine array length fix.
Sets up Django environment properly before testing.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fks_project.settings')
sys.path.insert(0, '/app')
django.setup()

import pandas as pd
import numpy as np
from datetime import datetime

from trading.backtest import run_backtest


def create_sample_data(n_periods=1000):
    """Create sample OHLCV data for testing"""
    dates = pd.date_range(start='2023-01-01', periods=n_periods, freq='1h')
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'AVAXUSDT', 'SUIUSDT']
    df_prices = {}
    
    np.random.seed(42)
    for i, symbol in enumerate(symbols):
        base_price = 100 * (i + 1)
        closes = base_price + np.cumsum(np.random.randn(n_periods) * 2)
        highs = closes + np.abs(np.random.randn(n_periods) * 1)
        lows = closes - np.abs(np.random.randn(n_periods) * 1)
        opens = closes + np.random.randn(n_periods) * 0.5
        volumes = np.random.randint(1000, 10000, n_periods)
        
        df = pd.DataFrame({
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        }, index=dates)
        
        df_prices[symbol] = df
    
    return df_prices


def test_array_length_fix():
    """Test that the array length issue is fixed"""
    print("\n" + "="*70)
    print("TESTING: Array Length Consistency Fix")
    print("="*70)
    
    df_prices = create_sample_data(1000)
    
    symbols_config = {
        'SYMBOLS': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'AVAXUSDT', 'SUIUSDT'],
        'MAINS': ['BTCUSDT', 'ETHUSDT'],
        'ALTS': ['SOLUSDT', 'AVAXUSDT', 'SUIUSDT']
    }
    
    # Test with parameters from the error log
    test_params = [
        {'M': 78, 'atr_period': 29, 'sl_multiplier': 3.93, 'tp_multiplier': 6.39},
        {'M': 35, 'atr_period': 9, 'sl_multiplier': 1.23, 'tp_multiplier': 8.80},
        {'M': 122, 'atr_period': 23, 'sl_multiplier': 1.08, 'tp_multiplier': 9.73},
        {'M': 168, 'atr_period': 10, 'sl_multiplier': 1.73, 'tp_multiplier': 2.65},
        {'M': 64, 'atr_period': 18, 'sl_multiplier': 2.73, 'tp_multiplier': 3.62},
    ]
    
    print(f"\nTesting {len(test_params)} parameter combinations that previously caused errors...")
    
    errors = []
    successes = 0
    
    for i, params in enumerate(test_params):
        try:
            print(f"\nTrial {i}: M={params['M']}, atr_period={params['atr_period']}, "
                  f"sl_multiplier={params['sl_multiplier']:.2f}, tp_multiplier={params['tp_multiplier']:.2f}")
            
            metrics, returns, cum_ret, trades = run_backtest(
                df_prices=df_prices,
                M=params['M'],
                atr_period=params['atr_period'],
                sl_multiplier=params['sl_multiplier'],
                tp_multiplier=params['tp_multiplier'],
                symbols_config=symbols_config,
                fee_rate=0.001
            )
            
            # Verify lengths
            assert len(cum_ret) == 1000, f"cum_ret length {len(cum_ret)} != 1000"
            assert len(returns) == 1000, f"returns length {len(returns)} != 1000"
            assert cum_ret.iloc[0] == 1.0, f"cum_ret should start at 1.0, got {cum_ret.iloc[0]}"
            assert returns.iloc[0] == 0.0, f"First return should be 0, got {returns.iloc[0]}"
            
            print(f"  ✓ SUCCESS - Sharpe: {metrics['Sharpe']:.4f}, Total Return: {metrics['Total Return']:.2%}")
            print(f"  ✓ Array lengths correct: cum_ret={len(cum_ret)}, returns={len(returns)}")
            successes += 1
            
        except Exception as e:
            error_msg = f"Trial {i} FAILED: {type(e).__name__}: {str(e)}"
            print(f"  ✗ {error_msg}")
            errors.append(error_msg)
    
    print("\n" + "="*70)
    print(f"RESULTS: {successes}/{len(test_params)} trials successful")
    
    if errors:
        print(f"\n{len(errors)} ERRORS:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("\n✓ ALL TESTS PASSED! The array length issue is FIXED.")
        return True


def test_edge_cases():
    """Test edge cases"""
    print("\n" + "="*70)
    print("TESTING: Edge Cases")
    print("="*70)
    
    symbols_config = {
        'SYMBOLS': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
        'MAINS': ['BTCUSDT', 'ETHUSDT'],
        'ALTS': ['SOLUSDT']
    }
    
    test_cases = [
        ("Short data (50 periods)", 50),
        ("Medium data (500 periods)", 500),
        ("Long data (2000 periods)", 2000),
    ]
    
    for name, n_periods in test_cases:
        print(f"\nTesting: {name}")
        df_prices = create_sample_data(n_periods)
        
        try:
            metrics, returns, cum_ret, trades = run_backtest(
                df_prices=df_prices,
                M=20,
                atr_period=14,
                sl_multiplier=2.0,
                tp_multiplier=3.0,
                symbols_config=symbols_config,
                fee_rate=0.001
            )
            
            assert len(cum_ret) == n_periods
            assert len(returns) == n_periods
            print(f"  ✓ SUCCESS - Lengths match: {n_periods}")
            
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            return False
    
    print("\n✓ ALL EDGE CASES PASSED!")
    return True


if __name__ == '__main__':
    try:
        # Run tests
        test1_passed = test_array_length_fix()
        test2_passed = test_edge_cases()
        
        # Summary
        print("\n" + "="*70)
        print("FINAL SUMMARY")
        print("="*70)
        if test1_passed and test2_passed:
            print("✓ ALL TESTS PASSED - The backtest_engine fix is working correctly!")
            print("\nThe Optuna optimization should now run without ValueError.")
            sys.exit(0)
        else:
            print("✗ SOME TESTS FAILED - Please review the errors above.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n✗ TEST EXECUTION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
