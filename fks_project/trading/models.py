"""
Django models for fks trading app.
Migrated from the original database.py with SQLAlchemy models.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class Account(models.Model):
    """Trading account model"""
    EXCHANGE_CHOICES = [
        ('binance', 'Binance'),
        ('coinbase', 'Coinbase'),
        ('kraken', 'Kraken'),
        ('bybit', 'Bybit'),
    ]
    
    ACCOUNT_TYPE_CHOICES = [
        ('spot', 'Spot'),
        ('futures', 'Futures'),
        ('margin', 'Margin'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts', null=True, blank=True)
    exchange = models.CharField(max_length=50, choices=EXCHANGE_CHOICES)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    api_key = models.CharField(max_length=255)
    api_secret = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    account_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'accounts'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.exchange} - {self.account_type}"


class Position(models.Model):
    """Open position model"""
    SIDE_CHOICES = [
        ('long', 'Long'),
        ('short', 'Short'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('liquidated', 'Liquidated'),
    ]
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='positions')
    symbol = models.CharField(max_length=20)
    side = models.CharField(max_length=10, choices=SIDE_CHOICES)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    current_price = models.DecimalField(max_digits=20, decimal_places=8)
    unrealized_pnl = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    position_metadata = models.JSONField(default=dict, blank=True)
    entry_time = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'positions'
        ordering = ['-entry_time']
        indexes = [
            models.Index(fields=['symbol', 'status']),
            models.Index(fields=['account', 'status']),
        ]
        
    def __str__(self):
        return f"{self.symbol} {self.side} - {self.quantity}"
    
    def calculate_pnl(self):
        """Calculate current PnL"""
        if self.side == 'long':
            pnl = (self.current_price - self.entry_price) * self.quantity
        else:
            pnl = (self.entry_price - self.current_price) * self.quantity
        self.unrealized_pnl = pnl
        return pnl


class Trade(models.Model):
    """Completed trade model"""
    SIDE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ]
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='trades')
    symbol = models.CharField(max_length=20)
    side = models.CharField(max_length=10, choices=SIDE_CHOICES)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    pnl = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    fees = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    trade_metadata = models.JSONField(default=dict, blank=True)
    entry_time = models.DateTimeField(default=timezone.now)
    exit_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'trades'
        ordering = ['-entry_time']
        indexes = [
            models.Index(fields=['symbol', 'entry_time']),
            models.Index(fields=['account', 'status']),
        ]
        
    def __str__(self):
        return f"{self.symbol} {self.side} @ {self.entry_price}"
    
    def calculate_pnl(self):
        """Calculate trade PnL"""
        if self.exit_price:
            if self.side == 'buy':
                self.pnl = (self.exit_price - self.entry_price) * self.quantity - self.fees
            else:
                self.pnl = (self.entry_price - self.exit_price) * self.quantity - self.fees
            return self.pnl
        return Decimal('0')


class BalanceHistory(models.Model):
    """Account balance history"""
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='balance_history')
    total_balance = models.DecimalField(max_digits=20, decimal_places=8)
    available_balance = models.DecimalField(max_digits=20, decimal_places=8)
    reserved_balance = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'balance_history'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['account', 'timestamp']),
        ]
        
    def __str__(self):
        return f"{self.account} - {self.total_balance} @ {self.timestamp}"


class Strategy(models.Model):
    """Trading strategy configuration"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('testing', 'Testing'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parameters = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    performance_metrics = models.JSONField(default=dict, blank=True)
    strategy_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'strategies'
        ordering = ['-created_at']
        verbose_name_plural = 'Strategies'
        
    def __str__(self):
        return self.name


class Signal(models.Model):
    """Trading signal model"""
    SIGNAL_TYPE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('hold', 'Hold'),
    ]
    
    symbol = models.CharField(max_length=20)
    signal_type = models.CharField(max_length=10, choices=SIGNAL_TYPE_CHOICES)
    strategy = models.ForeignKey(Strategy, on_delete=models.SET_NULL, null=True, blank=True)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    confidence = models.FloatField(default=0.0)
    indicators = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'signals'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['symbol', 'created_at']),
            models.Index(fields=['signal_type', 'created_at']),
        ]
        
    def __str__(self):
        return f"{self.symbol} - {self.signal_type} @ {self.price}"


class BacktestResult(models.Model):
    """Backtest results storage"""
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, related_name='backtest_results')
    symbol = models.CharField(max_length=20)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    initial_capital = models.DecimalField(max_digits=20, decimal_places=8)
    final_capital = models.DecimalField(max_digits=20, decimal_places=8)
    total_return = models.FloatField()
    sharpe_ratio = models.FloatField()
    max_drawdown = models.FloatField()
    win_rate = models.FloatField()
    total_trades = models.IntegerField()
    parameters = models.JSONField(default=dict)
    equity_curve = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'backtest_results'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.strategy.name} - {self.symbol} ({self.total_return:.2%})"
