"""URL configuration for monitor app."""

from django.urls import path

from . import views

app_name = "monitor"

urlpatterns = [
    # Dashboard
    path("", views.MonitorDashboardView.as_view(), name="dashboard"),
    # API endpoints
    path("api/health/", views.ServiceHealthAPI.as_view(), name="api_health_all"),
    path("api/health/<int:service_id>/", views.ServiceHealthAPI.as_view(), name="api_health_service"),
    path("api/registry/", views.ServiceRegistryAPI.as_view(), name="api_registry"),
    path("api/discover/", views.ServiceDiscoverAPI.as_view(), name="api_discover"),
    path("api/ping/", views.PingAPI.as_view(), name="api_ping"),
]
