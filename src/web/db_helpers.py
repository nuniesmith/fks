"""Database helper functions for web views."""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database.models import Account, BalanceHistory, Position, Trade, Session as DBSession


def get_db_session() -> Session:
    """Get a database session."""
    return DBSession()


def close_db_session(session: Session) -> None:
    """Close a database session."""
    if session:
        session.close()


def get_user_accounts(user_id: int = None) -> List[Account]:
    """Get all active accounts for a user (or all if user_id is None)."""
    session = get_db_session()
    try:
        query = session.query(Account).filter(Account.is_active == True)
        return query.all()
    finally:
        close_db_session(session)


def get_account_summary(account_id: int = None) -> Dict[str, Any]:
    """Get summary statistics for an account."""
    session = get_db_session()
    try:
        # Get account
        if account_id:
            account = session.query(Account).filter(Account.id == account_id).first()
        else:
            # Get first active account
            account = session.query(Account).filter(Account.is_active == True).first()
        
        if not account:
            return get_empty_account_summary()
        
        # Get trades for this account
        trades = session.query(Trade).filter(Trade.account_id == account.id).all()
        
        # Get positions for this account
        positions = session.query(Position).filter(Position.account_id == account.id).all()
        
        # Calculate metrics
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.realized_pnl and t.realized_pnl > 0])
        losing_trades = len([t for t in trades if t.realized_pnl and t.realized_pnl < 0])
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Calculate total PnL
        total_pnl = sum([float(t.realized_pnl or 0) for t in trades])
        
        # Calculate profit factor
        total_wins = sum([float(t.realized_pnl) for t in trades if t.realized_pnl and t.realized_pnl > 0])
        total_losses = abs(sum([float(t.realized_pnl) for t in trades if t.realized_pnl and t.realized_pnl < 0]))
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0
        
        # Calculate unrealized PnL from positions
        unrealized_pnl = sum([float(p.unrealized_pnl or 0) for p in positions])
        
        # Active positions value
        active_positions_value = sum([float(p.quantity * p.current_price) if p.current_price else 0 for p in positions])
        
        return {
            'account': account,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'profit_factor': round(profit_factor, 2),
            'active_positions': len(positions),
            'active_positions_value': round(active_positions_value, 2),
            'current_balance': float(account.current_balance),
        }
    finally:
        close_db_session(session)


def get_empty_account_summary() -> Dict[str, Any]:
    """Return empty account summary when no data exists."""
    return {
        'account': None,
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'win_rate': 0,
        'total_pnl': 0,
        'unrealized_pnl': 0,
        'profit_factor': 0,
        'active_positions': 0,
        'active_positions_value': 0,
        'current_balance': 0,
    }


def get_recent_trades(account_id: int = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent trades for display."""
    session = get_db_session()
    try:
        query = session.query(Trade)
        
        if account_id:
            query = query.filter(Trade.account_id == account_id)
        
        trades = query.order_by(Trade.time.desc()).limit(limit).all()
        
        result = []
        for trade in trades:
            result.append({
                'symbol': trade.symbol,
                'type': trade.trade_type,
                'position_side': trade.position_side or 'BOTH',
                'quantity': float(trade.quantity),
                'price': float(trade.price),
                'pnl': float(trade.realized_pnl or 0),
                'pnl_percent': calculate_pnl_percent(trade),
                'time': trade.time,
                'strategy': trade.strategy_name or 'Manual',
            })
        
        return result
    finally:
        close_db_session(session)


def get_active_positions(account_id: int = None) -> List[Dict[str, Any]]:
    """Get active positions for display."""
    session = get_db_session()
    try:
        query = session.query(Position)
        
        if account_id:
            query = query.filter(Position.account_id == account_id)
        
        positions = query.all()
        
        result = []
        for pos in positions:
            entry_price = float(pos.entry_price)
            current_price = float(pos.current_price) if pos.current_price else entry_price
            pnl = float(pos.unrealized_pnl or 0)
            pnl_percent = (pnl / (entry_price * float(pos.quantity)) * 100) if entry_price > 0 else 0
            
            result.append({
                'symbol': pos.symbol,
                'type': pos.position_type or 'LONG',
                'entry_price': entry_price,
                'current_price': current_price,
                'pnl': pnl,
                'pnl_percent': round(pnl_percent, 2),
                'size': float(pos.quantity),
                'stop_loss': float(pos.stop_loss) if pos.stop_loss else None,
                'take_profit': float(pos.take_profit) if pos.take_profit else None,
            })
        
        return result
    finally:
        close_db_session(session)


def calculate_pnl_percent(trade: Trade) -> float:
    """Calculate PnL percentage for a trade."""
    if not trade.realized_pnl:
        return 0
    
    trade_value = float(trade.quantity) * float(trade.price)
    if trade_value == 0:
        return 0
    
    return round(float(trade.realized_pnl) / trade_value * 100, 2)


def get_performance_metrics(account_id: int = None, days: int = 30) -> Dict[str, Any]:
    """Get detailed performance metrics."""
    session = get_db_session()
    try:
        query = session.query(Trade)
        
        if account_id:
            query = query.filter(Trade.account_id == account_id)
        
        trades = query.all()
        
        if not trades:
            return get_empty_performance_metrics()
        
        # Calculate metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.realized_pnl and t.realized_pnl > 0]
        losing_trades = [t for t in trades if t.realized_pnl and t.realized_pnl < 0]
        
        avg_win = sum([float(t.realized_pnl) for t in winning_trades]) / len(winning_trades) if winning_trades else 0
        avg_loss = sum([float(t.realized_pnl) for t in losing_trades]) / len(losing_trades) if losing_trades else 0
        
        total_wins = sum([float(t.realized_pnl) for t in winning_trades])
        total_losses = abs(sum([float(t.realized_pnl) for t in losing_trades]))
        
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0
        
        # Calculate total commissions
        total_commissions = sum([float(t.fee or 0) for t in trades])
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'total_commissions': round(total_commissions, 2),
            'expectancy': round(avg_win + avg_loss, 2),  # Simplified expectancy
        }
    finally:
        close_db_session(session)


def get_empty_performance_metrics() -> Dict[str, Any]:
    """Return empty performance metrics when no data exists."""
    return {
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'avg_win': 0,
        'avg_loss': 0,
        'profit_factor': 0,
        'total_commissions': 0,
        'expectancy': 0,
    }


def get_strategy_performance() -> List[Dict[str, Any]]:
    """Get performance breakdown by strategy."""
    session = get_db_session()
    try:
        # Group trades by strategy
        trades_by_strategy = {}
        trades = session.query(Trade).all()
        
        for trade in trades:
            strategy = trade.strategy_name or 'Manual'
            if strategy not in trades_by_strategy:
                trades_by_strategy[strategy] = []
            trades_by_strategy[strategy].append(trade)
        
        result = []
        for strategy, strategy_trades in trades_by_strategy.items():
            total_trades = len(strategy_trades)
            winning_trades = [t for t in strategy_trades if t.realized_pnl and t.realized_pnl > 0]
            losing_trades = [t for t in strategy_trades if t.realized_pnl and t.realized_pnl < 0]
            
            win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
            
            total_wins = sum([float(t.realized_pnl) for t in winning_trades])
            total_losses = abs(sum([float(t.realized_pnl) for t in losing_trades]))
            profit_factor = (total_wins / total_losses) if total_losses > 0 else 0
            
            total_pnl = sum([float(t.realized_pnl or 0) for t in strategy_trades])
            
            avg_win = total_wins / len(winning_trades) if winning_trades else 0
            avg_loss = total_losses / len(losing_trades) if losing_trades else 0
            
            result.append({
                'name': strategy,
                'total_trades': total_trades,
                'win_rate': round(win_rate, 2),
                'profit_factor': round(profit_factor, 2),
                'total_pnl': round(total_pnl, 2),
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'sharpe': 0,  # Would need more data to calculate properly
                'status': 'active',  # Could be determined from recent activity
            })
        
        return result
    finally:
        close_db_session(session)


def get_balance_history(account_id: int = None, days: int = 30) -> Dict[str, List]:
    """Get balance history for charts."""
    session = get_db_session()
    try:
        query = session.query(BalanceHistory)
        
        if account_id:
            query = query.filter(BalanceHistory.account_id == account_id)
        
        history = query.order_by(BalanceHistory.time.desc()).limit(days).all()
        
        labels = []
        balances = []
        
        for entry in reversed(history):
            labels.append(entry.time.strftime('%Y-%m-%d'))
            balances.append(float(entry.balance))
        
        return {
            'labels': labels,
            'balances': balances,
        }
    finally:
        close_db_session(session)
