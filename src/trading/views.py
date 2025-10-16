"""
Views for fks trading application.
Migrated from Streamlit app.py

Implements all 5 tabs from the original Streamlit app:
1. Data Pull - Fetch historical data
2. Optimization & Backtest - Strategy optimization
3. Current Signal - Generate trading signals
4. Trade Tracking - Log and view trades
5. Notifications - Discord webhook integration
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.conf import settings
from django.db.models import Sum, Avg, Count
import json
import traceback
from datetime import datetime, timedelta
import pytz
import pandas as pd

from .models import Account, Trade, Position, Signal, Strategy, BacktestResult
from .forms import (
    DataPullForm,
    OptimizationForm,
    SignalForm,
    TradeForm,
    NotificationForm,
    TestNotificationForm,
    FilterTradesForm
)
from .utils.data_fetcher import (
    get_historical_data, 
    get_current_price, 
    get_live_prices,
    get_multiple_historical_data,
    align_dataframes
)
from .utils.signal_generator import get_current_signal
from .utils.backtest_engine import run_backtest, analyze_trade_distribution
from .utils.optimizer import run_optimization
from .utils.helpers import (
    send_discord_notification,
    format_trade_suggestions_for_discord,
    format_backtest_results_for_discord,
    log_trade_to_db
)

# Configuration
SYMBOLS = getattr(settings, 'TRADING_SYMBOLS', ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'AVAXUSDT', 'SUIUSDT'])
MAINS = getattr(settings, 'TRADING_MAINS', ['BTCUSDT', 'ETHUSDT'])
ALTS = getattr(settings, 'TRADING_ALTS', ['SOLUSDT', 'AVAXUSDT', 'SUIUSDT'])
FEE_RATE = getattr(settings, 'TRADING_FEE_RATE', 0.001)
RISK_PER_TRADE = getattr(settings, 'TRADING_RISK_PER_TRADE', 0.01)
DISCORD_WEBHOOK_URL = getattr(settings, 'DISCORD_WEBHOOK_URL', None)
TIMEZONE = pytz.timezone(getattr(settings, 'TIME_ZONE', 'America/Toronto'))


def dashboard(request):
    """
    Main dashboard view
    Shows overview of accounts, positions, recent trades, and signals
    """
    # Get live prices
    try:
        live_prices = get_live_prices(SYMBOLS)
    except Exception as e:
        live_prices = {}
        messages.warning(request, f'Could not fetch live prices: {e}')
    
    # Calculate summary statistics
    open_positions = Position.objects.filter(status='open')
    total_pnl = open_positions.aggregate(Sum('unrealized_pnl'))['unrealized_pnl__sum'] or 0
    
    recent_trades = Trade.objects.all().order_by('-time')[:10]
    total_trades = Trade.objects.count()
    
    # Calculate win rate from closed trades - Note: trades table doesn't have status
    # Filter by realized_pnl existence as indicator of completed trade
    closed_trades = Trade.objects.filter(realized_pnl__isnull=False)
    winning_trades = closed_trades.filter(realized_pnl__gt=0).count()
    total_closed = closed_trades.count()
    win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0
    
    context = {
        'symbols': SYMBOLS,
        'live_prices': live_prices,
        'accounts': Account.objects.filter(is_active=True),
        'recent_trades': recent_trades,
        'total_trades': total_trades,
        'open_positions': open_positions,
        'total_pnl': total_pnl,
        'win_rate': win_rate,
        'recent_signals': [],  # Signal.objects.all().order_by('-created_at')[:10] - signals table not yet created
        'has_cached_data': bool(cache.get(f'df_prices_{request.session.session_key}')),
        'has_best_params': bool(request.session.get('best_params')),
    }
    return render(request, 'trading/dashboard.html', context)


def data_pull_view(request):
    """
    Pull historical data - equivalent to Streamlit tab 1
    
    Fetches OHLCV data from Binance and stores in cache
    """
    cache_key = f'df_prices_{request.session.session_key}'
    cached_data = cache.get(cache_key)
    data_info = None
    
    if cached_data:
        # Extract info from cached data
        first_symbol = list(cached_data.keys())[0]
        if first_symbol in cached_data:
            df = cached_data[first_symbol]
            data_info = {
                'num_periods': len(df),
                'start_date': df.index[0].date(),
                'end_date': df.index[-1].date(),
                'symbols': list(cached_data.keys())
            }
    
    if request.method == 'POST':
        form = DataPullForm(request.POST)
        if form.is_valid():
            interval = form.cleaned_data['interval']
            limit = form.cleaned_data['limit']
        
            try:
                # Fetch data for all symbols
                df_prices = get_multiple_historical_data(SYMBOLS, interval, limit)
                
                # Align data on common index
                df_prices = align_dataframes(df_prices)
                
                # Validate data
                if not df_prices or all(df.empty for df in df_prices.values()):
                    messages.error(request, 'No data retrieved. Please check symbols and try again.')
                else:
                    # Check for sufficient data
                    common_length = min(len(df) for df in df_prices.values() if not df.empty)
                    if common_length < 100:
                        messages.error(request, f'Insufficient data: only {common_length} periods retrieved.')
                    else:
                        # Store in cache (1 hour timeout)
                        cache.set(cache_key, df_prices, timeout=3600)
                        
                        # Get date range
                        first_symbol = list(df_prices.keys())[0]
                        start_date = df_prices[first_symbol].index[0].date()
                        end_date = df_prices[first_symbol].index[-1].date()
                        
                        messages.success(
                            request,
                            f'Successfully pulled {common_length} periods from {start_date} to {end_date} for {len(df_prices)} symbols.'
                        )
                        
                        data_info = {
                            'num_periods': common_length,
                            'start_date': start_date,
                            'end_date': end_date,
                            'symbols': list(df_prices.keys())
                        }
                        
                        # Data quality checks
                        issues = []
                        for sym, df in df_prices.items():
                            if df.isnull().values.any():
                                issues.append(f'NaNs detected in {sym}')
                            if (df['close'] <= 0).any():
                                issues.append(f'Non-positive prices in {sym}')
                        
                        if issues:
                            for issue in issues:
                                messages.warning(request, issue)
            
            except Exception as e:
                messages.error(request, f'Error fetching data: {e}')
                traceback.print_exc()
        else:
            # Form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = DataPullForm()
    
    context = {
        'form': form,
        'intervals': ['1d', '4h', '1h'],
        'symbols': SYMBOLS,
        'data_info': data_info,
        'has_cached_data': bool(cached_data),
    }
    return render(request, 'trading/data_pull.html', context)


def optimization_view(request):
    """
    Run optimization and backtest - equivalent to Streamlit tab 2
    
    Allows users to:
    1. Run Optuna optimization to find best parameters
    2. Run backtest with optimized parameters
    """
    cache_key = f'df_prices_{request.session.session_key}'
    df_prices = cache.get(cache_key)
    
    if not df_prices:
        messages.warning(request, 'Please pull historical data first.')
        return redirect('trading:data_pull')
    
    best_params = request.session.get('best_params')
    backtest_results = None
    
    if request.method == 'POST':
        form = OptimizationForm(request.POST, symbols=SYMBOLS)
        if form.is_valid():
            n_trials = form.cleaned_data['n_trials']
            symbol = form.cleaned_data['symbol']
            
            try:
                # Show progress message
                messages.info(request, f'Running optimization with {n_trials} trials. This may take a few minutes...')
                
                # Run optimization
                symbols_config = {
                    'SYMBOLS': SYMBOLS,
                    'MAINS': MAINS,
                    'ALTS': ALTS
                }
                
                result = run_optimization(
                    df_prices=df_prices,
                    n_trials=n_trials,
                    symbols_config=symbols_config,
                    fee_rate=FEE_RATE,
                    show_progress_bar=False  # Can't show progress in web view
                )
                
                best_params = result['best_params']
                best_value = result['best_value']
                
                # Store in session
                request.session['best_params'] = best_params
                request.session['optimization_result'] = {
                    'best_value': best_value,
                    'n_trials': n_trials,
                    'timestamp': datetime.now(TIMEZONE).isoformat()
                }
                
                messages.success(
                    request,
                    f'Optimization complete! Best Sharpe Ratio: {best_value:.2f}'
                )
                
                # Show parameter details
                params_str = ', '.join([f'{k}={v}' for k, v in best_params.items()])
                messages.info(request, f'Best parameters: {params_str}')
                
                # Auto-run backtest with best params
                try:
                    messages.info(request, 'Running backtest with optimized parameters...')
                    
                    symbols_config = {
                        'SYMBOLS': SYMBOLS,
                        'MAINS': MAINS,
                        'ALTS': ALTS
                    }
                    
                    # Run backtest for all symbols
                    backtest_results = []
                    for sym in SYMBOLS:
                        sym_df = {sym: df_prices[sym]}
                        metrics, returns, cum_ret, trades = run_backtest(
                            df_prices=sym_df,
                            M=best_params['M'],
                            atr_period=best_params['atr_period'],
                            sl_multiplier=best_params['sl_multiplier'],
                            tp_multiplier=best_params['tp_multiplier'],
                            symbols_config={'SYMBOLS': [sym], 'MAINS': [sym], 'ALTS': []},
                            fee_rate=FEE_RATE
                        )
                        
                        backtest_results.append({
                            'symbol': sym,
                            'total_return': metrics.get('Total Return', 0) * 100,
                            'sharpe_ratio': metrics.get('Sharpe', 0),
                            'sortino_ratio': metrics.get('Sortino', 0),
                            'max_drawdown': metrics.get('Max Drawdown', 0) * 100,
                            'num_trades': metrics.get('Num Trades', 0),
                            'win_rate': metrics.get('Win Rate', 0) * 100,
                        })
                    
                    request.session['backtest_results'] = backtest_results
                    
                except Exception as backtest_e:
                    messages.warning(request, f'Optimization succeeded but backtest failed: {backtest_e}')
                
            except Exception as e:
                messages.error(request, f'Error during optimization: {e}')
                traceback.print_exc()
        else:
            # Form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = OptimizationForm(symbols=SYMBOLS)
    
    # Get optimization history and backtest results
    optimization_result = request.session.get('optimization_result')
    backtest_results = request.session.get('backtest_results', [])
    
    context = {
        'form': form,
        'symbols': SYMBOLS,
        'best_params': best_params,
        'optimization_result': optimization_result,
        'backtest_results': backtest_results,
        'has_cached_data': bool(df_prices),
    }
    return render(request, 'trading/optimization.html', context)


def signals_view(request):
    """
    Generate current trading signals - equivalent to Streamlit tab 3
    
    Uses optimized parameters to generate real-time trading signals
    with position sizing, stop-loss, and take-profit levels
    """
    cache_key = f'df_prices_{request.session.session_key}'
    df_prices = cache.get(cache_key)
    best_params = request.session.get('best_params')
    
    if not df_prices:
        messages.warning(request, 'Please pull historical data first.')
        return redirect('trading:data_pull')
    
    signals = None
    
    if request.method == 'POST':
        form = SignalForm(request.POST)
        if form.is_valid():
            account_size = float(form.cleaned_data['account_size'])
            risk_per_trade = float(form.cleaned_data['risk_per_trade']) / 100  # Convert to decimal
            
            # Check for warnings
            warnings = form.get_warnings()
            for field, warning_list in warnings.items():
                for warning in warning_list:
                    messages.warning(request, warning)
            
            try:
                # Generate signals for all symbols
                signals = []
                for symbol in SYMBOLS:
                    sym_df = {symbol: df_prices[symbol]}
                    
                    # Get current price
                    current_price = df_prices[symbol]['close'].iloc[-1]
                    
                    # Generate signal using best params or defaults
                    params_to_use = best_params or {
                        'M': 14,
                        'atr_period': 14,
                        'sl_multiplier': 2.0,
                        'tp_multiplier': 4.0
                    }
                    
                    signal_result = get_current_signal(
                        df_prices=sym_df,
                        best_params=params_to_use,
                        account_size=account_size,
                        symbols_config={'SYMBOLS': [symbol], 'MAINS': [symbol], 'ALTS': []},
                        risk_per_trade=risk_per_trade
                    )
                    
                    # Parse signal result
                    signal_type = signal_result[0]  # 1 for buy, 0 for hold, -1 for sell
                    suggestions = signal_result[1] if len(signal_result) > 1 else []
                    
                    # Get suggestion for this symbol
                    suggestion = suggestions[0] if suggestions else {}
                    
                    signals.append({
                        'symbol': symbol,
                        'signal': 'BUY' if signal_type == 1 else ('SELL' if signal_type == -1 else 'HOLD'),
                        'current_price': current_price,
                        'entry_price': suggestion.get('entry_price', current_price),
                        'stop_loss': suggestion.get('stop_loss'),
                        'take_profit': suggestion.get('target_price'),
                        'position_size': suggestion.get('position_size'),
                        'risk_amount': suggestion.get('risk_amount'),
                        'rsi': df_prices[symbol]['close'].rolling(14).apply(lambda x: 50).iloc[-1],  # Placeholder
                        'macd': 0,  # Placeholder
                    })
                
                # Store in session
                request.session['current_signals'] = signals
                request.session['signal_params'] = {
                    'account_size': account_size,
                    'risk_per_trade': risk_per_trade
                }
                
                # Count signals
                buy_count = sum(1 for s in signals if s['signal'] == 'BUY')
                sell_count = sum(1 for s in signals if s['signal'] == 'SELL')
                
                messages.success(
                    request,
                    f'Signals generated: {buy_count} BUY, {sell_count} SELL, {len(signals) - buy_count - sell_count} HOLD'
                )
                
            except Exception as e:
                messages.error(request, f'Error generating signals: {e}')
                traceback.print_exc()
        else:
            # Form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = SignalForm()
    
    context = {
        'form': form,
        'signals': signals or request.session.get('current_signals'),
        'best_params': best_params,
        'has_cached_data': bool(df_prices),
    }
    return render(request, 'trading/signals.html', context)


def trades_view(request):
    """
    Track and manage trades - equivalent to Streamlit tab 4
    
    View past trades and log new trades from signals
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'log_from_signal':
            # Log trades from current signal suggestions
            signal_id = request.session.get('current_signal_id')
            suggestions = request.session.get('current_suggestions', [])
            
            if not signal_id or not suggestions:
                messages.warning(request, 'No current signal suggestions to log. Generate a signal first.')
            else:
                try:
                    # Get or create default account
                    account, created = Account.objects.get_or_create(
                        exchange='binance',
                        account_type='spot',
                        defaults={
                            'api_key': 'demo',
                            'api_secret': 'demo',
                            'status': 'active'
                        }
                    )
                    
                    if created:
                        messages.info(request, 'Created demo account for trade logging.')
                    
                    trades_logged = 0
                    for sug in suggestions:
                        if 'symbol' in sug and sug.get('action') != 'HOLD USDT or SELL if holding assets':
                            Trade.objects.create(
                                account=account,
                                symbol=sug['symbol'],
                                side='long',  # Assuming long positions
                                quantity=sug.get('quantity', 0),
                                entry_price=sug.get('price', 0),
                                stop_loss=sug.get('sl'),
                                take_profit=sug.get('tp'),
                                status='open',
                                entry_time=datetime.now(TIMEZONE),
                                trade_metadata={
                                    'action': sug.get('action'),
                                    'allocated_usdt': sug.get('allocated_usdt'),
                                    'signal_id': signal_id
                                }
                            )
                            trades_logged += 1
                    
                    if trades_logged > 0:
                        messages.success(request, f'Successfully logged {trades_logged} trade(s).')
                        # Clear the current suggestions after logging
                        request.session.pop('current_suggestions', None)
                    else:
                        messages.warning(request, 'No valid trades to log from suggestions.')
                
                except Exception as e:
                    messages.error(request, f'Error logging trades: {e}')
                    traceback.print_exc()
        
        elif action == 'manual_log':
            # Manual trade entry
            try:
                account_id = request.POST.get('account_id')
                symbol = request.POST.get('symbol')
                side = request.POST.get('side', 'long')
                quantity = float(request.POST.get('quantity', 0))
                entry_price = float(request.POST.get('entry_price', 0))
                stop_loss = request.POST.get('stop_loss')
                take_profit = request.POST.get('take_profit')
                
                if not account_id or not symbol or quantity <= 0 or entry_price <= 0:
                    messages.error(request, 'Please provide valid trade details.')
                else:
                    account = Account.objects.get(id=account_id)
                    
                    Trade.objects.create(
                        account=account,
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        entry_price=entry_price,
                        stop_loss=float(stop_loss) if stop_loss else None,
                        take_profit=float(take_profit) if take_profit else None,
                        status='open',
                        entry_time=datetime.now(TIMEZONE)
                    )
                    
                    messages.success(request, f'Manually logged trade for {symbol}.')
            
            except Exception as e:
                messages.error(request, f'Error logging manual trade: {e}')
                traceback.print_exc()
        
        elif action == 'close_trade':
            # Close a trade
            try:
                trade_id = request.POST.get('trade_id')
                exit_price = float(request.POST.get('exit_price', 0))
                
                if not trade_id or exit_price <= 0:
                    messages.error(request, 'Please provide valid exit details.')
                else:
                    trade = Trade.objects.get(id=trade_id)
                    
                    # Calculate PnL
                    if trade.side == 'long':
                        pnl = (exit_price - trade.entry_price) * trade.quantity
                    else:  # short
                        pnl = (trade.entry_price - exit_price) * trade.quantity
                    
                    # Update trade
                    trade.exit_price = exit_price
                    trade.exit_time = datetime.now(TIMEZONE)
                    trade.pnl = pnl
                    trade.status = 'closed'
                    trade.save()
                    
                    messages.success(
                        request,
                        f'Closed trade for {trade.symbol}. P&L: ${pnl:,.2f}'
                    )
            
            except Exception as e:
                messages.error(request, f'Error closing trade: {e}')
                traceback.print_exc()
    
    # Get trades with filters
    status_filter = request.GET.get('status', 'all')
    symbol_filter = request.GET.get('symbol', 'all')
    
    trades = Trade.objects.all()
    
    if status_filter != 'all':
        trades = trades.filter(status=status_filter)
    
    if symbol_filter != 'all':
        trades = trades.filter(symbol=symbol_filter)
    
    trades = trades.order_by('-time')
    
    # Calculate statistics
    total_trades = trades.count()
    # Note: trades table doesn't have status field
    open_trades = 0
    closed_trades = trades.filter(realized_pnl__isnull=False)
    
    total_pnl = closed_trades.aggregate(Sum('pnl'))['pnl__sum'] or 0
    winning_trades = closed_trades.filter(pnl__gt=0).count()
    losing_trades = closed_trades.filter(pnl__lt=0).count()
    win_rate = (winning_trades / closed_trades.count() * 100) if closed_trades.count() > 0 else 0
    
    context = {
        'trades': trades[:50],  # Limit to 50 most recent
        'total_trades': total_trades,
        'open_trades': open_trades,
        'closed_trades_count': closed_trades.count(),
        'total_pnl': total_pnl,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'status_filter': status_filter,
        'symbol_filter': symbol_filter,
        'symbols': SYMBOLS,
        'accounts': Account.objects.filter(is_active=True),
        'recent_signals': [],  # Signal.objects.all().order_by('-created_at')[:5] - signals table not yet created
        'has_current_suggestions': bool(request.session.get('current_suggestions')),
    }
    return render(request, 'trading/trades.html', context)


def notifications_view(request):
    """
    Discord notifications - equivalent to Streamlit tab 5
    
    Send trading signals and backtest results to Discord webhook
    """
    webhook_url = request.session.get('webhook_url', DISCORD_WEBHOOK_URL or '')
    notify_settings = request.session.get('notify_settings', {
        'signals': True,
        'trades': True,
        'positions': True,
        'errors': True
    })
    
    if request.method == 'POST':
        form = NotificationForm(request.POST)
        if form.is_valid():
            # Save settings to session
            webhook_url = form.cleaned_data['webhook_url']
            request.session['webhook_url'] = webhook_url
            request.session['notify_settings'] = {
                'signals': form.cleaned_data['notify_signals'],
                'trades': form.cleaned_data['notify_trades'],
                'positions': form.cleaned_data['notify_positions'],
                'errors': form.cleaned_data['notify_errors'],
            }
            
            messages.success(request, 'Notification settings saved successfully!')
        else:
            # Form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        # Pre-fill form with saved settings
        form = NotificationForm(initial={
            'webhook_url': webhook_url,
            'notify_signals': notify_settings.get('signals', True),
            'notify_trades': notify_settings.get('trades', True),
            'notify_positions': notify_settings.get('positions', True),
            'notify_errors': notify_settings.get('errors', True),
        })
    
    context = {
        'form': form,
        'webhook_url': webhook_url,
        'notify_signals': notify_settings.get('signals', True),
        'notify_trades': notify_settings.get('trades', True),
        'notify_positions': notify_settings.get('positions', True),
        'notify_errors': notify_settings.get('errors', True),
    }
    return render(request, 'trading/notifications.html', context)


@require_http_methods(["POST"])
def test_notification(request):
    """Send a test Discord notification."""
    form = TestNotificationForm(request.POST)
    if form.is_valid():
        message = form.cleaned_data['message']
        webhook_url = request.session.get('webhook_url')
        
        if not webhook_url:
            messages.error(request, 'Please configure webhook URL first.')
        else:
            try:
                send_discord_notification(webhook_url, message)
                messages.success(request, 'Test notification sent successfully!')
            except Exception as e:
                messages.error(request, f'Error sending notification: {e}')
                traceback.print_exc()
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
    
    return redirect('trading:notifications')


# ============================================================================
# Additional Helper Views
# ============================================================================

def positions_view(request):
    """
    View and manage open positions
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_price':
            # Update current prices for all open positions
            try:
                open_positions = Position.objects.filter(status='open')
                updated_count = 0
                
                for position in open_positions:
                    try:
                        current_price = get_current_price(position.symbol)
                        position.current_price = current_price
                        position.calculate_pnl()
                        position.save()
                        updated_count += 1
                    except Exception as e:
                        print(f"Error updating price for {position.symbol}: {e}")
                
                messages.success(request, f'Updated prices for {updated_count} position(s).')
            
            except Exception as e:
                messages.error(request, f'Error updating prices: {e}')
        
        elif action == 'close_position':
            # Close a position
            try:
                position_id = request.POST.get('position_id')
                position = Position.objects.get(id=position_id)
                
                # Create trade record
                Trade.objects.create(
                    account=position.account,
                    symbol=position.symbol,
                    side=position.side,
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                    exit_price=position.current_price,
                    pnl=position.unrealized_pnl,
                    entry_time=position.entry_time,
                    exit_time=datetime.now(TIMEZONE),
                    status='closed'
                )
                
                # Close position
                position.status = 'closed'
                position.save()
                
                messages.success(
                    request,
                    f'Closed position {position.symbol}. P&L: ${position.unrealized_pnl:,.2f}'
                )
            
            except Exception as e:
                messages.error(request, f'Error closing position: {e}')
    
    # Get positions
    status_filter = request.GET.get('status', 'open')
    positions = Position.objects.filter(status=status_filter).order_by('-opened_at')
    
    # Calculate totals
    total_pnl = positions.aggregate(Sum('unrealized_pnl'))['unrealized_pnl__sum'] or 0
    
    context = {
        'positions': positions,
        'total_pnl': total_pnl,
        'status_filter': status_filter,
        'symbols': SYMBOLS,
    }
    return render(request, 'trading/positions.html', context)


def backtest_detail_view(request, backtest_id):
    """
    View detailed backtest results
    """
    backtest = get_object_or_404(BacktestResult, id=backtest_id)
    
    # Prepare equity curve data
    equity_data = None
    if hasattr(backtest, 'equity_curve') and backtest.equity_curve:
        equity_data = {
            'dates': [d.isoformat() for d in backtest.equity_curve.index],
            'values': backtest.equity_curve.tolist()
        }
    
    context = {
        'backtest': backtest,
        'metrics': backtest.metrics,
        'parameters': backtest.parameters,
        'trades': backtest.trades_data,
        'equity_data': equity_data,
    }
    return render(request, 'trading/backtest_detail.html', context)


def clear_cache_view(request):
    """
    Clear cached data and session
    """
    if request.method == 'POST':
        try:
            # Clear price data cache
            cache_key = f'df_prices_{request.session.session_key}'
            cache.delete(cache_key)
            
            # Clear session data
            request.session.pop('best_params', None)
            request.session.pop('current_suggestions', None)
            request.session.pop('current_signal_id', None)
            request.session.pop('optimization_result', None)
            request.session.pop('last_backtest_id', None)
            
            messages.success(request, 'Cache and session data cleared.')
        except Exception as e:
            messages.error(request, f'Error clearing cache: {e}')
    
    return redirect('trading:dashboard')


# ============================================================================
# API Views (JSON responses)
# ============================================================================

@require_http_methods(["GET"])
def api_live_prices(request):
    """API endpoint for live prices"""
    try:
        symbols = request.GET.getlist('symbols') or SYMBOLS
        prices = get_live_prices(symbols)
        
        return JsonResponse({
            'success': True,
            'prices': prices,
            'timestamp': datetime.now(TIMEZONE).isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def api_positions(request):
    """API endpoint for open positions"""
    try:
        status = request.GET.get('status', 'open')
        positions = Position.objects.filter(status=status).values(
            'id', 'symbol', 'side', 'quantity', 'entry_price',
            'current_price', 'unrealized_pnl', 'entry_time', 'stop_loss', 'take_profit'
        )
        
        return JsonResponse({
            'success': True,
            'positions': list(positions),
            'count': len(positions)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def api_recent_trades(request):
    """API endpoint for recent trades"""
    try:
        limit = int(request.GET.get('limit', 20))
        # Note: trades table doesn't have status field  
        trades = Trade.objects.all()
        
        trades = trades.order_by('-time')[:limit].values(
            'id', 'symbol', 'trade_type', 'quantity', 'price',
            'realized_pnl', 'time', 'fee'
        )
        
        return JsonResponse({
            'success': True,
            'trades': list(trades),
            'count': len(trades)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def api_current_signal(request):
    """API endpoint to get current trading signal"""
    try:
        # Check if we have cached data
        cache_key = f'df_prices_{request.session.session_key}'
        df_prices = cache.get(cache_key)
        best_params = request.session.get('best_params')
        
        if not df_prices or not best_params:
            return JsonResponse({
                'success': False,
                'error': 'No data available. Please run optimization first.'
            }, status=400)
        
        account_size = float(request.GET.get('account_size', 10000))
        
        symbols_config = {
            'SYMBOLS': SYMBOLS,
            'MAINS': MAINS,
            'ALTS': ALTS
        }
        
        signal, suggestions = get_current_signal(
            df_prices=df_prices,
            best_params=best_params,
            account_size=account_size,
            symbols_config=symbols_config,
            risk_per_trade=RISK_PER_TRADE
        )
        
        return JsonResponse({
            'success': True,
            'signal': signal,
            'signal_text': "HOLD ASSETS" if signal == 1 else "HOLD USDT",
            'suggestions': suggestions,
            'timestamp': datetime.now(TIMEZONE).isoformat()
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def api_backtest_results(request, backtest_id=None):
    """API endpoint for backtest results"""
    try:
        if backtest_id:
            backtest = get_object_or_404(BacktestResult, id=backtest_id)
            return JsonResponse({
                'success': True,
                'backtest': {
                    'id': backtest.id,
                    'strategy_name': backtest.strategy_name,
                    'parameters': backtest.parameters,
                    'metrics': backtest.metrics,
                    'trades_data': backtest.trades_data,
                    'created_at': backtest.created_at.isoformat()
                }
            })
        else:
            # Return list of backtests
            limit = int(request.GET.get('limit', 10))
            backtests = BacktestResult.objects.all().order_by('-created_at')[:limit]
            
            return JsonResponse({
                'success': True,
                'backtests': [
                    {
                        'id': b.id,
                        'strategy_name': b.strategy_name,
                        'metrics': b.metrics,
                        'created_at': b.created_at.isoformat()
                    }
                    for b in backtests
                ],
                'count': len(backtests)
            })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def api_update_position_prices(request):
    """API endpoint to update all position prices"""
    try:
        open_positions = Position.objects.filter(status='open')
        updated = []
        errors = []
        
        for position in open_positions:
            try:
                current_price = get_current_price(position.symbol)
                position.current_price = current_price
                position.calculate_pnl()
                position.save()
                
                updated.append({
                    'id': position.id,
                    'symbol': position.symbol,
                    'price': current_price,
                    'pnl': float(position.unrealized_pnl)
                })
            except Exception as e:
                errors.append({
                    'symbol': position.symbol,
                    'error': str(e)
                })
        
        return JsonResponse({
            'success': True,
            'updated': updated,
            'errors': errors,
            'count': len(updated)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
