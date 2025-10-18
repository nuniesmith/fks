"""
URL configuration for chatbot app.
"""

from django.http import HttpResponse
from django.urls import path


def placeholder_view(request):
    return HttpResponse("Chatbot module - Coming soon")


urlpatterns = [
    path("", placeholder_view, name="chatbot_home"),
]
