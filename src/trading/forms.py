"""
Django forms for the trading application.
Provides validation, cleaning, and user-friendly error messages.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
import re


class DataPullForm(forms.Form):
    """Form for pulling historical price data from Binance."""
    
    INTERVAL_CHOICES = [
        ('1h', '1 hour'),
        ('4h', '4 hours'),
        ('1d', '1 day'),
    ]
    
    interval = forms.ChoiceField(
        choices=INTERVAL_CHOICES,
        initial='1d',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'interval'
        }),
        help_text='Candle interval (1h = hourly, 4h = 4-hour, 1d = daily)'
    )
    
    limit = forms.IntegerField(
        initial=1000,
        min_value=100,
        max_value=2000,
        validators=[
            MinValueValidator(100, message='Minimum 100 periods required for backtesting'),
            MaxValueValidator(2000, message='Maximum 2000 periods allowed')
        ],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'limit',
            'step': '100'
        }),
        help_text='Number of candles to fetch (100-2000). Recommendation: 1000 for daily data.'
    )
    
    def clean_limit(self):
        """Ensure limit is a multiple of 100 for cleaner data ranges."""
        limit = self.cleaned_data.get('limit')
        if limit and limit % 100 != 0:
            # Round to nearest 100
            limit = round(limit / 100) * 100
        return limit


class OptimizationForm(forms.Form):
    """Form for running Optuna strategy optimization."""
    
    n_trials = forms.IntegerField(
        initial=50,
        min_value=10,
        max_value=500,
        validators=[
            MinValueValidator(10, message='Minimum 10 trials required'),
            MaxValueValidator(500, message='Maximum 500 trials allowed')
        ],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'n_trials',
            'step': '10'
        }),
        help_text='More trials = better optimization but slower (10-500)',
        label='Number of Trials'
    )
    
    symbol = forms.ChoiceField(
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'symbol'
        }),
        help_text='Symbol to optimize (will apply to all in backtest)'
    )
    
    def __init__(self, *args, symbols=None, **kwargs):
        """Initialize form with dynamic symbol choices."""
        super().__init__(*args, **kwargs)
        if symbols:
            self.fields['symbol'].choices = [(s, s) for s in symbols]
    
    def clean_n_trials(self):
        """Round n_trials to nearest 10."""
        n_trials = self.cleaned_data.get('n_trials')
        if n_trials and n_trials % 10 != 0:
            n_trials = round(n_trials / 10) * 10
        return n_trials


class SignalForm(forms.Form):
    """Form for generating trading signals with position sizing."""
    
    account_size = forms.DecimalField(
        initial=10000,
        min_value=100,
        max_value=10000000,
        decimal_places=2,
        validators=[
            MinValueValidator(100, message='Minimum account size is $100'),
            MaxValueValidator(10000000, message='Maximum account size is $10,000,000')
        ],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'account_size',
            'step': '100'
        }),
        help_text='Total account value for position sizing',
        label='Account Size (USD)'
    )
    
    risk_per_trade = forms.DecimalField(
        initial=2.0,
        min_value=0.5,
        max_value=10.0,
        decimal_places=1,
        validators=[
            MinValueValidator(0.5, message='Minimum risk is 0.5%'),
            MaxValueValidator(10.0, message='Maximum risk is 10% (not recommended above 5%)')
        ],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'risk_per_trade',
            'step': '0.5'
        }),
        help_text='Percentage of account to risk per trade (0.5-10%)',
        label='Risk Per Trade (%)'
    )
    
    def clean_risk_per_trade(self):
        """Warn if risk is too high."""
        risk = self.cleaned_data.get('risk_per_trade')
        if risk and risk > 5.0:
            # Add a warning (not an error)
            self.add_warning('risk_per_trade', 
                           f'Risk of {risk}% is quite high. Consider reducing to 2-3% for better risk management.')
        return risk
    
    def add_warning(self, field, message):
        """Add a non-blocking warning message."""
        if not hasattr(self, '_warnings'):
            self._warnings = {}
        if field not in self._warnings:
            self._warnings[field] = []
        self._warnings[field].append(message)
    
    def get_warnings(self):
        """Get all warning messages."""
        return getattr(self, '_warnings', {})


class TradeForm(forms.Form):
    """Form for manually adding a trade."""
    
    symbol = forms.ChoiceField(
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Symbol'
    )
    
    SIDE_CHOICES = [
        ('BUY', 'BUY'),
        ('SELL', 'SELL'),
    ]
    
    side = forms.ChoiceField(
        choices=SIDE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Side'
    )
    
    quantity = forms.DecimalField(
        min_value=0.0001,
        max_value=10000,
        decimal_places=4,
        validators=[
            MinValueValidator(0.0001, message='Minimum quantity is 0.0001')
        ],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.0001'
        }),
        label='Quantity'
    )
    
    entry_price = forms.DecimalField(
        min_value=0.01,
        decimal_places=2,
        validators=[
            MinValueValidator(0.01, message='Price must be greater than 0')
        ],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        label='Entry Price'
    )
    
    stop_loss = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        label='Stop Loss (optional)',
        help_text='Recommended: Set a stop loss for risk management'
    )
    
    take_profit = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        label='Take Profit (optional)',
        help_text='Recommended: Set a take profit target'
    )
    
    def __init__(self, *args, symbols=None, **kwargs):
        """Initialize form with dynamic symbol choices."""
        super().__init__(*args, **kwargs)
        if symbols:
            self.fields['symbol'].choices = [(s, s) for s in symbols]
    
    def clean(self):
        """Cross-field validation."""
        cleaned_data = super().clean()
        side = cleaned_data.get('side')
        entry_price = cleaned_data.get('entry_price')
        stop_loss = cleaned_data.get('stop_loss')
        take_profit = cleaned_data.get('take_profit')
        
        if side and entry_price:
            # Validate stop loss for BUY orders
            if side == 'BUY' and stop_loss:
                if stop_loss >= entry_price:
                    raise ValidationError({
                        'stop_loss': 'Stop loss must be below entry price for BUY orders'
                    })
            
            # Validate stop loss for SELL orders
            if side == 'SELL' and stop_loss:
                if stop_loss <= entry_price:
                    raise ValidationError({
                        'stop_loss': 'Stop loss must be above entry price for SELL orders'
                    })
            
            # Validate take profit for BUY orders
            if side == 'BUY' and take_profit:
                if take_profit <= entry_price:
                    raise ValidationError({
                        'take_profit': 'Take profit must be above entry price for BUY orders'
                    })
            
            # Validate take profit for SELL orders
            if side == 'SELL' and take_profit:
                if take_profit >= entry_price:
                    raise ValidationError({
                        'take_profit': 'Take profit must be below entry price for SELL orders'
                    })
            
            # Check risk/reward ratio
            if stop_loss and take_profit and entry_price:
                if side == 'BUY':
                    risk = entry_price - stop_loss
                    reward = take_profit - entry_price
                else:
                    risk = stop_loss - entry_price
                    reward = entry_price - take_profit
                
                if risk > 0:
                    risk_reward_ratio = reward / risk
                    if risk_reward_ratio < 1:
                        self.add_warning('take_profit', 
                                       f'Risk/Reward ratio is {risk_reward_ratio:.2f}. '
                                       f'Consider increasing take profit for better risk/reward (aim for 2:1 or higher).')
        
        return cleaned_data
    
    def add_warning(self, field, message):
        """Add a non-blocking warning message."""
        if not hasattr(self, '_warnings'):
            self._warnings = {}
        if field not in self._warnings:
            self._warnings[field] = []
        self._warnings[field].append(message)
    
    def get_warnings(self):
        """Get all warning messages."""
        return getattr(self, '_warnings', {})


class NotificationForm(forms.Form):
    """Form for configuring Discord webhook notifications."""
    
    webhook_url = forms.URLField(
        max_length=500,
        validators=[URLValidator(message='Please enter a valid Discord webhook URL')],
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'id': 'webhook_url',
            'placeholder': 'https://discord.com/api/webhooks/...'
        }),
        label='Webhook URL',
        help_text='Your Discord webhook URL. Get it from Server Settings → Integrations → Webhooks.'
    )
    
    notify_signals = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'notify_signals'
        }),
        label='Trading Signals (BUY/SELL alerts)'
    )
    
    notify_trades = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'notify_trades'
        }),
        label='Trade Executions (entries and exits)'
    )
    
    notify_positions = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'notify_positions'
        }),
        label='Position Updates (P&L changes, stop loss/take profit triggers)'
    )
    
    notify_errors = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'notify_errors'
        }),
        label='Errors and Warnings'
    )
    
    def clean_webhook_url(self):
        """Validate that the URL is a Discord webhook."""
        url = self.cleaned_data.get('webhook_url')
        if url:
            # Check if it's a Discord webhook URL
            discord_pattern = r'^https://discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$'
            if not re.match(discord_pattern, url):
                raise ValidationError(
                    'This doesn\'t appear to be a valid Discord webhook URL. '
                    'It should look like: https://discord.com/api/webhooks/123456789/abcdefg'
                )
        return url
    
    def clean(self):
        """Ensure at least one notification type is enabled."""
        cleaned_data = super().clean()
        
        if not any([
            cleaned_data.get('notify_signals'),
            cleaned_data.get('notify_trades'),
            cleaned_data.get('notify_positions'),
            cleaned_data.get('notify_errors')
        ]):
            raise ValidationError(
                'Please enable at least one notification type.'
            )
        
        return cleaned_data


class TestNotificationForm(forms.Form):
    """Form for sending a test Discord notification."""
    
    message = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'id': 'test_message',
            'rows': '3'
        }),
        label='Test Message',
        help_text='Message to send to Discord (max 2000 characters)',
        initial='🤖 Test notification from FKS Trading Bot\n\nThis is a test message to verify your Discord webhook is working correctly.'
    )
    
    def clean_message(self):
        """Ensure message is not empty or too long."""
        message = self.cleaned_data.get('message')
        if message:
            message = message.strip()
            if len(message) < 10:
                raise ValidationError('Message must be at least 10 characters long.')
            if len(message) > 2000:
                raise ValidationError('Discord messages are limited to 2000 characters.')
        return message


class CloseTradeForm(forms.Form):
    """Form for closing a trade (used in API)."""
    
    exit_price = forms.DecimalField(
        required=False,
        min_value=0.01,
        decimal_places=2,
        label='Exit Price',
        help_text='Leave empty to use current market price'
    )


class FilterTradesForm(forms.Form):
    """Form for filtering trade history."""
    
    symbol = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm'
        }),
        label='Symbol'
    )
    
    SIDE_CHOICES = [
        ('', 'All Sides'),
        ('BUY', 'BUY'),
        ('SELL', 'SELL'),
    ]
    
    side = forms.ChoiceField(
        required=False,
        choices=SIDE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm'
        }),
        label='Side'
    )
    
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('OPEN', 'OPEN'),
        ('CLOSED', 'CLOSED'),
    ]
    
    status = forms.ChoiceField(
        required=False,
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm'
        }),
        label='Status'
    )
    
    def __init__(self, *args, symbols=None, **kwargs):
        """Initialize form with dynamic symbol choices."""
        super().__init__(*args, **kwargs)
        if symbols:
            self.fields['symbol'].choices = [('', 'All Symbols')] + [(s, s) for s in symbols]
