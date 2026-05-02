"""
VULNERABLE Django App Config - DO NOT USE IN PRODUCTION
This file contains intentional security vulnerabilities for educational purposes.
"""

from django.apps import AppConfig


class VulnerableAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vulnerable_app'
    verbose_name = 'Vulnerable Job Board'
    
    def ready(self):
        """VULNERABLE: No security initialization"""
        pass  # Missing security headers setup
