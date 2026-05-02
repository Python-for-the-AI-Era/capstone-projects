"""
VULNERABLE Django URLs - DO NOT USE IN PRODUCTION
This file contains intentional security vulnerabilities for educational purposes.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('job/<int:job_id>/', views.job_detail, name='job_detail'),
    path('apply/<int:job_id>/', views.apply_job, name='apply_job'),
    path('profile/', views.profile, name='profile'),
    path('company/<int:company_id>/jobs/', views.company_jobs, name='company_jobs'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/search/', views.api_search, name='api_search'),
    
    # VULNERABILITY 1: Debug endpoint accessible without authentication
    path('debug/', views.debug_info, name='debug_info'),
    path('admin/debug/', views.admin_debug, name='admin_debug'),
    
    # VULNERABILITY 2: Media files served without access control
    path('media/<path:file_path>', views.serve_media, name='serve_media'),
]

# VULNERABILITY 3: Serve media files in development (security risk)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
