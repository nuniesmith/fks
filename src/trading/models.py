"""
Django models for fks trading app.
Migrated from the original database.py with SQLAlchemy models.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class Account(models.Model):
    """Trading account model - mapped to existing accounts table"""
    ACCOUNT_TYPE_CHOICES = [
        ('personal', 'Personal'),
        ('prop_firm', 'Prop Firm'),
    ]
    
    # Actual database columns
    name = models.CharField(max_length=255, unique=True)
    account_type = models.CharField(max_length=50, choices=ACCOUNT_TYPE_CHOICES)
    broker = models.CharField(max_length=100, null=True, blank=True)
    initial_balance = models.DecimalField(max_digits=20, decimal_places=8)
    current_balance = models.DecimalField(max_digits=20, decimal_places=8)
    currency = models.CharField(max_length=10, default='USDT')
    api_key_encrypted = models.TextField(null=True, blank=True)
    api_secret_encrypted = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    account_metadata = models.JSONField(default=dict, blank=True, null=True)
    
    class Meta:
        db_table = 'accounts'
        ordering = ['-created_at']
        managed = False
    
    # Properties for backward compatibility
    @property
    def exchange(self):
        """Alias for broker"""
        return self.broker
    
    @exchange.setter
    def exchange(self, value):
        """Allow setting exchange which maps to broker"""
        self.broker = value
    
    @property
    def api_key(self):
        """Alias for api_key_encrypted"""
        return self.api_key_encrypted
    
    @api_key.setter
    def api_key(self, value):
        """Allow setting api_key which maps to api_key_encrypted"""
        self.api_key_encrypted = value
    
    @property
    def api_secret(self):
        """Alias for api_secret_encrypted"""
        return self.api_secret_encrypted
    
    @api_secret.setter
    def api_secret(self, value):
        """Allow setting api_secret which maps to api_secret_encrypted"""
        self.api_secret_encrypted = value
    
    @property
    def status(self):
        """Map is_active to status"""
        return 'active' if self.is_active else 'inactive'
    
    @status.setter
    def status(self, value):
        """Allow setting status which maps to is_active"""
        self.is_active = (value == 'active')
        
    def __str__(self):
        return f"{self.name} - {self.account_type}"


class Position(models.Model):
    """Open position model - mapped to existing positions table"""
    SIDE_CHOICES = [
        ('LONG', 'Long'),
        ('SHORT', 'Short'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('liquidated', 'Liquidated'),
    ]
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='positions')
    symbol = models.CharField(max_length=20)
    side = models.CharField(max_length=10, choices=SIDE_CHOICES, db_column='position_type')
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    current_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    unrealized_pnl = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    unrealized_pnl_percent = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    position_metadata = models.JSONField(default=dict, blank=True, null=True)
    opened_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'positions'
        ordering = ['-opened_at']
        managed = False  # Don't let Django manage this table
    
    @property
    def entry_time(self):
        """Alias for opened_at to maintain compatibility with views"""
        return self.opened_at
    
    @entry_time.setter
    def entry_time(self, value):
        """Allow setting entry_time which maps to opened_at"""
        self.opened_at = value
        
    def __str__(self):
        return f"{self.symbol} {self.side} - {self.quantity}"
    
    def calculate_pnl(self):
        """Calculate current PnL"""
        if self.side == 'LONG':
            pnl = (self.current_price - self.entry_price) * self.quantity
        else:
            pnl = (self.entry_price - self.current_price) * self.quantity
        self.unrealized_pnl = pnl
        return pnl


class Trade(models.Model):
    """Completed trade model - mapped to existing trades table"""
    TRADE_TYPE_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]
    
    POSITION_SIDE_CHOICES = [
        ('LONG', 'Long'),
        ('SHORT', 'Short'),
        ('BOTH', 'Both'),
    ]
    
    # Actual database columns
    time = models.DateTimeField()
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='trades')
    symbol = models.CharField(max_length=20)
    trade_type = models.CharField(max_length=10, choices=TRADE_TYPE_CHOICES)
    position_side = models.CharField(max_length=10, choices=POSITION_SIDE_CHOICES, null=True, blank=True)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    fee = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    fee_currency = models.CharField(max_length=10, null=True, blank=True)
    realized_pnl = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    order_type = models.CharField(max_length=20, null=True, blank=True)
    order_id = models.CharField(max_length=100, null=True, blank=True)
    is_entry = models.BooleanField(default=True)
    notes = models.TextField(null=True, blank=True)
    strategy_name = models.CharField(max_length=100, null=True, blank=True)
    trade_metadata = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'trades'
        ordering = ['-time']
        managed = False
    
    # Properties for backward compatibility with views
    @property
    def entry_time(self):
        """Alias for time"""
        return self.time
    
    @entry_time.setter
    def entry_time(self, value):
        """Allow setting entry_time which maps to time"""
        self.time = value
    
    @property
    def side(self):
        """Alias for trade_type"""
        return self.trade_type.lower() if self.trade_type else None
    
    @side.setter
    def side(self, value):
        """Allow setting side which maps to trade_type"""
        self.trade_type = value.upper() if value else None
    
    @property
    def pnl(self):
        """Alias for realized_pnl"""
        return self.realized_pnl
    
    @pnl.setter
    def pnl(self, value):
        """Allow setting pnl which maps to realized_pnl"""
        self.realized_pnl = value
    
    @property
    def fees(self):
        """Alias for fee"""
        return self.fee
    
    @fees.setter
    def fees(self, value):
        """Allow setting fees which maps to fee"""
        self.fee = value
    
    @property
    def entry_price(self):
        """Alias for price"""
        return self.price
    
    @entry_price.setter
    def entry_price(self, value):
        """Allow setting entry_price which maps to price"""
        self.price = value
        
    def __str__(self):
        return f"{self.symbol} {self.trade_type} @ {self.price}"
    
    def calculate_pnl(self):
        """Calculate trade PnL - for compatibility"""
        # PnL is already stored in realized_pnl
        return self.realized_pnl or Decimal('0')


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
        managed = False
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
        managed = False
        
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
        managed = False
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
        managed = False
        
    def __str__(self):
        return f"{self.strategy.name} - {self.symbol} ({self.total_return:.2%})"
