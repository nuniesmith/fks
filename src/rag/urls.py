"""
URL configuration for RAG (Retrieval-Augmented Generation) app.
"""

from django.urls import path
from django.http import HttpResponse

def placeholder_view(request):
    return HttpResponse("RAG module - Coming soon")

urlpatterns = [
    path('', placeholder_view, name='rag_home'),
]
