"""
User authentication models with Redis-backed session management
"""

import json
from datetime import datetime

from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.db import models


class User(AbstractUser):
    """
    Extended user model with trading-specific fields
    """

    USER_TYPES = (
        ("admin", "Administrator"),
        ("trader", "Trader"),
        ("viewer", "Viewer"),
        ("analyst", "Analyst"),
    )

    USER_STATUS = (
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("suspended", "Suspended"),
        ("trial", "Trial"),
    )

    user_type = models.CharField(max_length=20, choices=USER_TYPES, default="viewer")
    status = models.CharField(max_length=20, choices=USER_STATUS, default="trial")

    # Trading-specific fields
    api_key_enabled = models.BooleanField(default=False)
    max_concurrent_sessions = models.IntegerField(default=3)

    # Additional info
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    timezone = models.CharField(max_length=50, default="America/Toronto")

    # Timestamps
    last_active = models.DateTimeField(auto_now=True)
    trial_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "auth_users"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["user_type", "status"]),
        ]

    def __str__(self):
        return f"{self.username} ({self.user_type})"

    def get_redis_key(self, key_type="session"):
        """Generate Redis key for this user"""
        return f"user:{self.id}:{key_type}"

    def set_user_state(self, state_data):
        """Store user state in Redis"""
        key = self.get_redis_key("state")
        cache.set(key, json.dumps(state_data), timeout=86400)  # 24 hours

    def get_user_state(self):
        """Retrieve user state from Redis"""
        key = self.get_redis_key("state")
        data = cache.get(key)
        return json.loads(data) if data else {}

    def get_active_sessions(self):
        """Get list of active sessions for this user"""
        key = self.get_redis_key("sessions")
        sessions = cache.get(key)
        return json.loads(sessions) if sessions else []

    def add_session(self, session_id, device_info=None):
        """Add a new session to Redis"""
        sessions = self.get_active_sessions()
        sessions.append(
            {
                "session_id": session_id,
                "device_info": device_info,
                "created_at": datetime.now().isoformat(),
            }
        )

        # Limit concurrent sessions
        if len(sessions) > self.max_concurrent_sessions:
            sessions = sessions[-self.max_concurrent_sessions :]

        key = self.get_redis_key("sessions")
        cache.set(key, json.dumps(sessions), timeout=86400 * 7)  # 7 days

    def remove_session(self, session_id):
        """Remove a session from Redis"""
        sessions = self.get_active_sessions()
        sessions = [s for s in sessions if s["session_id"] != session_id]

        key = self.get_redis_key("sessions")
        if sessions:
            cache.set(key, json.dumps(sessions), timeout=86400 * 7)
        else:
            cache.delete(key)

    @property
    def is_premium(self):
        """Check if user has premium access"""
        return self.user_type in ["admin", "trader"] and self.status == "active"

    def can_access_feature(self, feature):
        """Check if user can access a specific feature"""
        permissions = {
            "admin": ["*"],  # All features
            "trader": ["trading", "backtest", "analytics", "api"],
            "analyst": ["analytics", "backtest", "reports"],
            "viewer": ["dashboard", "reports"],
        }

        user_permissions = permissions.get(self.user_type, [])
        return "*" in user_permissions or feature in user_permissions


class UserProfile(models.Model):
    """
    Extended profile information for users
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # Trading preferences
    risk_tolerance = models.CharField(
        max_length=20,
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
    )
    default_strategy = models.CharField(max_length=100, blank=True)
    preferred_exchanges = models.JSONField(default=list)

    # Notification settings
    email_notifications = models.BooleanField(default=True)
    discord_notifications = models.BooleanField(default=False)
    discord_webhook = models.URLField(blank=True, null=True)

    # API credentials (encrypted in production)
    binance_api_key = models.CharField(max_length=255, blank=True)
    binance_api_secret = models.CharField(max_length=255, blank=True)

    # Usage statistics
    total_trades = models.IntegerField(default=0)
    successful_trades = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profiles"

    def __str__(self):
        return f"Profile for {self.user.username}"

    def update_trade_stats(self, success):
        """Update trading statistics"""
        self.total_trades += 1
        if success:
            self.successful_trades += 1
        self.save()

    @property
    def success_rate(self):
        """Calculate success rate"""
        if self.total_trades == 0:
            return 0
        return (self.successful_trades / self.total_trades) * 100


class APIKey(models.Model):
    """
    API keys for programmatic access
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=64, unique=True)

    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)

    # Permissions
    permissions = models.JSONField(default=list)

    # Rate limiting
    rate_limit = models.IntegerField(default=100)  # requests per minute

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "api_keys"
        indexes = [
            models.Index(fields=["key"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.user.username}"

    def increment_usage(self):
        """Record API key usage"""
        key = f"api_key:{self.key}:usage"
        current = cache.get(key, 0)
        cache.set(key, current + 1, timeout=60)  # Per minute

        self.last_used = datetime.now()
        self.save(update_fields=["last_used"])

        return current + 1

    def is_rate_limited(self):
        """Check if API key has exceeded rate limit"""
        key = f"api_key:{self.key}:usage"
        usage = cache.get(key, 0)
        return usage >= self.rate_limit


class UserSession(models.Model):
    """
    Track user sessions with additional metadata
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    session_key = models.CharField(max_length=40, unique=True)

    # Session metadata
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device_type = models.CharField(max_length=50, blank=True)

    # Location (optional)
    country = models.CharField(max_length=2, blank=True)
    city = models.CharField(max_length=100, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "user_sessions"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["session_key"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.device_type} - {self.created_at}"

    def terminate(self):
        """Terminate this session"""
        self.is_active = False
        self.save()

        # Remove from Redis
        self.user.remove_session(self.session_key)
