"""
Django admin configuration for authentication models
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import APIKey, User, UserProfile, UserSession


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model"""

    list_display = (
        "username",
        "email",
        "user_type",
        "status",
        "last_active",
        "is_staff",
    )
    list_filter = ("user_type", "status", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")

    fieldsets = BaseUserAdmin.fieldsets + (
        ("User Type & Status", {"fields": ("user_type", "status", "api_key_enabled")}),
        ("Session Management", {"fields": ("max_concurrent_sessions",)}),
        (
            "Additional Info",
            {"fields": ("phone_number", "timezone", "trial_expires_at")},
        ),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("User Type & Status", {"fields": ("user_type", "status")}),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface for UserProfile model"""

    list_display = (
        "user",
        "risk_tolerance",
        "total_trades",
        "success_rate",
        "created_at",
    )
    list_filter = ("risk_tolerance", "email_notifications")
    search_fields = ("user__username", "user__email")

    fieldsets = (
        ("User", {"fields": ("user",)}),
        (
            "Trading Preferences",
            {"fields": ("risk_tolerance", "default_strategy", "preferred_exchanges")},
        ),
        (
            "Notifications",
            {
                "fields": (
                    "email_notifications",
                    "discord_notifications",
                    "discord_webhook",
                )
            },
        ),
        (
            "API Credentials",
            {
                "fields": ("binance_api_key", "binance_api_secret"),
                "classes": ("collapse",),
            },
        ),
        (
            "Statistics",
            {"fields": ("total_trades", "successful_trades"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ("created_at", "updated_at")


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    """Admin interface for APIKey model"""

    list_display = (
        "name",
        "user",
        "is_active",
        "last_used",
        "rate_limit",
        "created_at",
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "user__username", "key")

    fieldsets = (
        ("Basic Info", {"fields": ("user", "name", "key")}),
        ("Status", {"fields": ("is_active", "last_used")}),
        ("Permissions & Limits", {"fields": ("permissions", "rate_limit")}),
        ("Validity", {"fields": ("created_at", "expires_at")}),
    )

    readonly_fields = ("created_at", "last_used")


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Admin interface for UserSession model"""

    list_display = (
        "user",
        "device_type",
        "ip_address",
        "is_active",
        "created_at",
        "last_activity",
    )
    list_filter = ("is_active", "device_type", "created_at")
    search_fields = ("user__username", "ip_address", "session_key")

    fieldsets = (
        ("User & Session", {"fields": ("user", "session_key")}),
        ("Device Info", {"fields": ("ip_address", "user_agent", "device_type")}),
        ("Location", {"fields": ("country", "city"), "classes": ("collapse",)}),
        (
            "Status & Timing",
            {"fields": ("is_active", "created_at", "last_activity", "expires_at")},
        ),
    )

    readonly_fields = ("created_at", "last_activity")

    actions = ["terminate_sessions"]

    def terminate_sessions(self, request, queryset):
        """Admin action to terminate selected sessions"""
        for session in queryset:
            session.terminate()
        self.message_user(request, f"{queryset.count()} sessions terminated.")

    terminate_sessions.short_description = "Terminate selected sessions"
