"""Web UI views."""

import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from .db_helpers import (
    get_account_summary,
    get_active_positions,
    get_balance_history,
    get_performance_metrics,
    get_recent_trades,
    get_strategy_performance,
    get_user_accounts,
)


class HomeView(TemplateView):
    """Home page view."""

    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Fetch real account data
        try:
            accounts = get_user_accounts()
            
            # Calculate total metrics across all accounts
            total_balance = sum([float(acc.current_balance) for acc in accounts])
            total_pnl = 0
            
            trading_accounts = []
            for account in accounts:
                summary = get_account_summary(account.id)
                pnl = summary['total_pnl'] + summary['unrealized_pnl']
                total_pnl += pnl
                
                trading_accounts.append({
                    "name": account.name,
                    "exchange": account.broker or "Unknown",
                    "balance": float(account.current_balance),
                    "pnl": pnl,
                    "status": "active" if account.is_active else "inactive",
                })
            
            # Calculate gamification metrics based on trading activity
            # XP based on total trades and performance
            summary = get_account_summary() if accounts else None
            total_trades = summary['total_trades'] if summary else 0
            win_rate = summary['win_rate'] if summary else 0
            
            user_xp = int(total_trades * 10 + win_rate * 100)
            expense_coverage = min(100, int((total_pnl / total_balance * 100) if total_balance > 0 else 0))
            
            context["user_xp"] = user_xp
            context["expense_coverage"] = max(0, expense_coverage)
            context["tax_savings"] = int(total_pnl * 0.2) if total_pnl > 0 else 0  # Simplified
            context["active_accounts"] = len([a for a in accounts if a.is_active])
            context["next_milestone"] = {
                "name": "Senior Trader",
                "progress": min(100, int((user_xp / 20000) * 100)),
                "xp_needed": 20000,
            }
            context["trading_accounts"] = trading_accounts
            
        except Exception as e:
            # Fallback to empty state if database is not available
            context["user_xp"] = 0
            context["expense_coverage"] = 0
            context["tax_savings"] = 0
            context["active_accounts"] = 0
            context["next_milestone"] = {
                "name": "Senior Trader",
                "progress": 0,
                "xp_needed": 20000,
            }
            context["trading_accounts"] = []
        
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    """Trading dashboard view."""

    template_name = "pages/dashboard.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Fetch real trading data from database
            summary = get_account_summary()
            
            context["total_profit"] = summary['total_pnl'] + summary['unrealized_pnl']
            context["win_rate"] = summary['win_rate']
            context["active_positions"] = summary['active_positions']
            context["active_positions_value"] = summary['active_positions_value']
            context["sharpe_ratio"] = 0  # Would need historical returns to calculate properly
            context["symbol"] = "BTCUSDT"  # Default symbol

            # Get balance history for chart
            balance_history = get_balance_history(days=7)
            
            # Chart data (serialize as JSON for JavaScript)
            if balance_history['labels']:
                context["price_labels"] = json.dumps([label.split()[0] for label in balance_history['labels'][-6:]])
                context["price_data"] = json.dumps(balance_history['balances'][-6:])
            else:
                context["price_labels"] = json.dumps(["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6"])
                context["price_data"] = json.dumps([10000, 10000, 10000, 10000, 10000, 10000])
            
            # Daily PnL would require more detailed time-series data
            context["daily_pnl"] = json.dumps([0, 0, 0, 0, 0, 0, 0])

            # Recent signals - would come from a signals table or cache
            # For now, return empty list as signals are generated by Celery tasks
            context["recent_signals"] = []

            # Active positions
            positions = get_active_positions()
            context["active_trades"] = positions[:10]  # Limit to 10 for display
            
        except Exception as e:
            # Fallback to default values if database is not available
            context["total_profit"] = 0
            context["win_rate"] = 0
            context["active_positions"] = 0
            context["active_positions_value"] = 0
            context["sharpe_ratio"] = 0
            context["symbol"] = "BTCUSDT"
            context["price_labels"] = json.dumps(["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6"])
            context["price_data"] = json.dumps([10000, 10000, 10000, 10000, 10000, 10000])
            context["daily_pnl"] = json.dumps([0, 0, 0, 0, 0, 0, 0])
            context["recent_signals"] = []
            context["active_trades"] = []

        return context


class MetricsView(LoginRequiredMixin, TemplateView):
    """Metrics and analytics view."""

    template_name = "pages/metrics.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Fetch real metrics from database
            metrics = get_performance_metrics()
            summary = get_account_summary()
            
            context["total_trades"] = metrics['total_trades']
            context["new_trades"] = 0  # Would need to track time-based new trades
            context["avg_win"] = metrics['avg_win']
            context["avg_loss"] = abs(metrics['avg_loss'])
            context["profit_factor"] = metrics['profit_factor']
            context["max_drawdown"] = 0  # Would need historical equity curve
            context["recovery_factor"] = 0  # Would need max drawdown to calculate
            context["expectancy"] = metrics['expectancy']
            context["kelly_percent"] = 0  # Would need win rate and avg win/loss
            context["total_commissions"] = metrics['total_commissions']
            context["winning_trades"] = metrics['winning_trades']
            context["losing_trades"] = metrics['losing_trades']

            # Get balance history for equity chart
            balance_history = get_balance_history(days=35)
            
            # Chart data
            if balance_history['labels']:
                # Group by weeks for equity chart
                weeks = min(5, len(balance_history['labels']) // 7)
                week_labels = [f"Week {i+1}" for i in range(weeks)]
                week_data = []
                for i in range(weeks):
                    start_idx = i * 7
                    end_idx = min(start_idx + 7, len(balance_history['balances']))
                    if end_idx > start_idx:
                        week_data.append(balance_history['balances'][end_idx - 1])
                
                context["equity_labels"] = json.dumps(week_labels)
                context["equity_data"] = json.dumps(week_data)
            else:
                context["equity_labels"] = json.dumps(["Week 1", "Week 2", "Week 3", "Week 4", "Week 5"])
                context["equity_data"] = json.dumps([10000, 10000, 10000, 10000, 10000])
            
            # Placeholder data for charts that need more complex calculations
            context["duration_data"] = json.dumps([0, 0, 0, 0, 0])
            context["weekday_pnl"] = json.dumps([0, 0, 0, 0, 0, 0, 0])
            context["hourly_labels"] = json.dumps(["00", "04", "08", "12", "16", "20"])
            context["hourly_pnl"] = json.dumps([0, 0, 0, 0, 0, 0])

            # Strategy performance
            strategies = get_strategy_performance()
            context["strategies"] = strategies
            
        except Exception as e:
            # Fallback to default values
            context["total_trades"] = 0
            context["new_trades"] = 0
            context["avg_win"] = 0
            context["avg_loss"] = 0
            context["profit_factor"] = 0
            context["max_drawdown"] = 0
            context["recovery_factor"] = 0
            context["expectancy"] = 0
            context["kelly_percent"] = 0
            context["total_commissions"] = 0
            context["winning_trades"] = 0
            context["losing_trades"] = 0
            context["equity_labels"] = json.dumps(["Week 1", "Week 2", "Week 3", "Week 4", "Week 5"])
            context["equity_data"] = json.dumps([10000, 10000, 10000, 10000, 10000])
            context["duration_data"] = json.dumps([0, 0, 0, 0, 0])
            context["weekday_pnl"] = json.dumps([0, 0, 0, 0, 0, 0, 0])
            context["hourly_labels"] = json.dumps(["00", "04", "08", "12", "16", "20"])
            context["hourly_pnl"] = json.dumps([0, 0, 0, 0, 0, 0])
            context["strategies"] = []

        return context


class CustomLoginView(LoginView):
    """Custom login view with custom template."""

    template_name = "pages/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        """Redirect to next parameter or dashboard."""
        next_url = self.request.GET.get("next")
        if next_url:
            return next_url
        return reverse_lazy("web_app:dashboard")

    def form_invalid(self, form):
        """Add error message on failed login."""
        messages.error(self.request, "Invalid username or password. Please try again.")
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    """Custom logout view."""

    next_page = "web_app:home"

    def dispatch(self, request, *args, **kwargs):
        """Add success message on logout."""
        if request.user.is_authenticated:
            messages.success(request, "You have been successfully logged out.")
        return super().dispatch(request, *args, **kwargs)


class SignalsView(LoginRequiredMixin, TemplateView):
    """Trading signals view with manual approval workflow."""

    template_name = "pages/signals.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Signals would typically come from a signals table or Redis cache
            # populated by Celery tasks. For now, return empty state.
            # TODO: Implement signals table and fetch from database
            context["active_signals"] = 0
            context["avg_confidence"] = 0
            context["signal_win_rate"] = 0
            context["signal_total_profit"] = 0
            context["signals"] = []
            
            # Pending signals awaiting manual approval
            # TODO: Fetch from signals table WHERE status='pending'
            context["pending_signals"] = []
            
        except Exception as e:
            context["active_signals"] = 0
            context["avg_confidence"] = 0
            context["signal_win_rate"] = 0
            context["signal_total_profit"] = 0
            context["signals"] = []
            context["pending_signals"] = []

        return context


class BacktestView(LoginRequiredMixin, TemplateView):
    """Backtest results view."""

    template_name = "pages/backtest.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Backtest results would come from a backtests table
            # For now, return empty state with sample structure
            # TODO: Implement backtest results table and fetch from database
            context["backtest_result"] = {
                "total_return": 0,
                "win_rate": 0,
                "winning_trades": 0,
                "total_trades": 0,
                "losing_trades": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "recovery_factor": 0,
                "expectancy": 0,
                "strategy_name": "No backtest available",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "initial_capital": 10000.00,
                "final_equity": 10000.00,
                "commission": 0.1,
                "slippage": 0.05,
                "duration": "N/A",
                "trades": [],
            }
            
        except Exception as e:
            context["backtest_result"] = {
                "total_return": 0,
                "win_rate": 0,
                "winning_trades": 0,
                "total_trades": 0,
                "losing_trades": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "recovery_factor": 0,
                "expectancy": 0,
                "strategy_name": "Error loading backtest",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "initial_capital": 10000.00,
                "final_equity": 10000.00,
                "commission": 0.1,
                "slippage": 0.05,
                "duration": "N/A",
                "trades": [],
            }

        return context


class SettingsView(LoginRequiredMixin, TemplateView):
    """Strategy settings view."""

    template_name = "pages/settings.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Strategy configurations would come from StrategyParameters table
        # For now, this view doesn't need data, just renders the form
        # TODO: Fetch strategy configurations from StrategyParameters table
        return context


# API Views - Migrated from FastAPI routes


@require_http_methods(["GET"])
def api_health_check(request):
    """Health check endpoint (migrated from FastAPI)."""
    return JsonResponse(
        {
            "status": "healthy",
            "service": "fks-django-api",
            "version": "1.0.0",
            "timestamp": "2025-10-18T00:00:00Z",
        }
    )


@require_http_methods(["GET"])
@login_required
def api_performance(request):
    """Performance metrics endpoint (migrated from FastAPI)."""
    try:
        metrics = get_performance_metrics()
        summary = get_account_summary()
        
        return JsonResponse(
            {
                "total_pnl": summary['total_pnl'] + summary['unrealized_pnl'],
                "total_trades": metrics['total_trades'],
                "win_rate": summary['win_rate'] / 100,  # Convert to decimal
                "profit_factor": metrics['profit_factor'],
                "sharpe_ratio": 0,  # Would need historical returns
                "max_drawdown": 0,  # Would need equity curve
                "last_updated": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return JsonResponse(
            {
                "total_pnl": 0,
                "total_trades": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "last_updated": datetime.now().isoformat(),
                "error": "Database unavailable",
            },
            status=503
        )


@require_http_methods(["GET"])
@login_required
def api_signals(request):
    """Current signals endpoint (migrated from FastAPI)."""
    try:
        # Signals would come from a signals table or cache
        # For now, return empty list as signals are generated by Celery tasks
        # TODO: Implement signals table and fetch active signals
        signals = []
        
        return JsonResponse({"signals": signals})
    except Exception as e:
        return JsonResponse(
            {"signals": [], "error": "Database unavailable"},
            status=503
        )


@require_http_methods(["GET"])
@login_required
def api_assets(request):
    """Assets endpoint (migrated from FastAPI)."""
    try:
        # Assets/symbols would come from trading configuration or a symbols table
        # For now, use the constants from framework config
        from framework.config.constants import SYMBOLS
        
        assets = []
        for symbol in SYMBOLS:
            # Parse symbol (e.g., BTCUSDT -> BTC)
            base = symbol.replace('USDT', '').replace('USD', '')
            assets.append({
                "symbol": symbol,
                "name": base,
                "type": "crypto"
            })
        
        return JsonResponse({"assets": assets})
    except Exception as e:
        # Fallback to basic list
        assets = [
            {"symbol": "BTCUSDT", "name": "Bitcoin", "type": "crypto"},
            {"symbol": "ETHUSDT", "name": "Ethereum", "type": "crypto"},
            {"symbol": "BNBUSDT", "name": "Binance Coin", "type": "crypto"},
        ]
        return JsonResponse({"assets": assets})


# Intelligence Dashboard and Manual Notification Views


class IntelligenceView(LoginRequiredMixin, TemplateView):
    """FKS Intelligence Dashboard with RAG system overview."""

    template_name = "pages/intelligence.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Check RAG availability
            try:
                from src.rag.orchestrator import IntelligenceOrchestrator
                context["rag_available"] = True
            except ImportError:
                context["rag_available"] = False
            
            # Get symbols count
            from framework.config.constants import SYMBOLS, MAINS, ALTS
            context["total_symbols"] = len(SYMBOLS)
            
            # Get active strategies count
            # TODO: Fetch from StrategyParameters table
            context["active_strategies"] = 3  # Scalp, Swing, Long-term
            
            # Get current risk level
            # TODO: Implement risk level calculation from positions
            context["risk_level"] = "LOW"
            context["risk_level_color"] = "success"
            
            # Opportunity categorization counts
            # TODO: Fetch from signals table grouped by timeframe
            context["scalp_count"] = 3
            context["swing_count"] = 2
            context["longterm_count"] = 1
            
            # Recent RAG insights
            # TODO: Fetch from RAG insights/signals table
            context["recent_insights"] = []
            
        except Exception as e:
            # Fallback to default values
            context["rag_available"] = False
            context["total_symbols"] = 12
            context["active_strategies"] = 3
            context["risk_level"] = "LOW"
            context["risk_level_color"] = "success"
            context["scalp_count"] = 0
            context["swing_count"] = 0
            context["longterm_count"] = 0
            context["recent_insights"] = []

        return context


@login_required
@require_http_methods(["POST"])
def approve_signal(request, signal_id):
    """Approve a pending signal and send for execution."""
    try:
        # TODO: Fetch signal from database and mark as approved
        # TODO: Send notification via Discord webhook
        # TODO: Execute trade or add to execution queue
        
        from trading.tasks import send_discord_notification
        
        message = f"✅ **Signal Approved**\nSignal ID: {signal_id}\nManually approved by user. Executing trade..."
        send_discord_notification(message)
        
        messages.success(request, f"Signal #{signal_id} approved and sent for execution.")
        
    except Exception as e:
        messages.error(request, f"Failed to approve signal: {str(e)}")
    
    return redirect('web_app:signals')


@login_required
@require_http_methods(["POST"])
def reject_signal(request, signal_id):
    """Reject a pending signal."""
    try:
        # TODO: Fetch signal from database and mark as rejected
        # TODO: Send notification via Discord webhook
        
        from trading.tasks import send_discord_notification
        
        message = f"❌ **Signal Rejected**\nSignal ID: {signal_id}\nManually rejected by user."
        send_discord_notification(message)
        
        messages.warning(request, f"Signal #{signal_id} rejected.")
        
    except Exception as e:
        messages.error(request, f"Failed to reject signal: {str(e)}")
    
    return redirect('web_app:signals')


@login_required
@require_http_methods(["POST"])
def approve_all_signals(request):
    """Approve all pending signals."""
    try:
        # TODO: Fetch all pending signals and mark as approved
        # TODO: Send batch notification via Discord
        
        from trading.tasks import send_discord_notification
        
        message = "✅ **All Signals Approved**\nAll pending signals approved by user. Executing trades..."
        send_discord_notification(message)
        
        messages.success(request, "All pending signals approved and sent for execution.")
        
    except Exception as e:
        messages.error(request, f"Failed to approve all signals: {str(e)}")
    
    return redirect('web_app:signals')


@login_required
@require_http_methods(["POST"])
def reject_all_signals(request):
    """Reject all pending signals."""
    try:
        # TODO: Fetch all pending signals and mark as rejected
        # TODO: Send batch notification via Discord
        
        from trading.tasks import send_discord_notification
        
        message = "❌ **All Signals Rejected**\nAll pending signals rejected by user."
        send_discord_notification(message)
        
        messages.warning(request, "All pending signals rejected.")
        
    except Exception as e:
        messages.error(request, f"Failed to reject all signals: {str(e)}")
    
    return redirect('web_app:signals')
