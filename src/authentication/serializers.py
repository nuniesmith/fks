"""
DRF serializers for authentication
"""

from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import APIKey, User, UserProfile, UserSession


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "user_type",
            "status",
            "api_key_enabled",
            "timezone",
            "last_active",
            "date_joined",
        )
        read_only_fields = ("id", "date_joined", "last_active")


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model"""

    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            "user",
            "risk_tolerance",
            "default_strategy",
            "preferred_exchanges",
            "email_notifications",
            "discord_notifications",
            "total_trades",
            "successful_trades",
            "success_rate",
        )
        read_only_fields = ("total_trades", "successful_trades", "success_rate")


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
        )

    def validate(self, data):
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError("Passwords do not match")
        return data

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        user = User.objects.create_user(**validated_data)

        # Create user profile
        UserProfile.objects.create(user=user)

        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get("username")
        password = data.get("password")

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError("Invalid credentials")
            if not user.is_active:
                raise serializers.ValidationError("User account is disabled")
            if user.status in ["suspended", "inactive"]:
                raise serializers.ValidationError(f"Account is {user.status}")
        else:
            raise serializers.ValidationError("Must provide username and password")

        data["user"] = user
        return data


class APIKeySerializer(serializers.ModelSerializer):
    """Serializer for API keys"""

    class Meta:
        model = APIKey
        fields = (
            "id",
            "name",
            "key",
            "is_active",
            "permissions",
            "rate_limit",
            "last_used",
            "created_at",
            "expires_at",
        )
        read_only_fields = ("key", "last_used", "created_at")


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer for user sessions"""

    class Meta:
        model = UserSession
        fields = (
            "id",
            "session_key",
            "device_type",
            "ip_address",
            "country",
            "city",
            "created_at",
            "last_activity",
            "is_active",
        )
        read_only_fields = ("session_key", "created_at", "last_activity")
