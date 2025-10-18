"""
Celery configuration for web.django.
"""

import os

from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.django.settings")

app = Celery("web.django")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat schedule - All 16 tasks configured
app.conf.beat_schedule = {
    # Market Data & Core (Every 5-15 minutes)
    'sync-market-data': {
        'task': 'trading.tasks.sync_market_data_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'update-positions': {
        'task': 'trading.tasks.update_positions_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'sync-account-balance': {
        'task': 'trading.tasks.sync_account_balance_task',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    
    # Signal Generation & Analysis (Every 15-30 minutes)
    'generate-signals': {
        'task': 'trading.tasks.generate_signals_task',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'update-indicators': {
        'task': 'trading.tasks.update_indicators_task',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    'analyze-risk': {
        'task': 'trading.tasks.analyze_risk_task',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    
    # Trading Execution & Monitoring (Hourly or on-demand)
    'check-stop-loss': {
        'task': 'trading.tasks.check_stop_loss_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes (critical)
    },
    
    # Daily Tasks (Run at specific times)
    'run-backtest': {
        'task': 'trading.tasks.run_backtest_task',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'optimize-portfolio': {
        'task': 'trading.tasks.optimize_portfolio_task',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
    },
    'calculate-metrics': {
        'task': 'trading.tasks.calculate_metrics_task',
        'schedule': crontab(hour=23, minute=0),  # Daily at 11 PM
    },
    'generate-daily-report': {
        'task': 'trading.tasks.generate_report_task',
        'schedule': crontab(hour=23, minute=30),  # Daily at 11:30 PM
        'kwargs': {'report_type': 'daily'}
    },
    'validate-strategies': {
        'task': 'trading.tasks.validate_strategies_task',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
    
    # Weekly Tasks
    'generate-weekly-report': {
        'task': 'trading.tasks.generate_report_task',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),  # Monday 8 AM
        'kwargs': {'report_type': 'weekly'}
    },
    
    # Data Management
    'fetch-news': {
        'task': 'trading.tasks.fetch_news_task',
        'schedule': crontab(minute='*/60'),  # Every hour
    },
    'archive-old-data': {
        'task': 'trading.tasks.archive_old_data_task',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
