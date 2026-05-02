"""
VULNERABLE Django Views - DO NOT USE IN PRODUCTION
This file contains intentional security vulnerabilities for educational purposes.
"""

import json
import hashlib
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import connection
from django.views.decorators.debug import sensitive_variables, sensitive_post_parameters
from django.conf import settings
from .models import Job, JobApplication, User, Company


def home(request):
    """Home page with job listings"""
    # VULNERABILITY 1: SQL Injection in search
    search_query = request.GET.get('q', '')
    
    if search_query:
        # ❌ VULNERABLE: Raw SQL with string formatting
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT * FROM vulnerable_app_job 
                WHERE title LIKE '%{search_query}%' 
                OR description LIKE '%{search_query}%'
                ORDER BY posted_at DESC
            """)
            jobs = cursor.fetchall()
    else:
        jobs = Job.objects.filter(is_active=True).order_by('-posted_at')[:10]
    
    return render(request, 'home.html', {'jobs': jobs})


@login_required
def job_detail(request, job_id):
    """Job detail view"""
    # VULNERABILITY 2: SQL Injection in job detail
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT j.*, u.username as posted_by_name 
            FROM vulnerable_app_job j 
            JOIN vulnerable_app_user u ON j.posted_by_id = u.id 
            WHERE j.id = {job_id}
        """)
        job = cursor.fetchone()
    
    if not job:
        return redirect('home')
    
    return render(request, 'job_detail.html', {'job': job})


@login_required
def apply_job(request, job_id):
    """Apply for a job"""
    if request.method == 'POST':
        job = get_object_or_404(Job, id=job_id)
        
        # Handle file upload to S3 (vulnerable - no validation)
        resume_file = request.FILES.get('resume')
        if resume_file:
            # VULNERABILITY 3: No file validation, direct S3 upload
            resume_path = f"resumes/{request.user.id}_{resume_file.name}"
            # In real vulnerable app, this would upload directly to public S3
            
            JobApplication.objects.create(
                job=job,
                applicant=request.user,
                cover_letter=request.POST.get('cover_letter', ''),
                resume_path=resume_path
            )
            
            messages.success(request, 'Application submitted successfully!')
            return redirect('job_detail', job_id=job_id)
    
    return render(request, 'apply_job.html', {'job_id': job_id})


@login_required
def profile(request):
    """User profile view"""
    # VULNERABILITY 4: SQL Injection in profile update
    if request.method == 'POST':
        with connection.cursor() as cursor:
            cursor.execute(f"""
                UPDATE vulnerable_app_user 
                SET email = '{request.POST.get('email')}',
                    phone = '{request.POST.get('phone')}',
                    bio = '{request.POST.get('bio')}'
                WHERE id = {request.user.id}
            """)
        
        messages.success(request, 'Profile updated!')
    
    return render(request, 'profile.html')


# VULNERABILITY 5: Debug endpoint accessible without authentication
def debug_info(request):
    """Debug information endpoint - VULNERABLE: No authentication"""
    debug_data = {
        'django_version': '4.2.0',
        'python_version': '3.11.0',
        'settings': {
            'DEBUG': settings.DEBUG,
            'DATABASES': {
                'default': {
                    'ENGINE': settings.DATABASES['default']['ENGINE'],
                    'NAME': settings.DATABASES['default']['NAME'],
                    'HOST': settings.DATABASES['default']['HOST'],
                }
            },
            'SECRET_KEY': settings.SECRET_KEY[:20] + '...',  # Partial exposure
        },
        'environment_variables': dict(request.META),
        'request_headers': dict(request.headers),
    }
    
    return JsonResponse(debug_data)


@login_required
def company_jobs(request, company_id):
    """Jobs by company"""
    # VULNERABILITY 6: SQL Injection in company filter
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT * FROM vulnerable_app_job 
            WHERE company_id = {company_id}
            AND is_active = TRUE
            ORDER BY posted_at DESC
        """)
        jobs = cursor.fetchall()
    
    return render(request, 'company_jobs.html', {'jobs': jobs})


def api_search(request):
    """API endpoint for job search - VULNERABLE: No rate limiting"""
    query = request.GET.get('q', '')
    
    # VULNERABILITY 7: SQL Injection in API
    with connection.cursor() as cursor:
        if query:
            cursor.execute(f"""
                SELECT id, title, company, location, salary_min, salary_max 
                FROM vulnerable_app_job 
                WHERE title LIKE '%{query}%' 
                LIMIT 50
            """)
        else:
            cursor.execute("""
                SELECT id, title, company, location, salary_min, salary_max 
                FROM vulnerable_app_job 
                WHERE is_active = TRUE 
                LIMIT 50
            """)
        
        columns = [col[0] for col in cursor.description]
        jobs = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    return JsonResponse({'jobs': jobs})


@login_required
def dashboard(request):
    """User dashboard with statistics"""
    with connection.cursor() as cursor:
        # VULNERABILITY 8: SQL Injection in dashboard stats
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_applications,
                COUNT(CASE WHEN applied_at > DATE('now', '-30 days') THEN 1 END) as recent_applications
            FROM vulnerable_app_jobapplication 
            WHERE applicant_id = {request.user.id}
        """)
        stats = cursor.fetchone()
    
    return render(request, 'dashboard.html', {'stats': stats})


# VULNERABILITY 9: Media file serving without access control
def serve_media(request, file_path):
    """Serve media files directly - VULNERABLE: No access control"""
    import os
    from django.conf import settings
    
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    if os.path.exists(full_path):
        with open(full_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
            return response
    
    return HttpResponse('File not found', status=404)


def admin_debug(request):
    """Admin debug endpoint - VULNERABLE: Exposed in production"""
    if request.method == 'POST':
        command = request.POST.get('command', '')
        
        # VULNERABILITY 10: Command execution
        try:
            result = eval(command)  # Extremely dangerous!
            return JsonResponse({'result': str(result)})
        except Exception as e:
            return JsonResponse({'error': str(e)})
    
    return JsonResponse({'message': 'POST a command to execute'})
