"""Tests for web views with database integration."""

import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.database.models import Account, Position, Trade
from web.db_helpers import (
    get_account_summary,
    get_active_positions,
    get_performance_metrics,
    get_strategy_performance,
    get_user_accounts,
)

User = get_user_model()


@pytest.mark.web
class TestWebViewsWithMockDB:
    """Test web views with mocked database responses."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return Client()

    @pytest.fixture
    def user(self, db):
        """Create test user."""
        return User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    @pytest.fixture
    def authenticated_client(self, client, user):
        """Create authenticated client."""
        client.force_login(user)
        return client

    def test_home_view_with_empty_database(self, client):
        """Test home view returns successfully with empty database."""
        with patch('web.views.get_user_accounts', return_value=[]):
            response = client.get(reverse('web_app:home'))
            
            assert response.status_code == 200
            assert 'user_xp' in response.context
            assert response.context['user_xp'] == 0
            assert response.context['active_accounts'] == 0
            assert response.context['trading_accounts'] == []

    def test_dashboard_view_requires_login(self, client):
        """Test dashboard view requires authentication."""
        response = client.get(reverse('web_app:dashboard'))
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_dashboard_view_with_empty_database(self, authenticated_client):
        """Test dashboard view with empty database."""
        with patch('web.views.get_account_summary') as mock_summary, \
             patch('web.views.get_balance_history') as mock_history, \
             patch('web.views.get_active_positions', return_value=[]):
            
            mock_summary.return_value = {
                'total_pnl': 0,
                'unrealized_pnl': 0,
                'win_rate': 0,
                'active_positions': 0,
                'active_positions_value': 0,
            }
            mock_history.return_value = {'labels': [], 'balances': []}
            
            response = authenticated_client.get(reverse('web_app:dashboard'))
            
            assert response.status_code == 200
            assert response.context['total_profit'] == 0
            assert response.context['win_rate'] == 0
            assert response.context['active_trades'] == []

    def test_metrics_view_with_empty_database(self, authenticated_client):
        """Test metrics view with empty database."""
        with patch('web.views.get_performance_metrics') as mock_perf, \
             patch('web.views.get_account_summary') as mock_summary, \
             patch('web.views.get_balance_history') as mock_history, \
             patch('web.views.get_strategy_performance', return_value=[]):
            
            mock_perf.return_value = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'total_commissions': 0,
                'expectancy': 0,
            }
            mock_summary.return_value = {
                'total_trades': 0,
                'win_rate': 0,
            }
            mock_history.return_value = {'labels': [], 'balances': []}
            
            response = authenticated_client.get(reverse('web_app:metrics'))
            
            assert response.status_code == 200
            assert response.context['total_trades'] == 0
            assert response.context['strategies'] == []

    def test_signals_view(self, authenticated_client):
        """Test signals view."""
        response = authenticated_client.get(reverse('web_app:signals'))
        
        assert response.status_code == 200
        assert 'signals' in response.context
        assert response.context['active_signals'] == 0

    def test_backtest_view(self, authenticated_client):
        """Test backtest view."""
        response = authenticated_client.get(reverse('web_app:backtest'))
        
        assert response.status_code == 200
        assert 'backtest_result' in response.context
        assert response.context['backtest_result']['total_trades'] == 0

    def test_api_performance_endpoint(self, authenticated_client):
        """Test API performance endpoint."""
        with patch('web.views.get_performance_metrics') as mock_perf, \
             patch('web.views.get_account_summary') as mock_summary:
            
            mock_perf.return_value = {
                'total_trades': 100,
                'profit_factor': 2.5,
            }
            mock_summary.return_value = {
                'total_pnl': 1000,
                'unrealized_pnl': 500,
                'win_rate': 65,
            }
            
            response = authenticated_client.get(reverse('web_app:api_performance'))
            
            assert response.status_code == 200
            data = json.loads(response.content)
            assert data['total_pnl'] == 1500
            assert data['total_trades'] == 100
            assert 'last_updated' in data

    def test_api_signals_endpoint(self, authenticated_client):
        """Test API signals endpoint."""
        response = authenticated_client.get(reverse('web_app:api_signals'))
        
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'signals' in data
        assert isinstance(data['signals'], list)

    def test_api_assets_endpoint(self, authenticated_client):
        """Test API assets endpoint."""
        response = authenticated_client.get(reverse('web_app:api_assets'))
        
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'assets' in data
        assert len(data['assets']) > 0
        assert all('symbol' in asset for asset in data['assets'])


@pytest.mark.web
@pytest.mark.integration
class TestDBHelpers:
    """Test database helper functions."""

    def test_get_empty_account_summary(self):
        """Test account summary with no data."""
        with patch('web.db_helpers.get_db_session') as mock_session:
            mock_session.return_value.query.return_value.filter.return_value.first.return_value = None
            
            summary = get_account_summary()
            
            assert summary['total_trades'] == 0
            assert summary['win_rate'] == 0
            assert summary['account'] is None

    def test_get_active_positions_empty(self):
        """Test getting positions with empty database."""
        with patch('web.db_helpers.get_db_session') as mock_session:
            mock_session.return_value.query.return_value.all.return_value = []
            
            positions = get_active_positions()
            
            assert positions == []

    def test_get_performance_metrics_empty(self):
        """Test performance metrics with empty database."""
        with patch('web.db_helpers.get_db_session') as mock_session:
            mock_session.return_value.query.return_value.all.return_value = []
            
            metrics = get_performance_metrics()
            
            assert metrics['total_trades'] == 0
            assert metrics['winning_trades'] == 0
            assert metrics['profit_factor'] == 0

    def test_get_strategy_performance_empty(self):
        """Test strategy performance with empty database."""
        with patch('web.db_helpers.get_db_session') as mock_session:
            mock_session.return_value.query.return_value.all.return_value = []
            
            strategies = get_strategy_performance()
            
            assert strategies == []

    def test_get_user_accounts_empty(self):
        """Test getting accounts with empty database."""
        with patch('web.db_helpers.get_db_session') as mock_session:
            mock_session.return_value.query.return_value.filter.return_value.all.return_value = []
            
            accounts = get_user_accounts()
            
            assert accounts == []


@pytest.mark.web
class TestViewsErrorHandling:
    """Test error handling in views."""

    @pytest.fixture
    def authenticated_client(self, client, db):
        """Create authenticated client."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        client.force_login(user)
        return client

    def test_home_view_handles_database_error(self, client):
        """Test home view handles database errors gracefully."""
        with patch('web.views.get_user_accounts', side_effect=Exception("DB Error")):
            response = client.get(reverse('web_app:home'))
            
            # Should still return 200 with fallback data
            assert response.status_code == 200
            assert response.context['active_accounts'] == 0

    def test_dashboard_view_handles_database_error(self, authenticated_client):
        """Test dashboard view handles database errors gracefully."""
        with patch('web.views.get_account_summary', side_effect=Exception("DB Error")):
            response = authenticated_client.get(reverse('web_app:dashboard'))
            
            assert response.status_code == 200
            assert response.context['total_profit'] == 0

    def test_api_performance_handles_error(self, authenticated_client):
        """Test API performance endpoint handles errors."""
        with patch('web.views.get_performance_metrics', side_effect=Exception("DB Error")):
            response = authenticated_client.get(reverse('web_app:api_performance'))
            
            # Should return 503 Service Unavailable
            assert response.status_code == 503
            data = json.loads(response.content)
            assert 'error' in data
