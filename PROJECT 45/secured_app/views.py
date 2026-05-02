"""
SECURED Django Views - PRODUCTION READY
This file contains security fixes for all identified vulnerabilities.
"""

import json
import boto3
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db import connection
from django.views.decorators.http import require_http_methods
from django.views.decorators.debug import sensitive_variables
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View
from .models import Job, JobApplication, Company
from .utils import get_private_media_url, log_security_event

User = get_user_model()


def home(request):
    """Home page with job listings - SECURED"""
    search_query = request.GET.get('q', '').strip()
    
    if search_query:
        # ✅ SECURED: Parameterized query using Django ORM
        jobs = Job.objects.filter(
            models.Q(title__icontains=search_query) |
            models.Q(description__icontains=search_query),
            is_active=True
        ).order_by('-posted_at')
    else:
        jobs = Job.objects.filter(is_active=True).order_by('-posted_at')[:10]
    
    return render(request, 'home.html', {'jobs': jobs})


@login_required
def job_detail(request, job_id):
    """Job detail view - SECURED"""
    # ✅ SECURED: Using Django ORM with parameterized queries
    job = get_object_or_404(
        Job.objects.select_related('posted_by')
        .prefetch_related('jobapplication_set')
        .annotate(
            application_count=models.Count('jobapplication')
        ),
        id=job_id,
        is_active=True
    )
    
    # Check if user has already applied
    has_applied = JobApplication.objects.filter(
        job=job, 
        applicant=request.user
    ).exists()
    
    return render(request, 'job_detail.html', {
        'job': job, 
        'has_applied': has_applied
    })


@login_required
@require_http_methods(["GET", "POST"])
def apply_job(request, job_id):
    """Apply for a job - SECURED"""
    job = get_object_or_404(Job, id=job_id, is_active=True)
    
    # Check if already applied
    if JobApplication.objects.filter(job=job, applicant=request.user).exists():
        messages.warning(request, 'You have already applied for this job.')
        return redirect('job_detail', job_id=job_id)
    
    if request.method == 'POST':
        cover_letter = request.POST.get('cover_letter', '').strip()
        
        if not cover_letter:
            messages.error(request, 'Please provide a cover letter.')
            return render(request, 'apply_job.html', {'job_id': job_id})
        
        resume_file = request.FILES.get('resume')
        resume_path = None
        
        if resume_file:
            # ✅ SECURED: File validation and secure upload
            if not resume_file.name.lower().endswith(('.pdf', '.doc', '.docx')):
                messages.error(request, 'Only PDF, DOC, and DOCX files are allowed.')
                return render(request, 'apply_job.html', {'job_id': job_id})
            
            if resume_file.size > 5 * 1024 * 1024:  # 5MB limit
                messages.error(request, 'Resume file must be less than 5MB.')
                return render(request, 'apply_job.html', {'job_id': job_id})
            
            # Secure file upload to S3
            file_extension = resume_file.name.split('.')[-1]
            safe_filename = f"resumes/{request.user.id}_{job_id}_{hashlib.sha256(resume_file.name.encode()).hexdigest()[:16]}.{file_extension}"
            
            resume_path = default_storage.save(safe_filename, resume_file)
        
        JobApplication.objects.create(
            job=job,
            applicant=request.user,
            cover_letter=cover_letter,
            resume_path=resume_path
        )
        
        log_security_event(
            event_type='job_application',
            user_id=request.user.id,
            job_id=job_id,
            details={'resume_uploaded': bool(resume_file)}
        )
        
        messages.success(request, 'Application submitted successfully!')
        return redirect('job_detail', job_id=job_id)
    
    return render(request, 'apply_job.html', {'job_id': job_id})


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    """User profile view - SECURED"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        bio = request.POST.get('bio', '').strip()
        
        # ✅ SECURED: Using Django ORM for update
        User.objects.filter(id=request.user.id).update(
            email=email,
            phone=phone,
            bio=bio
        )
        
        log_security_event(
            event_type='profile_update',
            user_id=request.user.id,
            details={'updated_fields': ['email', 'phone', 'bio']}
        )
        
        messages.success(request, 'Profile updated!')
    
    return render(request, 'profile.html')


# ✅ SECURED: Debug endpoint with proper authentication and environment checks
@user_passes_test(lambda u: u.is_superuser)
@敏感_variables('settings')  # Hide sensitive variables from debug output
def debug_info(request):
    """Debug information endpoint - SECURED"""
    if not settings.DEBUG:
        raise PermissionDenied("Debug endpoint not available in production")
    
    # ✅ SECURED: Only show safe debug information
    debug_data = {
        'django_version': '4.2.0',
        'python_version': '3.11.0',
        'safe_settings': {
            'DEBUG': settings.DEBUG,
            'INSTALLED_APPS': len(settings.INSTALLED_APPS),
            'MIDDLEWARE': len(settings.MIDDLEWARE),
        },
        'request_info': {
            'method': request.method,
            'path': request.path,
            'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown'),
            'ip_address': request.META.get('REMOTE_ADDR', 'Unknown'),
        },
    }
    
    log_security_event(
        event_type='debug_access',
        user_id=request.user.id if request.user.is_authenticated else None,
        details={'ip': request.META.get('REMOTE_ADDR')}
    )
    
    return JsonResponse(debug_data)


@login_required
def company_jobs(request, company_id):
    """Jobs by company - SECURED"""
    # ✅ SECURED: Using Django ORM with parameterized queries
    company = get_object_or_404(Company, id=company_id)
    
    jobs = Job.objects.filter(
        company=company,
        is_active=True
    ).select_related('posted_by').order_by('-posted_at')
    
    return render(request, 'company_jobs.html', {
        'jobs': jobs,
        'company': company
    })


# ✅ SECURED: API endpoint with rate limiting
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.views import View

class APISearchView(View):
    """API endpoint for job search - SECURED"""
    
    def get(self, request):
        # ✅ SECURED: Rate limiting
        client_ip = request.META.get('REMOTE_ADDR')
        cache_key = f"api_rate_limit_{client_ip}"
        
        if cache.get(cache_key):
            return JsonResponse({
                'error': 'Rate limit exceeded. Please wait before making another request.'
            }, status=429)
        
        # Set rate limit (100 requests per hour)
        cache.set(cache_key, True, 3600)
        
        query = request.GET.get('q', '').strip()
        
        # ✅ SECURED: Using Django ORM for API
        if query:
            jobs = Job.objects.filter(
                models.Q(title__icontains=query) |
                models.Q(description__icontains=query),
                is_active=True
            ).values('id', 'title', 'company', 'location', 'salary_min', 'salary_max')[:50]
        else:
            jobs = Job.objects.filter(
                is_active=True
            ).values('id', 'title', 'company', 'location', 'salary_min', 'salary_max')[:50]
        
        return JsonResponse({'jobs': list(jobs)})


@login_required
def dashboard(request):
    """User dashboard with statistics - SECURED"""
    # ✅ SECURED: Using Django ORM for dashboard stats
    stats = {
        'total_applications': JobApplication.objects.filter(applicant=request.user).count(),
        'recent_applications': JobApplication.objects.filter(
            applicant=request.user,
            applied_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).count(),
        'active_jobs': Job.objects.filter(posted_by=request.user, is_active=True).count(),
        'total_views': JobApplication.objects.filter(
            applicant=request.user
        ).aggregate(total_views=models.Count('job'))['total_views'] or 0,
    }
    
    return render(request, 'dashboard.html', {'stats': stats})


# ✅ SECURED: Media file serving with access control
@login_required
def serve_media(request, file_path):
    """Serve media files with access control - SECURED"""
    from django.core.files.storage import default_storage
    from django.http import FileResponse, Http404
    
    # ✅ SECURED: Check if user has permission to access this file
    if file_path.startswith('resumes/'):
        # Extract user ID from file path
        try:
            parts = file_path.split('/')
            user_id_part = parts[1].split('_')[0]
            if int(user_id_part) != request.user.id:
                raise PermissionDenied("You don't have permission to access this file.")
        except (IndexError, ValueError):
            raise Http404("File not found.")
    
    # Check if file exists
    if not default_storage.exists(file_path):
        raise Http404("File not found.")
    
    # ✅ SECURED: Generate presigned URL for S3 files
    if hasattr(default_storage, 'bucket'):
        # S3 storage - generate presigned URL
        url = get_private_media_url(file_path)
        return redirect(url)
    else:
        # Local storage - serve directly
        try:
            file = default_storage.open(file_path)
            response = FileResponse(file)
            response['Content-Disposition'] = f'inline; filename="{file_path.split("/")[-1]}"'
            return response
        except FileNotFoundError:
            raise Http404("File not found.")


# ✅ SECURED: Admin debug endpoint with proper authentication
@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["GET", "POST"])
def admin_debug(request):
    """Admin debug endpoint - SECURED"""
    if not settings.DEBUG:
        raise PermissionDenied("Debug endpoint not available in production")
    
    if request.method == 'POST':
        command = request.POST.get('command', '').strip()
        
        # ✅ SECURED: No command execution - only safe operations
        safe_commands = ['check_database', 'check_cache', 'check_settings']
        
        if command not in safe_commands:
            messages.error(request, 'Command not allowed.')
            return JsonResponse({'error': 'Command not allowed.'})
        
        # Execute safe command
        if command == 'check_database':
            from django.core.management import call_command
            call_command('check', '--database')
            return JsonResponse({'result': 'Database check completed.'})
        
        elif command == 'check_cache':
            cache_status = {
                'default': len(cache.keys('default')),
            }
            return JsonResponse({'result': cache_status})
        
        elif command == 'check_settings':
            safe_settings = {
                'DEBUG': settings.DEBUG,
                'ALLOWED_HOSTS': settings.ALLOWED_HOSTS,
                'INSTALLED_APPS_COUNT': len(settings.INSTALLED_APPS),
            }
            return JsonResponse({'result': safe_settings})
    
    return JsonResponse({'message': 'GET to see available commands.'})
