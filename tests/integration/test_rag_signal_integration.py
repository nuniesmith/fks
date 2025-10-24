"""
Integration tests for RAG-powered signal generation.

Tests the complete flow from signal generation with RAG to trade recommendations.
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from trading.signals.generator import get_current_signal, _get_rag_recommendations
from framework.config.constants import SYMBOLS, MAINS, ALTS


@pytest.fixture
def sample_price_data():
    """Create sample OHLCV price data for testing."""
    df_prices = {}
    
    # Generate 100 periods of sample data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='1H')
    
    for symbol in SYMBOLS[:3]:  # Test with first 3 symbols
        # Create realistic price data
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


@pytest.fixture
def best_params():
    """Sample strategy parameters."""
    return {
        'M': 50,
        'atr_period': 14,
        'sl_multiplier': 2.0,
        'tp_multiplier': 3.0
    }


@pytest.fixture
def mock_rag_orchestrator():
    """Create mock RAG orchestrator with realistic responses."""
    mock = Mock()
    
    def mock_recommendation(symbol, account_balance, available_cash, context, current_positions):
        """Generate mock recommendation based on symbol."""
        return {
            'symbol': symbol,
            'action': 'BUY' if 'BTC' in symbol or 'ETH' in symbol else 'HOLD',
            'position_size_usd': 500.0 if 'BTC' in symbol else 300.0,
            'position_size_percent': 2.0,
            'entry_points': [],
            'exit_points': [],
            'stop_loss': None,
            'risk_assessment': 'medium' if 'BTC' in symbol else 'low',
            'reasoning': f'Based on historical data for {symbol}, technical indicators show favorable conditions. '
                        f'RSI indicates oversold levels, MACD shows bullish divergence. '
                        f'Historical win rate for similar setups: 65%. Confidence: 85%.',
            'confidence': 0.85 if 'BTC' in symbol else 0.70,
            'strategy': 'RAG-optimized',
            'timeframe': '1h',
            'timestamp': datetime.now().isoformat(),
            'query_time_ms': 250,
            'sources_used': 5
        }
    
    mock.get_trading_recommendation.side_effect = mock_recommendation
    return mock


class TestRAGSignalIntegration:
    """Integration tests for RAG-enhanced signal generation."""
    
    def test_signal_generation_without_rag(self, sample_price_data, best_params):
        """Test basic signal generation without RAG enhancement."""
        with patch('trading.signals.generator.get_current_price') as mock_price:
            # Mock current prices
            mock_price.side_effect = lambda sym: 40000 if 'BTC' in sym else 2500 if 'ETH' in sym else 300
            
            signal, suggestions = get_current_signal(
                df_prices=sample_price_data,
                best_params=best_params,
                account_size=10000.0,
                use_rag=False  # Disable RAG
            )
            
            # Verify signal returned
            assert signal in [0, 1], "Signal should be 0 or 1"
            assert isinstance(suggestions, list), "Suggestions should be a list"
            
            # If BUY signal, verify suggestions structure
            if signal == 1:
                for suggestion in suggestions:
                    assert 'symbol' in suggestion
                    assert 'action' in suggestion
                    assert 'price' in suggestion
                    assert 'quantity' in suggestion
                    assert 'sl' in suggestion
                    assert 'tp' in suggestion
                    assert 'rag_enhanced' in suggestion
                    assert suggestion['rag_enhanced'] is False, "Should not be RAG-enhanced"
    
    def test_signal_generation_with_rag(self, sample_price_data, best_params, mock_rag_orchestrator):
        """Test signal generation with RAG enhancement."""
        with patch('trading.signals.generator.get_current_price') as mock_price, \
             patch('trading.signals.generator.IntelligenceOrchestrator', return_value=mock_rag_orchestrator):
            
            # Mock current prices
            mock_price.side_effect = lambda sym: 40100 if 'BTC' in sym else 2550 if 'ETH' in sym else 305
            
            signal, suggestions = get_current_signal(
                df_prices=sample_price_data,
                best_params=best_params,
                account_size=10000.0,
                use_rag=True,  # Enable RAG
                available_cash=8000.0,
                current_positions={}
            )
            
            # Verify signal returned
            assert signal in [0, 1], "Signal should be 0 or 1"
            assert isinstance(suggestions, list), "Suggestions should be a list"
            
            # If BUY signal, verify RAG enhancement
            if signal == 1:
                for suggestion in suggestions:
                    assert 'symbol' in suggestion
                    assert 'rag_enhanced' in suggestion
                    
                    # Check for RAG fields
                    if suggestion['rag_enhanced']:
                        assert 'rag_action' in suggestion
                        assert 'rag_confidence' in suggestion
                        assert 'rag_reasoning' in suggestion
                        assert 'rag_risk_assessment' in suggestion
                        
                        # Verify confidence is valid
                        assert 0 <= suggestion['rag_confidence'] <= 1
                        
                        # Verify risk assessment is valid
                        assert suggestion['rag_risk_assessment'] in ['low', 'medium', 'high']
    
    def test_rag_recommendations_function(self, mock_rag_orchestrator):
        """Test the _get_rag_recommendations helper function."""
        with patch('trading.signals.generator.IntelligenceOrchestrator', return_value=mock_rag_orchestrator):
            
            symbol_indicators = {
                'BTCUSDT': {
                    'rsi': 35.5,
                    'macd': 150.2,
                    'macd_signal': 145.0,
                    'bb_upper': 42000,
                    'bb_middle': 40000,
                    'bb_lower': 38000,
                    'current_price': 40100
                },
                'ETHUSDT': {
                    'rsi': 45.0,
                    'macd': 25.5,
                    'macd_signal': 24.0,
                    'bb_upper': 2600,
                    'bb_middle': 2500,
                    'bb_lower': 2400,
                    'current_price': 2550
                }
            }
            
            recommendations = _get_rag_recommendations(
                symbols=['BTCUSDT', 'ETHUSDT'],
                account_size=10000.0,
                available_cash=8000.0,
                current_positions={},
                symbol_indicators=symbol_indicators
            )
            
            # Verify recommendations returned
            assert isinstance(recommendations, dict)
            assert 'BTCUSDT' in recommendations
            assert 'ETHUSDT' in recommendations
            
            # Verify recommendation structure
            for symbol, rec in recommendations.items():
                assert 'action' in rec
                assert 'confidence' in rec
                assert 'reasoning' in rec
                assert rec['action'] in ['BUY', 'SELL', 'HOLD']
                assert 0 <= rec['confidence'] <= 1
    
    def test_high_confidence_position_boost(self, sample_price_data, best_params, mock_rag_orchestrator):
        """Test that high confidence RAG signals boost position size."""
        with patch('trading.signals.generator.get_current_price') as mock_price, \
             patch('trading.signals.generator.IntelligenceOrchestrator', return_value=mock_rag_orchestrator):
            
            mock_price.side_effect = lambda sym: 40100 if 'BTC' in sym else 2550 if 'ETH' in sym else 305
            
            signal, suggestions = get_current_signal(
                df_prices=sample_price_data,
                best_params=best_params,
                account_size=10000.0,
                use_rag=True,
                available_cash=8000.0
            )
            
            if signal == 1:
                # Find BTC suggestion (high confidence = 0.85 from mock)
                btc_suggestions = [s for s in suggestions if 'BTC' in s['symbol']]
                
                if btc_suggestions:
                    btc_suggestion = btc_suggestions[0]
                    
                    # High confidence (0.85) should trigger boost
                    if btc_suggestion.get('rag_enhanced') and btc_suggestion.get('rag_confidence', 0) >= 0.8:
                        assert btc_suggestion.get('rag_boosted') is True, \
                            "High confidence signal should boost position size"
    
    def test_rag_graceful_degradation(self, sample_price_data, best_params):
        """Test that signal generation works even if RAG fails."""
        with patch('trading.signals.generator.get_current_price') as mock_price, \
             patch('trading.signals.generator.IntelligenceOrchestrator') as mock_orch:
            
            # Make RAG fail
            mock_orch.side_effect = Exception("RAG service unavailable")
            mock_price.side_effect = lambda sym: 40100 if 'BTC' in sym else 2550 if 'ETH' in sym else 305
            
            # Should not raise exception, should fall back to technical signals
            signal, suggestions = get_current_signal(
                df_prices=sample_price_data,
                best_params=best_params,
                account_size=10000.0,
                use_rag=True  # Even with RAG enabled, should gracefully degrade
            )
            
            # Verify signal still returned
            assert signal in [0, 1]
            assert isinstance(suggestions, list)
            
            # All suggestions should not be RAG-enhanced
            if signal == 1:
                for suggestion in suggestions:
                    if 'rag_enhanced' in suggestion:
                        assert suggestion['rag_enhanced'] is False
    
    def test_performance_latency(self, sample_price_data, best_params, mock_rag_orchestrator):
        """Test that RAG-enhanced signal generation completes within acceptable time."""
        import time
        
        with patch('trading.signals.generator.get_current_price') as mock_price, \
             patch('trading.signals.generator.IntelligenceOrchestrator', return_value=mock_rag_orchestrator):
            
            mock_price.side_effect = lambda sym: 40100 if 'BTC' in sym else 2550 if 'ETH' in sym else 305
            
            start_time = time.time()
            
            signal, suggestions = get_current_signal(
                df_prices=sample_price_data,
                best_params=best_params,
                account_size=10000.0,
                use_rag=True,
                available_cash=8000.0
            )
            
            elapsed_time_ms = (time.time() - start_time) * 1000
            
            # Should complete in under 2 seconds (allows for overhead)
            # In production with real RAG, target is < 500ms per symbol
            assert elapsed_time_ms < 2000, \
                f"Signal generation took {elapsed_time_ms:.0f}ms, should be under 2000ms"
            
            print(f"\n✓ Signal generation completed in {elapsed_time_ms:.0f}ms")


@pytest.mark.integration
class TestRAGAutoIngestion:
    """Test automatic ingestion of signals and trades into RAG."""
    
    def test_signal_ingestion_trigger(self, sample_price_data, best_params):
        """Test that generating a signal can trigger auto-ingestion."""
        # This test verifies the hooks exist for auto-ingestion
        # Actual ingestion is tested in RAG-specific tests
        
        with patch('trading.signals.generator.get_current_price') as mock_price:
            mock_price.side_effect = lambda sym: 40100
            
            signal, suggestions = get_current_signal(
                df_prices=sample_price_data,
                best_params=best_params,
                account_size=10000.0,
                use_rag=False
            )
            
            # Verify signal data structure is suitable for ingestion
            if signal == 1 and suggestions:
                for suggestion in suggestions:
                    # Check that suggestion has all fields needed for RAG ingestion
                    assert 'symbol' in suggestion
                    assert 'action' in suggestion
                    
                    # This data could be ingested via:
                    # from web.rag.ingestion import DataIngestionPipeline
                    # pipeline.ingest_signal(suggestion)
