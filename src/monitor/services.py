"""Service layer for monitoring and health checks."""

import logging
import time
from typing import Any

import httpx
from django.db import models
from django.utils import timezone

from .models import HealthCheck, ServiceRegistry

logger = logging.getLogger(__name__)


class HealthCheckService:
    """Service for performing health checks on registered services."""

    def __init__(self, timeout: float = 5.0):
        """Initialize health check service.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)

    def check_service(self, service: ServiceRegistry) -> HealthCheck:
        """Perform health check on a single service.

        Args:
            service: Service to check

        Returns:
            HealthCheck record
        """
        start_time = time.time()
        health_check = HealthCheck(service=service)

        try:
            response = self.client.get(service.health_url)
            response_time_ms = (time.time() - start_time) * 1000

            health_check.status_code = response.status_code
            health_check.response_time_ms = response_time_ms
            health_check.success = response.status_code == 200

            try:
                health_check.response_data = response.json()
            except Exception:
                health_check.response_data = {"raw": response.text[:1000]}

            if health_check.success:
                # Extract version and metadata from response
                version = health_check.response_data.get("version")
                metadata = health_check.response_data.get("metadata", {})
                service.mark_healthy(version=version, metadata=metadata)
                logger.info(f"✅ Health check passed for {service.name} ({response_time_ms:.2f}ms)")
            else:
                health_check.error_message = f"HTTP {response.status_code}: {response.text[:500]}"
                service.mark_down()
                logger.warning(f"⚠️ Health check failed for {service.name}: {health_check.error_message}")

        except httpx.TimeoutException:
            response_time_ms = (time.time() - start_time) * 1000
            health_check.status_code = 0
            health_check.response_time_ms = response_time_ms
            health_check.success = False
            health_check.error_message = f"Request timeout after {self.timeout}s"
            service.mark_down()
            logger.error(f"❌ Timeout checking {service.name}: {health_check.error_message}")

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            health_check.status_code = 0
            health_check.response_time_ms = response_time_ms
            health_check.success = False
            health_check.error_message = str(e)
            service.mark_down()
            logger.error(f"❌ Error checking {service.name}: {e}")

        health_check.save()
        return health_check

    def check_all_services(self) -> dict[str, Any]:
        """Check health of all active services.

        Returns:
            Dictionary with check results
        """
        services = ServiceRegistry.objects.filter(is_active=True)
        results = {"total": 0, "healthy": 0, "unhealthy": 0, "checks": []}

        for service in services:
            health_check = self.check_service(service)
            results["total"] += 1
            if health_check.success:
                results["healthy"] += 1
            else:
                results["unhealthy"] += 1
            results["checks"].append(
                {
                    "service": service.name,
                    "success": health_check.success,
                    "response_time_ms": health_check.response_time_ms,
                    "status_code": health_check.status_code,
                }
            )

        return results

    def get_service_health_summary(self, service: ServiceRegistry, hours: int = 24) -> dict[str, Any]:
        """Get health summary for a service over the last N hours.

        Args:
            service: Service to get summary for
            hours: Number of hours to look back

        Returns:
            Health summary dictionary
        """
        since = timezone.now() - timezone.timedelta(hours=hours)
        checks = HealthCheck.objects.filter(service=service, checked_at__gte=since)

        total_checks = checks.count()
        if total_checks == 0:
            return {
                "service": service.name,
                "total_checks": 0,
                "success_rate": 0,
                "avg_response_time_ms": 0,
                "uptime_percentage": 0,
            }

        successful_checks = checks.filter(success=True).count()
        avg_response_time = checks.filter(success=True).aggregate(avg=models.Avg("response_time_ms"))["avg"] or 0

        return {
            "service": service.name,
            "total_checks": total_checks,
            "successful_checks": successful_checks,
            "failed_checks": total_checks - successful_checks,
            "success_rate": (successful_checks / total_checks) * 100,
            "avg_response_time_ms": round(avg_response_time, 2),
            "uptime_percentage": (successful_checks / total_checks) * 100,
        }

    def close(self):
        """Close HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class ServiceDiscoveryService:
    """Service for discovering and registering FKS microservices."""

    DEFAULT_SERVICES = [
        {
            "name": "fks_api",
            "service_type": "api",
            "host": "fks_api",
            "port": 8001,
            "health_endpoint": "/api/health",
        },
        {
            "name": "fks_data",
            "service_type": "data",
            "host": "fks_data",
            "port": 8002,
            "health_endpoint": "/health",
        },
        {
            "name": "fks_execution",
            "service_type": "execution",
            "host": "fks_execution",
            "port": 8003,
            "health_endpoint": "/health",
        },
        {
            "name": "fks_ninja",
            "service_type": "ninja",
            "host": "fks_ninja",
            "port": 8004,
            "health_endpoint": "/health",
        },
        {
            "name": "fks_web_ui",
            "service_type": "web",
            "host": "fks_web",
            "port": 3000,
            "health_endpoint": "/health",
        },
        {
            "name": "fks_rag",
            "service_type": "rag",
            "host": "rag_service",
            "port": 8001,
            "health_endpoint": "/health",
        },
        {
            "name": "celery_worker",
            "service_type": "celery",
            "host": "celery_worker",
            "port": 5555,  # Flower monitoring
            "health_endpoint": "/healthcheck",
        },
    ]

    @classmethod
    def register_default_services(cls):
        """Register all default FKS services."""
        for service_config in cls.DEFAULT_SERVICES:
            service, created = ServiceRegistry.objects.get_or_create(
                name=service_config["name"],
                defaults=service_config,
            )
            if created:
                logger.info(f"✅ Registered service: {service.name}")
            else:
                # Update existing service config
                for key, value in service_config.items():
                    if key != "name":
                        setattr(service, key, value)
                service.save()
                logger.info(f"🔄 Updated service: {service.name}")

    @classmethod
    def discover_services(cls) -> list[ServiceRegistry]:
        """Discover all registered services.

        Returns:
            List of all services
        """
        return list(ServiceRegistry.objects.filter(is_active=True))
