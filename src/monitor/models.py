"""Models for the FKS monitoring service."""

from django.db import models
from django.utils import timezone


class ServiceRegistry(models.Model):
    """Registry of all FKS microservices."""

    SERVICE_TYPES = [
        ("api", "API Service"),
        ("data", "Data Ingestion Service"),
        ("execution", "Trade Execution Service"),
        ("ninja", "NinjaTrader Integration"),
        ("web", "Web UI Service"),
        ("monitor", "Monitoring Service"),
        ("rag", "RAG/AI Service"),
        ("celery", "Celery Worker"),
    ]

    STATUS_CHOICES = [
        ("healthy", "Healthy"),
        ("degraded", "Degraded"),
        ("down", "Down"),
        ("unknown", "Unknown"),
    ]

    name = models.CharField(max_length=100, unique=True, help_text="Service name")
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES)
    host = models.CharField(max_length=255, help_text="Service host (e.g., localhost, fks_api)")
    port = models.IntegerField(help_text="Service port")
    health_endpoint = models.CharField(
        max_length=255,
        default="/health",
        help_text="Health check endpoint path",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unknown")
    last_seen = models.DateTimeField(null=True, blank=True, help_text="Last successful health check")
    version = models.CharField(max_length=50, blank=True, help_text="Service version")
    is_active = models.BooleanField(default=True, help_text="Is service enabled?")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional service metadata")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"
        ordering = ["service_type", "name"]
        indexes = [
            models.Index(fields=["status", "is_active"]),
            models.Index(fields=["service_type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_service_type_display()}) - {self.status}"

    @property
    def base_url(self):
        """Get the base URL for this service."""
        return f"http://{self.host}:{self.port}"

    @property
    def health_url(self):
        """Get the full health check URL."""
        return f"{self.base_url}{self.health_endpoint}"

    def mark_healthy(self, version=None, metadata=None):
        """Mark service as healthy."""
        self.status = "healthy"
        self.last_seen = timezone.now()
        if version:
            self.version = version
        if metadata:
            self.metadata.update(metadata)
        self.save(update_fields=["status", "last_seen", "version", "metadata", "updated_at"])

    def mark_down(self):
        """Mark service as down."""
        self.status = "down"
        self.save(update_fields=["status", "updated_at"])


class HealthCheck(models.Model):
    """Record of health check pings between services."""

    service = models.ForeignKey(
        ServiceRegistry,
        on_delete=models.CASCADE,
        related_name="health_checks",
    )
    status_code = models.IntegerField(help_text="HTTP status code")
    response_time_ms = models.FloatField(help_text="Response time in milliseconds")
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    response_data = models.JSONField(default=dict, blank=True, help_text="Health check response")

    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Health Check"
        verbose_name_plural = "Health Checks"
        ordering = ["-checked_at"]
        indexes = [
            models.Index(fields=["service", "-checked_at"]),
            models.Index(fields=["success", "-checked_at"]),
        ]

    def __str__(self):
        status = "✅" if self.success else "❌"
        return f"{status} {self.service.name} - {self.checked_at.strftime('%Y-%m-%d %H:%M:%S')}"


class ServiceDependency(models.Model):
    """Tracks dependencies between services."""

    service = models.ForeignKey(
        ServiceRegistry,
        on_delete=models.CASCADE,
        related_name="dependencies",
        help_text="The service that depends on another",
    )
    depends_on = models.ForeignKey(
        ServiceRegistry,
        on_delete=models.CASCADE,
        related_name="dependents",
        help_text="The service being depended upon",
    )
    is_critical = models.BooleanField(
        default=True,
        help_text="Is this dependency critical? (service can't function without it)",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional dependency info (e.g., why it's needed)",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Service Dependency"
        verbose_name_plural = "Service Dependencies"
        unique_together = [["service", "depends_on"]]
        ordering = ["service__name", "depends_on__name"]

    def __str__(self):
        critical = "⚠️" if self.is_critical else "ℹ️"
        return f"{critical} {self.service.name} → {self.depends_on.name}"


class ServiceMetric(models.Model):
    """Time-series metrics for services."""

    METRIC_TYPES = [
        ("cpu", "CPU Usage"),
        ("memory", "Memory Usage"),
        ("requests", "Request Count"),
        ("errors", "Error Count"),
        ("latency", "Average Latency"),
        ("custom", "Custom Metric"),
    ]

    service = models.ForeignKey(
        ServiceRegistry,
        on_delete=models.CASCADE,
        related_name="metrics",
    )
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    metric_name = models.CharField(max_length=100, help_text="Metric name")
    value = models.FloatField(help_text="Metric value")
    unit = models.CharField(max_length=20, blank=True, help_text="Unit (%, ms, count, etc.)")
    tags = models.JSONField(default=dict, blank=True, help_text="Additional tags/labels")

    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Service Metric"
        verbose_name_plural = "Service Metrics"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["service", "metric_type", "-recorded_at"]),
            models.Index(fields=["-recorded_at"]),
        ]

    def __str__(self):
        return f"{self.service.name} - {self.metric_name}: {self.value}{self.unit}"
