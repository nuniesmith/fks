"""
URL configuration for authentication app
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"users", views.UserViewSet, basename="user")
router.register(r"profiles", views.UserProfileViewSet, basename="profile")
router.register(r"api-keys", views.APIKeyViewSet, basename="apikey")

app_name = "authentication"

urlpatterns = [
    # Auth endpoints
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("me/", views.current_user_view, name="current-user"),
    path("state/", views.update_user_state_view, name="update-state"),
    # Router URLs
    path("", include(router.urls)),
]
