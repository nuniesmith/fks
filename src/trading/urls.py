"""
URL configuration for trading app.
Maps views to URL patterns.
"""

from django.urls import path
from . import views

app_name = 'trading'

urlpatterns = [
    # Main views (from Streamlit tabs)
    path('', views.dashboard, name='dashboard'),
    path('data-pull/', views.data_pull_view, name='data_pull'),
    path('optimization/', views.optimization_view, name='optimization'),
    path('signals/', views.signals_view, name='signals'),
    path('trades/', views.trades_view, name='trades'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('test-notification/', views.test_notification, name='test_notification'),
    
    # Additional views
    path('positions/', views.positions_view, name='positions'),
    path('backtest/<int:backtest_id>/', views.backtest_detail_view, name='backtest_detail'),
    path('clear-cache/', views.clear_cache_view, name='clear_cache'),
    
    # API endpoints
    path('api/live-prices/', views.api_live_prices, name='api_live_prices'),
    path('api/positions/', views.api_positions, name='api_positions'),
    path('api/trades/', views.api_recent_trades, name='api_recent_trades'),
    path('api/signal/', views.api_current_signal, name='api_current_signal'),
    path('api/backtest/', views.api_backtest_results, name='api_backtest_list'),
    path('api/backtest/<int:backtest_id>/', views.api_backtest_results, name='api_backtest_detail'),
    path('api/update-prices/', views.api_update_position_prices, name='api_update_prices'),
]
