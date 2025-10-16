"""
Django admin configuration for trading app.
Provides powerful web interface for data management and debugging.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Account,
    Position,
    Trade,
    BalanceHistory,
    Strategy,
    Signal,
    BacktestResult
)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """Admin interface for Account model"""
    
    list_display = [
        'id',
        'name',
        'broker',
        'account_type',
        'is_active',
        'current_balance',
        'created_at',
        'trade_count',
        'position_count'
    ]
    
    list_filter = [
        'broker',
        'account_type',
        'is_active',
        'created_at'
    ]
    
    search_fields = [
        'name',
        'broker',
        'api_key_encrypted'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'api_secret_masked',
        'trade_count',
        'position_count',
        'balance_link'
    ]
    
    fieldsets = (
        ('Account Information', {
            'fields': ('name', 'broker', 'account_type', 'is_active')
        }),
        ('Balance', {
            'fields': ('initial_balance', 'current_balance', 'currency')
        }),
        ('API Credentials', {
            'fields': ('api_key_encrypted', 'api_secret_masked'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('account_metadata',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('trade_count', 'position_count', 'balance_link')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_accounts', 'deactivate_accounts']
    
    def api_secret_masked(self, obj):
        """Display masked API secret"""
        if obj.api_secret_encrypted:
            masked_len = len(obj.api_secret_encrypted) - 8 if len(obj.api_secret_encrypted) > 8 else 0
            return '•' * masked_len + obj.api_secret_encrypted[-8:] if masked_len > 0 else obj.api_secret_encrypted
        return '-'
    api_secret_masked.short_description = 'API Secret (Masked)'
    
    def trade_count(self, obj):
        """Count of trades for this account"""
        count = obj.trades.count()
        url = reverse('admin:trading_trade_changelist') + f'?account__id__exact={obj.id}'
        return format_html('<a href="{}">{} trades</a>', url, count)
    trade_count.short_description = 'Trades'
    
    def position_count(self, obj):
        """Count of positions for this account"""
        count = obj.positions.filter(status='open').count()
        url = reverse('admin:trading_position_changelist') + f'?account__id__exact={obj.id}'
        return format_html('<a href="{}">{} positions</a>', url, count)
    position_count.short_description = 'Open Positions'
    
    def balance_link(self, obj):
        """Link to balance history"""
        count = obj.balance_history.count()
        url = reverse('admin:trading_balancehistory_changelist') + f'?account__id__exact={obj.id}'
        return format_html('<a href="{}">View {} balance records</a>', url, count)
    balance_link.short_description = 'Balance History'
    
    def activate_accounts(self, request, queryset):
        """Bulk activate accounts"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} account(s) activated.')
    activate_accounts.short_description = 'Activate selected accounts'
    
    def deactivate_accounts(self, request, queryset):
        """Bulk deactivate accounts"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} account(s) deactivated.')
    deactivate_accounts.short_description = 'Deactivate selected accounts'


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    """Admin interface for Position model"""
    
    list_display = [
        'id',
        'symbol',
        'side_badge',
        'quantity',
        'entry_price',
        'current_price',
        'pnl_display',
        'status_badge',
        'opened_at',
        'account'
    ]
    
    list_filter = [
        'side',
        'status',
        'symbol',
        'opened_at',
        'account__broker'
    ]
    
    search_fields = [
        'symbol',
        'account__broker'
    ]
    
    readonly_fields = [
        'opened_at',
        'updated_at',
        'pnl_percentage',
        'position_value',
        'risk_amount'
    ]
    
    fieldsets = (
        ('Position Details', {
            'fields': ('account', 'symbol', 'side', 'status')
        }),
        ('Pricing', {
            'fields': ('quantity', 'entry_price', 'current_price')
        }),
        ('Risk Management', {
            'fields': ('stop_loss', 'take_profit', 'unrealized_pnl')
        }),
        ('Calculated Fields', {
            'fields': ('pnl_percentage', 'position_value', 'risk_amount'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('position_metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('opened_at', 'updated_at')
        }),
    )
    
    actions = ['close_positions', 'calculate_pnl']
    
    date_hierarchy = 'opened_at'
    
    def side_badge(self, obj):
        """Display side with colored badge"""
        color = '#28a745' if obj.side == 'long' else '#dc3545'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_side_display()
        )
    side_badge.short_description = 'Side'
    
    def status_badge(self, obj):
        """Display status with colored badge"""
        colors = {
            'open': '#ffc107',
            'closed': '#28a745',
            'liquidated': '#dc3545'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def pnl_display(self, obj):
        """Display P&L with color coding"""
        pnl = obj.unrealized_pnl
        color = '#28a745' if pnl >= 0 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">${:,.2f}</span>',
            color,
            float(pnl)
        )
    pnl_display.short_description = 'Unrealized P&L'
    
    def pnl_percentage(self, obj):
        """Calculate P&L percentage"""
        if obj.entry_price > 0:
            pnl_pct = (obj.unrealized_pnl / (obj.entry_price * obj.quantity)) * 100
            color = '#28a745' if pnl_pct >= 0 else '#dc3545'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:+.2f}%</span>',
                color,
                pnl_pct
            )
        return '-'
    pnl_percentage.short_description = 'P&L %'
    
    def position_value(self, obj):
        """Current position value"""
        value = obj.current_price * obj.quantity
        return f'${value:,.2f}'
    position_value.short_description = 'Position Value'
    
    def risk_amount(self, obj):
        """Risk amount if stop loss hit"""
        if obj.stop_loss:
            if obj.side == 'long':
                risk = (obj.entry_price - obj.stop_loss) * obj.quantity
            else:
                risk = (obj.stop_loss - obj.entry_price) * obj.quantity
            return f'${risk:,.2f}'
        return '-'
    risk_amount.short_description = 'Risk Amount'
    
    def close_positions(self, request, queryset):
        """Bulk close positions"""
        updated = queryset.update(status='closed')
        self.message_user(request, f'{updated} position(s) closed.')
    close_positions.short_description = 'Close selected positions'
    
    def calculate_pnl(self, request, queryset):
        """Recalculate P&L for positions"""
        for position in queryset:
            position.calculate_pnl()
            position.save()
        self.message_user(request, f'{queryset.count()} position(s) P&L recalculated.')
    calculate_pnl.short_description = 'Recalculate P&L'


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    """Admin interface for Trade model"""
    
    list_display = [
        'id',
        'symbol',
        'trade_type_badge',
        'quantity',
        'price',
        'pnl_display',
        'time',
        'account'
    ]
    
    list_filter = [
        'trade_type',
        'position_side',
        'symbol',
        'time',
        'account__broker'
    ]
    
    search_fields = [
        'symbol',
        'account__broker',
        'order_id'
    ]
    
    readonly_fields = [
        'created_at',
        'time',
        'realized_pnl'
    ]
    
    fieldsets = (
        ('Trade Details', {
            'fields': ('account', 'symbol', 'trade_type', 'position_side', 'quantity')
        }),
        ('Pricing', {
            'fields': ('price', 'fee', 'fee_currency', 'realized_pnl')
        }),
        ('Risk Management', {
            'fields': ('stop_loss', 'take_profit')
        }),
        ('Order Info', {
            'fields': ('order_type', 'order_id', 'is_entry')
        }),
        ('Timing', {
            'fields': ('time', 'created_at')
        }),
        ('Strategy & Notes', {
            'fields': ('strategy_name', 'notes')
        }),
        ('Metadata', {
            'fields': ('trade_metadata',),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'time'
    
    def trade_type_badge(self, obj):
        """Display trade type with colored badge"""
        color = '#28a745' if obj.trade_type == 'BUY' else '#dc3545'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.trade_type
        )
    trade_type_badge.short_description = 'Type'
    
    def pnl_display(self, obj):
        """Display PNL with colored formatting"""
        pnl = obj.realized_pnl or 0
        color = '#28a745' if pnl >= 0 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">${:,.2f}</span>',
            color,
            float(pnl)
        )
    pnl_display.short_description = 'P&L'
    
    def pnl_percentage(self, obj):
        """Calculate P&L percentage"""
        if obj.exit_price and obj.entry_price > 0:
            cost_basis = obj.entry_price * obj.quantity
            pnl_pct = (obj.pnl / cost_basis) * 100
            color = '#28a745' if pnl_pct >= 0 else '#dc3545'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:+.2f}%</span>',
                color,
                pnl_pct
            )
        return '-'
    pnl_percentage.short_description = 'P&L %'
    
    def trade_duration(self, obj):
        """Calculate trade duration"""
        if obj.exit_time:
            duration = obj.exit_time - obj.entry_time
            days = duration.days
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            if days > 0:
                return f'{days}d {hours}h'
            elif hours > 0:
                return f'{hours}h {minutes}m'
            else:
                return f'{minutes}m'
        return 'Open'
    trade_duration.short_description = 'Duration'
    
    def gross_pnl(self, obj):
        """Gross P&L (before fees)"""
        if obj.exit_price:
            if obj.side == 'buy':
                gross = (obj.exit_price - obj.entry_price) * obj.quantity
            else:
                gross = (obj.entry_price - obj.exit_price) * obj.quantity
            return f'${gross:,.2f}'
        return '-'
    gross_pnl.short_description = 'Gross P&L'
    
    def net_pnl(self, obj):
        """Net P&L (after fees)"""
        return f'${obj.pnl:,.2f}'
    net_pnl.short_description = 'Net P&L'
    
    def close_trades(self, request, queryset):
        """Bulk close trades"""
        updated = queryset.update(status='closed')
        self.message_user(request, f'{updated} trade(s) closed.')
    close_trades.short_description = 'Close selected trades'
    
    def calculate_pnl(self, request, queryset):
        """Recalculate P&L for trades"""
        for trade in queryset:
            trade.calculate_pnl()
            trade.save()
        self.message_user(request, f'{queryset.count()} trade(s) P&L recalculated.')
    calculate_pnl.short_description = 'Recalculate P&L'


@admin.register(BalanceHistory)
class BalanceHistoryAdmin(admin.ModelAdmin):
    """Admin interface for BalanceHistory model"""
    
    list_display = [
        'id',
        'account',
        'total_balance_display',
        'available_balance_display',
        'reserved_balance_display',
        'timestamp'
    ]
    
    list_filter = [
        'account',
        'timestamp'
    ]
    
    search_fields = [
        'account__broker'
    ]
    
    readonly_fields = [
        'timestamp',
        'utilization_percentage'
    ]
    
    date_hierarchy = 'timestamp'
    
    def total_balance_display(self, obj):
        """Format total balance"""
        return f'${obj.total_balance:,.2f}'
    total_balance_display.short_description = 'Total Balance'
    total_balance_display.admin_order_field = 'total_balance'
    
    def available_balance_display(self, obj):
        """Format available balance"""
        return f'${obj.available_balance:,.2f}'
    available_balance_display.short_description = 'Available'
    
    def reserved_balance_display(self, obj):
        """Format reserved balance"""
        return f'${obj.reserved_balance:,.2f}'
    reserved_balance_display.short_description = 'Reserved'
    
    def utilization_percentage(self, obj):
        """Calculate balance utilization"""
        if obj.total_balance > 0:
            util = (obj.reserved_balance / obj.total_balance) * 100
            return f'{util:.1f}%'
        return '0%'
    utilization_percentage.short_description = 'Utilization %'


@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    """Admin interface for Strategy model"""
    
    list_display = [
        'id',
        'name',
        'status_badge',
        'backtest_count',
        'created_at',
        'updated_at'
    ]
    
    list_filter = [
        'status',
        'created_at'
    ]
    
    search_fields = [
        'name',
        'description'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'backtest_count',
        'backtest_link'
    ]
    
    fieldsets = (
        ('Strategy Information', {
            'fields': ('name', 'description', 'status')
        }),
        ('Parameters', {
            'fields': ('parameters',)
        }),
        ('Performance', {
            'fields': ('performance_metrics', 'backtest_link'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('strategy_metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['activate_strategies', 'deactivate_strategies']
    
    def status_badge(self, obj):
        """Display status with colored badge"""
        colors = {
            'active': '#28a745',
            'inactive': '#6c757d',
            'testing': '#ffc107'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def backtest_count(self, obj):
        """Count of backtest results"""
        count = obj.backtest_results.count()
        return count
    backtest_count.short_description = 'Backtests'
    
    def backtest_link(self, obj):
        """Link to backtest results"""
        count = obj.backtest_results.count()
        url = reverse('admin:trading_backtestresult_changelist') + f'?strategy__id__exact={obj.id}'
        return format_html('<a href="{}">View {} backtest results</a>', url, count)
    backtest_link.short_description = 'Backtest Results'
    
    def activate_strategies(self, request, queryset):
        """Bulk activate strategies"""
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} strategy/ies activated.')
    activate_strategies.short_description = 'Activate selected strategies'
    
    def deactivate_strategies(self, request, queryset):
        """Bulk deactivate strategies"""
        updated = queryset.update(status='inactive')
        self.message_user(request, f'{updated} strategy/ies deactivated.')
    deactivate_strategies.short_description = 'Deactivate selected strategies'


@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    """Admin interface for Signal model"""
    
    list_display = [
        'id',
        'symbol',
        'signal_badge',
        'price',
        'confidence_display',
        'strategy',
        'created_at'
    ]
    
    list_filter = [
        'signal_type',
        'symbol',
        'strategy',
        'created_at'
    ]
    
    search_fields = [
        'symbol',
        'strategy__name'
    ]
    
    readonly_fields = [
        'created_at',
        'confidence_bar'
    ]
    
    fieldsets = (
        ('Signal Information', {
            'fields': ('symbol', 'signal_type', 'strategy', 'price')
        }),
        ('Analysis', {
            'fields': ('confidence', 'confidence_bar', 'indicators')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def signal_badge(self, obj):
        """Display signal type with colored badge"""
        colors = {
            'buy': '#28a745',
            'sell': '#dc3545',
            'hold': '#6c757d'
        }
        color = colors.get(obj.signal_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_signal_type_display().upper()
        )
    signal_badge.short_description = 'Signal'
    
    def confidence_display(self, obj):
        """Display confidence percentage"""
        color = '#28a745' if obj.confidence >= 0.7 else ('#ffc107' if obj.confidence >= 0.5 else '#dc3545')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.0%}</span>',
            color,
            obj.confidence
        )
    confidence_display.short_description = 'Confidence'
    confidence_display.admin_order_field = 'confidence'
    
    def confidence_bar(self, obj):
        """Visual confidence bar"""
        percentage = int(obj.confidence * 100)
        color = '#28a745' if percentage >= 70 else ('#ffc107' if percentage >= 50 else '#dc3545')
        return format_html(
            '<div style="width: 200px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; color: white; text-align: center; border-radius: 3px; padding: 2px;">{}%</div>'
            '</div>',
            percentage,
            color,
            percentage
        )
    confidence_bar.short_description = 'Confidence Bar'


@admin.register(BacktestResult)
class BacktestResultAdmin(admin.ModelAdmin):
    """Admin interface for BacktestResult model"""
    
    list_display = [
        'id',
        'strategy',
        'symbol',
        'return_display',
        'sharpe_display',
        'trades_display',
        'win_rate_display',
        'date_range',
        'created_at'
    ]
    
    list_filter = [
        'strategy',
        'symbol',
        'created_at',
        'start_date',
        'end_date'
    ]
    
    search_fields = [
        'strategy__name',
        'symbol'
    ]
    
    readonly_fields = [
        'created_at',
        'performance_summary',
        'risk_metrics',
        'trade_statistics'
    ]
    
    fieldsets = (
        ('Backtest Configuration', {
            'fields': ('strategy', 'symbol', 'start_date', 'end_date')
        }),
        ('Capital', {
            'fields': ('initial_capital', 'final_capital')
        }),
        ('Performance Summary', {
            'fields': ('performance_summary',)
        }),
        ('Risk Metrics', {
            'fields': ('risk_metrics',)
        }),
        ('Trade Statistics', {
            'fields': ('trade_statistics',)
        }),
        ('Parameters', {
            'fields': ('parameters',),
            'classes': ('collapse',)
        }),
        ('Equity Curve', {
            'fields': ('equity_curve',),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def return_display(self, obj):
        """Display total return with color"""
        color = '#28a745' if obj.total_return >= 0 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:+.2%}</span>',
            color,
            obj.total_return
        )
    return_display.short_description = 'Total Return'
    return_display.admin_order_field = 'total_return'
    
    def sharpe_display(self, obj):
        """Display Sharpe ratio"""
        color = '#28a745' if obj.sharpe_ratio >= 1.0 else ('#ffc107' if obj.sharpe_ratio >= 0 else '#dc3545')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}</span>',
            color,
            obj.sharpe_ratio
        )
    sharpe_display.short_description = 'Sharpe'
    sharpe_display.admin_order_field = 'sharpe_ratio'
    
    def trades_display(self, obj):
        """Display total trades"""
        return f'{obj.total_trades} trades'
    trades_display.short_description = 'Trades'
    
    def win_rate_display(self, obj):
        """Display win rate with color"""
        color = '#28a745' if obj.win_rate >= 0.5 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1%}</span>',
            color,
            obj.win_rate
        )
    win_rate_display.short_description = 'Win Rate'
    win_rate_display.admin_order_field = 'win_rate'
    
    def date_range(self, obj):
        """Display backtest date range"""
        return f'{obj.start_date.date()} to {obj.end_date.date()}'
    date_range.short_description = 'Period'
    
    def performance_summary(self, obj):
        """Formatted performance summary"""
        pnl = obj.final_capital - obj.initial_capital
        pnl_color = '#28a745' if pnl >= 0 else '#dc3545'
        return format_html(
            '<table style="width: 100%;">'
            '<tr><th style="text-align: left;">Initial Capital:</th><td>${:,.2f}</td></tr>'
            '<tr><th style="text-align: left;">Final Capital:</th><td>${:,.2f}</td></tr>'
            '<tr><th style="text-align: left;">P&L:</th><td style="color: {}; font-weight: bold;">${:,.2f}</td></tr>'
            '<tr><th style="text-align: left;">Total Return:</th><td style="color: {}; font-weight: bold;">{:+.2%}</td></tr>'
            '</table>',
            float(obj.initial_capital),
            float(obj.final_capital),
            pnl_color,
            float(pnl),
            pnl_color,
            obj.total_return
        )
    performance_summary.short_description = 'Performance Summary'
    
    def risk_metrics(self, obj):
        """Formatted risk metrics"""
        sharpe_color = '#28a745' if obj.sharpe_ratio >= 1.0 else '#dc3545'
        return format_html(
            '<table style="width: 100%;">'
            '<tr><th style="text-align: left;">Sharpe Ratio:</th><td style="color: {}; font-weight: bold;">{:.2f}</td></tr>'
            '<tr><th style="text-align: left;">Max Drawdown:</th><td style="color: #dc3545; font-weight: bold;">{:.2%}</td></tr>'
            '</table>',
            sharpe_color,
            obj.sharpe_ratio,
            obj.max_drawdown
        )
    risk_metrics.short_description = 'Risk Metrics'
    
    def trade_statistics(self, obj):
        """Formatted trade statistics"""
        win_rate_color = '#28a745' if obj.win_rate >= 0.5 else '#dc3545'
        return format_html(
            '<table style="width: 100%;">'
            '<tr><th style="text-align: left;">Total Trades:</th><td>{}</td></tr>'
            '<tr><th style="text-align: left;">Win Rate:</th><td style="color: {}; font-weight: bold;">{:.1%}</td></tr>'
            '</table>',
            obj.total_trades,
            win_rate_color,
            obj.win_rate
        )
    trade_statistics.short_description = 'Trade Statistics'


# Customize admin site header and title
admin.site.site_header = 'FKS Trading Admin'
admin.site.site_title = 'Trading Admin'
admin.site.index_title = 'Trading Dashboard'
