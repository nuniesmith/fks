"""
Unit tests for ASMBTR prediction Celery task.

Tests:
1. ASMBTRPredictionService initialization
2. State encoder creation
3. Tick fetching (mocked)
4. State updates
5. Prediction generation
6. Redis storage
7. Full prediction cycle
8. Error handling and retries
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = MagicMock()
    redis_mock.setex = MagicMock()
    return redis_mock


@pytest.fixture
def prediction_service(mock_redis):
    """Create ASMBTRPredictionService with mocked Redis."""
    with patch("redis.from_url", return_value=mock_redis):
        from src.services.app.src.tasks.asmbtr_prediction import (
            ASMBTRPredictionService,
        )

        service = ASMBTRPredictionService(
            redis_url="redis://localhost:6379/1",
            depth=8,
            confidence_threshold=Decimal("0.60"),
            decay_rate=Decimal("0.95"),
            min_observations=5,
        )
        return service


class TestASMBTRPredictionService:
    """Tests for ASMBTRPredictionService."""

    def test_initialization(self, prediction_service):
        """Test service initialization."""
        assert prediction_service.depth == 8
        assert prediction_service.confidence_threshold == Decimal("0.60")
        assert prediction_service.decay_rate == Decimal("0.95")
        assert prediction_service.min_observations == 5
        assert len(prediction_service.encoders) == 0
        assert len(prediction_service.prediction_tables) == 0

    def test_get_or_create_encoder(self, prediction_service):
        """Test encoder creation."""
        symbol = "BTC/USDT"

        # First call creates encoder
        encoder1 = prediction_service._get_or_create_encoder(symbol)
        assert symbol in prediction_service.encoders
        assert encoder1.depth == 8

        # Second call returns same encoder
        encoder2 = prediction_service._get_or_create_encoder(symbol)
        assert encoder1 is encoder2

    def test_get_or_create_predictor(self, prediction_service):
        """Test predictor creation."""
        symbol = "BTC/USDT"

        # First call creates predictor
        predictor1 = prediction_service._get_or_create_predictor(symbol)
        assert symbol in prediction_service.prediction_tables
        assert predictor1.decay_rate == Decimal("0.95")

        # Second call returns same predictor
        predictor2 = prediction_service._get_or_create_predictor(symbol)
        assert predictor1 is predictor2

    def test_update_state(self, prediction_service):
        """Test state updates with ticks."""
        symbol = "BTC/USDT"
        ticks = [
            {
                "timestamp": datetime.now(timezone.utc),
                "last": Decimal("100000.00"),
                "volume": Decimal("10.5"),
            },
            {
                "timestamp": datetime.now(timezone.utc),
                "last": Decimal("100100.00"),
                "volume": Decimal("12.3"),
            },
            {
                "timestamp": datetime.now(timezone.utc),
                "last": Decimal("99900.00"),
                "volume": Decimal("8.7"),
            },
        ]

        # Update state
        state = prediction_service.update_state(symbol, ticks)

        # Verify encoder exists
        assert symbol in prediction_service.encoders
        # State may be None if not enough movements (depth=8 requires 8 price changes)
        # This is expected behavior

    def test_update_state_empty_ticks(self, prediction_service):
        """Test state update with no ticks."""
        state = prediction_service.update_state("BTC/USDT", [])
        assert state is None

    def test_generate_prediction_no_state(self, prediction_service):
        """Test prediction with unknown state."""
        symbol = "BTC/USDT"
        state = "10101010"

        # No observations for this state
        prediction = prediction_service.generate_prediction(symbol, state)
        assert prediction is None

    def test_store_prediction(self, prediction_service, mock_redis):
        """Test Redis storage."""
        symbol = "BTC/USDT"
        prediction = {
            "symbol": symbol,
            "state": "10101010",
            "prediction": 1,
            "confidence": 0.75,
            "up_prob": 0.75,
            "down_prob": 0.25,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        prediction_service.store_prediction(symbol, prediction)

        # Verify Redis was called
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == f"asmbtr:predictions:{symbol}"
        assert args[1] == 120  # TTL
        # Verify JSON structure
        stored_data = json.loads(args[2])
        assert stored_data["symbol"] == symbol
        assert stored_data["confidence"] == 0.75

    @patch("src.services.app.src.tasks.asmbtr_prediction.ccxt")
    def test_fetch_latest_ticks(self, mock_ccxt, prediction_service):
        """Test tick fetching from CCXT."""
        symbol = "BTC/USDT"

        # Mock Binance exchange
        mock_exchange = MagicMock()
        mock_exchange.fetch_ohlcv.return_value = [
            [1609459200000, 29000, 29100, 28900, 29050, 100],  # OHLCV candle
            [1609459260000, 29050, 29200, 29000, 29150, 120],
        ]
        mock_ccxt.binance.return_value = mock_exchange

        # Fetch ticks
        ticks = prediction_service.fetch_latest_ticks(symbol, limit=2)

        assert len(ticks) == 2
        assert ticks[0]["last"] == Decimal("29050")
        assert ticks[1]["last"] == Decimal("29150")
        assert "timestamp" in ticks[0]
        assert "volume" in ticks[0]

    @patch("src.services.app.src.tasks.asmbtr_prediction.ccxt")
    def test_fetch_latest_ticks_error(self, mock_ccxt, prediction_service):
        """Test tick fetching with CCXT error."""
        mock_ccxt.binance.side_effect = Exception("API error")

        ticks = prediction_service.fetch_latest_ticks("BTC/USDT", limit=10)
        assert ticks == []

    @patch.object(
        ASMBTRPredictionService := __import__(
            "src.services.app.src.tasks.asmbtr_prediction",
            fromlist=["ASMBTRPredictionService"],
        ).ASMBTRPredictionService,
        "fetch_latest_ticks",
    )
    def test_run_prediction_cycle(self, mock_fetch, prediction_service):
        """Test full prediction cycle."""
        symbols = ["BTC/USDT"]

        # Mock tick data
        mock_fetch.return_value = [
            {
                "timestamp": datetime.now(timezone.utc),
                "last": Decimal("100000"),
                "volume": Decimal("10"),
            },
            {
                "timestamp": datetime.now(timezone.utc),
                "last": Decimal("100100"),
                "volume": Decimal("12"),
            },
        ]

        # Run cycle (may not generate prediction due to lack of observations)
        prediction_service.run_prediction_cycle(symbols)

        # Verify fetch was called
        mock_fetch.assert_called_once_with("BTC/USDT", limit=100)


class TestPredictASMBTRTask:
    """Tests for predict_asmbtr_task Celery task."""

    @patch("src.services.app.src.tasks.asmbtr_prediction.ASMBTRPredictionService")
    def test_task_success(self, mock_service_class):
        """Test successful task execution."""
        from src.services.app.src.tasks.asmbtr_prediction import predict_asmbtr_task

        # Mock service
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # Run task
        result = predict_asmbtr_task(symbols=["BTC/USDT", "ETH/USDT"])

        assert result["status"] == "success"
        assert result["symbols"] == ["BTC/USDT", "ETH/USDT"]
        assert "timestamp" in result
        mock_service.run_prediction_cycle.assert_called_once_with(
            ["BTC/USDT", "ETH/USDT"]
        )

    @patch("src.services.app.src.tasks.asmbtr_prediction.ASMBTRPredictionService")
    def test_task_default_symbols(self, mock_service_class):
        """Test task with default symbols."""
        from src.services.app.src.tasks.asmbtr_prediction import predict_asmbtr_task

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = predict_asmbtr_task()

        assert result["symbols"] == ["BTC/USDT", "ETH/USDT"]

    @patch("src.services.app.src.tasks.asmbtr_prediction.ASMBTRPredictionService")
    def test_task_retry_on_error(self, mock_service_class):
        """Test task retry on failure."""
        from src.services.app.src.tasks.asmbtr_prediction import predict_asmbtr_task

        # Mock service to raise error
        mock_service = MagicMock()
        mock_service.run_prediction_cycle.side_effect = Exception("Test error")
        mock_service_class.return_value = mock_service

        # Create mock self for retry
        mock_self = Mock()
        mock_self.request.retries = 0
        mock_self.retry.side_effect = Exception("Retry called")

        with pytest.raises(Exception, match="Retry called"):
            predict_asmbtr_task(mock_self, symbols=["BTC/USDT"])

        # Verify retry was called with backoff
        mock_self.retry.assert_called_once()
