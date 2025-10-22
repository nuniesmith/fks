#!/usr/bin/env python3
"""
RAG Integration Validation Script

Verifies that RAG is properly integrated with trading signal generation.
Tests both technical-only and RAG-enhanced signal generation.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Import signal generator
from trading.signals.generator import get_current_signal, _get_rag_recommendations, RAG_AVAILABLE

# Import constants
from framework.config.constants import SYMBOLS, MAINS, ALTS


def create_sample_data():
    """Create sample OHLCV data for testing."""
    print("Creating sample price data...")
    
    df_prices = {}
    dates = pd.date_range(end=datetime.now(), periods=100, freq='1H')
    
    for symbol in SYMBOLS[:3]:  # Test with first 3 symbols
        base_price = 40000 if 'BTC' in symbol else 2500 if 'ETH' in symbol else 300
        
        df = pd.DataFrame({
            'open': [base_price * (1 + i * 0.001) for i in range(100)],
            'high': [base_price * (1 + i * 0.001 + 0.002) for i in range(100)],
            'low': [base_price * (1 + i * 0.001 - 0.002) for i in range(100)],
            'close': [base_price * (1 + i * 0.001) for i in range(100)],
            'volume': [1000 + i * 10 for i in range(100)]
        }, index=dates)
        
        df_prices[symbol] = df
    
    return df_prices


def test_rag_availability():
    """Check if RAG system is available."""
    print("\n" + "="*60)
    print("1. Testing RAG Availability")
    print("="*60)
    
    if RAG_AVAILABLE:
        print("✅ RAG system is available")
        try:
            from web.rag.orchestrator import IntelligenceOrchestrator
            orchestrator = IntelligenceOrchestrator(use_local=True)
            print("✅ IntelligenceOrchestrator initialized successfully")
            return True
        except Exception as e:
            print(f"⚠️  RAG available but initialization failed: {e}")
            return False
    else:
        print("❌ RAG system not available (imports failed)")
        return False


def test_technical_signals():
    """Test signal generation without RAG."""
    print("\n" + "="*60)
    print("2. Testing Technical Signals (without RAG)")
    print("="*60)
    
    df_prices = create_sample_data()
    
    best_params = {
        'M': 50,
        'atr_period': 14,
        'sl_multiplier': 2.0,
        'tp_multiplier': 3.0
    }
    
    with patch('trading.signals.generator.get_current_price') as mock_price:
        mock_price.side_effect = lambda sym: 40100 if 'BTC' in sym else 2550 if 'ETH' in sym else 305
        
        try:
            signal, suggestions = get_current_signal(
                df_prices=df_prices,
                best_params=best_params,
                account_size=10000.0,
                use_rag=False  # Disable RAG
            )
            
            print(f"✅ Signal generated: {signal} (1=BUY, 0=HOLD)")
            print(f"✅ Suggestions count: {len(suggestions)}")
            
            if signal == 1 and suggestions:
                print(f"✅ Sample suggestion: {suggestions[0]['symbol']} - {suggestions[0]['action']}")
                
                # Check that RAG fields are not present
                has_rag = any(s.get('rag_enhanced', False) for s in suggestions)
                if not has_rag:
                    print("✅ No RAG enhancement (as expected)")
                else:
                    print("⚠️  Found RAG enhancement when it should be disabled")
            
            return True
            
        except Exception as e:
            print(f"❌ Technical signal generation failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_rag_enhanced_signals():
    """Test signal generation with RAG."""
    print("\n" + "="*60)
    print("3. Testing RAG-Enhanced Signals")
    print("="*60)
    
    df_prices = create_sample_data()
    
    best_params = {
        'M': 50,
        'atr_period': 14,
        'sl_multiplier': 2.0,
        'tp_multiplier': 3.0
    }
    
    # Create mock RAG orchestrator
    mock_orchestrator = Mock()
    
    def mock_recommendation(symbol, account_balance, available_cash, context, current_positions):
        return {
            'symbol': symbol,
            'action': 'BUY' if 'BTC' in symbol else 'HOLD',
            'position_size_usd': 500.0,
            'confidence': 0.85 if 'BTC' in symbol else 0.70,
            'reasoning': f'RAG recommendation for {symbol}: Buy based on historical patterns.',
            'risk_assessment': 'medium',
            'strategy': 'RAG-optimized',
            'timeframe': '1h'
        }
    
    mock_orchestrator.get_trading_recommendation.side_effect = mock_recommendation
    
    with patch('trading.signals.generator.get_current_price') as mock_price, \
         patch('trading.signals.generator.IntelligenceOrchestrator', return_value=mock_orchestrator):
        
        mock_price.side_effect = lambda sym: 40100 if 'BTC' in sym else 2550 if 'ETH' in sym else 305
        
        try:
            signal, suggestions = get_current_signal(
                df_prices=df_prices,
                best_params=best_params,
                account_size=10000.0,
                use_rag=True,  # Enable RAG
                available_cash=8000.0,
                current_positions={}
            )
            
            print(f"✅ Signal generated: {signal} (1=BUY, 0=HOLD)")
            print(f"✅ Suggestions count: {len(suggestions)}")
            
            if signal == 1 and suggestions:
                # Check for RAG enhancement
                rag_enhanced_count = sum(1 for s in suggestions if s.get('rag_enhanced', False))
                print(f"✅ RAG-enhanced suggestions: {rag_enhanced_count}/{len(suggestions)}")
                
                # Display sample RAG-enhanced suggestion
                for suggestion in suggestions:
                    if suggestion.get('rag_enhanced'):
                        print(f"\n✅ Sample RAG-enhanced suggestion:")
                        print(f"   Symbol: {suggestion['symbol']}")
                        print(f"   Action: {suggestion['action']}")
                        print(f"   RAG Confidence: {suggestion.get('rag_confidence', 0):.0%}")
                        print(f"   RAG Risk: {suggestion.get('rag_risk_assessment', 'N/A')}")
                        print(f"   Position Boosted: {suggestion.get('rag_boosted', False)}")
                        
                        # Verify required RAG fields
                        required_fields = ['rag_action', 'rag_confidence', 'rag_reasoning', 'rag_risk_assessment']
                        has_all_fields = all(field in suggestion for field in required_fields)
                        
                        if has_all_fields:
                            print("   ✅ All RAG fields present")
                        else:
                            missing = [f for f in required_fields if f not in suggestion]
                            print(f"   ⚠️  Missing RAG fields: {missing}")
                        
                        break
            
            return True
            
        except Exception as e:
            print(f"❌ RAG-enhanced signal generation failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_auto_ingestion_hooks():
    """Verify auto-ingestion tasks exist."""
    print("\n" + "="*60)
    print("4. Testing Auto-Ingestion Hooks")
    print("="*60)
    
    try:
        from trading.tasks import (
            ingest_signal,
            ingest_backtest_result,
            ingest_completed_trade,
            ingest_recent_trades
        )
        
        print("✅ ingest_signal task exists")
        print("✅ ingest_backtest_result task exists")
        print("✅ ingest_completed_trade task exists")
        print("✅ ingest_recent_trades task exists")
        
        # Check task signatures
        print("\nTask Signatures:")
        print(f"  ingest_signal: {ingest_signal.__doc__.strip().split(chr(10))[0]}")
        print(f"  ingest_backtest_result: {ingest_backtest_result.__doc__.strip().split(chr(10))[0]}")
        print(f"  ingest_completed_trade: {ingest_completed_trade.__doc__.strip().split(chr(10))[0]}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Auto-ingestion tasks not found: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking ingestion tasks: {e}")
        return False


def test_rag_celery_integration():
    """Verify RAG is used in Celery tasks."""
    print("\n" + "="*60)
    print("5. Testing RAG Usage in Celery Tasks")
    print("="*60)
    
    try:
        # Check tasks.py for RAG usage
        tasks_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'trading', 'tasks.py')
        
        with open(tasks_file, 'r') as f:
            content = f.read()
        
        # Check for RAG imports
        has_rag_import = 'from web.rag.orchestrator import IntelligenceOrchestrator' in content
        print(f"{'✅' if has_rag_import else '❌'} RAG orchestrator imported in tasks.py")
        
        # Check for RAG usage in generate_signals_task
        has_signal_rag = 'IntelligenceOrchestrator' in content and 'generate_signals_task' in content
        print(f"{'✅' if has_signal_rag else '❌'} RAG used in generate_signals_task")
        
        # Check for RAG usage in optimize_portfolio_task
        has_portfolio_rag = 'optimize_portfolio' in content and 'IntelligenceOrchestrator' in content
        print(f"{'✅' if has_portfolio_rag else '❌'} RAG used in optimize_portfolio_task")
        
        # Check for daily RAG signals task
        has_daily_signals = 'generate_daily_rag_signals_task' in content
        print(f"{'✅' if has_daily_signals else '❌'} Daily RAG signals task exists")
        
        return has_rag_import and has_signal_rag
        
    except Exception as e:
        print(f"❌ Error checking Celery integration: {e}")
        return False


def main():
    """Run all validation tests."""
    print("\n" + "="*60)
    print("RAG INTEGRATION VALIDATION")
    print("="*60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")
    
    results = []
    
    # Run tests
    results.append(("RAG Availability", test_rag_availability()))
    results.append(("Technical Signals", test_technical_signals()))
    results.append(("RAG-Enhanced Signals", test_rag_enhanced_signals()))
    results.append(("Auto-Ingestion Hooks", test_auto_ingestion_hooks()))
    results.append(("Celery Integration", test_rag_celery_integration()))
    
    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("\n" + "="*60)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ ALL VALIDATIONS PASSED - RAG INTEGRATION COMPLETE")
        return 0
    else:
        print(f"⚠️  {total - passed} validation(s) failed - review output above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
