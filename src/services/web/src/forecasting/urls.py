"""
URL configuration for forecasting app.
"""

from django.http import HttpResponse
from django.urls import path


def placeholder_view(request):
    return HttpResponse("Forecasting module - Coming soon")


urlpatterns = [
    path("", placeholder_view, name="forecasting_home"),
]
