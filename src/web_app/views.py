"""Web UI views."""
from django.shortcuts import render
from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Home page view."""
    template_name = 'pages/home.html'


class DashboardView(TemplateView):
    """Trading dashboard view."""
    template_name = 'pages/dashboard.html'


# More views will be added during migration from React
