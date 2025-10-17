"""
Celery configuration for web.django.
"""
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.django.settings')

app = Celery('web.django')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat schedule
# TODO: Re-enable once task implementations are complete
app.conf.beat_schedule = {
    # 'sync-market-data': {
    #     'task': 'trading.tasks.sync_market_data',
    #     'schedule': crontab(minute='*/5'),  # Every 5 minutes
    # },
    # 'update-signals': {
    #     'task': 'trading.tasks.update_signals',
    #     'schedule': crontab(minute='*/15'),  # Every 15 minutes
    # },
    # 'run-backtests': {
    #     'task': 'trading.tasks.run_scheduled_backtests',
    #     'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    # },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
