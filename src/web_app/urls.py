"""Web UI URL patterns."""
from django.urls import path
from . import views

app_name = 'web_app'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    # More URL patterns will be added during migration
]
