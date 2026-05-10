"""
Job views with debug endpoint vulnerability FIXED.

This file contains the secure code that fixes the debug endpoint vulnerability.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Q, Count, Avg, Max
from django.core.paginator import Paginator
from django.conf import settings
import json
import logging

from .models import Job, Company, JobApplication, JobSearch

User = get_user_model()
logger = logging.getLogger(__name__)


def is_staff_user(user):
    """Check if user is staff member."""
    return user.is_staff or user.is_superuser


def job_list(request):
    """List all active jobs."""
    jobs = Job.objects.filter(is_active=True).select_related('company')
    
    # Pagination
    paginator = Paginator(jobs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'jobs/job_list.html', {'page_obj': page_obj})


def job_detail(request, job_id):
    """View job details."""
    job = get_object_or_404(Job, id=job_id, is_active=True)
    
    # Log job view for analytics
    if request.user.is_authenticated:
        # Could add job view tracking here
        pass
    
    return render(request, 'jobs/job_detail.html', {'job': job})


@login_required
@require_http_methods(["POST"])
def apply_job(request, job_id):
    """Apply for a job."""
    job = get_object_or_404(Job, id=job_id, is_active=True)
    
    # Check if user has already applied
    if JobApplication.objects.filter(job=job, applicant=request.user).exists():
        messages.warning(request, 'You have already applied for this job.')
        return redirect('job_detail', job_id=job.id)
    
    if request.method == 'POST':
        try:
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
            logger.info(f"User {request.user.username} applied for job {job.title}")
            
            return redirect('job_detail', job_id=job.id)
            
        except Exception as e:
            messages.error(request, 'An error occurred while submitting your application.')
            logger.error(f"Error in job application: {e}")
    
    return render(request, 'jobs/apply_job.html', {'job': job})


def job_search(request):
    """
    SECURE: SQL injection vulnerability FIXED using Django ORM.
    
    This view uses Django ORM to prevent SQL injection attacks.
    """
    query = request.GET.get('q', '').strip()
    location = request.GET.get('location', '').strip()
    salary_min = request.GET.get('salary_min', '').strip()
    
    # SECURE CODE: Using Django ORM to prevent SQL injection
    jobs = Job.objects.filter(is_active=True).select_related('company')
    
    if query:
        jobs = jobs.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query) |
            Q(company__name__icontains=query)
        )
    
    if location:
        jobs = jobs.filter(location__icontains=location)
    
    if salary_min:
        try:
            salary_min_int = int(salary_min)
            jobs = jobs.filter(salary_min__gte=salary_min_int)
        except ValueError:
            messages.warning(request, 'Invalid salary minimum value.')
    
    # Pagination
    paginator = Paginator(jobs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Save search if user is authenticated
    if request.user.is_authenticated and query:
        JobSearch.objects.create(
            user=request.user,
            query=query,
            location=location,
            salary_min=int(salary_min) if salary_min.isdigit() else None
        )
    
    return render(request, 'jobs/job_search.html', {
        'page_obj': page_obj,
        'query': query,
        'location': location,
        'salary_min': salary_min
    })


# SECURE: Debug endpoint vulnerability FIXED
@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["GET"])
def debug_info(request):
    """
    SECURE: Debug endpoint vulnerability FIXED with authentication and DEBUG check.
    
    This endpoint is now properly secured with:
    1. Authentication required (@login_required)
    2. Staff permission check (@user_passes_test)
    3. DEBUG=False check in production
    4. No arbitrary code execution
    5. Limited information exposure
    """
    
    # SECURE CODE: Check if DEBUG is enabled
    if not settings.DEBUG:
        logger.warning(f"Unauthorized debug attempt by user {request.user.username}")
        return HttpResponseForbidden("Debug endpoint is only available in development mode.")
    
    # SECURE CODE: Only staff users can access debug info
    if not request.user.is_staff:
        logger.warning(f"Non-staff user {request.user.username} attempted to access debug endpoint")
        return HttpResponseForbidden("Access denied. Staff privileges required.")
    
    if request.method == 'GET':
        # SECURE CODE: Limited debug information
        debug_data = {
            'django_version': '4.2.7',
            'python_version': '3.11.0',
            'debug_mode': settings.DEBUG,
            'installed_apps': settings.INSTALLED_APPS,
            'middleware': settings.MIDDLEWARE,
            'database_info': {
                'engine': 'postgresql',
                'name': 'jumpapp',
            },
            'request_info': {
                'method': request.method,
                'path': request.path,
                'user': request.user.username if request.user.is_authenticated else 'Anonymous',
            }
        }
        
        # Log debug access
        logger.info(f"Debug endpoint accessed by staff user {request.user.username}")
        
        return JsonResponse(debug_data, json_dumps_params={'indent': 2})
    
    return HttpResponseForbidden("Method not allowed.")


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["GET"])
def system_health(request):
    """
    SECURE: System health check endpoint for monitoring.
    
    This endpoint provides system health information for monitoring
    without exposing sensitive configuration details.
    """
    
    from django.db import connection
    from django.core.cache import cache
    
    health_data = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'database': {
            'status': 'connected',
            'connection_pool': 'active',
        },
        'cache': {
            'status': 'connected',
            'backend': 'redis',
        },
        'application': {
            'version': '1.0.0',
            'environment': 'production' if not settings.DEBUG else 'development',
        }
    }
    
    # Test database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_data['database']['status'] = 'connected'
    except Exception as e:
        health_data['database']['status'] = 'error'
        health_data['database']['error'] = str(e)
        health_data['status'] = 'unhealthy'
    
    # Test cache connection
    try:
        cache.set('health_check', 'ok', 10)
        cache_result = cache.get('health_check')
        if cache_result == 'ok':
            health_data['cache']['status'] = 'connected'
        else:
            health_data['cache']['status'] = 'error'
            health_data['status'] = 'unhealthy'
    except Exception as e:
        health_data['cache']['status'] = 'error'
        health_data['cache']['error'] = str(e)
        health_data['status'] = 'unhealthy'
    
    status_code = 200 if health_data['status'] == 'healthy' else 503
    return JsonResponse(health_data, status=status_code)


def company_jobs(request, company_id):
    """
    SECURE: SQL injection vulnerability FIXED using Django ORM.
    
    This view uses Django ORM to prevent SQL injection attacks.
    """
    company = get_object_or_404(Company, id=company_id)
    
    # SECURE CODE: Using Django ORM to prevent SQL injection
    jobs = Job.objects.filter(
        company=company,
        is_active=True
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(jobs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'jobs/company_jobs.html', {
        'company': company,
        'page_obj': page_obj
    })


@login_required
def my_applications(request):
    """View user's job applications."""
    applications = JobApplication.objects.filter(
        applicant=request.user
    ).select_related('job', 'job__company')
    
    # Pagination
    paginator = Paginator(applications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'jobs/my_applications.html', {
        'page_obj': page_obj
    })


@login_required
@require_http_methods(["POST"])
def withdraw_application(request, application_id):
    """Withdraw job application."""
    application = get_object_or_404(
        JobApplication, 
        id=application_id, 
        applicant=request.user
    )
    
    if application.can_withdraw():
        application.delete()
        messages.success(request, 'Application withdrawn successfully.')
        logger.info(f"User {request.user.username} withdrew application for job {application.job.title}")
    else:
        messages.warning(request, 'This application can no longer be withdrawn.')
    
    return redirect('my_applications')


def job_statistics(request):
    """
    SECURE: SQL injection vulnerability FIXED using Django ORM.
    
    This view uses Django ORM to prevent SQL injection attacks.
    """
    # SECURE CODE: Using Django ORM aggregation
    statistics = Job.objects.filter(is_active=True).values(
        'company__name'
    ).annotate(
        job_count=Count('id'),
        avg_salary=Avg('salary_min'),
        max_salary=Max('salary_max')
    ).order_by('-job_count')[:20]
    
    # Additional statistics
    total_jobs = Job.objects.filter(is_active=True).count()
    total_companies = Company.objects.count()
    
    return JsonResponse({
        'statistics': list(statistics),
        'summary': {
            'total_jobs': total_jobs,
            'total_companies': total_companies,
        }
    })


@login_required
def api_job_list(request):
    """
    SECURE: SQL injection vulnerability FIXED using Django ORM.
    
    This API endpoint uses Django ORM to prevent SQL injection attacks.
    """
    # SECURE CODE: Using Django ORM with proper validation
    try:
        limit = min(int(request.GET.get('limit', '10')), 100)  # Max 100 items
        offset = max(int(request.GET.get('offset', '0')), 0)  # Min 0
    except ValueError:
        return JsonResponse({'error': 'Invalid limit or offset parameter'}, status=400)
    
    jobs = Job.objects.filter(is_active=True).select_related('company')[
        offset:offset+limit
    ]
    
    job_data = []
    for job in jobs:
        job_data.append({
            'id': job.id,
            'title': job.title,
            'company': job.company.name,
            'location': job.location,
            'salary_min': job.salary_min,
            'salary_max': job.salary_max,
            'created_at': job.created_at.isoformat(),
            'url': job.get_absolute_url(),
        })
    
    return JsonResponse({
        'jobs': job_data,
        'count': len(job_data),
        'limit': limit,
        'offset': offset
    })


def job_suggestions(request):
    """Provide job suggestions based on user profile."""
    if not request.user.is_authenticated:
        return JsonResponse({'suggestions': []})
    
    # Get user's search history
    user_searches = JobSearch.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]
    
    # Suggest similar jobs
    suggestions = []
    for search in user_searches:
        similar_jobs = Job.objects.filter(
            is_active=True,
            title__icontains=search.query
        ).exclude(
            applications__applicant=request.user
        )[:3]
        
        for job in similar_jobs:
            suggestions.append({
                'id': job.id,
                'title': job.title,
                'company': job.company.name,
                'location': job.location,
                'url': job.get_absolute_url(),
            })
    
    return JsonResponse({'suggestions': suggestions[:10]})


@require_http_methods(["POST"])
@csrf_exempt
def track_job_view(request, job_id):
    """Track job views for analytics."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error'}, status=401)
    
    try:
        job = get_object_or_404(Job, id=job_id, is_active=True)
        
        # Log job view (could be stored in a separate model)
        logger.info(f"Job {job.title} viewed by user {request.user.username}")
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Error tracking job view: {e}")
        return JsonResponse({'status': 'error'}, status=500)
