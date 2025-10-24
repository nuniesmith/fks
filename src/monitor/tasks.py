"""Celery tasks for monitoring service."""

import logging

from celery import shared_task

from .services import HealthCheckService, ServiceDiscoveryService

logger = logging.getLogger(__name__)


@shared_task(name="monitor.check_all_services")
def check_all_services_task():
    """Celery task to check health of all services."""
    logger.info("🔍 Starting health check for all services...")

    with HealthCheckService() as checker:
        results = checker.check_all_services()

    logger.info(
        f"✅ Health check complete: {results['healthy']}/{results['total']} services healthy"
    )
    return results


@shared_task(name="monitor.register_services")
def register_services_task():
    """Celery task to register default services on startup."""
    logger.info("📝 Registering default FKS services...")
    ServiceDiscoveryService.register_default_services()
    logger.info("✅ Service registration complete")
