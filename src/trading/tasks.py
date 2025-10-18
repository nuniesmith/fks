"""
Celery tasks for FKS trading platform.
Minimal stub for initial setup - will be populated as models are created.
"""

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True)
def debug_task(self):
    """Debug task to test Celery is working."""
    logger.info(f"Request: {self.request!r}")
    return "Celery is working!"


@shared_task
def sync_market_data():
    """Placeholder for market data sync task."""
    logger.info("Market data sync task called - not yet implemented")
    return "Market data sync - stub"


@shared_task
def update_signals():
    """Placeholder for signals update task."""
    logger.info("Update signals task called - not yet implemented")
    return "Update signals - stub"


@shared_task
def run_scheduled_backtests():
    """Placeholder for scheduled backtests task."""
    logger.info("Run scheduled backtests task called - not yet implemented")
    return "Run scheduled backtests - stub"
