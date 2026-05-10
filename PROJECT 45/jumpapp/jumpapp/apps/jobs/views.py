"""
Job views with debug endpoint vulnerability (before fix).

This file contains the vulnerable debug endpoint that needs to be secured.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db import connection
import json
import traceback
import sys

from .models import Job, Company, JobApplication, JobSearch


def job_list(request):
    """List all active jobs."""
    jobs = Job.objects.filter(is_active=True).select_related('company')
    return render(request, 'jobs/job_list.html', {'jobs': jobs})


def job_detail(request, job_id):
    """View job details."""
    job = get_object_or_404(Job, id=job_id, is_active=True)
    return render(request, 'jobs/job_detail.html', {'job': job})


@login_required
@require_http_methods(["POST"])
def apply_job(request, job_id):
    """Apply for a job."""
    job = get_object_or_404(Job, id=job_id, is_active=True)
    
    if request.method == 'POST':
        # Process application
        application = JobApplication.objects.create(
            job=job,
            applicant=request.user,
            cover_letter=request.POST.get('cover_letter', ''),
        )
        
        # Handle file upload
        if 'resume' in request.FILES:
            application.resume = request.FILES['resume']
            application.save()
        
        messages.success(request, 'Application submitted successfully!')
        return redirect('job_detail', job_id=job.id)
    
    return render(request, 'jobs/apply_job.html', {'job': job})


def job_search(request):
    """Search jobs with potential security issues."""
    query = request.GET.get('q', '')
    location = request.GET.get('location', '')
    salary_min = request.GET.get('salary_min', '')
    
    # VULNERABLE: Direct use of user input in database queries
    from django.db import connection
    
    with connection.cursor() as cursor:
        sql = f"""
        SELECT j.*, c.name as company_name 
        FROM jobs_job j 
        JOIN jobs_company c ON j.company_id = c.id 
        WHERE j.is_active = True
        """
        
        if query:
            sql += f" AND j.title LIKE '%{query}%'"
        
        if location:
            sql += f" AND j.location LIKE '%{location}%'"
        
        if salary_min:
            sql += f" AND j.salary_min >= {salary_min}"
        
        sql += " ORDER BY j.created_at DESC"
        
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
    
    return render(request, 'jobs/job_search.html', {
        'jobs': results,
        'query': query,
        'location': location,
        'salary_min': salary_min
    })


# VULNERABLE: Debug endpoint accessible without authentication
def debug_info(request):
    """
    VULNERABLE: Debug endpoint accessible without authentication.
    
    This endpoint exposes sensitive system information and is
    accessible to anyone who can reach the URL.
    """
    
    if request.method == 'GET':
        debug_data = {
            'django_version': '4.2.7',
            'python_version': sys.version,
            'database_info': {
                'engine': 'postgresql',
                'name': 'jumpapp',
                'host': 'localhost',
                'port': '5432'
            },
            'settings': {
                'DEBUG': True,  # This should be False in production!
                'SECRET_KEY': 'django-insecure-change-me-in-production',
                'ALLOWED_HOSTS': ['localhost', '127.0.0.1'],
                'DATABASES': {
                    'default': {
                        'ENGINE': 'django.db.backends.postgresql',
                        'NAME': 'jumpapp',
                        'USER': 'postgres',
                        'PASSWORD': '***'
                    }
                }
            },
            'environment_variables': {
                'DJANGO_SETTINGS_MODULE': 'jumpapp.config.settings',
                'PYTHONPATH': '/app',
                'PATH': '/usr/local/bin:/usr/bin:/bin'
            },
            'file_permissions': {
                'media_root': '/app/media',
                'static_root': '/app/static',
                'logs_dir': '/app/logs'
            },
            'installed_apps': [
                'django.contrib.admin',
                'django.contrib.auth',
                'django.contrib.contenttypes',
                'django.contrib.sessions',
                'django.contrib.messages',
                'django.contrib.staticfiles',
                'rest_framework',
                'corsheaders',
                'csp',
                'django_extensions',
                'storages',
                'jumpapp.apps.jobs',
                'jumpapp.apps.users',
                'jumpapp.apps.companies',
            ],
            'middleware': [
                'django.middleware.security.SecurityMiddleware',
                'corsheaders.middleware.CorsMiddleware',
                'csp.middleware.CSPMiddleware',
                'django.contrib.sessions.middleware.SessionMiddleware',
                'django.middleware.common.CommonMiddleware',
                'django.middleware.csrf.CsrfViewMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware',
                'django.contrib.messages.middleware.MessageMiddleware',
                'django.middleware.clickjacking.XFrameOptionsMiddleware',
                'whitenoise.middleware.WhiteNoiseMiddleware',
            ]
        }
        
        # Add database schema information
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name, column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """)
            schema_info = []
            for row in cursor.fetchall():
                schema_info.append({
                    'table': row[0],
                    'column': row[1],
                    'type': row[2]
                })
            debug_data['database_schema'] = schema_info
        
        # Add system file information
        import os
        debug_data['file_system'] = {
            'current_directory': os.getcwd(),
            'python_path': sys.path,
            'environment_variables': dict(os.environ)
        }
        
        # Add request information
        debug_data['request_info'] = {
            'method': request.method,
            'path': request.path,
            'GET': dict(request.GET),
            'POST': dict(request.POST),
            'META': {
                k: v for k, v in request.META.items() 
                if k.startswith('HTTP_') or k in ['REMOTE_ADDR', 'SERVER_NAME']
            }
        }
        
        return JsonResponse(debug_data, json_dumps_params={'indent': 2})
    
    elif request.method == 'POST':
        # VULNERABLE: Allow arbitrary code execution
        code = request.POST.get('code', '')
        
        if code:
            try:
                # VULNERABLE: Executing arbitrary code
                result = eval(code)
                return JsonResponse({
                    'status': 'success',
                    'result': str(result),
                    'type': type(result).__name__
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
        
        return JsonResponse({'error': 'No code provided'})


def company_jobs(request, company_id):
    """View jobs for a specific company."""
    company = get_object_or_404(Company, id=company_id)
    
    # VULNERABLE: Another SQL injection point
    with connection.cursor() as cursor:
        sql = f"""
        SELECT * FROM jobs_job 
        WHERE company_id = {company_id} 
        AND is_active = True 
        ORDER BY created_at DESC
        """
        
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
    
    return render(request, 'jobs/company_jobs.html', {
        'company': company,
        'jobs': results
    })


@login_required
def my_applications(request):
    """View user's job applications."""
    applications = JobApplication.objects.filter(
        applicant=request.user
    ).select_related('job', 'job__company')
    
    return render(request, 'jobs/my_applications.html', {
        'applications': applications
    })


def job_statistics(request):
    """Job statistics dashboard."""
    
    # VULNERABLE: SQL injection in statistics
    with connection.cursor() as cursor:
        sql = """
        SELECT 
            c.name as company_name,
            COUNT(j.id) as job_count,
            AVG(j.salary_min) as avg_salary,
            MAX(j.salary_max) as max_salary
        FROM jobs_company c
        LEFT JOIN jobs_job j ON c.id = j.company_id AND j.is_active = True
        GROUP BY c.id, c.name
        ORDER BY job_count DESC
        """
        
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
    
    return JsonResponse({'statistics': results})


def api_job_list(request):
    """API endpoint for job listings."""
    
    # VULNERABLE: SQL injection in API
    limit = request.GET.get('limit', '10')
    offset = request.GET.get('offset', '0')
    
    with connection.cursor() as cursor:
        sql = f"""
        SELECT j.*, c.name as company_name 
        FROM jobs_job j 
        JOIN jobs_company c ON j.company_id = c.id 
        WHERE j.is_active = True 
        ORDER BY j.created_at DESC 
        LIMIT {limit} OFFSET {offset}
        """
        
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
    
    return JsonResponse({'jobs': results})
