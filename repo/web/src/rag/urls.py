"""
URL configuration for RAG (Retrieval-Augmented Generation) app.
"""

from django.http import HttpResponse
from django.urls import path


def placeholder_view(request):
    return HttpResponse("RAG module - Coming soon")


urlpatterns = [
    path("", placeholder_view, name="rag_home"),
]
