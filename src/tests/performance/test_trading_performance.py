"""
Performance tests for trading operations using pytest-benchmark.
Benchmarks signal processing, backtesting, and portfolio operations.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal


@pytest.mark.benchmark
class TestSignalProcessingPerformance:
    """Benchmark signal generation and processing."""

    @pytest.fixture
    def mock_market_data(self):
        """Generate mock market data."""
        return {
            'symbol': 'BTCUSDT',
            'open': 50000.0,
            'high': 51000.0,
            'low': 49500.0,
            'close': 50500.0,
            'volume': 1250.5,
            'timestamp': datetime.utcnow()
        }

    @pytest.fixture
    def mock_indicators(self):
        """Generate mock technical indicators."""
        return {
            'rsi': 65.5,
            'macd': 0.25,
            'macd_signal': 0.20,
            'macd_hist': 0.05,
            'bb_upper': 51000.0,
            'bb_middle': 50000.0,
            'bb_lower': 49000.0,
            'sma_20': 50200.0,
            'ema_12': 50300.0,
            'ema_26': 50100.0
        }

    def test_rsi_calculation_performance(self, benchmark, mock_market_data):
        """Benchmark RSI calculation."""
        def calculate_rsi(prices, period=14):
            """Simple RSI calculation for benchmarking."""
            deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            gains = [d if d > 0 else 0 for d in deltas]
            losses = [-d if d < 0 else 0 for d in deltas]
            
            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period
            
            if avg_loss == 0:
                return 100
            rs = avg_gain / avg_loss
            return 100 - (100 / (1 + rs))
        
        prices = [50000 + (i * 10) for i in range(100)]
        result = benchmark(calculate_rsi, prices)
        
        assert 0 <= result <= 100
        stats = benchmark.stats.stats
        print(f"\nRSI calculation: mean={stats.mean:.6f}s")

    def test_signal_evaluation_performance(self, benchmark, mock_indicators):
        """Benchmark signal evaluation logic."""
        def evaluate_signal(indicators):
            """Evaluate trading signal based on indicators."""
            score = 0
            
            # RSI signal
            if indicators['rsi'] < 30:
                score += 2  # Oversold - buy signal
            elif indicators['rsi'] > 70:
                score -= 2  # Overbought - sell signal
            
            # MACD signal
            if indicators['macd'] > indicators['macd_signal']:
                score += 1
            else:
                score -= 1
            
            # Bollinger Bands
            price = indicators['bb_middle']
            if price < indicators['bb_lower']:
                score += 1
            elif price > indicators['bb_upper']:
                score -= 1
            
            return score
        
        result = benchmark(evaluate_signal, mock_indicators)
        
        assert isinstance(result, int)
        stats = benchmark.stats.stats
        print(f"\nSignal evaluation: mean={stats.mean:.6f}s")

    def test_multi_symbol_signal_generation(self, benchmark):
        """Benchmark signal generation for multiple symbols."""
        def generate_signals_batch(symbols, indicators_map):
            """Generate signals for multiple symbols."""
            signals = []
            for symbol in symbols:
                indicators = indicators_map.get(symbol, {})
                signal = {
                    'symbol': symbol,
                    'type': 'LONG' if indicators.get('rsi', 50) < 40 else 'SHORT',
                    'strength': 0.75,
                    'timestamp': datetime.utcnow()
                }
                signals.append(signal)
            return signals
        
        symbols = [f'SYM{i}USDT' for i in range(50)]
        indicators_map = {
            sym: {'rsi': 30 + i, 'macd': 0.1} for i, sym in enumerate(symbols)
        }
        
        result = benchmark(generate_signals_batch, symbols, indicators_map)
        
        assert len(result) == 50
        stats = benchmark.stats.stats
        print(f"\nBatch signal generation (50 symbols): mean={stats.mean:.4f}s")


@pytest.mark.benchmark
class TestBacktestPerformance:
    """Benchmark backtesting operations."""

    @pytest.fixture
    def mock_historical_data(self):
        """Generate mock historical data."""
        base_price = 50000
        data = []
        for i in range(1000):
            data.append({
                'timestamp': datetime.utcnow() - timedelta(hours=1000-i),
                'open': base_price + (i % 100),
                'high': base_price + (i % 100) + 50,
                'low': base_price + (i % 100) - 50,
                'close': base_price + (i % 100) + 10,
                'volume': 1000 + (i % 500)
            })
        return data

    def test_backtest_single_strategy_performance(self, benchmark, mock_historical_data):
        """Benchmark backtesting a single strategy."""
        def run_backtest(data, initial_capital=10000):
            """Simple backtest execution."""
            capital = initial_capital
            position = None
            trades = []
            
            for i in range(len(data) - 1):
                current = data[i]
                next_bar = data[i + 1]
                
                # Simple strategy: buy when price < 50050, sell when > 50100
                if position is None and current['close'] < 50050:
                    # Enter long
                    position = {
                        'entry_price': next_bar['open'],
                        'quantity': capital / next_bar['open']
                    }
                elif position is not None and current['close'] > 50100:
                    # Exit long
                    exit_price = next_bar['open']
                    pnl = (exit_price - position['entry_price']) * position['quantity']
                    capital += pnl
                    trades.append({
                        'entry': position['entry_price'],
                        'exit': exit_price,
                        'pnl': pnl
                    })
                    position = None
            
            return {
                'final_capital': capital,
                'total_trades': len(trades),
                'total_return': (capital - initial_capital) / initial_capital
            }
        
        result = benchmark(run_backtest, mock_historical_data)
        
        assert 'final_capital' in result
        assert 'total_trades' in result
        stats = benchmark.stats.stats
        print(f"\nBacktest (1000 bars): mean={stats.mean:.4f}s, trades={result['total_trades']}")

    def test_backtest_metrics_calculation_performance(self, benchmark):
        """Benchmark performance metrics calculation."""
        def calculate_metrics(trades):
            """Calculate backtest performance metrics."""
            if not trades:
                return {}
            
            total_pnl = sum(t['pnl'] for t in trades)
            wins = [t for t in trades if t['pnl'] > 0]
            losses = [t for t in trades if t['pnl'] < 0]
            
            win_rate = len(wins) / len(trades) if trades else 0
            avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
            avg_loss = abs(sum(t['pnl'] for t in losses) / len(losses)) if losses else 0
            profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
            
            # Calculate returns for Sharpe ratio
            returns = [t['pnl'] for t in trades]
            avg_return = sum(returns) / len(returns) if returns else 0
            
            # Variance calculation
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns) if returns else 0
            std_dev = variance ** 0.5
            sharpe_ratio = avg_return / std_dev if std_dev > 0 else 0
            
            return {
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'sharpe_ratio': sharpe_ratio,
                'total_trades': len(trades)
            }
        
        # Generate sample trades
        trades = [
            {'pnl': 100 if i % 3 != 0 else -50}
            for i in range(100)
        ]
        
        result = benchmark(calculate_metrics, trades)
        
        assert 'win_rate' in result
        assert 'sharpe_ratio' in result
        stats = benchmark.stats.stats
        print(f"\nMetrics calculation (100 trades): mean={stats.mean:.6f}s")


@pytest.mark.benchmark
class TestPortfolioOperationsPerformance:
    """Benchmark portfolio management operations."""

    @pytest.fixture
    def mock_positions(self):
        """Generate mock positions."""
        return [
            {
                'symbol': f'SYM{i}USDT',
                'quantity': 10 + i,
                'entry_price': 1000 + (i * 10),
                'current_price': 1050 + (i * 10),
                'unrealized_pnl': (50 * (10 + i))
            }
            for i in range(20)
        ]

    def test_portfolio_valuation_performance(self, benchmark, mock_positions):
        """Benchmark portfolio valuation."""
        def calculate_portfolio_value(positions):
            """Calculate total portfolio value."""
            total_value = 0
            total_pnl = 0
            
            for pos in positions:
                position_value = pos['current_price'] * pos['quantity']
                total_value += position_value
                total_pnl += pos['unrealized_pnl']
            
            return {
                'total_value': total_value,
                'total_pnl': total_pnl,
                'position_count': len(positions)
            }
        
        result = benchmark(calculate_portfolio_value, mock_positions)
        
        assert result['position_count'] == 20
        stats = benchmark.stats.stats
        print(f"\nPortfolio valuation (20 positions): mean={stats.mean:.6f}s")

    def test_risk_calculation_performance(self, benchmark, mock_positions):
        """Benchmark portfolio risk calculation."""
        def calculate_portfolio_risk(positions, total_capital=100000):
            """Calculate portfolio risk metrics."""
            total_exposure = sum(p['current_price'] * p['quantity'] for p in positions)
            position_weights = [
                (p['current_price'] * p['quantity']) / total_exposure
                for p in positions
            ]
            
            # Calculate concentration risk
            max_position = max(position_weights) if position_weights else 0
            
            # Calculate leverage
            leverage = total_exposure / total_capital if total_capital > 0 else 0
            
            # Risk per position
            risks = [
                abs(p['unrealized_pnl']) / total_capital
                for p in positions
            ]
            
            return {
                'leverage': leverage,
                'max_concentration': max_position,
                'avg_risk_per_position': sum(risks) / len(risks) if risks else 0
            }
        
        result = benchmark(calculate_portfolio_risk, mock_positions)
        
        assert 'leverage' in result
        stats = benchmark.stats.stats
        print(f"\nRisk calculation (20 positions): mean={stats.mean:.6f}s")

    def test_rebalancing_decision_performance(self, benchmark, mock_positions):
        """Benchmark portfolio rebalancing logic."""
        def determine_rebalancing(positions, target_allocation):
            """Determine rebalancing actions."""
            actions = []
            
            # Calculate current allocation
            total_value = sum(p['current_price'] * p['quantity'] for p in positions)
            
            for pos in positions:
                current_weight = (pos['current_price'] * pos['quantity']) / total_value
                target_weight = target_allocation.get(pos['symbol'], 0.05)  # Default 5%
                
                deviation = abs(current_weight - target_weight)
                
                if deviation > 0.02:  # 2% threshold
                    actions.append({
                        'symbol': pos['symbol'],
                        'action': 'BUY' if current_weight < target_weight else 'SELL',
                        'deviation': deviation
                    })
            
            return actions
        
        target_allocation = {f'SYM{i}USDT': 0.05 for i in range(20)}
        
        result = benchmark(determine_rebalancing, mock_positions, target_allocation)
        
        assert isinstance(result, list)
        stats = benchmark.stats.stats
        print(f"\nRebalancing decisions: mean={stats.mean:.6f}s, actions={len(result)}")


@pytest.mark.benchmark
class TestDataProcessingPerformance:
    """Benchmark data processing operations."""

    def test_market_data_parsing_performance(self, benchmark):
        """Benchmark market data parsing."""
        def parse_market_data(raw_data):
            """Parse raw market data into structured format."""
            parsed = []
            for item in raw_data:
                parsed.append({
                    'symbol': item['s'],
                    'price': float(item['p']),
                    'quantity': float(item['q']),
                    'timestamp': int(item['T'])
                })
            return parsed
        
        # Generate raw data
        raw_data = [
            {'s': f'SYM{i}', 'p': f'{1000+i}', 'q': f'{10+i}', 'T': f'{1700000000+i}'}
            for i in range(1000)
        ]
        
        result = benchmark(parse_market_data, raw_data)
        
        assert len(result) == 1000
        stats = benchmark.stats.stats
        print(f"\nMarket data parsing (1000 items): mean={stats.mean:.4f}s")

    def test_order_book_aggregation_performance(self, benchmark):
        """Benchmark order book aggregation."""
        def aggregate_order_book(bids, asks, levels=10):
            """Aggregate order book to specified levels."""
            def aggregate_side(orders, levels):
                aggregated = {}
                for price, qty in orders:
                    price_level = round(price, -1)  # Round to nearest 10
                    aggregated[price_level] = aggregated.get(price_level, 0) + qty
                
                sorted_levels = sorted(aggregated.items(), key=lambda x: x[0], reverse=True)
                return sorted_levels[:levels]
            
            agg_bids = aggregate_side(bids, levels)
            agg_asks = aggregate_side(asks, levels)
            
            return {
                'bids': agg_bids,
                'asks': agg_asks
            }
        
        # Generate order book data
        bids = [(50000 - i, 1.5 + (i * 0.1)) for i in range(100)]
        asks = [(50000 + i, 1.5 + (i * 0.1)) for i in range(100)]
        
        result = benchmark(aggregate_order_book, bids, asks)
        
        assert len(result['bids']) <= 10
        assert len(result['asks']) <= 10
        stats = benchmark.stats.stats
        print(f"\nOrder book aggregation: mean={stats.mean:.6f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "benchmark", "--benchmark-only"])
