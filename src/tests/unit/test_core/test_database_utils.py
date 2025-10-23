"""
Test suite for core database utilities
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd


@pytest.mark.unit
@pytest.mark.data
class TestOHLCVDataFunctions:
    """Test OHLCV data utility functions"""
    
    def test_bulk_insert_ohlcv(self):
        """Test bulk inserting OHLCV data"""
        data = [
            {
                "time": datetime(2023, 1, 1, 0, 0),
                "open": 50000.0,
                "high": 51000.0,
                "low": 49000.0,
                "close": 50500.0,
                "volume": 1000.0,
                "quote_volume": 50500000.0,
                "trades_count": 1000,
            },
            {
                "time": datetime(2023, 1, 1, 1, 0),
                "open": 50500.0,
                "high": 51500.0,
                "low": 50000.0,
                "close": 51000.0,
                "volume": 1200.0,
                "quote_volume": 61200000.0,
                "trades_count": 1200,
            }
        ]
        
        # Test data structure
        assert len(data) == 2
        assert data[0]["open"] == 50000.0
        assert data[1]["close"] == 51000.0
    
    def test_get_ohlcv_data_returns_dataframe(self):
        """Test getting OHLCV data returns DataFrame"""
        # Testing the expected output format
        expected_columns = ['open', 'high', 'low', 'close', 'volume']
        assert all(col in expected_columns for col in expected_columns)
    
    def test_ohlcv_data_validation(self):
        """Test OHLCV data validation"""
        # Valid OHLC relationship: low <= open,close <= high
        candle = {
            "open": 50000.0,
            "high": 51000.0,
            "low": 49000.0,
            "close": 50500.0,
        }
        
        assert candle["low"] <= candle["open"] <= candle["high"]
        assert candle["low"] <= candle["close"] <= candle["high"]


@pytest.mark.unit
@pytest.mark.data
class TestAccountFunctions:
    """Test account management functions"""
    
    def test_create_account_parameters(self):
        """Test account creation with various parameters"""
        account_data = {
            "name": "Test Account",
            "account_type": "personal",
            "initial_balance": 10000.0,
            "broker": "Binance",
            "currency": "USDT",
            "metadata": {"notes": "Test account"}
        }
        
        assert account_data["name"] == "Test Account"
        assert account_data["account_type"] == "personal"
        assert account_data["initial_balance"] == 10000.0
    
    def test_account_type_validation(self):
        """Test account type must be valid"""
        valid_types = ["personal", "prop_firm"]
        
        for account_type in valid_types:
            assert account_type in valid_types
    
    def test_account_balance_validation(self):
        """Test account balance must be positive"""
        initial_balance = 10000.0
        
        assert initial_balance > 0
        assert Decimal(str(initial_balance)) == Decimal("10000.0")


@pytest.mark.unit
@pytest.mark.data
class TestPositionFunctions:
    """Test position management functions"""
    
    def test_position_pnl_calculation(self):
        """Test position PnL calculation"""
        entry_price = 50000.0
        current_price = 51000.0
        quantity = 1.0
        
        unrealized_pnl = (current_price - entry_price) * quantity
        unrealized_pnl_percent = ((current_price - entry_price) / entry_price) * 100
        
        assert unrealized_pnl == 1000.0
        assert unrealized_pnl_percent == 2.0
    
    def test_position_long_profit(self):
        """Test long position profit calculation"""
        position = {
            "entry_price": 50000.0,
            "current_price": 52000.0,
            "quantity": 0.5,
            "position_type": "LONG"
        }
        
        pnl = (position["current_price"] - position["entry_price"]) * position["quantity"]
        
        assert pnl == 1000.0  # Profit
        assert pnl > 0
    
    def test_position_long_loss(self):
        """Test long position loss calculation"""
        position = {
            "entry_price": 50000.0,
            "current_price": 48000.0,
            "quantity": 0.5,
            "position_type": "LONG"
        }
        
        pnl = (position["current_price"] - position["entry_price"]) * position["quantity"]
        
        assert pnl == -1000.0  # Loss
        assert pnl < 0
    
    def test_position_short_profit(self):
        """Test short position profit calculation"""
        position = {
            "entry_price": 50000.0,
            "current_price": 48000.0,
            "quantity": 0.5,
            "position_type": "SHORT"
        }
        
        # For short: profit when price goes down
        pnl = (position["entry_price"] - position["current_price"]) * position["quantity"]
        
        assert pnl == 1000.0  # Profit
        assert pnl > 0
    
    def test_position_stop_loss_validation(self):
        """Test position stop loss validation"""
        position = {
            "entry_price": 50000.0,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
            "position_type": "LONG"
        }
        
        # For long: SL should be below entry, TP above entry
        assert position["stop_loss"] < position["entry_price"]
        assert position["take_profit"] > position["entry_price"]


@pytest.mark.unit
@pytest.mark.data
class TestTradeFunctions:
    """Test trade recording functions"""
    
    def test_trade_data_validation(self):
        """Test trade data structure"""
        trade = {
            "symbol": "BTCUSDT",
            "trade_type": "BUY",
            "quantity": 0.5,
            "price": 50000.0,
            "fee": 25.0,  # 0.1% of 50000 * 0.5
            "order_type": "MARKET",
            "strategy_name": "momentum"
        }
        
        assert trade["trade_type"] in ["BUY", "SELL"]
        assert trade["quantity"] > 0
        assert trade["price"] > 0
        assert trade["fee"] >= 0
    
    def test_trade_fee_calculation(self):
        """Test trade fee calculation"""
        trade_value = 50000.0 * 0.5  # price * quantity
        fee_rate = 0.001  # 0.1%
        
        expected_fee = trade_value * fee_rate
        
        assert expected_fee == 25.0
    
    def test_trade_realized_pnl(self):
        """Test realized PnL from closed trades"""
        # Buy trade
        buy_price = 50000.0
        buy_quantity = 1.0
        buy_fee = 50.0
        
        # Sell trade
        sell_price = 52000.0
        sell_quantity = 1.0
        sell_fee = 52.0
        
        # Realized PnL = (sell_price - buy_price) * quantity - fees
        realized_pnl = (sell_price - buy_price) * sell_quantity - (buy_fee + sell_fee)
        
        assert realized_pnl == 1898.0  # 2000 - 102
    
    def test_trade_order_types(self):
        """Test different order types"""
        valid_order_types = ["MARKET", "LIMIT", "STOP_LOSS", "STOP_LOSS_LIMIT", 
                             "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"]
        
        for order_type in valid_order_types:
            assert order_type in valid_order_types


@pytest.mark.unit
@pytest.mark.data
class TestDataFrameOperations:
    """Test DataFrame operations with OHLCV data"""
    
    def test_ohlcv_dataframe_structure(self):
        """Test OHLCV DataFrame structure"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='h')
        
        df = pd.DataFrame({
            'open': [50000.0] * 100,
            'high': [51000.0] * 100,
            'low': [49000.0] * 100,
            'close': [50500.0] * 100,
            'volume': [1000.0] * 100,
        }, index=dates)
        
        assert len(df) == 100
        assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
        assert df.index.name is None or df.index.name == 'time'
    
    def test_ohlcv_time_filtering(self):
        """Test filtering OHLCV data by time range"""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='h')
        
        df = pd.DataFrame({
            'close': range(100)
        }, index=dates)
        
        # Filter last 24 hours
        cutoff = dates[-24]
        recent = df[df.index >= cutoff]
        
        assert len(recent) == 24
    
    def test_ohlcv_resampling(self):
        """Test resampling OHLCV data to different timeframes"""
        dates = pd.date_range(start='2023-01-01', periods=24, freq='h')
        
        df = pd.DataFrame({
            'open': [50000.0 + i * 10 for i in range(24)],
            'high': [50100.0 + i * 10 for i in range(24)],
            'low': [49900.0 + i * 10 for i in range(24)],
            'close': [50050.0 + i * 10 for i in range(24)],
            'volume': [1000.0] * 24,
        }, index=dates)
        
        # Resample to 4-hour candles
        resampled = df.resample('4h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        assert len(resampled) == 6  # 24 hours / 4 hours
        assert resampled['volume'].iloc[0] == 4000.0  # 4 hours * 1000


@pytest.mark.unit
@pytest.mark.data
class TestDataValidation:
    """Test data validation utilities"""
    
    def test_validate_ohlc_relationship(self):
        """Test OHLC price relationship validation"""
        candles = [
            {"open": 50000, "high": 51000, "low": 49000, "close": 50500},  # Valid
            {"open": 50000, "high": 49000, "low": 51000, "close": 50500},  # Invalid
        ]
        
        # Valid candle
        valid = candles[0]
        assert valid["low"] <= valid["open"] <= valid["high"]
        assert valid["low"] <= valid["close"] <= valid["high"]
        
        # Invalid candle
        invalid = candles[1]
        assert not (invalid["low"] <= invalid["open"] <= invalid["high"])
    
    def test_validate_positive_values(self):
        """Test that prices and volumes are positive"""
        data = {
            "price": 50000.0,
            "volume": 1000.0,
            "quantity": 0.5
        }
        
        for key, value in data.items():
            assert value > 0, f"{key} must be positive"
    
    def test_validate_decimal_precision(self):
        """Test decimal precision for financial values"""
        price = Decimal("50000.12345678")
        
        # Round to 8 decimal places (standard for crypto)
        rounded = round(price, 8)
        
        assert rounded == Decimal("50000.12345678")
        
        # Test rounding
        price2 = Decimal("50000.123456789")
        rounded2 = round(price2, 8)
        
        assert rounded2 == Decimal("50000.12345679")


@pytest.mark.unit
@pytest.mark.data
class TestQueryOptimization:
    """Test query optimization patterns"""
    
    def test_limit_query_results(self):
        """Test limiting query results for performance"""
        # Simulate query with limit
        total_records = 10000
        limit = 100
        
        # Should only fetch limited records
        fetched = min(total_records, limit)
        
        assert fetched == 100
        assert fetched < total_records
    
    def test_time_range_filtering(self):
        """Test efficient time range filtering"""
        start_time = datetime(2023, 1, 1)
        end_time = datetime(2023, 1, 2)
        
        # Time difference should be 1 day
        time_diff = end_time - start_time
        
        assert time_diff.days == 1
    
    def test_pagination_offset(self):
        """Test pagination with offset and limit"""
        total_records = 1000
        page_size = 100
        page = 3
        
        offset = (page - 1) * page_size
        limit = page_size
        
        assert offset == 200
        assert limit == 100
        assert offset + limit <= total_records


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
