"""Web UI URL patterns."""
from django.urls import path
from . import views
from .health import HealthDashboardView, HealthAPIView

app_name = 'web_app'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('metrics/', views.MetricsView.as_view(), name='metrics'),
    
    # Health monitoring
    path('health/', HealthAPIView.as_view(), name='health_api'),
    path('health/dashboard/', HealthDashboardView.as_view(), name='health_dashboard'),
    
    # More URL patterns will be added during migration
]
