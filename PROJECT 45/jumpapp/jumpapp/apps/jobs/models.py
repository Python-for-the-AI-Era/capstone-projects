"""
Job models with SQL injection vulnerability (before fix).

This file contains the vulnerable code that needs to be fixed.
"""

from django.db import models
from django.contrib.auth import get_user_model
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
    """Job model with SQL injection vulnerability in custom manager."""
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
    
    def __str__(self):
        return self.title


class JobApplication(models.Model):
    """Job application model."""
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    resume = models.FileField(upload_to='resumes/')
    cover_letter = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.applicant.username} - {self.job.title}"


class JobSearch(models.Model):
    """Search query model with potential security issues."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='searches')
    query = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    salary_min = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.query}"


class JobViewManager(models.Manager):
    """Custom manager with SQL injection vulnerability (before fix)."""
    
    def search_jobs(self, query, location=None, salary_min=None):
        """
        VULNERABLE: SQL injection vulnerability using string formatting.
        
        This method constructs SQL queries using string formatting,
        which is vulnerable to SQL injection attacks.
        """
        from django.db import connection
        
        # VULNERABLE CODE - DO NOT USE IN PRODUCTION
        sql = f"""
        SELECT * FROM jobs_job 
        WHERE title LIKE '%{query}%' 
        AND is_active = True
        """
        
        if location:
            sql += f" AND location LIKE '%{location}%'"
        
        if salary_min:
            sql += f" AND salary_min >= {salary_min}"
        
        sql += " ORDER BY created_at DESC"
        
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
        
        return results
    
    def get_popular_jobs(self, limit=10):
        """
        Another vulnerable SQL query with string formatting.
        """
        from django.db import connection
        
        # VULNERABLE CODE
        sql = f"""
        SELECT j.*, COUNT(a.id) as application_count 
        FROM jobs_job j 
        LEFT JOIN jobs_jobapplication a ON j.id = a.job_id 
        WHERE j.is_active = True 
        GROUP BY j.id 
        ORDER BY application_count DESC 
        LIMIT {limit}
        """
        
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
        
        return results
    
    def get_job_statistics(self):
        """
        Vulnerable aggregation query with string formatting.
        """
        from django.db import connection
        
        # VULNERABLE CODE
        sql = """
        SELECT 
            location,
            COUNT(*) as job_count,
            AVG(salary_min) as avg_salary,
            MAX(salary_max) as max_salary
        FROM jobs_job 
        WHERE is_active = True 
        AND salary_min IS NOT NULL
        GROUP BY location
        ORDER BY job_count DESC
        """
        
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
        
        return results


class Job(models.Model):
    """Job model with vulnerable custom manager."""
    # ... (same as above)
    
    objects = models.Manager()
    vulnerable_manager = JobViewManager()
    
    def get_applicant_count(self):
        """Method that could be vulnerable if not properly implemented."""
        return self.applications.count()
    
    def get_salary_range_display(self):
        """Display salary range safely."""
        if self.salary_min and self.salary_max:
            return f"${self.salary_min:,} - ${self.salary_max:,}"
        elif self.salary_min:
            return f"From ${self.salary_min:,}"
        else:
            return "Salary not specified"
