"""Web UI URL patterns."""
from django.urls import path
from . import views

app_name = 'web_app'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('metrics/', views.MetricsView.as_view(), name='metrics'),
    # More URL patterns will be added during migration
]
