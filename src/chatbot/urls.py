"""
URL configuration for chatbot app.
"""

from django.urls import path
from django.http import HttpResponse

def placeholder_view(request):
    return HttpResponse("Chatbot module - Coming soon")

urlpatterns = [
    path('', placeholder_view, name='chatbot_home'),
]
