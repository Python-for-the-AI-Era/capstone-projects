"""
SECURED Django Models - PRODUCTION READY
This file contains security fixes for all identified vulnerabilities.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone


class User(AbstractUser):
    """User model with secure password hashing"""
    email = models.EmailField(unique=True)
    phone = models.CharField(
        max_length=20, 
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ]
    )
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_password_change = models.DateTimeField(auto_now_add=True)
    
    # ✅ SECURED: Using Django's built-in secure password hashing
    # No need to override set_password() - Django handles it securely
    
    def __str__(self):
        return self.email


class Job(models.Model):
    """Job posting model with security considerations"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    company = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    salary_min = models.IntegerField(null=True, blank=True)
    salary_max = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE)
    posted_at = models.DateTimeField(auto_now_add=True)
    views_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['is_active', 'posted_at']),
            models.Index(fields=['company']),
            models.Index(fields=['title']),
        ]
    
    def __str__(self):
        return f"{self.title} at {self.company}"
    
    def get_absolute_url(self):
        """✅ SECURED: Safe URL generation"""
        from django.urls import reverse
        return reverse('job_detail', kwargs={'job_id': self.id})


class JobApplication(models.Model):
    """Job application model with security considerations"""
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    applicant = models.ForeignKey(User, on_delete=models.CASCADE)
    cover_letter = models.TextField()
    resume_path = models.CharField(max_length=500)
    applied_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['job', 'applicant']
        indexes = [
            models.Index(fields=['applicant', 'applied_at']),
            models.Index(fields=['job', 'applied_at']),
        ]
    
    def __str__(self):
        return f"{self.applicant.username} -> {self.job.title}"


class Company(models.Model):
    """Company model with security considerations"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    website = models.URLField(blank=True)
    logo_path = models.CharField(max_length=500, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['is_verified']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return self.name


class SecurityLog(models.Model):
    """Security event logging model"""
    EVENT_TYPES = [
        ('login_success', 'Login Success'),
        ('login_failed', 'Login Failed'),
        ('password_change', 'Password Changed'),
        ('profile_update', 'Profile Updated'),
        ('job_application', 'Job Application'),
        ('debug_access', 'Debug Access'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('rate_limit_exceeded', 'Rate Limit Exceeded'),
    ]
    
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.timestamp}"


class FailedLoginAttempt(models.Model):
    """Track failed login attempts for rate limiting"""
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['username', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]
    
    def __str__(self):
        return f"Failed login: {self.username} at {self.timestamp}"


class UserSession(models.Model):
    """Track user sessions for security monitoring"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"Session for {self.user.username}"
