"""
URL configuration for fks_project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # New refactored apps
    path('api/', include('api_app.urls')),
    path('', include('web_app.urls')),  # Web UI at root
    
    # Legacy apps (to be migrated)
    path('trading/', include('trading.urls')),
    path('forecasting/', include('forecasting.urls')),
    path('chatbot/', include('chatbot.urls')),
    path('rag/', include('rag.urls')),
]

# Serve media and static files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Customize admin site
admin.site.site_header = "FKS Trading Admin"
admin.site.site_title = "FKS Trading Admin Portal"
admin.site.index_title = "Welcome to FKS Trading Administration"
