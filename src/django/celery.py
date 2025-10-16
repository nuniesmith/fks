"""
Celery configuration for fks trading platform.
Handles background tasks, scheduled jobs, and async processing.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fks_project.settings')

app = Celery('fks_project')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


# Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Fetch price data every 5 minutes
    'fetch-latest-prices-every-5-minutes': {
        'task': 'trading.tasks.fetch_latest_prices',
        'schedule': 300.0,  # 5 minutes in seconds
        'options': {
            'expires': 240.0,  # Expire if not run within 4 minutes
        }
    },
    
    # Generate trading signals every 15 minutes
    'generate-signals-every-15-minutes': {
        'task': 'trading.tasks.generate_trading_signals',
        'schedule': 900.0,  # 15 minutes
        'options': {
            'expires': 840.0,
        }
    },
    
    # Update open positions every 1 minute
    'update-positions-every-minute': {
        'task': 'trading.tasks.update_open_positions',
        'schedule': 60.0,  # 1 minute
        'options': {
            'expires': 50.0,
        }
    },
    
    # Record account balances every hour
    'record-balances-hourly': {
        'task': 'trading.tasks.record_account_balances',
        'schedule': crontab(minute=0),  # Every hour at minute 0
    },
    
    # Run daily optimization at 2 AM UTC
    'daily-optimization': {
        'task': 'trading.tasks.run_daily_optimization',
        'schedule': crontab(hour=2, minute=0),  # 2:00 AM UTC
        'options': {
            'expires': 3600.0,  # 1 hour
        }
    },
    
    # Clean up old signals (older than 7 days) - Daily at 3 AM
    'cleanup-old-signals': {
        'task': 'trading.tasks.cleanup_old_data',
        'schedule': crontab(hour=3, minute=0),
        'kwargs': {'days': 7, 'model_type': 'signal'},
    },
    
    # Send daily performance summary at 9 AM UTC
    'daily-performance-report': {
        'task': 'trading.tasks.send_performance_summary',
        'schedule': crontab(hour=9, minute=0),
        'kwargs': {'period': 'daily'},
    },
    
    # Weekly performance report on Monday at 10 AM
    'weekly-performance-report': {
        'task': 'trading.tasks.send_performance_summary',
        'schedule': crontab(hour=10, minute=0, day_of_week=1),
        'kwargs': {'period': 'weekly'},
    },
}


# Celery configuration
app.conf.update(
    # Task settings
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Broker settings
    broker_connection_retry_on_startup=True,
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to test Celery configuration"""
    print(f'Request: {self.request!r}')
