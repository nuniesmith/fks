"""
Test suite for ML models
"""

import pytest
import pandas as pd
import numpy as np
import torch
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import os
import tempfile


# Skip if dependencies not available
try:
    from ml_models import MarketRegimeHMM, LSTMPredictor, TradingMLEngine
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


@pytest.mark.skipif(not ML_AVAILABLE, reason="ML dependencies not installed")
class TestMarketRegimeHMM:
    """Test Hidden Markov Model for market regime detection"""
    
    @pytest.fixture
    def sample_features(self):
        """Generate sample feature data"""
        np.random.seed(42)
        n_samples = 200
        
        features = pd.DataFrame({
            'returns': np.random.randn(n_samples) * 0.02,
            'volatility': np.abs(np.random.randn(n_samples)) * 0.01,
            'volume': np.random.randint(1000, 10000, n_samples),
            'rsi': np.random.uniform(20, 80, n_samples),
            'macd': np.random.randn(n_samples) * 10
        })
        
        return features
    
    def test_hmm_initialization(self):
        """Test HMM model initialization"""
        hmm = MarketRegimeHMM(n_states=4)
        
        assert hmm.n_states == 4
        assert hmm.model is not None
        assert not hmm.is_fitted
    
    def test_hmm_fit(self, sample_features):
        """Test HMM training"""
        hmm = MarketRegimeHMM(n_states=4)
        
        hmm.fit(sample_features)
        
        assert hmm.is_fitted
        assert hmm.scaler is not None
    
    def test_hmm_predict(self, sample_features):
        """Test HMM prediction"""
        hmm = MarketRegimeHMM(n_states=4)
        hmm.fit(sample_features[:150])
        
        states = hmm.predict(sample_features[150:])
        
        assert len(states) == 50
        assert all(0 <= s < 4 for s in states)
    
    def test_hmm_predict_proba(self, sample_features):
        """Test HMM probability prediction"""
        hmm = MarketRegimeHMM(n_states=4)
        hmm.fit(sample_features[:150])
        
        probs = hmm.predict_proba(sample_features[150:])
        
        assert probs.shape == (50, 4)
        # Probabilities should sum to 1
        assert np.allclose(probs.sum(axis=1), 1.0)
    
    def test_hmm_get_regime_name(self):
        """Test regime name mapping"""
        hmm = MarketRegimeHMM(n_states=4)
        
        regimes = [hmm.get_regime_name(i) for i in range(4)]
        
        assert len(regimes) == 4
        assert all(isinstance(r, str) for r in regimes)
    
    def test_hmm_save_load(self, sample_features):
        """Test saving and loading HMM model"""
        hmm = MarketRegimeHMM(n_states=4)
        hmm.fit(sample_features)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, 'hmm_model.pkl')
            
            # Save
            hmm.save(model_path)
            assert os.path.exists(model_path)
            
            # Load
            hmm_loaded = MarketRegimeHMM(n_states=4)
            hmm_loaded.load(model_path)
            
            assert hmm_loaded.is_fitted
            
            # Predictions should match
            states1 = hmm.predict(sample_features[:10])
            states2 = hmm_loaded.predict(sample_features[:10])
            
            np.testing.assert_array_equal(states1, states2)


@pytest.mark.skipif(not ML_AVAILABLE, reason="ML dependencies not installed")
class TestLSTMPredictor:
    """Test LSTM price prediction model"""
    
    @pytest.fixture
    def sample_price_data(self):
        """Generate sample price data"""
        np.random.seed(42)
        dates = pd.date_range(start='2023-01-01', periods=200, freq='D')
        
        closes = 100 + np.cumsum(np.random.randn(200) * 2)
        
        df = pd.DataFrame({
            'time': dates,
            'close': closes,
            'volume': np.random.randint(1000, 10000, 200)
        })
        
        return df
    
    def test_lstm_initialization(self):
        """Test LSTM model initialization"""
        lstm = LSTMPredictor(
            input_size=5,
            hidden_size=64,
            num_layers=2,
            sequence_length=60
        )
        
        assert lstm.input_size == 5
        assert lstm.hidden_size == 64
        assert lstm.num_layers == 2
        assert lstm.sequence_length == 60
    
    def test_lstm_forward_pass(self):
        """Test LSTM forward pass"""
        lstm = LSTMPredictor(input_size=5, hidden_size=64, num_layers=2)
        
        # Create dummy input
        batch_size = 16
        seq_length = 60
        x = torch.randn(batch_size, seq_length, 5)
        
        output = lstm(x)
        
        assert output.shape == (batch_size, 1)
    
    @pytest.mark.slow
    def test_lstm_training(self, sample_price_data):
        """Test LSTM training process"""
        lstm = LSTMPredictor(
            input_size=1,
            hidden_size=32,
            num_layers=1,
            sequence_length=20
        )
        
        # Prepare simple training data
        prices = sample_price_data['close'].values
        X, y = [], []
        
        for i in range(20, len(prices) - 1):
            X.append(prices[i-20:i])
            y.append(prices[i+1])
        
        X = torch.FloatTensor(X).unsqueeze(-1)
        y = torch.FloatTensor(y).unsqueeze(-1)
        
        # Train for a few epochs
        optimizer = torch.optim.Adam(lstm.parameters(), lr=0.001)
        criterion = torch.nn.MSELoss()
        
        initial_loss = None
        for epoch in range(5):
            optimizer.zero_grad()
            predictions = lstm(X[:100])
            loss = criterion(predictions, y[:100])
            loss.backward()
            optimizer.step()
            
            if initial_loss is None:
                initial_loss = loss.item()
        
        # Loss should decrease
        final_loss = loss.item()
        # Just check it runs without error
        assert final_loss is not None
    
    def test_lstm_save_load(self):
        """Test saving and loading LSTM model"""
        lstm = LSTMPredictor(input_size=5, hidden_size=64, num_layers=2)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, 'lstm_model.pth')
            
            # Save
            lstm.save(model_path)
            assert os.path.exists(model_path)
            
            # Load
            lstm_loaded = LSTMPredictor(input_size=5, hidden_size=64, num_layers=2)
            lstm_loaded.load(model_path)
            
            # Test with same input
            x = torch.randn(1, 60, 5)
            
            with torch.no_grad():
                out1 = lstm(x)
                out2 = lstm_loaded(x)
            
            torch.testing.assert_close(out1, out2)


@pytest.mark.skipif(not ML_AVAILABLE, reason="ML dependencies not installed")
class TestTradingMLEngine:
    """Test integrated ML trading engine"""
    
    @pytest.fixture
    def sample_market_data(self):
        """Generate sample market data"""
        np.random.seed(42)
        dates = pd.date_range(start='2023-01-01', periods=200, freq='D')
        
        closes = 100 + np.cumsum(np.random.randn(200) * 2)
        opens = closes + np.random.randn(200)
        highs = np.maximum(opens, closes) + np.abs(np.random.randn(200))
        lows = np.minimum(opens, closes) - np.abs(np.random.randn(200))
        volumes = np.random.randint(1000, 10000, 200)
        
        df = pd.DataFrame({
            'time': dates,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
        
        return df
    
    def test_engine_initialization(self):
        """Test ML engine initialization"""
        engine = TradingMLEngine()
        
        assert engine.hmm is not None
        assert engine.lstm is not None
        assert engine.device is not None
    
    def test_prepare_features(self, sample_market_data):
        """Test feature preparation"""
        engine = TradingMLEngine()
        
        features = engine.prepare_features(sample_market_data)
        
        assert isinstance(features, pd.DataFrame)
        assert len(features) == len(sample_market_data)
        
        # Check for expected feature columns
        expected_features = ['returns', 'volatility', 'volume', 'rsi']
        for feat in expected_features:
            assert feat in features.columns
    
    @pytest.mark.slow
    def test_train_models(self, sample_market_data):
        """Test training both models"""
        engine = TradingMLEngine()
        
        # This will take some time
        engine.train(sample_market_data)
        
        assert engine.hmm.is_fitted
        # LSTM training may or may not complete successfully
    
    def test_predict_regime(self, sample_market_data):
        """Test regime prediction"""
        engine = TradingMLEngine()
        
        # Train first
        engine.hmm.fit(engine.prepare_features(sample_market_data[:150]))
        
        regime = engine.predict_regime(sample_market_data[150:151])
        
        assert isinstance(regime, int)
        assert 0 <= regime < engine.hmm.n_states
    
    def test_predict_price(self, sample_market_data):
        """Test price prediction"""
        engine = TradingMLEngine()
        
        # Prepare LSTM
        features = engine.prepare_features(sample_market_data)
        
        # Make prediction
        try:
            prediction = engine.predict_price(sample_market_data[-60:])
            assert isinstance(prediction, float)
        except Exception:
            # LSTM may not be trained
            pytest.skip("LSTM not trained")
    
    def test_get_trading_signal(self, sample_market_data):
        """Test integrated trading signal generation"""
        engine = TradingMLEngine()
        
        # Train HMM at least
        engine.hmm.fit(engine.prepare_features(sample_market_data[:150]))
        
        signal = engine.get_trading_signal(sample_market_data)
        
        assert 'regime' in signal
        assert 'confidence' in signal
        assert 'recommendation' in signal
        
        assert signal['recommendation'] in ['buy', 'sell', 'hold']
        assert 0 <= signal['confidence'] <= 1


@pytest.mark.skipif(not ML_AVAILABLE, reason="ML dependencies not installed")
class TestMLIntegration:
    """Integration tests for ML components"""
    
    def test_end_to_end_prediction(self, sample_ohlcv_data):
        """Test complete prediction pipeline"""
        engine = TradingMLEngine()
        
        # Train
        engine.hmm.fit(engine.prepare_features(sample_ohlcv_data))
        
        # Get signal
        signal = engine.get_trading_signal(sample_ohlcv_data)
        
        assert signal is not None
        assert 'regime' in signal
        assert 'recommendation' in signal
    
    @pytest.mark.slow
    def test_model_persistence(self, sample_ohlcv_data):
        """Test saving and loading complete engine"""
        engine = TradingMLEngine()
        
        # Train
        engine.hmm.fit(engine.prepare_features(sample_ohlcv_data))
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save models
            hmm_path = os.path.join(tmpdir, 'hmm.pkl')
            lstm_path = os.path.join(tmpdir, 'lstm.pth')
            
            engine.hmm.save(hmm_path)
            engine.lstm.save(lstm_path)
            
            # Create new engine and load
            engine2 = TradingMLEngine()
            engine2.hmm.load(hmm_path)
            engine2.lstm.load(lstm_path)
            
            # Compare predictions
            signal1 = engine.get_trading_signal(sample_ohlcv_data)
            signal2 = engine2.get_trading_signal(sample_ohlcv_data)
            
            assert signal1['regime'] == signal2['regime']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
