"""Web UI views."""
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import login
from django.contrib import messages
from django.urls import reverse_lazy
import json


class HomeView(TemplateView):
    """Home page view."""
    template_name = 'pages/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # TODO: Fetch real data from database/API
        context['user_xp'] = 15420
        context['expense_coverage'] = 87
        context['tax_savings'] = 2340
        context['active_accounts'] = 3
        context['next_milestone'] = {
            'name': 'Senior Trader',
            'progress': 65,
            'xp_needed': 20000
        }
        context['trading_accounts'] = [
            {'name': 'Main Trading', 'exchange': 'Binance', 'balance': 45230.50, 'pnl': 1250.30, 'status': 'active'},
            {'name': 'Scalping Bot', 'exchange': 'Kraken', 'balance': 12450.00, 'pnl': -125.50, 'status': 'active'},
            {'name': 'Long Term Hold', 'exchange': 'Coinbase', 'balance': 89000.00, 'pnl': 8900.00, 'status': 'active'},
        ]
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    """Trading dashboard view."""
    template_name = 'pages/dashboard.html'
    login_url = '/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # TODO: Fetch real trading data from database
        context['total_profit'] = 12450.00
        context['win_rate'] = 68.5
        context['active_positions'] = 5
        context['active_positions_value'] = 45230
        context['sharpe_ratio'] = 1.85
        context['symbol'] = 'BTCUSDT'
        
        # Chart data (serialize as JSON for JavaScript)
        context['price_labels'] = json.dumps(['00:00', '04:00', '08:00', '12:00', '16:00', '20:00'])
        context['price_data'] = json.dumps([42000, 42500, 41800, 43200, 43500, 43100])
        context['daily_pnl'] = json.dumps([1200, -350, 890, 1450, -120, 780, 920])
        
        # Recent signals
        context['recent_signals'] = [
            {'type': 'BUY', 'symbol': 'ETHUSDT', 'strategy': 'RSI Divergence', 'confidence': 85, 'price': 2250.50, 'time_ago': '5m ago'},
            {'type': 'SELL', 'symbol': 'SOLUSDT', 'strategy': 'MA Cross', 'confidence': 72, 'price': 98.30, 'time_ago': '15m ago'},
            {'type': 'BUY', 'symbol': 'BTCUSDT', 'strategy': 'Breakout', 'confidence': 90, 'price': 43100.00, 'time_ago': '25m ago'},
        ]
        
        # Active trades
        context['active_trades'] = [
            {'symbol': 'BTCUSDT', 'type': 'LONG', 'entry_price': 42500, 'current_price': 43100, 'pnl': 600, 'pnl_percent': 1.41, 'size': 1.0},
            {'symbol': 'ETHUSDT', 'type': 'LONG', 'entry_price': 2200, 'current_price': 2250, 'pnl': 50, 'pnl_percent': 2.27, 'size': 2.5},
            {'symbol': 'SOLUSDT', 'type': 'SHORT', 'entry_price': 105, 'current_price': 98.30, 'pnl': 6.70, 'pnl_percent': 6.38, 'size': 10},
        ]
        
        return context


class MetricsView(LoginRequiredMixin, TemplateView):
    """Metrics and analytics view."""
    template_name = 'pages/metrics.html'
    login_url = '/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # TODO: Fetch real metrics from database
        context['total_trades'] = 1247
        context['new_trades'] = 42
        context['avg_win'] = 345.20
        context['avg_loss'] = 142.50
        context['profit_factor'] = 2.42
        context['max_drawdown'] = 12.5
        context['recovery_factor'] = 4.8
        context['expectancy'] = 185.50
        context['kelly_percent'] = 15.8
        context['total_commissions'] = 1245
        context['winning_trades'] = 854
        context['losing_trades'] = 393
        
        # Chart data
        context['equity_labels'] = json.dumps(['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5'])
        context['equity_data'] = json.dumps([10000, 11200, 10800, 12500, 13450])
        context['duration_data'] = json.dumps([120, 340, 280, 190, 85])
        context['weekday_pnl'] = json.dumps([850, 920, 1100, -150, 780, 650, 420])
        context['hourly_labels'] = json.dumps(['00', '04', '08', '12', '16', '20'])
        context['hourly_pnl'] = json.dumps([120, 80, 450, 680, 520, 290])
        
        # Strategy performance
        context['strategies'] = [
            {'name': 'RSI Divergence', 'total_trades': 342, 'win_rate': 68, 'profit_factor': 2.8, 'total_pnl': 4250, 'avg_win': 385, 'avg_loss': 145, 'sharpe': 1.92, 'status': 'active'},
            {'name': 'MA Crossover', 'total_trades': 528, 'win_rate': 62, 'profit_factor': 2.1, 'total_pnl': 3850, 'avg_win': 320, 'avg_loss': 155, 'sharpe': 1.65, 'status': 'active'},
            {'name': 'Breakout', 'total_trades': 185, 'win_rate': 72, 'profit_factor': 3.2, 'total_pnl': 5680, 'avg_win': 450, 'avg_loss': 130, 'sharpe': 2.15, 'status': 'active'},
            {'name': 'Mean Reversion', 'total_trades': 192, 'win_rate': 55, 'profit_factor': 1.5, 'total_pnl': 1120, 'avg_win': 280, 'avg_loss': 185, 'sharpe': 1.12, 'status': 'inactive'},
        ]
        
        return context


class CustomLoginView(LoginView):
    """Custom login view with custom template."""
    template_name = 'pages/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        """Redirect to next parameter or dashboard."""
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy('web_app:dashboard')
    
    def form_invalid(self, form):
        """Add error message on failed login."""
        messages.error(self.request, 'Invalid username or password. Please try again.')
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    """Custom logout view."""
    next_page = 'web_app:home'
    
    def dispatch(self, request, *args, **kwargs):
        """Add success message on logout."""
        if request.user.is_authenticated:
            messages.success(request, 'You have been successfully logged out.')
        return super().dispatch(request, *args, **kwargs)


# More views will be added during migration from React
