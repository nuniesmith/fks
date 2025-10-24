"""Admin interface for monitoring service."""

from django.contrib import admin
from django.utils.html import format_html

from .models import HealthCheck, ServiceDependency, ServiceMetric, ServiceRegistry


@admin.register(ServiceRegistry)
class ServiceRegistryAdmin(admin.ModelAdmin):
    """Admin for ServiceRegistry model."""

    list_display = [
        "name",
        "service_type",
        "status_badge",
        "host",
        "port",
        "last_seen",
        "is_active",
    ]
    list_filter = ["service_type", "status", "is_active"]
    search_fields = ["name", "host"]
    readonly_fields = ["created_at", "updated_at", "last_seen"]
    fieldsets = [
        (
            "Basic Information",
            {
                "fields": [
                    "name",
                    "service_type",
                    "is_active",
                ]
            },
        ),
        (
            "Connection Details",
            {
                "fields": [
                    "host",
                    "port",
                    "health_endpoint",
                ]
            },
        ),
        (
            "Status",
            {
                "fields": [
                    "status",
                    "last_seen",
                    "version",
                ]
            },
        ),
        (
            "Metadata",
            {
                "fields": ["metadata"],
                "classes": ["collapse"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def status_badge(self, obj):
        """Display status with color badge."""
        colors = {
            "healthy": "#28a745",
            "degraded": "#ffc107",
            "down": "#dc3545",
            "unknown": "#6c757d",
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"


@admin.register(HealthCheck)
class HealthCheckAdmin(admin.ModelAdmin):
    """Admin for HealthCheck model."""

    list_display = [
        "service",
        "success_badge",
        "status_code",
        "response_time_ms",
        "checked_at",
    ]
    list_filter = ["success", "service", "checked_at"]
    search_fields = ["service__name", "error_message"]
    readonly_fields = ["checked_at"]
    date_hierarchy = "checked_at"

    def success_badge(self, obj):
        """Display success status with emoji."""
        if obj.success:
            return format_html('<span style="color: #28a745; font-size: 16px;">✅</span>')
        return format_html('<span style="color: #dc3545; font-size: 16px;">❌</span>')

    success_badge.short_description = "Result"


@admin.register(ServiceDependency)
class ServiceDependencyAdmin(admin.ModelAdmin):
    """Admin for ServiceDependency model."""

    list_display = [
        "service",
        "depends_on",
        "is_critical",
        "created_at",
    ]
    list_filter = ["is_critical", "service__service_type", "depends_on__service_type"]
    search_fields = ["service__name", "depends_on__name"]
    readonly_fields = ["created_at"]


@admin.register(ServiceMetric)
class ServiceMetricAdmin(admin.ModelAdmin):
    """Admin for ServiceMetric model."""

    list_display = [
        "service",
        "metric_type",
        "metric_name",
        "value",
        "unit",
        "recorded_at",
    ]
    list_filter = ["metric_type", "service", "recorded_at"]
    search_fields = ["service__name", "metric_name"]
    readonly_fields = ["recorded_at"]
    date_hierarchy = "recorded_at"
