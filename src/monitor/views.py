"""Views for the monitoring service."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from .models import ServiceRegistry
from .services import HealthCheckService, ServiceDiscoveryService


class MonitorDashboardView(LoginRequiredMixin, TemplateView):
    """Main monitoring dashboard."""

    template_name = "pages/monitor_dashboard.html"

    def get_context_data(self, **kwargs):
        """Add monitoring data to context."""
        context = super().get_context_data(**kwargs)
        services = ServiceRegistry.objects.filter(is_active=True).order_by("service_type", "name")

        context["services"] = services
        context["total_services"] = services.count()
        context["healthy_services"] = services.filter(status="healthy").count()
        context["degraded_services"] = services.filter(status="degraded").count()
        context["down_services"] = services.filter(status="down").count()

        return context


class ServiceHealthAPI(View):
    """API endpoint for checking service health."""

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        """Disable CSRF for API endpoint."""
        return super().dispatch(*args, **kwargs)

    def get(self, request, service_id=None):
        """Get health status of services.

        GET /monitor/api/health/ - Check all services
        GET /monitor/api/health/<id>/ - Check specific service
        """
        if service_id:
            service = get_object_or_404(ServiceRegistry, id=service_id, is_active=True)
            with HealthCheckService() as checker:
                health_check = checker.check_service(service)

            return JsonResponse(
                {
                    "service": service.name,
                    "status": service.status,
                    "success": health_check.success,
                    "response_time_ms": health_check.response_time_ms,
                    "last_seen": service.last_seen.isoformat() if service.last_seen else None,
                }
            )

        # Check all services
        with HealthCheckService() as checker:
            results = checker.check_all_services()

        return JsonResponse(results)


class ServiceRegistryAPI(View):
    """API endpoint for service registry."""

    def get(self, request):
        """Get list of all registered services."""
        services = ServiceRegistry.objects.filter(is_active=True)
        data = {
            "services": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.service_type,
                    "status": s.status,
                    "base_url": s.base_url,
                    "health_url": s.health_url,
                    "last_seen": s.last_seen.isoformat() if s.last_seen else None,
                    "version": s.version,
                }
                for s in services
            ]
        }
        return JsonResponse(data)


class ServiceDiscoverAPI(View):
    """API endpoint for service discovery and registration."""

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        """Disable CSRF for API endpoint."""
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        """Register default services."""
        ServiceDiscoveryService.register_default_services()
        return JsonResponse({"status": "success", "message": "Services registered"})


class PingAPI(View):
    """Simple ping endpoint for inter-service health checks."""

    def get(self, request):
        """Respond to ping requests from other services."""
        return JsonResponse(
            {
                "status": "healthy",
                "service": "fks_monitor",
                "version": "1.0.0",
                "timestamp": timezone.now().isoformat(),
            }
        )
