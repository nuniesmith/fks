"""
Authentication views and API endpoints
"""

import secrets
from datetime import timedelta

from django.contrib.auth import login, logout
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import APIKey, User, UserProfile, UserSession
from .serializers import (
    APIKeySerializer,
    LoginSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserSerializer,
    UserSessionSerializer,
)
from .utils import get_client_ip, get_device_info


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    """Register a new user"""
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response(
            {
                "message": "User registered successfully",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """Login user and create session"""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data["user"]

        # Check concurrent sessions
        active_sessions = user.get_active_sessions()
        if len(active_sessions) >= user.max_concurrent_sessions:
            # Remove oldest session
            oldest = active_sessions[0]
            user.remove_session(oldest["session_id"])

        # Login user
        login(request, user)

        # Create session record
        session = UserSession.objects.create(
            user=user,
            session_key=request.session.session_key,
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            device_type=get_device_info(request),
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Add to Redis
        user.add_session(
            session.session_key,
            {"device": session.device_type, "ip": session.ip_address},
        )

        return Response(
            {
                "message": "Login successful",
                "user": UserSerializer(user).data,
                "session_id": session.session_key,
            }
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout user and terminate session"""
    try:
        session = UserSession.objects.get(
            user=request.user, session_key=request.session.session_key, is_active=True
        )
        session.terminate()
    except UserSession.DoesNotExist:
        pass

    logout(request)
    return Response({"message": "Logout successful"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def current_user_view(request):
    """Get current user info"""
    return Response(
        {
            "user": UserSerializer(request.user).data,
            "profile": UserProfileSerializer(request.user.profile).data,
            "state": request.user.get_user_state(),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_user_state_view(request):
    """Update user state in Redis"""
    state_data = request.data
    request.user.set_user_state(state_data)
    return Response({"message": "State updated", "state": state_data})


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User CRUD operations"""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Regular users can only see themselves
        if not self.request.user.is_staff:
            return User.objects.filter(id=self.request.user.id)
        return User.objects.all()

    @action(detail=True, methods=["get"])
    def sessions(self, request, pk=None):
        """Get active sessions for a user"""
        user = self.get_object()
        if user != request.user and not request.user.is_staff:
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        sessions = UserSession.objects.filter(user=user, is_active=True)
        serializer = UserSessionSerializer(sessions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def terminate_session(self, request, pk=None):
        """Terminate a specific session"""
        user = self.get_object()
        if user != request.user and not request.user.is_staff:
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        session_key = request.data.get("session_key")
        try:
            session = UserSession.objects.get(
                user=user, session_key=session_key, is_active=True
            )
            session.terminate()
            return Response({"message": "Session terminated"})
        except UserSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND
            )


class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for UserProfile operations"""

    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own profile
        if not self.request.user.is_staff:
            return UserProfile.objects.filter(user=self.request.user)
        return UserProfile.objects.all()


class APIKeyViewSet(viewsets.ModelViewSet):
    """ViewSet for API key management"""

    queryset = APIKey.objects.all()
    serializer_class = APIKeySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own API keys
        if not self.request.user.is_staff:
            return APIKey.objects.filter(user=self.request.user)
        return APIKey.objects.all()

    def perform_create(self, serializer):
        # Check if user can create API keys
        if not self.request.user.api_key_enabled:
            raise PermissionError("API key creation not enabled for this user")

        # Generate unique key
        key = secrets.token_urlsafe(48)
        serializer.save(user=self.request.user, key=key)

    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        """Regenerate an API key"""
        api_key = self.get_object()
        if api_key.user != request.user and not request.user.is_staff:
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        api_key.key = secrets.token_urlsafe(48)
        api_key.save()

        serializer = self.get_serializer(api_key)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        """Toggle API key active status"""
        api_key = self.get_object()
        if api_key.user != request.user and not request.user.is_staff:
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        api_key.is_active = not api_key.is_active
        api_key.save()

        serializer = self.get_serializer(api_key)
        return Response(serializer.data)
