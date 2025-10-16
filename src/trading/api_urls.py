"""
API URL configuration for trading app.
REST API endpoints for the trading application.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

# Create a router for viewsets
router = DefaultRouter()

# Register viewsets here when ready
# router.register(r'trades', TradeViewSet)
# router.register(r'positions', PositionViewSet)

urlpatterns = router.urls

# Add additional API paths here
# urlpatterns += [
#     path('custom-endpoint/', custom_view, name='custom-api'),
# ]
