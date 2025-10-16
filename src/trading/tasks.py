"""
Celery tasks for fks trading platform.
Background and scheduled tasks for data fetching, signal generation, and notifications.
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Sum, Avg, Q
from datetime import timedelta
from decimal import Decimal
import requests
import json

from .models import (
    Account,
    Position,
    Trade,
    Signal,
    Strategy,
    BalanceHistory,
    BacktestResult
)
from .utils.data_fetcher import get_historical_data
# from .utils.signal_generator import generate_signals
# from .utils.optimizer import optimize_strategy

logger = get_task_logger(__name__)


# =============================================================================
# DATA FETCHING TASKS
# =============================================================================

@shared_task(bind=True, name='trading.tasks.fetch_latest_prices')
def fetch_latest_prices(self):
    """
    Fetch latest prices for all active symbols.
    Runs every 5 minutes to keep price data current.
    """
    logger.info("Starting fetch_latest_prices task")
    
    try:
        # Get unique symbols from active accounts
        symbols = list(
            Position.objects
            .filter(status='open')
            .values_list('symbol', flat=True)
            .distinct()
        )
        
        if not symbols:
            symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']  # Default symbols
        
        results = {}
        for symbol in symbols:
            try:
                # Fetch latest candles (1h interval, last 2 candles)
                data = get_historical_data(symbol, interval='1h', limit=2)
                
                if data is not None and not data.empty:
                    latest_price = float(data['close'].iloc[-1])
                    
                    # Cache the price for 5 minutes
                    cache_key = f'price_{symbol.replace("/", "_")}'
                    cache.set(cache_key, latest_price, timeout=300)
                    
                    results[symbol] = latest_price
                    logger.info(f"Updated price for {symbol}: ${latest_price:,.2f}")
                    
            except Exception as e:
                logger.error(f"Error fetching price for {symbol}: {str(e)}")
                continue
        
        logger.info(f"Successfully fetched prices for {len(results)} symbols")
        return {
            'success': True,
            'symbols_updated': len(results),
            'prices': results
        }
        
    except Exception as e:
        logger.error(f"Error in fetch_latest_prices: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(bind=True, name='trading.tasks.fetch_historical_data')
def fetch_historical_data(self, symbol, interval='1h', limit=1000):
    """
    Fetch historical data for a specific symbol.
    Can be triggered manually or scheduled.
    """
    logger.info(f"Fetching historical data for {symbol} ({interval}, {limit} candles)")
    
    try:
        data = get_historical_data(symbol, interval=interval, limit=limit)
        
        if data is not None and not data.empty:
            # Cache the data for 1 hour
            cache_key = f'historical_{symbol.replace("/", "_")}_{interval}_{limit}'
            cache.set(cache_key, data.to_dict(), timeout=3600)
            
            logger.info(f"Successfully fetched {len(data)} candles for {symbol}")
            return {
                'success': True,
                'symbol': symbol,
                'candles': len(data),
                'start_date': str(data.index[0]),
                'end_date': str(data.index[-1])
            }
        else:
            logger.warning(f"No data retrieved for {symbol}")
            return {'success': False, 'error': 'No data retrieved'}
            
    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# SIGNAL GENERATION TASKS
# =============================================================================

@shared_task(bind=True, name='trading.tasks.generate_trading_signals')
def generate_trading_signals(self):
    """
    Generate trading signals for all active strategies.
    Runs every 15 minutes.
    """
    logger.info("Starting generate_trading_signals task")
    
    try:
        # Get active strategies
        strategies = Strategy.objects.filter(status='active')
        
        if not strategies.exists():
            logger.warning("No active strategies found")
            return {'success': True, 'signals_generated': 0}
        
        total_signals = 0
        
        for strategy in strategies:
            try:
                # Get parameters from strategy
                params = strategy.parameters or {}
                symbols = params.get('symbols', ['BTC/USDT', 'ETH/USDT'])
                
                for symbol in symbols:
                    # Fetch recent data
                    data = get_historical_data(symbol, interval='1h', limit=200)
                    
                    if data is not None and not data.empty:
                        # Generate signals
                        signal_data = generate_signals(data, params)
                        
                        # Get latest signal
                        latest_signal = signal_data['signal'].iloc[-1]
                        confidence = signal_data['confidence'].iloc[-1]
                        indicators = {
                            'rsi': float(signal_data.get('rsi', [0]).iloc[-1]) if 'rsi' in signal_data else None,
                            'macd': float(signal_data.get('macd', [0]).iloc[-1]) if 'macd' in signal_data else None,
                        }
                        
                        # Only create signal if confidence is high enough
                        if confidence >= 0.5 and latest_signal != 0:
                            signal_type = 'buy' if latest_signal == 1 else 'sell'
                            
                            Signal.objects.create(
                                symbol=symbol,
                                signal_type=signal_type,
                                strategy=strategy,
                                price=float(data['close'].iloc[-1]),
                                confidence=confidence,
                                indicators=indicators
                            )
                            
                            total_signals += 1
                            logger.info(
                                f"Created {signal_type.upper()} signal for {symbol} "
                                f"(confidence: {confidence:.1%})"
                            )
                            
            except Exception as e:
                logger.error(f"Error generating signals for strategy {strategy.name}: {str(e)}")
                continue
        
        logger.info(f"Successfully generated {total_signals} signals")
        return {
            'success': True,
            'signals_generated': total_signals,
            'strategies_processed': strategies.count()
        }
        
    except Exception as e:
        logger.error(f"Error in generate_trading_signals: {str(e)}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# POSITION MANAGEMENT TASKS
# =============================================================================

@shared_task(bind=True, name='trading.tasks.update_open_positions')
def update_open_positions(self):
    """
    Update current prices and P&L for all open positions.
    Runs every 1 minute.
    """
    logger.info("Starting update_open_positions task")
    
    try:
        positions = Position.objects.filter(status='open')
        
        if not positions.exists():
            logger.info("No open positions to update")
            return {'success': True, 'positions_updated': 0}
        
        updated_count = 0
        
        for position in positions:
            try:
                # Get cached price or fetch new one
                cache_key = f'price_{position.symbol.replace("/", "_")}'
                current_price = cache.get(cache_key)
                
                if current_price is None:
                    # Fetch fresh price
                    data = get_historical_data(position.symbol, interval='1m', limit=1)
                    if data is not None and not data.empty:
                        current_price = float(data['close'].iloc[-1])
                        cache.set(cache_key, current_price, timeout=60)
                
                if current_price:
                    # Update position
                    position.current_price = Decimal(str(current_price))
                    
                    # Calculate unrealized P&L
                    if position.side == 'long':
                        position.unrealized_pnl = (
                            (position.current_price - position.entry_price) * 
                            position.quantity
                        )
                    else:  # short
                        position.unrealized_pnl = (
                            (position.entry_price - position.current_price) * 
                            position.quantity
                        )
                    
                    position.save()
                    updated_count += 1
                    
                    # Check stop loss and take profit
                    check_position_triggers.delay(position.id)
                    
            except Exception as e:
                logger.error(f"Error updating position {position.id}: {str(e)}")
                continue
        
        logger.info(f"Successfully updated {updated_count} positions")
        return {
            'success': True,
            'positions_updated': updated_count
        }
        
    except Exception as e:
        logger.error(f"Error in update_open_positions: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(bind=True, name='trading.tasks.check_position_triggers')
def check_position_triggers(self, position_id):
    """
    Check if position hit stop loss or take profit.
    Sends notification if triggered.
    """
    try:
        position = Position.objects.get(id=position_id)
        
        if position.status != 'open':
            return {'success': True, 'action': 'none'}
        
        current_price = position.current_price
        triggered = False
        trigger_type = None
        
        # Check stop loss
        if position.stop_loss:
            if position.side == 'long' and current_price <= position.stop_loss:
                triggered = True
                trigger_type = 'stop_loss'
            elif position.side == 'short' and current_price >= position.stop_loss:
                triggered = True
                trigger_type = 'stop_loss'
        
        # Check take profit
        if not triggered and position.take_profit:
            if position.side == 'long' and current_price >= position.take_profit:
                triggered = True
                trigger_type = 'take_profit'
            elif position.side == 'short' and current_price <= position.take_profit:
                triggered = True
                trigger_type = 'take_profit'
        
        if triggered:
            # Send notification
            message = (
                f"🚨 **{trigger_type.replace('_', ' ').title()} Hit!**\n"
                f"Position: {position.symbol} {position.side.upper()}\n"
                f"Entry: ${position.entry_price:,.2f}\n"
                f"Current: ${current_price:,.2f}\n"
                f"P&L: ${position.unrealized_pnl:,.2f}"
            )
            send_discord_notification.delay(message)
            
            logger.warning(f"Position {position.id} hit {trigger_type}")
            return {
                'success': True,
                'action': 'triggered',
                'trigger_type': trigger_type,
                'position_id': position.id
            }
        
        return {'success': True, 'action': 'none'}
        
    except Position.DoesNotExist:
        logger.error(f"Position {position_id} not found")
        return {'success': False, 'error': 'Position not found'}
    except Exception as e:
        logger.error(f"Error checking position triggers: {str(e)}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# BALANCE TRACKING TASKS
# =============================================================================

@shared_task(bind=True, name='trading.tasks.record_account_balances')
def record_account_balances(self):
    """
    Record current balances for all active accounts.
    Runs hourly for balance tracking.
    """
    logger.info("Starting record_account_balances task")
    
    try:
        accounts = Account.objects.filter(status='active')
        
        if not accounts.exists():
            logger.warning("No active accounts found")
            return {'success': True, 'balances_recorded': 0}
        
        recorded_count = 0
        
        for account in accounts:
            try:
                # Calculate current balances
                open_positions = Position.objects.filter(
                    account=account,
                    status='open'
                )
                
                # Sum of position values
                reserved_balance = sum(
                    float(pos.entry_price * pos.quantity)
                    for pos in open_positions
                )
                
                # Get closed trades P&L
                closed_trades_pnl = Trade.objects.filter(
                    account=account,
                    status='closed'
                ).aggregate(total_pnl=Sum('pnl'))['total_pnl'] or 0
                
                # Calculate total balance (simplified - would use API in production)
                total_balance = 10000 + float(closed_trades_pnl)  # Starting capital + P&L
                available_balance = total_balance - reserved_balance
                
                # Create balance record
                BalanceHistory.objects.create(
                    account=account,
                    total_balance=Decimal(str(total_balance)),
                    available_balance=Decimal(str(available_balance)),
                    reserved_balance=Decimal(str(reserved_balance))
                )
                
                recorded_count += 1
                logger.info(f"Recorded balance for account {account.id}")
                
            except Exception as e:
                logger.error(f"Error recording balance for account {account.id}: {str(e)}")
                continue
        
        logger.info(f"Successfully recorded {recorded_count} account balances")
        return {
            'success': True,
            'balances_recorded': recorded_count
        }
        
    except Exception as e:
        logger.error(f"Error in record_account_balances: {str(e)}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# OPTIMIZATION TASKS
# =============================================================================

@shared_task(bind=True, name='trading.tasks.run_daily_optimization')
def run_daily_optimization(self):
    """
    Run strategy optimization daily at 2 AM.
    Updates strategy parameters based on recent performance.
    """
    logger.info("Starting run_daily_optimization task")
    
    try:
        strategies = Strategy.objects.filter(status__in=['active', 'testing'])
        
        if not strategies.exists():
            logger.warning("No strategies to optimize")
            return {'success': True, 'optimizations_run': 0}
        
        optimization_count = 0
        
        for strategy in strategies:
            try:
                params = strategy.parameters or {}
                symbols = params.get('symbols', ['BTC/USDT'])
                
                for symbol in symbols:
                    # Fetch data for optimization (last 30 days, 1h interval)
                    data = get_historical_data(symbol, interval='1h', limit=720)
                    
                    if data is not None and not data.empty:
                        # Run optimization
                        best_params = optimize_strategy(
                            data,
                            initial_capital=10000,
                            n_trials=50  # Reduced for daily run
                        )
                        
                        # Update strategy parameters if better
                        if best_params:
                            strategy.parameters.update(best_params)
                            strategy.save()
                            
                            logger.info(
                                f"Updated parameters for strategy {strategy.name} "
                                f"on {symbol}"
                            )
                            optimization_count += 1
                            
            except Exception as e:
                logger.error(f"Error optimizing strategy {strategy.name}: {str(e)}")
                continue
        
        logger.info(f"Successfully ran {optimization_count} optimizations")
        
        # Send summary notification
        if optimization_count > 0:
            send_discord_notification.delay(
                f"✅ Daily optimization complete! "
                f"Updated {optimization_count} strategy parameters."
            )
        
        return {
            'success': True,
            'optimizations_run': optimization_count
        }
        
    except Exception as e:
        logger.error(f"Error in run_daily_optimization: {str(e)}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# NOTIFICATION TASKS
# =============================================================================

@shared_task(bind=True, name='trading.tasks.send_discord_notification')
def send_discord_notification(self, message, webhook_url=None):
    """
    Send notification to Discord webhook.
    Can be called from other tasks or views.
    """
    from django.conf import settings
    
    webhook_url = webhook_url or settings.DISCORD_WEBHOOK_URL
    
    if not webhook_url:
        logger.warning("No Discord webhook URL configured")
        return {'success': False, 'error': 'No webhook URL'}
    
    try:
        payload = {
            'content': message,
            'username': 'FKS Trading Bot'
        }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        
        if response.status_code == 204:
            logger.info("Discord notification sent successfully")
            return {'success': True}
        else:
            logger.error(f"Discord API error: {response.status_code}")
            return {'success': False, 'error': f'HTTP {response.status_code}'}
            
    except Exception as e:
        logger.error(f"Error sending Discord notification: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(bind=True, name='trading.tasks.send_performance_summary')
def send_performance_summary(self, period='daily'):
    """
    Send performance summary to Discord.
    Period can be 'daily', 'weekly', or 'monthly'.
    """
    logger.info(f"Generating {period} performance summary")
    
    try:
        # Calculate date range
        now = timezone.now()
        if period == 'daily':
            start_date = now - timedelta(days=1)
            title = "📊 Daily Performance Summary"
        elif period == 'weekly':
            start_date = now - timedelta(days=7)
            title = "📊 Weekly Performance Summary"
        else:  # monthly
            start_date = now - timedelta(days=30)
            title = "📊 Monthly Performance Summary"
        
        # Get closed trades in period
        trades = Trade.objects.filter(
            status='closed',
            exit_time__gte=start_date
        )
        
        if not trades.exists():
            message = f"{title}\n\nNo trades closed in this period."
            send_discord_notification.delay(message)
            return {'success': True, 'trades': 0}
        
        # Calculate metrics
        total_trades = trades.count()
        total_pnl = trades.aggregate(Sum('pnl'))['pnl__sum'] or 0
        winning_trades = trades.filter(pnl__gt=0).count()
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        avg_win = trades.filter(pnl__gt=0).aggregate(Avg('pnl'))['pnl__avg'] or 0
        avg_loss = trades.filter(pnl__lt=0).aggregate(Avg('pnl'))['pnl__avg'] or 0
        
        # Build message
        message = f"""
{title}

**Overall Performance**
Total Trades: {total_trades}
Total P&L: ${total_pnl:,.2f}
Win Rate: {win_rate:.1f}%

**Trade Stats**
Winning Trades: {winning_trades}
Losing Trades: {total_trades - winning_trades}
Avg Win: ${avg_win:,.2f}
Avg Loss: ${avg_loss:,.2f}

**Active Positions**
Open: {Position.objects.filter(status='open').count()}

**Recent Signals**
Last 24h: {Signal.objects.filter(created_at__gte=now - timedelta(days=1)).count()}
        """
        
        send_discord_notification.delay(message.strip())
        
        logger.info(f"Sent {period} performance summary")
        return {
            'success': True,
            'period': period,
            'trades': total_trades,
            'pnl': float(total_pnl)
        }
        
    except Exception as e:
        logger.error(f"Error in send_performance_summary: {str(e)}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# MAINTENANCE TASKS
# =============================================================================

@shared_task(bind=True, name='trading.tasks.cleanup_old_data')
def cleanup_old_data(self, days=7, model_type='signal'):
    """
    Clean up old data to keep database lean.
    Removes signals, cache entries, etc. older than specified days.
    """
    logger.info(f"Starting cleanup_old_data for {model_type} (older than {days} days)")
    
    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count = 0
        
        if model_type == 'signal':
            # Delete old signals
            deleted = Signal.objects.filter(created_at__lt=cutoff_date).delete()
            deleted_count = deleted[0]
            
        elif model_type == 'balance_history':
            # Keep only 1 record per day for old data (compress history)
            old_records = BalanceHistory.objects.filter(
                timestamp__lt=cutoff_date
            ).order_by('account', 'timestamp')
            
            # Complex cleanup logic would go here
            # For now, just delete really old records (>90 days)
            very_old = timezone.now() - timedelta(days=90)
            deleted = BalanceHistory.objects.filter(timestamp__lt=very_old).delete()
            deleted_count = deleted[0]
        
        logger.info(f"Deleted {deleted_count} old {model_type} records")
        return {
            'success': True,
            'deleted_count': deleted_count,
            'model_type': model_type
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_data: {str(e)}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# MANUAL/ON-DEMAND TASKS
# =============================================================================

@shared_task(bind=True, name='trading.tasks.run_backtest_async')
def run_backtest_async(self, strategy_id, symbol, start_date, end_date, initial_capital=10000):
    """
    Run backtest asynchronously for a strategy.
    Can be triggered from the UI.
    """
    logger.info(f"Starting async backtest for strategy {strategy_id} on {symbol}")
    
    try:
        from .utils.backtest_engine import run_backtest
        
        strategy = Strategy.objects.get(id=strategy_id)
        
        # Fetch historical data
        # Calculate days between dates
        from datetime import datetime
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        days = (end_date - start_date).days
        limit = min(days * 24, 1000)  # 1h candles
        
        data = get_historical_data(symbol, interval='1h', limit=limit)
        
        if data is None or data.empty:
            return {'success': False, 'error': 'No data available'}
        
        # Run backtest
        results = run_backtest(
            data,
            strategy.parameters or {},
            initial_capital=initial_capital
        )
        
        # Save results
        backtest_result = BacktestResult.objects.create(
            strategy=strategy,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=Decimal(str(initial_capital)),
            final_capital=Decimal(str(results['final_capital'])),
            total_return=results['total_return'],
            sharpe_ratio=results['sharpe_ratio'],
            max_drawdown=results['max_drawdown'],
            win_rate=results['win_rate'],
            total_trades=results['total_trades'],
            parameters=strategy.parameters,
            equity_curve=results.get('equity_curve', {})
        )
        
        logger.info(f"Backtest complete. Result ID: {backtest_result.id}")
        
        # Send notification
        send_discord_notification.delay(
            f"✅ Backtest complete!\n"
            f"Strategy: {strategy.name}\n"
            f"Symbol: {symbol}\n"
            f"Return: {results['total_return']:.2%}\n"
            f"Sharpe: {results['sharpe_ratio']:.2f}\n"
            f"Trades: {results['total_trades']}"
        )
        
        return {
            'success': True,
            'backtest_id': backtest_result.id,
            'results': results
        }
        
    except Strategy.DoesNotExist:
        logger.error(f"Strategy {strategy_id} not found")
        return {'success': False, 'error': 'Strategy not found'}
    except Exception as e:
        logger.error(f"Error in run_backtest_async: {str(e)}")
        return {'success': False, 'error': str(e)}
