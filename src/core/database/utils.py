# src/db_utils.py
"""Database utility functions for TimescaleDB operations"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import pytz
from database import (
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
from sqlalchemy import and_, desc, func, text
from sqlalchemy.dialects.postgresql import insert

from framework.config.constants import SYMBOLS

TIMEZONE = pytz.timezone("America/Toronto")

# ============================================================================
# OHLCV DATA FUNCTIONS
# ============================================================================


def bulk_insert_ohlcv(data: list[dict], symbol: str, timeframe: str) -> int:
    """
    Bulk insert OHLCV data with upsert (update on conflict)

    Args:
        data: List of dicts with keys: time, open, high, low, close, volume, etc.
        symbol: Trading pair symbol
        timeframe: Timeframe string (1m, 5m, etc.)

    Returns:
        Number of records inserted/updated
    """
    session = Session()
    try:
        # Prepare data
        records = []
        for candle in data:
            records.append(
                {
                    "time": candle["time"],
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open": candle["open"],
                    "high": candle["high"],
                    "low": candle["low"],
                    "close": candle["close"],
                    "volume": candle["volume"],
                    "quote_volume": candle.get("quote_volume"),
                    "trades_count": candle.get("trades_count"),
                    "taker_buy_base_volume": candle.get("taker_buy_base_volume"),
                    "taker_buy_quote_volume": candle.get("taker_buy_quote_volume"),
                    "created_at": datetime.now(TIMEZONE),
                }
            )

        if not records:
            return 0

        # Use PostgreSQL INSERT ... ON CONFLICT for upsert
        stmt = insert(OHLCVData).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "timeframe", "time"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "quote_volume": stmt.excluded.quote_volume,
                "trades_count": stmt.excluded.trades_count,
                "taker_buy_base_volume": stmt.excluded.taker_buy_base_volume,
                "taker_buy_quote_volume": stmt.excluded.taker_buy_quote_volume,
            },
        )

        session.execute(stmt)
        session.commit()
        return len(records)

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_ohlcv_data(
    symbol: str,
    timeframe: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Retrieve OHLCV data as pandas DataFrame

    Args:
        symbol: Trading pair symbol
        timeframe: Timeframe string
        start_time: Start datetime (inclusive)
        end_time: End datetime (inclusive)
        limit: Maximum number of records

    Returns:
        DataFrame with OHLCV data indexed by time
    """
    session = Session()
    try:
        query = session.query(OHLCVData).filter(
            and_(OHLCVData.symbol == symbol, OHLCVData.timeframe == timeframe)
        )

        if start_time:
            query = query.filter(OHLCVData.time >= start_time)
        if end_time:
            query = query.filter(OHLCVData.time <= end_time)

        query = query.order_by(desc(OHLCVData.time))

        if limit:
            query = query.limit(limit)

        results = query.all()

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(
            [
                {
                    "time": r.time,
                    "open": float(r.open),
                    "high": float(r.high),
                    "low": float(r.low),
                    "close": float(r.close),
                    "volume": float(r.volume),
                }
                for r in results
            ]
        )

        df.set_index("time", inplace=True)
        df.sort_index(inplace=True)
        return df

    finally:
        session.close()


def get_latest_ohlcv_time(symbol: str, timeframe: str) -> datetime | None:
    """Get the timestamp of the most recent OHLCV data"""
    session = Session()
    try:
        result = (
            session.query(func.max(OHLCVData.time))
            .filter(and_(OHLCVData.symbol == symbol, OHLCVData.timeframe == timeframe))
            .scalar()
        )
        return result
    finally:
        session.close()


def get_oldest_ohlcv_time(symbol: str, timeframe: str) -> datetime | None:
    """Get the timestamp of the oldest OHLCV data"""
    session = Session()
    try:
        result = (
            session.query(func.min(OHLCVData.time))
            .filter(and_(OHLCVData.symbol == symbol, OHLCVData.timeframe == timeframe))
            .scalar()
        )
        return result
    finally:
        session.close()


def get_ohlcv_count(symbol: str, timeframe: str) -> int:
    """Get the count of OHLCV records for a symbol/timeframe"""
    session = Session()
    try:
        count = (
            session.query(OHLCVData)
            .filter(and_(OHLCVData.symbol == symbol, OHLCVData.timeframe == timeframe))
            .count()
        )
        return count
    finally:
        session.close()


# ============================================================================
# SYNC STATUS FUNCTIONS
# ============================================================================


def update_sync_status(
    symbol: str, timeframe: str, status: str, error_message: str | None = None
) -> None:
    """Update sync status for a symbol/timeframe pair"""
    session = Session()
    try:
        sync = (
            session.query(SyncStatus)
            .filter(
                and_(SyncStatus.symbol == symbol, SyncStatus.timeframe == timeframe)
            )
            .first()
        )

        if sync:
            sync.sync_status = status
            sync.last_sync_time = datetime.now(TIMEZONE)
            sync.error_message = error_message

            # Update data range info
            oldest = get_oldest_ohlcv_time(symbol, timeframe)
            newest = get_latest_ohlcv_time(symbol, timeframe)
            count = get_ohlcv_count(symbol, timeframe)

            sync.oldest_data_time = oldest
            sync.newest_data_time = newest
            sync.total_candles = count
        else:
            sync = SyncStatus(
                symbol=symbol,
                timeframe=timeframe,
                sync_status=status,
                last_sync_time=datetime.now(TIMEZONE),
                error_message=error_message,
            )
            session.add(sync)

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_sync_status(
    symbol: str | None = None, timeframe: str | None = None
) -> list[dict]:
    """Get sync status for symbols/timeframes"""
    session = Session()
    try:
        query = session.query(SyncStatus)

        if symbol:
            query = query.filter(SyncStatus.symbol == symbol)
        if timeframe:
            query = query.filter(SyncStatus.timeframe == timeframe)

        results = query.all()

        return [
            {
                "symbol": r.symbol,
                "timeframe": r.timeframe,
                "status": r.sync_status,
                "last_sync": r.last_sync_time,
                "oldest_data": r.oldest_data_time,
                "newest_data": r.newest_data_time,
                "total_candles": r.total_candles,
                "error": r.error_message,
            }
            for r in results
        ]
    finally:
        session.close()


# ============================================================================
# ACCOUNT FUNCTIONS
# ============================================================================


def create_account(
    name: str,
    account_type: str,
    initial_balance: float,
    broker: str | None = None,
    currency: str = "USDT",
    metadata: dict | None = None,
) -> Account:
    """Create a new trading account"""
    session = Session()
    try:
        account = Account(
            name=name,
            account_type=account_type,
            broker=broker,
            initial_balance=initial_balance,
            current_balance=initial_balance,
            currency=currency,
            metadata=metadata,
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        return account
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_accounts(active_only: bool = True) -> list[Account]:
    """Get all accounts"""
    session = Session()
    try:
        query = session.query(Account)
        if active_only:
            query = query.filter(Account.is_active)
        return query.all()
    finally:
        session.close()


def get_account_by_id(account_id: int) -> Account | None:
    """Get account by ID"""
    session = Session()
    try:
        return session.query(Account).filter(Account.id == account_id).first()
    finally:
        session.close()


# ============================================================================
# POSITION FUNCTIONS
# ============================================================================


def update_position(
    account_id: int,
    symbol: str,
    quantity: float,
    entry_price: float,
    current_price: float,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    position_type: str = "LONG",
) -> Position:
    """Create or update a position"""
    session = Session()
    try:
        position = (
            session.query(Position)
            .filter(and_(Position.account_id == account_id, Position.symbol == symbol))
            .first()
        )

        unrealized_pnl = (current_price - entry_price) * quantity
        unrealized_pnl_percent = ((current_price - entry_price) / entry_price) * 100

        if position:
            position.quantity = quantity
            position.current_price = current_price
            position.stop_loss = stop_loss
            position.take_profit = take_profit
            position.unrealized_pnl = unrealized_pnl
            position.unrealized_pnl_percent = unrealized_pnl_percent
        else:
            position = Position(
                account_id=account_id,
                symbol=symbol,
                position_type=position_type,
                quantity=quantity,
                entry_price=entry_price,
                current_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_percent=unrealized_pnl_percent,
            )
            session.add(position)

        session.commit()
        session.refresh(position)
        return position
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_positions(account_id: int) -> list[Position]:
    """Get all positions for an account"""
    session = Session()
    try:
        return session.query(Position).filter(Position.account_id == account_id).all()
    finally:
        session.close()


def close_position(account_id: int, symbol: str) -> None:
    """Close (delete) a position"""
    session = Session()
    try:
        session.query(Position).filter(
            and_(Position.account_id == account_id, Position.symbol == symbol)
        ).delete()
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


# ============================================================================
# TRADE FUNCTIONS
# ============================================================================


def record_trade(
    account_id: int,
    symbol: str,
    trade_type: str,
    quantity: float,
    price: float,
    time: datetime | None = None,
    fee: float | None = None,
    realized_pnl: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    order_type: str = "MARKET",
    strategy_name: str | None = None,
    metadata: dict | None = None,
) -> Trade:
    """Record a trade"""
    session = Session()
    try:
        trade = Trade(
            time=time or datetime.now(TIMEZONE),
            account_id=account_id,
            symbol=symbol,
            trade_type=trade_type,
            quantity=quantity,
            price=price,
            fee=fee,
            realized_pnl=realized_pnl,
            stop_loss=stop_loss,
            take_profit=take_profit,
            order_type=order_type,
            strategy_name=strategy_name,
            metadata=metadata,
        )
        session.add(trade)
        session.commit()
        session.refresh(trade)
        return trade
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_trades(
    account_id: int,
    symbol: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 100,
) -> list[Trade]:
    """Get trades for an account"""
    session = Session()
    try:
        query = session.query(Trade).filter(Trade.account_id == account_id)

        if symbol:
            query = query.filter(Trade.symbol == symbol)
        if start_time:
            query = query.filter(Trade.time >= start_time)
        if end_time:
            query = query.filter(Trade.time <= end_time)

        query = query.order_by(desc(Trade.time)).limit(limit)
        return query.all()
    finally:
        session.close()


# ============================================================================
# BALANCE HISTORY FUNCTIONS
# ============================================================================


def record_balance_snapshot(
    account_id: int,
    balance: float,
    equity: float,
    time: datetime | None = None,
    daily_pnl: float | None = None,
    cumulative_pnl: float | None = None,
) -> BalanceHistory:
    """Record a balance snapshot"""
    session = Session()
    try:
        snapshot = BalanceHistory(
            time=time or datetime.now(TIMEZONE),
            account_id=account_id,
            balance=balance,
            equity=equity,
            daily_pnl=daily_pnl,
            cumulative_pnl=cumulative_pnl,
        )
        session.add(snapshot)
        session.commit()
        session.refresh(snapshot)
        return snapshot
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_balance_history(
    account_id: int,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 1000,
) -> pd.DataFrame:
    """Get balance history as DataFrame"""
    session = Session()
    try:
        query = session.query(BalanceHistory).filter(
            BalanceHistory.account_id == account_id
        )

        if start_time:
            query = query.filter(BalanceHistory.time >= start_time)
        if end_time:
            query = query.filter(BalanceHistory.time <= end_time)

        query = query.order_by(BalanceHistory.time).limit(limit)
        results = query.all()

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(
            [
                {
                    "time": r.time,
                    "balance": float(r.balance),
                    "equity": float(r.equity),
                    "daily_pnl": float(r.daily_pnl) if r.daily_pnl else 0,
                    "cumulative_pnl": (
                        float(r.cumulative_pnl) if r.cumulative_pnl else 0
                    ),
                }
                for r in results
            ]
        )

        df.set_index("time", inplace=True)
        return df
    finally:
        session.close()


# ============================================================================
# STRATEGY PARAMETERS FUNCTIONS
# ============================================================================


def save_strategy_parameters(
    strategy_name: str,
    parameters: dict,
    symbol: str | None = None,
    timeframe: str | None = None,
    performance_metrics: dict | None = None,
    is_active: bool = False,
) -> StrategyParameters:
    """Save optimized strategy parameters"""
    session = Session()
    try:
        strategy = StrategyParameters(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            parameters=parameters,
            performance_metrics=performance_metrics,
            is_active=is_active,
        )
        session.add(strategy)
        session.commit()
        session.refresh(strategy)
        return strategy
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_active_strategy_parameters(strategy_name: str) -> StrategyParameters | None:
    """Get active strategy parameters"""
    session = Session()
    try:
        return (
            session.query(StrategyParameters)
            .filter(
                and_(
                    StrategyParameters.strategy_name == strategy_name,
                    StrategyParameters.is_active,
                )
            )
            .first()
        )
    finally:
        session.close()
