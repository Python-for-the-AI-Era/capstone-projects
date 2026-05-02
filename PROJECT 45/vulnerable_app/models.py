"""
VULNERABLE Django Models - DO NOT USE IN PRODUCTION
This file contains intentional security vulnerabilities for educational purposes.
"""

import hashlib
from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """User model with vulnerable password hashing"""
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def set_password(self, password):
        """VULNERABLE: Using MD5 for password hashing"""
        self.password = hashlib.md5(password.encode()).hexdigest()
    
    def check_password(self, password):
        """VULNERABLE: MD5 password verification"""
        return self.password == hashlib.md5(password.encode()).hexdigest()


class Job(models.Model):
    """Job posting model"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    company = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    salary_min = models.IntegerField(null=True, blank=True)
    salary_max = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE)
    posted_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} at {self.company}"


class JobApplication(models.Model):
    """Job application model"""
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    applicant = models.ForeignKey(User, on_delete=models.CASCADE)
    cover_letter = models.TextField()
    resume_path = models.CharField(max_length=500)  # S3 path
    applied_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['job', 'applicant']
    
    def __str__(self):
        return f"{self.applicant.username} -> {self.job.title}"


class Company(models.Model):
    """Company model"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    website = models.URLField(blank=True)
    logo_path = models.CharField(max_length=500, blank=True)  # S3 path
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
