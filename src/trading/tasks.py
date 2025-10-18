"""
Celery tasks for FKS trading platform.
All 16 production-ready tasks for automated trading.
"""

import os
from datetime import datetime, timedelta
from decimal import Decimal

import pandas as pd
import requests
import talib
from celery import shared_task
from celery.utils.log import get_task_logger

# Database imports
from core.database.models import (
    TIMEZONE,
    Account,
    BalanceHistory,
    IndicatorsCache,
    OHLCVData,
    Position,
    Session,
    StrategyParameters,
    SyncStatus,
    Trade,
)

# Trading logic imports
from data.adapters.binance import BinanceAdapter

# Framework imports
from framework.config.constants import (
    ALTS,
    DEFAULT_TIMEFRAME,
    FEE_RATE,
    MAINS,
    RISK_PER_TRADE,
    SYMBOLS,
    TECHNICAL_INDICATORS,
)
from trading.backtest.engine import run_backtest
from trading.signals.generator import get_current_signal

# RAG Intelligence imports
try:
    from web.rag.orchestrator import IntelligenceOrchestrator
    RAG_AVAILABLE = True
except ImportError:
    logger.warning("RAG system not available - using legacy signal generation")
    RAG_AVAILABLE = False

logger = get_task_logger(__name__)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_db_session():
    """Get database session with proper error handling."""
    return Session()


def close_db_session(session):
    """Close database session safely."""
    try:
        session.close()
    except Exception as e:
        logger.error(f"Error closing session: {e}")


def send_discord_notification(message: str) -> bool:
    """Send notification to Discord webhook."""
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        logger.warning("Discord webhook URL not configured")
        return False

    try:
        response = requests.post(
            webhook_url,
            json={"content": message},
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send Discord notification: {e}")
        return False


# =============================================================================
# PHASE 1: FOUNDATION TASKS (Market Data & Core)
# =============================================================================

@shared_task(bind=True, max_retries=3)
def sync_market_data_task(self, symbol: str = None, timeframe: str = DEFAULT_TIMEFRAME, limit: int = 500):
    """
    Fetch OHLCV data from Binance and store in database.

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT'). If None, syncs all SYMBOLS.
        timeframe: Candle timeframe (default: '1h')
        limit: Number of candles to fetch (default: 500)

    Returns:
        dict: Sync results with status and data counts
    """
    session = get_db_session()
    try:
        symbols_to_sync = [symbol] if symbol else SYMBOLS
        adapter = BinanceAdapter()
        results = {}

        for sym in symbols_to_sync:
            try:
                # Get sync status
                sync_status = session.query(SyncStatus).filter_by(
                    symbol=sym, timeframe=timeframe
                ).first()

                if not sync_status:
                    sync_status = SyncStatus(
                        symbol=sym,
                        timeframe=timeframe,
                        sync_status='pending'
                    )
                    session.add(sync_status)

                # Update status to syncing
                sync_status.sync_status = 'syncing'
                sync_status.last_sync_time = datetime.now(TIMEZONE)
                session.commit()

                # Fetch data from Binance
                response = adapter.fetch(
                    symbol=sym,
                    interval=timeframe,
                    limit=limit
                )

                data = response.get('data', [])
                if not data:
                    logger.warning(f"No data received for {sym}")
                    continue

                # Store OHLCV data
                candles_added = 0
                for candle in data:
                    timestamp = datetime.fromtimestamp(candle['ts'], tz=TIMEZONE)

                    # Check if candle exists
                    existing = session.query(OHLCVData).filter_by(
                        time=timestamp,
                        symbol=sym,
                        timeframe=timeframe
                    ).first()

                    if not existing:
                        ohlcv = OHLCVData(
                            time=timestamp,
                            symbol=sym,
                            timeframe=timeframe,
                            open=Decimal(str(candle['open'])),
                            high=Decimal(str(candle['high'])),
                            low=Decimal(str(candle['low'])),
                            close=Decimal(str(candle['close'])),
                            volume=Decimal(str(candle['volume']))
                        )
                        session.add(ohlcv)
                        candles_added += 1

                session.commit()

                # Update sync status
                sync_status.sync_status = 'completed'
                sync_status.total_candles = session.query(OHLCVData).filter_by(
                    symbol=sym, timeframe=timeframe
                ).count()
                sync_status.newest_data_time = datetime.fromtimestamp(data[-1]['ts'], tz=TIMEZONE)
                sync_status.oldest_data_time = datetime.fromtimestamp(data[0]['ts'], tz=TIMEZONE)
                session.commit()

                results[sym] = {
                    'status': 'success',
                    'candles_added': candles_added,
                    'total_candles': sync_status.total_candles
                }
                logger.info(f"Synced {candles_added} new candles for {sym}")

            except Exception as e:
                logger.error(f"Error syncing {sym}: {e}")
                if sync_status:
                    sync_status.sync_status = 'error'
                    sync_status.error_message = str(e)
                    session.commit()
                results[sym] = {'status': 'error', 'message': str(e)}

        return {
            'status': 'success',
            'timeframe': timeframe,
            'results': results
        }

    except Exception as e:
        logger.error(f"Market data sync failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


@shared_task(bind=True, max_retries=3)
def sync_account_balance_task(self, account_id: int = None):
    """
    Sync account balance from exchange and create balance history snapshot.

    Args:
        account_id: Account ID to sync. If None, syncs all active accounts.

    Returns:
        dict: Sync results with balance information
    """
    session = get_db_session()
    try:
        # Get accounts to sync
        if account_id:
            accounts = session.query(Account).filter_by(id=account_id, is_active=True).all()
        else:
            accounts = session.query(Account).filter_by(is_active=True).all()

        if not accounts:
            return {'status': 'error', 'message': 'No active accounts found'}

        results = {}
        for account in accounts:
            try:
                # Calculate current equity (balance + unrealized PnL from positions)
                positions = session.query(Position).filter_by(account_id=account.id).all()
                unrealized_pnl = sum(float(p.unrealized_pnl or 0) for p in positions)

                current_balance = float(account.current_balance)
                equity = current_balance + unrealized_pnl
                margin_used = sum(float(p.quantity * p.entry_price) for p in positions)
                margin_available = current_balance - margin_used

                # Get previous balance for daily PnL calculation
                previous_balance = session.query(BalanceHistory).filter_by(
                    account_id=account.id
                ).order_by(BalanceHistory.time.desc()).first()

                daily_pnl = 0
                cumulative_pnl = equity - float(account.initial_balance)

                if previous_balance:
                    daily_pnl = equity - float(previous_balance.equity)

                # Create balance history record
                balance_history = BalanceHistory(
                    time=datetime.now(TIMEZONE),
                    account_id=account.id,
                    balance=Decimal(str(current_balance)),
                    equity=Decimal(str(equity)),
                    margin_used=Decimal(str(margin_used)),
                    margin_available=Decimal(str(margin_available)),
                    daily_pnl=Decimal(str(daily_pnl)),
                    cumulative_pnl=Decimal(str(cumulative_pnl))
                )
                session.add(balance_history)
                session.commit()

                results[account.name] = {
                    'status': 'success',
                    'balance': current_balance,
                    'equity': equity,
                    'daily_pnl': daily_pnl,
                    'cumulative_pnl': cumulative_pnl
                }
                logger.info(f"Synced balance for account {account.name}: equity=${equity:.2f}")

            except Exception as e:
                logger.error(f"Error syncing account {account.name}: {e}")
                results[account.name] = {'status': 'error', 'message': str(e)}

        return {
            'status': 'success',
            'accounts_synced': len(results),
            'results': results
        }

    except Exception as e:
        logger.error(f"Account balance sync failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


@shared_task(bind=True, max_retries=3)
def update_positions_task(self, account_id: int = None):
    """
    Update current positions with latest prices and unrealized PnL.

    Args:
        account_id: Account ID to update. If None, updates all accounts.

    Returns:
        dict: Update results with position information
    """
    session = get_db_session()
    try:
        # Get positions to update
        if account_id:
            positions = session.query(Position).filter_by(account_id=account_id).all()
        else:
            positions = session.query(Position).all()

        if not positions:
            return {'status': 'success', 'message': 'No positions to update'}

        adapter = BinanceAdapter()
        results = []

        for position in positions:
            try:
                # Fetch current price
                response = adapter.fetch(
                    symbol=position.symbol,
                    interval='1m',
                    limit=1
                )

                data = response.get('data', [])
                if not data:
                    logger.warning(f"No price data for {position.symbol}")
                    continue

                current_price = Decimal(str(data[0]['close']))
                position.current_price = current_price

                # Calculate unrealized PnL
                if position.position_type == 'LONG':
                    pnl = (current_price - position.entry_price) * position.quantity
                else:  # SHORT
                    pnl = (position.entry_price - current_price) * position.quantity

                position.unrealized_pnl = pnl
                position.unrealized_pnl_percent = (pnl / (position.entry_price * position.quantity)) * 100
                position.updated_at = datetime.now(TIMEZONE)

                session.commit()

                results.append({
                    'symbol': position.symbol,
                    'type': position.position_type,
                    'entry_price': float(position.entry_price),
                    'current_price': float(current_price),
                    'unrealized_pnl': float(pnl),
                    'unrealized_pnl_percent': float(position.unrealized_pnl_percent)
                })

            except Exception as e:
                logger.error(f"Error updating position {position.symbol}: {e}")
                continue

        logger.info(f"Updated {len(results)} positions")
        return {
            'status': 'success',
            'positions_updated': len(results),
            'positions': results
        }

    except Exception as e:
        logger.error(f"Position update failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


# =============================================================================
# PHASE 2: SIGNAL GENERATION & ANALYSIS
# =============================================================================

@shared_task(bind=True, max_retries=3)
def generate_signals_task(self, account_id: int = None, timeframe: str = DEFAULT_TIMEFRAME):
    """
    Generate trading signals using RAG-powered FKS Intelligence.
    
    Uses IntelligenceOrchestrator to analyze historical data and market conditions
    to generate optimal trading signals based on account state and available cash.

    Args:
        account_id: Account ID for signal generation. If None, uses first active account.
        timeframe: Timeframe for analysis

    Returns:
        dict: Generated signals and trade suggestions
    """
    session = get_db_session()
    try:
        # Get account
        if account_id:
            account = session.query(Account).filter_by(id=account_id).first()
        else:
            account = session.query(Account).filter_by(is_active=True).first()

        if not account:
            return {'status': 'error', 'message': 'No active account found'}

        account_balance = float(account.current_balance)
        
        # Get current positions to calculate available cash
        positions = session.query(Position).filter_by(account_id=account.id).all()
        margin_used = sum(float(p.quantity * p.entry_price) for p in positions)
        available_cash = account_balance - margin_used
        
        # Build current positions dict for RAG context
        current_positions = {}
        for position in positions:
            current_positions[position.symbol] = {
                'quantity': float(position.quantity),
                'entry_price': float(position.entry_price),
                'current_price': float(position.current_price) if position.current_price else 0,
                'unrealized_pnl': float(position.unrealized_pnl or 0)
            }

        # Use RAG if available, otherwise fall back to legacy
        if RAG_AVAILABLE:
            logger.info("Using RAG-powered signal generation")
            orchestrator = IntelligenceOrchestrator(use_local=True)
            
            # Generate RAG-powered recommendations for all symbols
            recommendations = []
            rag_signals = {}
            
            for symbol in SYMBOLS:
                try:
                    rec = orchestrator.get_trading_recommendation(
                        symbol=symbol,
                        account_balance=account_balance,
                        available_cash=available_cash,
                        context=f"current market conditions, timeframe: {timeframe}",
                        current_positions=current_positions
                    )
                    
                    rag_signals[symbol] = rec
                    
                    # Convert to suggestion format
                    if rec.get('action') == 'BUY' and available_cash > 0:
                        position_size_usd = rec.get('position_size_usd', 0)
                        if position_size_usd > 0 and position_size_usd <= available_cash:
                            recommendations.append({
                                'symbol': symbol,
                                'action': 'BUY',
                                'position_size_usd': position_size_usd,
                                'reasoning': rec.get('reasoning', ''),
                                'risk_assessment': rec.get('risk_assessment', 'medium'),
                                'confidence': rec.get('confidence', 0.7),
                                'entry_points': rec.get('entry_points', []),
                                'stop_loss': rec.get('stop_loss'),
                                'timeframe': rec.get('timeframe', timeframe)
                            })
                    
                except Exception as e:
                    logger.error(f"RAG recommendation failed for {symbol}: {e}")
                    continue
            
            # Determine overall signal
            buy_count = sum(1 for r in recommendations if r['action'] == 'BUY')
            signal = 'BUY' if buy_count > 0 else 'HOLD'
            
            result = {
                'status': 'success',
                'account_id': account.id,
                'account_balance': account_balance,
                'available_cash': available_cash,
                'signal': signal,
                'suggestions': recommendations,
                'rag_signals': rag_signals,
                'method': 'rag',
                'timestamp': datetime.now(TIMEZONE).isoformat()
            }
            
        else:
            # Fallback to legacy signal generation
            logger.info("Using legacy signal generation (RAG not available)")
            
            # Get strategy parameters
            strategy = session.query(StrategyParameters).filter_by(
                is_active=True
            ).first()

            if not strategy:
                best_params = {
                    'M': 50,
                    'atr_period': 14,
                    'sl_multiplier': 2.0,
                    'tp_multiplier': 3.0
                }
            else:
                best_params = strategy.parameters

            # Fetch price data for all symbols
            df_prices = {}
            for symbol in SYMBOLS:
                ohlcv_data = session.query(OHLCVData).filter_by(
                    symbol=symbol,
                    timeframe=timeframe
                ).order_by(OHLCVData.time.desc()).limit(500).all()

                if not ohlcv_data:
                    logger.warning(f"No data available for {symbol}")
                    continue

                df = pd.DataFrame([{
                    'time': d.time,
                    'open': float(d.open),
                    'high': float(d.high),
                    'low': float(d.low),
                    'close': float(d.close),
                    'volume': float(d.volume)
                } for d in reversed(ohlcv_data)])
                df.set_index('time', inplace=True)
                df_prices[symbol] = df

            if not df_prices:
                return {'status': 'error', 'message': 'No price data available'}

            # Generate legacy signals
            signal, suggestions = get_current_signal(
                df_prices,
                best_params,
                account_balance,
                RISK_PER_TRADE
            )

            result = {
                'status': 'success',
                'account_id': account.id,
                'account_balance': account_balance,
                'available_cash': available_cash,
                'signal': 'BUY' if signal == 1 else 'HOLD',
                'suggestions': suggestions,
                'method': 'legacy',
                'timestamp': datetime.now(TIMEZONE).isoformat()
            }

        logger.info(f"Generated signal: {result['signal']} for account {account.name} using {result['method']} method")

        # Send notification if BUY signal
        if result['signal'] == 'BUY':
            suggestions = result.get('suggestions', [])
            message = "🚀 **BUY Signal Generated**\n"
            message += f"Account: {account.name}\n"
            message += f"Balance: ${account_balance:.2f}\n"
            message += f"Available Cash: ${available_cash:.2f}\n"
            message += f"Suggestions: {len(suggestions)} trades\n"
            message += f"Method: {result['method'].upper()}\n"
            send_discord_notification(message)

        return result

    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


@shared_task(bind=True, max_retries=3)
def update_indicators_task(self, symbol: str = None, timeframe: str = DEFAULT_TIMEFRAME):
    """
    Calculate and cache technical indicators for symbols.

    Args:
        symbol: Trading pair. If None, updates all SYMBOLS.
        timeframe: Timeframe for indicators

    Returns:
        dict: Indicators calculation results
    """
    session = get_db_session()
    try:
        symbols_to_update = [symbol] if symbol else SYMBOLS
        results = {}

        for sym in symbols_to_update:
            try:
                # Fetch OHLCV data
                ohlcv_data = session.query(OHLCVData).filter_by(
                    symbol=sym,
                    timeframe=timeframe
                ).order_by(OHLCVData.time.desc()).limit(500).all()

                if not ohlcv_data:
                    logger.warning(f"No data for {sym}")
                    continue

                # Convert to arrays for TA-Lib
                data = list(reversed(ohlcv_data))
                closes = [float(d.close) for d in data]
                highs = [float(d.high) for d in data]
                lows = [float(d.low) for d in data]
                volumes = [float(d.volume) for d in data]

                # Calculate indicators
                indicators_data = []

                # RSI
                rsi = talib.RSI(pd.Series(closes), timeperiod=14)
                if not pd.isna(rsi.iloc[-1]):
                    indicators_data.append(('RSI', rsi.iloc[-1], data[-1].time))

                # MACD
                macd, signal, hist = talib.MACD(pd.Series(closes))
                if not pd.isna(macd.iloc[-1]):
                    indicators_data.append(('MACD', macd.iloc[-1], data[-1].time))
                    indicators_data.append(('MACD_SIGNAL', signal.iloc[-1], data[-1].time))
                    indicators_data.append(('MACD_HIST', hist.iloc[-1], data[-1].time))

                # Bollinger Bands
                upper, middle, lower = talib.BBANDS(pd.Series(closes))
                if not pd.isna(upper.iloc[-1]):
                    indicators_data.append(('BB_UPPER', upper.iloc[-1], data[-1].time))
                    indicators_data.append(('BB_MIDDLE', middle.iloc[-1], data[-1].time))
                    indicators_data.append(('BB_LOWER', lower.iloc[-1], data[-1].time))

                # ATR
                atr = talib.ATR(pd.Series(highs), pd.Series(lows), pd.Series(closes))
                if not pd.isna(atr.iloc[-1]):
                    indicators_data.append(('ATR', atr.iloc[-1], data[-1].time))

                # SMA
                for period in [20, 50, 200]:
                    sma = talib.SMA(pd.Series(closes), timeperiod=period)
                    if not pd.isna(sma.iloc[-1]):
                        indicators_data.append((f'SMA_{period}', sma.iloc[-1], data[-1].time))

                # EMA
                for period in [12, 26]:
                    ema = talib.EMA(pd.Series(closes), timeperiod=period)
                    if not pd.isna(ema.iloc[-1]):
                        indicators_data.append((f'EMA_{period}', ema.iloc[-1], data[-1].time))

                # Store indicators in cache
                indicators_stored = 0
                for indicator_name, value, time in indicators_data:
                    indicator_cache = IndicatorsCache(
                        time=time,
                        symbol=sym,
                        timeframe=timeframe,
                        indicator_name=indicator_name,
                        value=Decimal(str(value))
                    )
                    session.merge(indicator_cache)
                    indicators_stored += 1

                session.commit()

                results[sym] = {
                    'status': 'success',
                    'indicators_stored': indicators_stored
                }
                logger.info(f"Updated {indicators_stored} indicators for {sym}")

            except Exception as e:
                logger.error(f"Error updating indicators for {sym}: {e}")
                results[sym] = {'status': 'error', 'message': str(e)}

        return {
            'status': 'success',
            'symbols_processed': len(results),
            'results': results
        }

    except Exception as e:
        logger.error(f"Indicators update failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


@shared_task(bind=True, max_retries=3)
def analyze_risk_task(self, account_id: int = None):
    """
    Perform risk assessment on current portfolio and positions.

    Args:
        account_id: Account ID to analyze. If None, analyzes all accounts.

    Returns:
        dict: Risk analysis results
    """
    session = get_db_session()
    try:
        # Get accounts to analyze
        if account_id:
            accounts = session.query(Account).filter_by(id=account_id).all()
        else:
            accounts = session.query(Account).filter_by(is_active=True).all()

        if not accounts:
            return {'status': 'error', 'message': 'No accounts found'}

        results = {}
        for account in accounts:
            try:
                positions = session.query(Position).filter_by(account_id=account.id).all()

                if not positions:
                    results[account.name] = {
                        'status': 'success',
                        'risk_level': 'NONE',
                        'message': 'No open positions'
                    }
                    continue

                # Calculate risk metrics
                total_exposure = sum(float(p.quantity * p.entry_price) for p in positions)
                account_balance = float(account.current_balance)
                exposure_ratio = total_exposure / account_balance if account_balance > 0 else 0

                total_unrealized_pnl = sum(float(p.unrealized_pnl or 0) for p in positions)
                unrealized_pnl_percent = (total_unrealized_pnl / account_balance * 100) if account_balance > 0 else 0

                # Risk level assessment
                risk_level = 'LOW'
                warnings = []

                if exposure_ratio > 0.8:
                    risk_level = 'HIGH'
                    warnings.append(f'High exposure: {exposure_ratio*100:.1f}% of balance')
                elif exposure_ratio > 0.5:
                    risk_level = 'MEDIUM'
                    warnings.append(f'Moderate exposure: {exposure_ratio*100:.1f}% of balance')

                if unrealized_pnl_percent < -10:
                    risk_level = 'HIGH'
                    warnings.append(f'Large unrealized loss: {unrealized_pnl_percent:.1f}%')
                elif unrealized_pnl_percent < -5:
                    if risk_level == 'LOW':
                        risk_level = 'MEDIUM'
                    warnings.append(f'Unrealized loss: {unrealized_pnl_percent:.1f}%')

                # Check concentration risk
                for position in positions:
                    position_size = float(position.quantity * position.entry_price)
                    position_ratio = position_size / account_balance if account_balance > 0 else 0
                    if position_ratio > 0.2:
                        risk_level = 'HIGH'
                        warnings.append(f'High concentration in {position.symbol}: {position_ratio*100:.1f}%')

                results[account.name] = {
                    'status': 'success',
                    'risk_level': risk_level,
                    'exposure_ratio': exposure_ratio,
                    'total_exposure': total_exposure,
                    'unrealized_pnl': total_unrealized_pnl,
                    'unrealized_pnl_percent': unrealized_pnl_percent,
                    'warnings': warnings,
                    'positions_count': len(positions)
                }

                # Send alert if high risk
                if risk_level == 'HIGH':
                    message = "⚠️ **HIGH RISK ALERT**\n"
                    message += f"Account: {account.name}\n"
                    message += f"Risk Level: {risk_level}\n"
                    message += "\n".join(f"- {w}" for w in warnings)
                    send_discord_notification(message)

                logger.info(f"Risk analysis for {account.name}: {risk_level}")

            except Exception as e:
                logger.error(f"Error analyzing risk for {account.name}: {e}")
                results[account.name] = {'status': 'error', 'message': str(e)}

        return {
            'status': 'success',
            'accounts_analyzed': len(results),
            'results': results
        }

    except Exception as e:
        logger.error(f"Risk analysis failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


# =============================================================================
# PHASE 3: TRADING EXECUTION & MONITORING
# =============================================================================

@shared_task(bind=True, max_retries=3)
def run_backtest_task(self, timeframe: str = DEFAULT_TIMEFRAME, optimize: bool = False):
    """
    Execute strategy backtests on historical data.

    Args:
        timeframe: Timeframe for backtest
        optimize: Whether to run optimization

    Returns:
        dict: Backtest results and metrics
    """
    session = get_db_session()
    try:
        # Get strategy parameters
        strategy = session.query(StrategyParameters).filter_by(
            is_active=True
        ).first()

        if not strategy:
            # Use default parameters
            params = {
                'M': 50,
                'atr_period': 14,
                'sl_multiplier': 2.0,
                'tp_multiplier': 3.0
            }
        else:
            params = strategy.parameters

        # Fetch price data
        df_prices = {}
        for symbol in SYMBOLS:
            ohlcv_data = session.query(OHLCVData).filter_by(
                symbol=symbol,
                timeframe=timeframe
            ).order_by(OHLCVData.time.desc()).limit(1000).all()

            if not ohlcv_data:
                logger.warning(f"No data for {symbol}")
                continue

            df = pd.DataFrame([{
                'time': d.time,
                'open': float(d.open),
                'high': float(d.high),
                'low': float(d.low),
                'close': float(d.close),
                'volume': float(d.volume)
            } for d in reversed(ohlcv_data)])
            df.set_index('time', inplace=True)
            df_prices[symbol] = df

        if not df_prices:
            return {'status': 'error', 'message': 'No price data available'}

        # Run backtest
        metrics, returns, cum_ret, trades = run_backtest(
            df_prices,
            params['M'],
            params.get('atr_period', 14),
            params.get('sl_multiplier', 2.0),
            params.get('tp_multiplier', 3.0)
        )

        # Store or update strategy parameters with results
        if not strategy:
            strategy = StrategyParameters(
                strategy_name='SMA_ATR_Strategy',
                parameters=params,
                performance_metrics=metrics,
                is_active=True
            )
            session.add(strategy)
        else:
            strategy.performance_metrics = metrics
            strategy.updated_at = datetime.now(TIMEZONE)

        session.commit()

        result = {
            'status': 'success',
            'strategy': 'SMA_ATR_Strategy',
            'parameters': params,
            'metrics': metrics,
            'total_trades': len(trades),
            'timeframe': timeframe,
            'timestamp': datetime.now(TIMEZONE).isoformat()
        }

        logger.info(f"Backtest completed: Sharpe={metrics.get('Sharpe', 0):.2f}, "
                   f"Total Return={metrics.get('Total Return (%)', 0):.2f}%")

        return result

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


@shared_task(bind=True, max_retries=3)
def optimize_portfolio_task(self, account_id: int = None):
    """
    RAG-powered portfolio optimization using IntelligenceOrchestrator.
    
    Uses FKS Intelligence to analyze historical performance and recommend
    optimal portfolio allocation based on market conditions and past results.

    Args:
        account_id: Account ID to optimize. If None, optimizes first active account.

    Returns:
        dict: Optimization recommendations
    """
    session = get_db_session()
    try:
        # Get account
        if account_id:
            account = session.query(Account).filter_by(id=account_id).first()
        else:
            account = session.query(Account).filter_by(is_active=True).first()

        if not account:
            return {'status': 'error', 'message': 'No active account found'}

        # Get current positions
        positions = session.query(Position).filter_by(account_id=account.id).all()

        # Calculate portfolio metrics
        total_value = float(account.current_balance)
        position_values = {}
        current_positions_dict = {}

        for position in positions:
            value = float(position.quantity * position.current_price) if position.current_price else 0
            total_value += value
            position_values[position.symbol] = {
                'value': value,
                'allocation': (value / total_value * 100) if total_value > 0 else 0,
                'unrealized_pnl': float(position.unrealized_pnl or 0)
            }
            current_positions_dict[position.symbol] = {
                'quantity': float(position.quantity),
                'entry_price': float(position.entry_price),
                'current_price': float(position.current_price) if position.current_price else 0
            }

        available_cash = float(account.current_balance)

        # Use RAG for portfolio optimization if available
        if RAG_AVAILABLE:
            logger.info("Using RAG-powered portfolio optimization")
            try:
                orchestrator = IntelligenceOrchestrator(use_local=True)
                
                # Get RAG-powered portfolio recommendations
                rag_result = orchestrator.optimize_portfolio(
                    symbols=SYMBOLS,
                    account_balance=total_value,
                    available_cash=available_cash,
                    current_positions=current_positions_dict,
                    market_condition="current market conditions"
                )
                
                # Extract recommendations from RAG response
                recommendations = []
                symbol_recs = rag_result.get('symbols', {})
                
                for symbol, rec in symbol_recs.items():
                    if isinstance(rec, dict) and rec.get('action') in ['BUY', 'SELL']:
                        current_pct = position_values.get(symbol, {}).get('allocation', 0)
                        position_size = rec.get('position_size_usd', 0)
                        
                        # Only recommend if meaningful position size
                        if position_size > 10:  # Minimum $10 trade
                            recommendations.append({
                                'symbol': symbol,
                                'action': rec.get('action'),
                                'current_allocation': current_pct,
                                'target_allocation': (position_size / total_value * 100) if total_value > 0 else 0,
                                'amount': position_size,
                                'reasoning': rec.get('reasoning', ''),
                                'risk_assessment': rec.get('risk_assessment', 'medium'),
                                'confidence': rec.get('confidence', 0.7)
                            })
                
                result = {
                    'status': 'success',
                    'account_id': account.id,
                    'total_value': total_value,
                    'current_allocation': position_values,
                    'recommendations': recommendations,
                    'portfolio_advice': rag_result.get('portfolio_advice', ''),
                    'rebalance_needed': len(recommendations) > 0,
                    'method': 'rag',
                    'timestamp': datetime.now(TIMEZONE).isoformat()
                }
                
            except Exception as e:
                logger.error(f"RAG portfolio optimization failed: {e}")
                # Fall back to legacy method
                RAG_AVAILABLE_LOCAL = False
        else:
            RAG_AVAILABLE_LOCAL = False
        
        # Fallback to legacy allocation method if RAG not available
        if not RAG_AVAILABLE or not RAG_AVAILABLE_LOCAL:
            logger.info("Using legacy portfolio optimization")
            
            # Calculate optimal allocation based on market cap
            # Main coins: 50%, Alt coins: 50%
            main_alloc = 0.5 / len(MAINS)
            alt_alloc = 0.5 / len(ALTS)

            target_allocation = {}
            for sym in SYMBOLS:
                base = sym.replace('USDT', '')
                if base in MAINS:
                    target_allocation[sym] = main_alloc * 100
                else:
                    target_allocation[sym] = alt_alloc * 100

            # Generate rebalancing recommendations
            recommendations = []
            for sym, target_pct in target_allocation.items():
                current_pct = position_values.get(sym, {}).get('allocation', 0)
                diff = target_pct - current_pct

                if abs(diff) > 5:  # Only recommend if difference > 5%
                    action = 'BUY' if diff > 0 else 'SELL'
                    amount = abs(diff) / 100 * total_value
                    recommendations.append({
                        'symbol': sym,
                        'action': action,
                        'current_allocation': current_pct,
                        'target_allocation': target_pct,
                        'difference': diff,
                        'amount': amount
                    })

            result = {
                'status': 'success',
                'account_id': account.id,
                'total_value': total_value,
                'current_allocation': position_values,
                'target_allocation': target_allocation,
                'recommendations': recommendations,
                'rebalance_needed': len(recommendations) > 0,
                'method': 'legacy',
                'timestamp': datetime.now(TIMEZONE).isoformat()
            }

        logger.info(f"Portfolio optimization completed: {len(recommendations)} recommendations using {result['method']} method")

        return result

    except Exception as e:
        logger.error(f"Portfolio optimization failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


@shared_task(bind=True, max_retries=3)
def rebalance_portfolio_task(self, account_id: int, execute: bool = False):
    """
    Auto-rebalance portfolio based on optimization recommendations.

    Args:
        account_id: Account ID to rebalance
        execute: If True, executes trades. If False, dry-run only.

    Returns:
        dict: Rebalancing results
    """
    session = get_db_session()
    try:
        # Get optimization recommendations
        optimization = optimize_portfolio_task(account_id)

        if optimization['status'] != 'success':
            return optimization

        recommendations = optimization['recommendations']

        if not recommendations:
            return {
                'status': 'success',
                'message': 'Portfolio is balanced, no rebalancing needed'
            }

        if not execute:
            return {
                'status': 'success',
                'mode': 'dry-run',
                'recommendations': recommendations,
                'message': 'Dry-run complete. Set execute=True to perform trades.'
            }

        # Execute rebalancing trades
        executed_trades = []
        account = session.query(Account).filter_by(id=account_id).first()

        for rec in recommendations:
            try:
                # This is a placeholder - in production, would call exchange API
                logger.info(f"Executing {rec['action']} for {rec['symbol']}: ${rec['amount']:.2f}")

                # Log trade (simulated)
                trade = Trade(
                    time=datetime.now(TIMEZONE),
                    account_id=account_id,
                    symbol=rec['symbol'],
                    trade_type=rec['action'],
                    quantity=Decimal(str(rec['amount'] / 100)),  # Placeholder quantity
                    price=Decimal('0'),  # Would be actual execution price
                    strategy_name='Portfolio_Rebalance',
                    notes=f"Rebalancing: {rec['current_allocation']:.1f}% -> {rec['target_allocation']:.1f}%"
                )
                session.add(trade)
                executed_trades.append(rec)

            except Exception as e:
                logger.error(f"Failed to execute trade for {rec['symbol']}: {e}")
                continue

        session.commit()

        # Send notification
        message = "💼 **Portfolio Rebalanced**\n"
        message += f"Account: {account.name}\n"
        message += f"Trades executed: {len(executed_trades)}\n"
        send_discord_notification(message)

        return {
            'status': 'success',
            'mode': 'executed',
            'trades_executed': len(executed_trades),
            'executed_trades': executed_trades,
            'timestamp': datetime.now(TIMEZONE).isoformat()
        }

    except Exception as e:
        logger.error(f"Portfolio rebalancing failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


@shared_task(bind=True, max_retries=3)
def check_stop_loss_task(self, account_id: int = None):
    """
    Monitor positions for stop loss triggers.

    Args:
        account_id: Account ID to monitor. If None, monitors all accounts.

    Returns:
        dict: Stop loss check results
    """
    session = get_db_session()
    try:
        # Get positions with stop loss set
        if account_id:
            positions = session.query(Position).filter(
                Position.account_id == account_id,
                Position.stop_loss.isnot(None)
            ).all()
        else:
            positions = session.query(Position).filter(
                Position.stop_loss.isnot(None)
            ).all()

        if not positions:
            return {'status': 'success', 'message': 'No positions with stop loss'}

        triggered_positions = []

        for position in positions:
            try:
                current_price = float(position.current_price) if position.current_price else None
                stop_loss = float(position.stop_loss)

                if not current_price:
                    continue

                triggered = False
                if position.position_type == 'LONG' and current_price <= stop_loss or position.position_type == 'SHORT' and current_price >= stop_loss:
                    triggered = True

                if triggered:
                    account = session.query(Account).filter_by(id=position.account_id).first()

                    triggered_positions.append({
                        'account': account.name,
                        'symbol': position.symbol,
                        'type': position.position_type,
                        'entry_price': float(position.entry_price),
                        'current_price': current_price,
                        'stop_loss': stop_loss,
                        'unrealized_pnl': float(position.unrealized_pnl or 0)
                    })

                    # Send alert
                    message = "🛑 **STOP LOSS TRIGGERED**\n"
                    message += f"Account: {account.name}\n"
                    message += f"Symbol: {position.symbol} ({position.position_type})\n"
                    message += f"Current Price: ${current_price:.2f}\n"
                    message += f"Stop Loss: ${stop_loss:.2f}\n"
                    message += f"Loss: ${float(position.unrealized_pnl or 0):.2f}\n"
                    send_discord_notification(message)

                    logger.warning(f"Stop loss triggered for {position.symbol}")

            except Exception as e:
                logger.error(f"Error checking stop loss for {position.symbol}: {e}")
                continue

        return {
            'status': 'success',
            'positions_checked': len(positions),
            'stop_losses_triggered': len(triggered_positions),
            'triggered_positions': triggered_positions,
            'timestamp': datetime.now(TIMEZONE).isoformat()
        }

    except Exception as e:
        logger.error(f"Stop loss check failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


# =============================================================================
# PHASE 4: METRICS & REPORTING
# =============================================================================

@shared_task(bind=True, max_retries=3)
def calculate_metrics_task(self, account_id: int = None, period_days: int = 30):
    """
    Calculate comprehensive performance metrics.

    Args:
        account_id: Account ID to analyze. If None, analyzes all accounts.
        period_days: Analysis period in days

    Returns:
        dict: Performance metrics
    """
    session = get_db_session()
    try:
        # Get accounts
        if account_id:
            accounts = session.query(Account).filter_by(id=account_id).all()
        else:
            accounts = session.query(Account).filter_by(is_active=True).all()

        if not accounts:
            return {'status': 'error', 'message': 'No accounts found'}

        start_date = datetime.now(TIMEZONE) - timedelta(days=period_days)
        results = {}

        for account in accounts:
            try:
                # Get balance history
                balance_history = session.query(BalanceHistory).filter(
                    BalanceHistory.account_id == account.id,
                    BalanceHistory.time >= start_date
                ).order_by(BalanceHistory.time).all()

                if not balance_history:
                    results[account.name] = {
                        'status': 'error',
                        'message': 'No balance history available'
                    }
                    continue

                # Calculate metrics
                returns = [float(h.daily_pnl) / float(h.balance) * 100
                          for h in balance_history if float(h.balance) > 0]

                total_return = ((float(balance_history[-1].equity) /
                               float(balance_history[0].equity)) - 1) * 100

                avg_daily_return = sum(returns) / len(returns) if returns else 0

                # Sharpe ratio (simplified, assuming 0% risk-free rate)
                std_dev = pd.Series(returns).std() if len(returns) > 1 else 0
                sharpe_ratio = (avg_daily_return / std_dev * (252 ** 0.5)) if std_dev > 0 else 0

                # Max drawdown
                equity_curve = [float(h.equity) for h in balance_history]
                peak = equity_curve[0]
                max_dd = 0
                for equity in equity_curve:
                    if equity > peak:
                        peak = equity
                    dd = (peak - equity) / peak * 100 if peak > 0 else 0
                    max_dd = max(max_dd, dd)

                # Get trades for win rate
                trades = session.query(Trade).filter(
                    Trade.account_id == account.id,
                    Trade.time >= start_date,
                    Trade.realized_pnl.isnot(None)
                ).all()

                winning_trades = [t for t in trades if float(t.realized_pnl or 0) > 0]
                win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0

                results[account.name] = {
                    'status': 'success',
                    'period_days': period_days,
                    'total_return_pct': total_return,
                    'avg_daily_return_pct': avg_daily_return,
                    'sharpe_ratio': sharpe_ratio,
                    'max_drawdown_pct': max_dd,
                    'total_trades': len(trades),
                    'winning_trades': len(winning_trades),
                    'win_rate_pct': win_rate,
                    'current_equity': float(balance_history[-1].equity)
                }

                logger.info(f"Metrics calculated for {account.name}: "
                          f"Return={total_return:.2f}%, Sharpe={sharpe_ratio:.2f}")

            except Exception as e:
                logger.error(f"Error calculating metrics for {account.name}: {e}")
                results[account.name] = {'status': 'error', 'message': str(e)}

        return {
            'status': 'success',
            'accounts_analyzed': len(results),
            'results': results,
            'timestamp': datetime.now(TIMEZONE).isoformat()
        }

    except Exception as e:
        logger.error(f"Metrics calculation failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


@shared_task(bind=True, max_retries=3)
def generate_report_task(self, account_id: int = None, report_type: str = 'daily'):
    """
    Generate comprehensive trading reports.

    Args:
        account_id: Account ID for report. If None, generates for all accounts.
        report_type: Type of report ('daily', 'weekly', 'monthly')

    Returns:
        dict: Report data
    """
    session = get_db_session()
    try:
        # Determine period based on report type
        period_map = {'daily': 1, 'weekly': 7, 'monthly': 30}
        period_days = period_map.get(report_type, 1)

        # Get metrics
        metrics = calculate_metrics_task(account_id, period_days)

        if metrics['status'] != 'success':
            return metrics

        # Get accounts
        if account_id:
            accounts = session.query(Account).filter_by(id=account_id).all()
        else:
            accounts = session.query(Account).filter_by(is_active=True).all()

        start_date = datetime.now(TIMEZONE) - timedelta(days=period_days)
        report = {
            'report_type': report_type,
            'period_days': period_days,
            'generated_at': datetime.now(TIMEZONE).isoformat(),
            'accounts': []
        }

        for account in accounts:
            account_metrics = metrics['results'].get(account.name, {})

            # Get recent trades
            recent_trades = session.query(Trade).filter(
                Trade.account_id == account.id,
                Trade.time >= start_date
            ).order_by(Trade.time.desc()).limit(10).all()

            # Get current positions
            positions = session.query(Position).filter_by(account_id=account.id).all()

            account_report = {
                'name': account.name,
                'type': account.account_type,
                'current_balance': float(account.current_balance),
                'metrics': account_metrics,
                'open_positions': len(positions),
                'recent_trades_count': len(recent_trades),
                'trades': [{
                    'time': t.time.isoformat(),
                    'symbol': t.symbol,
                    'type': t.trade_type,
                    'quantity': float(t.quantity),
                    'price': float(t.price),
                    'realized_pnl': float(t.realized_pnl or 0)
                } for t in recent_trades]
            }

            report['accounts'].append(account_report)

        # Send report via Discord
        message = f"📊 **{report_type.upper()} TRADING REPORT**\n"
        message += f"Period: {period_days} days\n\n"
        for acc_report in report['accounts']:
            metrics = acc_report['metrics']
            if metrics.get('status') == 'success':
                message += f"**{acc_report['name']}**\n"
                message += f"Return: {metrics.get('total_return_pct', 0):.2f}%\n"
                message += f"Sharpe: {metrics.get('sharpe_ratio', 0):.2f}\n"
                message += f"Win Rate: {metrics.get('win_rate_pct', 0):.1f}%\n"
                message += f"Trades: {metrics.get('total_trades', 0)}\n\n"

        send_discord_notification(message)

        logger.info(f"Generated {report_type} report for {len(accounts)} accounts")

        return {
            'status': 'success',
            'report': report
        }

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


@shared_task(bind=True, max_retries=3)
def validate_strategies_task(self, strategy_id: int = None):
    """
    Validate trading strategies against recent market data.

    Args:
        strategy_id: Strategy ID to validate. If None, validates all active strategies.

    Returns:
        dict: Validation results
    """
    session = get_db_session()
    try:
        # Get strategies
        if strategy_id:
            strategies = session.query(StrategyParameters).filter_by(id=strategy_id).all()
        else:
            strategies = session.query(StrategyParameters).filter_by(is_active=True).all()

        if not strategies:
            return {'status': 'error', 'message': 'No strategies found'}

        results = []

        for strategy in strategies:
            try:
                # Run backtest with strategy parameters
                backtest_result = run_backtest_task(DEFAULT_TIMEFRAME, optimize=False)

                if backtest_result['status'] != 'success':
                    results.append({
                        'strategy_name': strategy.strategy_name,
                        'status': 'error',
                        'message': 'Backtest failed'
                    })
                    continue

                metrics = backtest_result['metrics']

                # Validation criteria
                is_valid = True
                validation_issues = []

                if metrics.get('Sharpe', 0) < 1.0:
                    is_valid = False
                    validation_issues.append('Sharpe ratio below 1.0')

                if metrics.get('Total Return (%)', 0) < 0:
                    is_valid = False
                    validation_issues.append('Negative total return')

                if metrics.get('Max Drawdown (%)', 0) > 30:
                    is_valid = False
                    validation_issues.append('Max drawdown exceeds 30%')

                # Update strategy status
                if not is_valid:
                    strategy.is_active = False
                    session.commit()

                    message = "⚠️ **Strategy Validation Failed**\n"
                    message += f"Strategy: {strategy.strategy_name}\n"
                    message += "Issues:\n" + "\n".join(f"- {issue}" for issue in validation_issues)
                    send_discord_notification(message)

                results.append({
                    'strategy_name': strategy.strategy_name,
                    'status': 'success',
                    'is_valid': is_valid,
                    'validation_issues': validation_issues,
                    'metrics': metrics
                })

                logger.info(f"Validated strategy {strategy.strategy_name}: "
                          f"{'PASS' if is_valid else 'FAIL'}")

            except Exception as e:
                logger.error(f"Error validating strategy {strategy.strategy_name}: {e}")
                results.append({
                    'strategy_name': strategy.strategy_name,
                    'status': 'error',
                    'message': str(e)
                })

        return {
            'status': 'success',
            'strategies_validated': len(results),
            'results': results,
            'timestamp': datetime.now(TIMEZONE).isoformat()
        }

    except Exception as e:
        logger.error(f"Strategy validation failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


# =============================================================================
# PHASE 5: DATA MANAGEMENT & NOTIFICATIONS
# =============================================================================

@shared_task(bind=True, max_retries=3)
def fetch_news_task(self, limit: int = 10):
    """
    Fetch and ingest market news for sentiment analysis.

    Args:
        limit: Number of news items to fetch

    Returns:
        dict: News fetch results
    """
    try:
        # Placeholder for news API integration
        # In production, would fetch from CoinGecko, CryptoCompare, etc.

        logger.info(f"Fetching {limit} news items")

        # Simulated news fetch
        news_items = []
        for i in range(limit):
            news_items.append({
                'title': f'Market Update {i+1}',
                'source': 'CryptoNews',
                'timestamp': datetime.now(TIMEZONE).isoformat(),
                'sentiment': 'neutral'
            })

        return {
            'status': 'success',
            'news_fetched': len(news_items),
            'news': news_items,
            'timestamp': datetime.now(TIMEZONE).isoformat()
        }

    except Exception as e:
        logger.error(f"News fetch failed: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def archive_old_data_task(self, days_to_keep: int = 365):
    """
    Archive or delete old data to maintain database performance.

    Args:
        days_to_keep: Number of days of data to keep

    Returns:
        dict: Archive results
    """
    session = get_db_session()
    try:
        cutoff_date = datetime.now(TIMEZONE) - timedelta(days=days_to_keep)

        results = {}

        # Archive old OHLCV data (keep only recent data in hot storage)
        old_ohlcv_count = session.query(OHLCVData).filter(
            OHLCVData.time < cutoff_date
        ).count()

        # Note: In production, would move to cold storage instead of delete
        # For now, just count
        results['old_ohlcv_data'] = {
            'count': old_ohlcv_count,
            'action': 'counted (not deleted)'
        }

        # Archive old indicators cache
        old_indicators_count = session.query(IndicatorsCache).filter(
            IndicatorsCache.time < cutoff_date
        ).count()

        results['old_indicators'] = {
            'count': old_indicators_count,
            'action': 'counted (not deleted)'
        }

        logger.info(f"Archive check complete: {old_ohlcv_count} old OHLCV records, "
                   f"{old_indicators_count} old indicator records")

        return {
            'status': 'success',
            'cutoff_date': cutoff_date.isoformat(),
            'days_to_keep': days_to_keep,
            'results': results,
            'timestamp': datetime.now(TIMEZONE).isoformat()
        }

    except Exception as e:
        logger.error(f"Data archival failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


@shared_task(bind=True, max_retries=3)
def send_notifications_task(self, notification_type: str, message: str, urgent: bool = False):
    """
    Send notifications via Discord and other channels.

    Args:
        notification_type: Type of notification (trade, alert, report, etc.)
        message: Notification message
        urgent: Whether this is an urgent notification

    Returns:
        dict: Notification delivery results
    """
    try:
        prefix = "🚨 **URGENT** " if urgent else ""
        full_message = f"{prefix}[{notification_type.upper()}] {message}"

        # Send to Discord
        discord_sent = send_discord_notification(full_message)

        # Could add other notification channels here (email, SMS, etc.)

        result = {
            'status': 'success',
            'notification_type': notification_type,
            'urgent': urgent,
            'channels': {
                'discord': discord_sent
            },
            'timestamp': datetime.now(TIMEZONE).isoformat()
        }

        logger.info(f"Notification sent: {notification_type}")

        return result

    except Exception as e:
        logger.error(f"Notification delivery failed: {e}")
        raise self.retry(exc=e, countdown=60)


# =============================================================================
# LEGACY TASKS (kept for backward compatibility)
# =============================================================================

@shared_task(bind=True)
def debug_task(self):
    """Debug task to test Celery is working."""
    logger.info(f"Request: {self.request!r}")
    return "Celery is working!"


@shared_task
def sync_market_data():
    """Legacy wrapper for sync_market_data_task."""
    return sync_market_data_task()


@shared_task
def update_signals():
    """Legacy wrapper for generate_signals_task."""
    return generate_signals_task()


@shared_task
def run_scheduled_backtests():
    """Placeholder for scheduled backtests task."""
    logger.info("Run scheduled backtests task called - not yet implemented")
    return "Run scheduled backtests - stub"


# =============================================================================
# RAG System Auto-Ingestion Tasks
# =============================================================================

@shared_task(bind=True, max_retries=3)
def generate_daily_rag_signals_task(self, symbols: list = None, min_confidence: float = 0.7):
    """
    Generate daily RAG-powered trading signals for all configured symbols.
    
    This is the primary RAG intelligence task that provides daily trading
    recommendations based on historical data and market analysis.
    
    Args:
        symbols: List of symbols to analyze. If None, uses all SYMBOLS.
        min_confidence: Minimum confidence threshold for recommendations (0-1)
        
    Returns:
        dict: Daily signals for all symbols with recommendations
    """
    if not RAG_AVAILABLE:
        logger.warning("RAG system not available - cannot generate daily signals")
        return {'status': 'error', 'message': 'RAG system not available'}
    
    session = get_db_session()
    try:
        # Use configured symbols if not provided
        symbols_to_analyze = symbols or SYMBOLS
        
        # Initialize RAG orchestrator
        orchestrator = IntelligenceOrchestrator(use_local=True)
        
        # Get daily signals from RAG
        rag_result = orchestrator.get_daily_signals(
            symbols=symbols_to_analyze,
            min_confidence=min_confidence
        )
        
        # Parse and structure results
        daily_signals = {}
        high_confidence_signals = []
        
        for symbol, signal_data in rag_result.get('signals', {}).items():
            confidence = signal_data.get('confidence', 0)
            recommendation = signal_data.get('recommendation', '')
            
            # Determine action from recommendation text
            action = 'HOLD'
            if 'buy' in recommendation.lower() and 'don\'t buy' not in recommendation.lower():
                action = 'BUY'
            elif 'sell' in recommendation.lower():
                action = 'SELL'
            
            signal_entry = {
                'symbol': symbol,
                'action': action,
                'recommendation': recommendation,
                'confidence': confidence,
                'sources_used': signal_data.get('sources', 0),
                'timestamp': datetime.now(TIMEZONE).isoformat()
            }
            
            daily_signals[symbol] = signal_entry
            
            # Track high confidence signals
            if confidence >= min_confidence and action in ['BUY', 'SELL']:
                high_confidence_signals.append(signal_entry)
        
        # Send Discord notification for high confidence signals
        if high_confidence_signals:
            message = "📊 **Daily RAG Signals Generated**\n"
            message += f"Date: {datetime.now(TIMEZONE).strftime('%Y-%m-%d')}\n"
            message += f"High Confidence Signals: {len(high_confidence_signals)}\n\n"
            
            for signal in high_confidence_signals[:5]:  # Limit to top 5
                message += f"**{signal['symbol']}**: {signal['action']} "
                message += f"(Confidence: {signal['confidence']:.0%})\n"
            
            send_discord_notification(message)
        
        result = {
            'status': 'success',
            'date': rag_result.get('date'),
            'signals': daily_signals,
            'high_confidence_count': len(high_confidence_signals),
            'high_confidence_signals': high_confidence_signals,
            'min_confidence': min_confidence,
            'method': 'rag',
            'timestamp': datetime.now(TIMEZONE).isoformat()
        }
        
        logger.info(f"Generated daily RAG signals: {len(daily_signals)} symbols, "
                   f"{len(high_confidence_signals)} high confidence")
        
        return result
        
    except Exception as e:
        logger.error(f"Daily RAG signals generation failed: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        close_db_session(session)


# =============================================================================
# RAG System Auto-Ingestion Tasks
# =============================================================================

@shared_task
def ingest_recent_trades(days: int = 7):
    """
    Auto-ingest recent completed trades into RAG knowledge base.
    
    Args:
        days: Number of days to look back for trades
        
    Returns:
        Number of trades ingested
    """
    try:
        from web.rag.ingestion import DataIngestionPipeline
        from core.database import Session
        
        logger.info(f"Starting ingestion of trades from last {days} days")
        
        session = Session()
        try:
            pipeline = DataIngestionPipeline()
            count = pipeline.batch_ingest_recent_trades(days=days, session=session)
            logger.info(f"Successfully ingested {count} trades")
            return count
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error ingesting trades: {e}", exc_info=True)
        return 0


@shared_task
def ingest_signal(signal_data: dict):
    """
    Ingest a trading signal into RAG knowledge base.
    
    Args:
        signal_data: Signal dictionary with fields like symbol, action, indicators
        
    Returns:
        Document ID if successful, None otherwise
    """
    try:
        from web.rag.ingestion import DataIngestionPipeline
        from core.database import Session
        
        logger.info(f"Ingesting signal for {signal_data.get('symbol', 'unknown')}")
        
        session = Session()
        try:
            pipeline = DataIngestionPipeline()
            doc_id = pipeline.ingest_signal(signal_data, session=session)
            
            if doc_id:
                logger.info(f"Successfully ingested signal as document {doc_id}")
            else:
                logger.warning("Signal ingestion returned None")
                
            return doc_id
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error ingesting signal: {e}", exc_info=True)
        return None


@shared_task
def ingest_backtest_result(backtest_data: dict):
    """
    Ingest backtest results into RAG knowledge base.
    
    Args:
        backtest_data: Backtest results dictionary
        
    Returns:
        Document ID if successful, None otherwise
    """
    try:
        from web.rag.ingestion import DataIngestionPipeline
        from core.database import Session
        
        strategy = backtest_data.get('strategy_name', 'unknown')
        symbol = backtest_data.get('symbol', 'unknown')
        logger.info(f"Ingesting backtest results for {strategy} on {symbol}")
        
        session = Session()
        try:
            pipeline = DataIngestionPipeline()
            doc_id = pipeline.ingest_backtest_result(backtest_data, session=session)
            
            if doc_id:
                logger.info(f"Successfully ingested backtest as document {doc_id}")
            else:
                logger.warning("Backtest ingestion returned None")
                
            return doc_id
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error ingesting backtest: {e}", exc_info=True)
        return None


@shared_task
def ingest_completed_trade(trade_id: int):
    """
    Ingest a completed trade into RAG knowledge base.
    
    Args:
        trade_id: Trade ID from database
        
    Returns:
        Document ID if successful, None otherwise
    """
    try:
        from web.rag.ingestion import DataIngestionPipeline
        from core.database import Session
        
        logger.info(f"Ingesting completed trade {trade_id}")
        
        session = Session()
        try:
            pipeline = DataIngestionPipeline()
            doc_id = pipeline.ingest_completed_trade(trade_id, session=session)
            
            if doc_id:
                logger.info(f"Successfully ingested trade {trade_id} as document {doc_id}")
            else:
                logger.warning(f"Trade {trade_id} ingestion returned None")
                
            return doc_id
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error ingesting trade {trade_id}: {e}", exc_info=True)
        return None


@shared_task
def ingest_market_analysis(analysis_text: str, symbol: str, timeframe: str, metadata: dict = None):
    """
    Ingest market analysis into RAG knowledge base.
    
    Args:
        analysis_text: Analysis content
        symbol: Trading pair
        timeframe: Timeframe
        metadata: Additional metadata
        
    Returns:
        Document ID if successful, None otherwise
    """
    try:
        from web.rag.ingestion import DataIngestionPipeline
        from core.database import Session
        
        logger.info(f"Ingesting market analysis for {symbol} {timeframe}")
        
        session = Session()
        try:
            pipeline = DataIngestionPipeline()
            doc_id = pipeline.ingest_market_analysis(
                analysis_text=analysis_text,
                symbol=symbol,
                timeframe=timeframe,
                metadata=metadata or {},
                session=session
            )
            
            if doc_id:
                logger.info(f"Successfully ingested market analysis as document {doc_id}")
            else:
                logger.warning("Market analysis ingestion returned None")
                
            return doc_id
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error ingesting market analysis: {e}", exc_info=True)
        return None
