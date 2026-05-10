"""
Security middleware for JumpApp.

Provides comprehensive security headers, request logging, and
protection against common web application vulnerabilities.
"""

import logging
import time
from django.conf import settings
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import SuspiciousOperation
from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model
import json
import hashlib

User = get_user_model()
logger = logging.getLogger('jumpapp.security')


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Security middleware that adds comprehensive security headers.
    
    This middleware adds security headers to all HTTP responses
    to protect against XSS, clickjacking, and other attacks.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
        
        # Security headers configuration
        self.security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=(), payment=(), usb=()',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
        }
        
        # CSP headers (if django-csp is not used)
        if not getattr(settings, 'CSP_DEFAULT_SRC', None):
            self.security_headers.update({
                'Content-Security-Policy': self._get_csp_header(),
            })
    
    def _get_csp_header(self):
        """Generate Content Security Policy header."""
        csp_parts = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.trusted-cdn.com",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "img-src 'self' data: https:",
            "font-src 'self' https://fonts.gstatic.com",
            "connect-src 'self' https://api.jumpapp.com",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "upgrade-insecure-requests"
        ]
        
        return '; '.join(csp_parts)
    
    def process_response(self, request, response):
        """Add security headers to response."""
        # Only add to HTML responses
        if response.get('Content-Type', '').startswith('text/html'):
            for header, value in self.security_headers.items():
                response[header] = value
        
        # Add additional security headers for production
        if not settings.DEBUG:
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
        
        # Remove server information
        response.pop('Server', None)
        
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Request logging middleware for security monitoring.
    
    Logs all requests with security-relevant information
    for monitoring and audit purposes.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
        
        # Paths to exclude from logging
        self.exclude_paths = [
            '/health/',
            '/static/',
            '/media/',
            '/favicon.ico',
        ]
        
        # Sensitive parameters to exclude from logs
        self.sensitive_params = [
            'password',
            'csrfmiddlewaretoken',
            'secret',
            'token',
            'key',
        ]
    
    def process_request(self, request):
        """Log incoming request."""
        # Skip logging for excluded paths
        if any(request.path.startswith(path) for path in self.exclude_paths):
            return None
        
        # Get request information
        request_data = {
            'method': request.method,
            'path': request.path,
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'user': request.user.username if request.user.is_authenticated else 'Anonymous',
            'timestamp': time.time(),
        }
        
        # Log GET parameters (excluding sensitive ones)
        if request.GET:
            safe_params = {
                k: v for k, v in request.GET.items()
                if k not in self.sensitive_params
            }
            if safe_params:
                request_data['get_params'] = safe_params
        
        # Log suspicious requests
        if self._is_suspicious_request(request):
            logger.warning(f"Suspicious request detected: {request_data}")
            self._log_security_event(request, 'suspicious_activity', request_data)
        
        # Log all requests in debug mode
        if settings.DEBUG:
            logger.info(f"Request: {request_data}")
        
        return None
    
    def process_response(self, request, response):
        """Log response information."""
        # Skip logging for excluded paths
        if any(request.path.startswith(path) for path in self.exclude_paths):
            return response
        
        # Log response status for error responses
        if response.status_code >= 400:
            response_data = {
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'ip_address': self._get_client_ip(request),
                'user': request.user.username if request.user.is_authenticated else 'Anonymous',
                'timestamp': time.time(),
            }
            
            logger.warning(f"Error response: {response_data}")
            
            # Log security events for 4xx/5xx responses
            if response.status_code >= 500:
                self._log_security_event(request, 'server_error', response_data)
            elif response.status_code == 403:
                self._log_security_event(request, 'access_denied', response_data)
            elif response.status_code == 404:
                self._log_security_event(request, 'not_found', response_data)
        
        return response
    
    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _is_suspicious_request(self, request):
        """Check if request is suspicious."""
        suspicious_patterns = [
            '../',
            '<script',
            'javascript:',
            'onload=',
            'onerror=',
            'onclick=',
            'union select',
            'drop table',
            'exec(',
            'eval(',
        ]
        
        # Check URL parameters
        for param, value in request.GET.items():
            if any(pattern.lower() in value.lower() for pattern in suspicious_patterns):
                return True
        
        # Check POST data
        if hasattr(request, 'body'):
            body_str = request.body.decode('utf-8', errors='ignore').lower()
            if any(pattern.lower() in body_str for pattern in suspicious_patterns):
                return True
        
        # Check User-Agent
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        suspicious_agents = [
            'sqlmap',
            'nikto',
            'nmap',
            'masscan',
            'zap',
            'burp',
        ]
        
        if any(agent in user_agent for agent in suspicious_agents):
            return True
        
        return False
    
    def _log_security_event(self, request, event_type, data):
        """Log security event."""
        try:
            from .models import SecurityLog
            SecurityLog.log_event(
                user=request.user if request.user.is_authenticated else None,
                event_type=event_type,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details=data
            )
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")


class RateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting middleware for API protection.
    
    Implements rate limiting to prevent abuse and DoS attacks.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
        
        # Rate limiting configuration
        self.rate_limits = {
            'default': {'requests': 100, 'window': 3600},  # 100 requests per hour
            'api': {'requests': 1000, 'window': 3600},    # 1000 requests per hour
            'auth': {'requests': 10, 'window': 300},       # 10 requests per 5 minutes
        }
    
    def process_request(self, request):
        """Check rate limits."""
        client_ip = self._get_client_ip(request)
        
        # Determine rate limit category
        if request.path.startswith('/api/'):
            category = 'api'
        elif request.path.startswith('/login/') or request.path.startswith('/register/'):
            category = 'auth'
        else:
            category = 'default'
        
        # Check rate limit
        if self._is_rate_limited(client_ip, category):
            logger.warning(f"Rate limit exceeded for {client_ip} on {request.path}")
            return HttpResponse('Rate limit exceeded', status=429)
        
        return None
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    def _is_rate_limited(self, client_ip, category):
        """Check if client is rate limited."""
        from django.core.cache import cache
        
        rate_limit = self.rate_limits[category]
        cache_key = f"rate_limit:{category}:{client_ip}"
        
        # Get current count
        current_count = cache.get(cache_key, 0)
        
        if current_count >= rate_limit['requests']:
            return True
        
        # Increment count
        cache.set(cache_key, current_count + 1, rate_limit['window'])
        
        return False


class SessionSecurityMiddleware(MiddlewareMixin):
    """
    Session security middleware for enhanced session protection.
    
    Implements session fixation protection and session timeout.
    """
    
    def process_request(self, request):
        """Check session security."""
        if not request.user.is_authenticated:
            return None
        
        # Check session age
        if hasattr(request, 'session') and 'session_start' in request.session:
            session_age = time.time() - request.session['session_start']
            max_session_age = getattr(settings, 'SESSION_COOKIE_AGE', 3600)
            
            if session_age > max_session_age:
                # Session expired, logout user
                logger.info(f"Session expired for user {request.user.username}")
                from django.contrib.auth import logout
                logout(request)
                return None
        
        # Check for session fixation
        if not request.session.get('session_secure'):
            # Regenerate session ID
            request.session.cycle_key()
            request.session['session_secure'] = True
            request.session['session_start'] = time.time()
        
        return None


class InputValidationMiddleware(MiddlewareMixin):
    """
    Input validation middleware for request sanitization.
    
    Validates and sanitizes input data to prevent injection attacks.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
        
        # Malicious patterns to detect
        self.malicious_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'eval\s*\(',
            r'exec\s*\(',
            r'union\s+select',
            r'drop\s+table',
            r'insert\s+into',
            r'update\s+set',
            r'delete\s+from',
            r'--',
            r'/\*.*\*/',
        ]
    
    def process_request(self, request):
        """Validate request input."""
        # Validate GET parameters
        for param, value in request.GET.items():
            if self._contains_malicious_content(value):
                logger.warning(f"Malicious content detected in GET parameter {param}")
                return HttpResponse('Invalid input detected', status=400)
        
        # Validate POST data
        if hasattr(request, 'body'):
            try:
                body_str = request.body.decode('utf-8', errors='ignore')
                if self._contains_malicious_content(body_str):
                    logger.warning(f"Malicious content detected in request body")
                    return HttpResponse('Invalid input detected', status=400)
            except UnicodeDecodeError:
                pass
        
        return None
    
    def _contains_malicious_content(self, content):
        """Check if content contains malicious patterns."""
        import re
        
        content_lower = content.lower()
        
        for pattern in self.malicious_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return True
        
        return False
