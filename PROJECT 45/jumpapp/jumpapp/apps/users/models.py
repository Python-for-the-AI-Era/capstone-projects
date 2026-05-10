"""
User models with MD5 password vulnerability (before fix).

This file contains the vulnerable password hashing that needs to be migrated.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
import hashlib


class User(AbstractUser):
    """Custom user model with MD5 password vulnerability."""
    
    # Additional fields
    bio = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    website = models.URLField(blank=True)
    linkedin_profile = models.URLField(blank=True)
    github_profile = models.URLField(blank=True)
    is_job_seeker = models.BooleanField(default=True)
    is_recruiter = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, blank=True)
    resume = models.FileField(upload_to='resumes/', blank=True)
    
    # Profile completion tracking
    profile_completion_percentage = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.username
    
    def set_password(self, raw_password):
        """
        VULNERABLE: MD5 password hashing instead of secure Django hashing.
        
        This method overrides Django's secure password hashing with
        insecure MD5, making passwords vulnerable to rainbow table attacks.
        """
        # VULNERABLE CODE - Using MD5 for password hashing
        password_hash = hashlib.md5(raw_password.encode('utf-8')).hexdigest()
        self.password = password_hash
        super().set_password(raw_password)  # Still call parent for compatibility
    
    def check_password(self, raw_password):
        """
        VULNERABLE: MD5 password verification.
        
        This method uses MD5 for password verification instead of
        Django's secure password verification.
        """
        # VULNERABLE CODE - Using MD5 for password verification
        password_hash = hashlib.md5(raw_password.encode('utf-8')).hexdigest()
        return self.password == password_hash
    
    def calculate_profile_completion(self):
        """Calculate profile completion percentage."""
        fields_to_check = [
            self.bio,
            self.location,
            self.website,
            self.linkedin_profile,
            self.github_profile,
            self.phone_number,
        ]
        
        completed_fields = sum(1 for field in fields_to_check if field)
        total_fields = len(fields_to_check)
        
        completion = (completed_fields / total_fields) * 100
        self.profile_completion_percentage = int(completion)
        self.save(update_fields=['profile_completion_percentage'])
        
        return completion
    
    def get_full_name(self):
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_profile_url(self):
        """Get profile URL."""
        return f"/profile/{self.username}/"
    
    def is_complete_profile(self):
        """Check if profile is complete."""
        return self.profile_completion_percentage >= 80


class UserProfile(models.Model):
    """Extended user profile with additional information."""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Work experience
    years_of_experience = models.IntegerField(null=True, blank=True)
    current_position = models.CharField(max_length=200, blank=True)
    current_company = models.CharField(max_length=200, blank=True)
    
    # Education
    highest_education = models.CharField(max_length=100, blank=True)
    university = models.CharField(max_length=200, blank=True)
    graduation_year = models.IntegerField(null=True, blank=True)
    
    # Skills
    skills = models.TextField(blank=True)  # JSON-like string of skills
    
    # Preferences
    preferred_job_types = models.TextField(blank=True)  # JSON-like string
    preferred_locations = models.TextField(blank=True)  # JSON-like string
    salary_expectation_min = models.IntegerField(null=True, blank=True)
    salary_expectation_max = models.IntegerField(null=True, blank=True)
    
    # Privacy settings
    show_email = models.BooleanField(default=True)
    show_phone = models.BooleanField(default=False)
    allow_recruiters = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s profile"
    
    def get_skills_list(self):
        """Parse skills from string to list."""
        if self.skills:
            try:
                import json
                return json.loads(self.skills)
            except json.JSONDecodeError:
                return [skill.strip() for skill in self.skills.split(',')]
        return []
    
    def set_skills_list(self, skills_list):
        """Set skills from list to string."""
        try:
            import json
            self.skills = json.dumps(skills_list)
        except (TypeError, ValueError):
            self.skills = ', '.join(skills_list)
    
    def get_salary_range_display(self):
        """Display salary range."""
        if self.salary_expectation_min and self.salary_expectation_max:
            return f"${self.salary_expectation_min:,} - ${self.salary_expectation_max:,}"
        elif self.salary_expectation_min:
            return f"From ${self.salary_expectation_min:,}"
        else:
            return "Not specified"


class UserSession(models.Model):
    """Track user sessions for security monitoring."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.session_key[:8]}..."


class LoginAttempt(models.Model):
    """Track login attempts for security monitoring."""
    
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        status = "Success" if self.success else "Failed"
        return f"{self.username} - {status} at {self.timestamp}"


class PasswordResetToken(models.Model):
    """Password reset tokens with potential security issues."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField()
    
    def __str__(self):
        return f"{self.user.username} - {self.token[:8]}..."
    
    def is_expired(self):
        """Check if token is expired."""
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    def generate_token(self):
        """
        VULNERABLE: Weak token generation using MD5.
        
        This method generates weak tokens using MD5, making them
        predictable and vulnerable to brute force attacks.
        """
        import time
        import random
        
        # VULNERABLE CODE - Using MD5 for token generation
        timestamp = str(time.time())
        random_str = str(random.random())
        user_id = str(self.user.id)
        
        token_string = f"{timestamp}{random_str}{user_id}"
        self.token = hashlib.md5(token_string.encode('utf-8')).hexdigest()
        
        # Set expiration to 1 hour from now
        from django.utils import timezone
        from datetime import timedelta
        self.expires_at = timezone.now() + timedelta(hours=1)
        
        return self.token
