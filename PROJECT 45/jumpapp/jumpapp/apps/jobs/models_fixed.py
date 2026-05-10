"""
Job models with SQL injection vulnerability FIXED.

This file contains the secure code that fixes SQL injection vulnerabilities.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError
from django.db.models import Q, F, Count, Avg, Max
import hashlib

User = get_user_model()


class Company(models.Model):
    """Company model for job postings."""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    location = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class Job(models.Model):
    """Job model with secure SQL queries."""
    title = models.CharField(max_length=200)
    description = models.TextField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='jobs')
    location = models.CharField(max_length=200)
    salary_min = models.IntegerField(null=True, blank=True)
    salary_max = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'created_at']),
            models.Index(fields=['location']),
            models.Index(fields=['salary_min']),
        ]
    
    def __str__(self):
        return self.title


class JobApplication(models.Model):
    """Job application model."""
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    resume = models.FileField(upload_to='resumes/')
    cover_letter = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['applicant', 'applied_at']),
            models.Index(fields=['job', 'applied_at']),
        ]
    
    def __str__(self):
        return f"{self.applicant.username} - {self.job.title}"


class JobSearch(models.Model):
    """Search query model."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='searches')
    query = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    salary_min = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.query}"


class JobViewManager(models.Manager):
    """Custom manager with SQL injection vulnerability FIXED."""
    
    def search_jobs(self, query, location=None, salary_min=None):
        """
        SECURE: SQL injection vulnerability FIXED using Django ORM.
        
        This method uses Django ORM to prevent SQL injection attacks.
        """
        # SECURE CODE: Using Django ORM to prevent SQL injection
        queryset = self.filter(is_active=True)
        
        if query:
            queryset = queryset.filter(title__icontains=query)
        
        if location:
            queryset = queryset.filter(location__icontains=location)
        
        if salary_min:
            queryset = queryset.filter(salary_min__gte=salary_min)
        
        return queryset.select_related('company').order_by('-created_at')
    
    def get_popular_jobs(self, limit=10):
        """
        SECURE: SQL injection vulnerability FIXED using Django ORM.
        
        This method uses Django ORM to prevent SQL injection attacks.
        """
        # SECURE CODE: Using Django ORM aggregation
        return self.filter(is_active=True).annotate(
            application_count=Count('applications')
        ).order_by('-application_count')[:limit]
    
    def get_job_statistics(self):
        """
        SECURE: SQL injection vulnerability FIXED using Django ORM.
        
        This method uses Django ORM to prevent SQL injection attacks.
        """
        # SECURE CODE: Using Django ORM aggregation
        return self.filter(
            is_active=True,
            salary_min__isnull=False
        ).values(
            'location'
        ).annotate(
            job_count=Count('id'),
            avg_salary=Avg('salary_min'),
            max_salary=Max('salary_max')
        ).order_by('-job_count')


class Job(models.Model):
    """Job model with secure custom manager."""
    
    objects = models.Manager()
    secure_manager = JobViewManager()
    
    def __str__(self):
        return self.title
    
    def get_applicant_count(self):
        """Get application count safely."""
        return self.applications.count()
    
    def get_salary_range_display(self):
        """Display salary range safely."""
        if self.salary_min and self.salary_max:
            return f"${self.salary_min:,} - ${self.salary_max:,}"
        elif self.salary_min:
            return f"From ${self.salary_min:,}"
        else:
            return "Salary not specified"
    
    def get_absolute_url(self):
        """Get absolute URL for job."""
        return f"/jobs/{self.id}/"
    
    def is_salary_negotiable(self):
        """Check if salary is negotiable."""
        return self.salary_min is None and self.salary_max is None
    
    def save(self, *args, **kwargs):
        """Override save to add validation."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate model data."""
        if self.salary_min and self.salary_max:
            if self.salary_min > self.salary_max:
                raise ValidationError('Salary minimum cannot be greater than maximum')
        
        if self.salary_min and self.salary_min < 0:
            raise ValidationError('Salary minimum cannot be negative')
        
        if self.salary_max and self.salary_max < 0:
            raise ValidationError('Salary maximum cannot be negative')


class JobApplication(models.Model):
    """Job application model with enhanced security."""
    
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    resume = models.FileField(upload_to='resumes/', validators=[validate_file_size])
    cover_letter = models.TextField(blank=True, validators=[validate_cover_letter])
    applied_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['applicant', 'applied_at']),
            models.Index(fields=['job', 'applied_at']),
            models.UniqueConstraint(fields=['job', 'applicant'], name='unique_job_application'),
        ]
    
    def __str__(self):
        return f"{self.applicant.username} - {self.job.title}"
    
    def get_absolute_url(self):
        """Get absolute URL for application."""
        return f"/applications/{self.id}/"
    
    def can_withdraw(self):
        """Check if application can be withdrawn."""
        from django.utils import timezone
        from datetime import timedelta
        
        # Allow withdrawal within 7 days
        return timezone.now() - self.applied_at < timedelta(days=7)


def validate_file_size(value):
    """Validate file size for resume uploads."""
    max_size = 5 * 1024 * 1024  # 5MB
    if value.size > max_size:
        raise ValidationError('File size cannot exceed 5MB.')


def validate_cover_letter(value):
    """Validate cover letter content."""
    if len(value) > 5000:
        raise ValidationError('Cover letter cannot exceed 5000 characters.')
    
    # Check for potentially malicious content
    malicious_patterns = [
        '<script',
        'javascript:',
        'onload=',
        'onerror=',
        'onclick=',
    ]
    
    content_lower = value.lower()
    for pattern in malicious_patterns:
        if pattern in content_lower:
            raise ValidationError('Invalid content detected in cover letter.')


class JobSearch(models.Model):
    """Search query model with validation."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='searches')
    query = models.CharField(max_length=200, validators=[validate_query])
    location = models.CharField(max_length=200, blank=True)
    salary_min = models.IntegerField(null=True, blank=True, validators=[validate_salary])
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.query}"
    
    def get_absolute_url(self):
        """Get absolute URL for search."""
        return f"/search/?q={self.query}"
    
    def has_filters(self):
        """Check if search has filters applied."""
        return bool(self.location or self.salary_min)


def validate_query(value):
    """Validate search query."""
    if len(value.strip()) < 2:
        raise ValidationError('Search query must be at least 2 characters long.')
    
    # Check for potentially malicious SQL injection patterns
    sql_patterns = [
        'union',
        'select',
        'insert',
        'update',
        'delete',
        'drop',
        'exec',
        'script',
        '--',
        '/*',
        '*/',
        "'",
        '"',
        ';',
        'xp_',
        'sp_',
    ]
    
    query_lower = value.lower()
    for pattern in sql_patterns:
        if pattern in query_lower:
            raise ValidationError('Invalid characters in search query.')


def validate_salary(value):
    """Validate salary minimum."""
    if value is not None and value < 0:
        raise ValidationError('Salary cannot be negative.')
    
    if value is not None and value > 10000000:
        raise ValidationError('Salary seems unrealistic (over $10M).')
