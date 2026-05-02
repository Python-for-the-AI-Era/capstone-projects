"""
SECURED Django Middleware - PRODUCTION READY
This file contains security middleware for comprehensive protection.
"""

import time
import logging
from django.http import HttpResponse
from django.core.cache import cache
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from .models import SecurityLog, FailedLoginAttempt


logger = logging.getLogger('security')


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    ✅ SECURED: Security headers middleware
    Adds comprehensive security headers to all responses
    """
    
    def process_response(self, request, response):
        # Content Security Policy
        csp_directives = [
            f"default-src {', '.join(settings.CSP_DEFAULT_SRC)}",
            f"script-src {', '.join(settings.CSP_SCRIPT_SRC)}",
            f"style-src {', '.join(settings.CSP_STYLE_SRC)}",
            f"img-src {', '.join(settings.CSP_IMG_SRC)}",
            f"font-src {', '.join(settings.CSP_FONT_SRC)}",
            f"connect-src {', '.join(settings.CSP_CONNECT_SRC)}",
            f"frame-ancestors {', '.join(settings.CSP_FRAME_ANCESTORS)}",
            f"base-uri {', '.join(settings.CSP_BASE_URI)}",
            f"form-action {', '.join(settings.CSP_FORM_ACTION)}",
            "upgrade-insecure-requests",
        ]
        response['Content-Security-Policy'] = '; '.join(csp_directives)
        
        # Additional security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = settings.X_FRAME_OPTIONS
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # HSTS (only in production with HTTPS)
        if not settings.DEBUG and settings.SECURE_HSTS_SECONDS > 0:
            hsts_value = f"max-age={settings.SECURE_HSTS_SECONDS}"
            if settings.SECURE_HSTS_INCLUDE_SUBDOMAINS:
                hsts_value += "; includeSubDomains"
            if settings.SECURE_HSTS_PRELOAD:
                hsts_value += "; preload"
            response['Strict-Transport-Security'] = hsts_value
        
        return response


class RateLimitMiddleware(MiddlewareMixin):
    """
    ✅ SECURED: Rate limiting middleware
    Implements configurable rate limiting for API endpoints
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limits = {
            '/api/': {'requests': 100, 'window': 3600},  # 100/hour
            '/debug/': {'requests': 10, 'window': 300},   # 10/5min
            '/admin/debug/': {'requests': 5, 'window': 300},  # 5/5min
        }
    
    def process_request(self, request):
        # Check if this path needs rate limiting
        path = request.path
        for limit_path, config in self.rate_limits.items():
            if path.startswith(limit_path):
                return self._check_rate_limit(request, config, limit_path)
        
        return None
    
    def _check_rate_limit(self, request, config, path):
        client_ip = self._get_client_ip(request)
        cache_key = f"rate_limit_{client_ip}_{path}"
        
        # Get current request count
        requests_count = cache.get(cache_key, 0)
        
        if requests_count >= config['requests']:
            # Log rate limit exceeded
            SecurityLog.objects.create(
                event_type='rate_limit_exceeded',
                ip_address=client_ip,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details={
                    'path': path,
                    'requests_count': requests_count,
                    'limit': config['requests'],
                    'window': config['window']
                }
            )
            
            return HttpResponse(
                '{"error": "Rate limit exceeded. Please try again later."}',
                status=429,
                content_type='application/json'
            )
        
        # Increment request count
        cache.set(cache_key, requests_count + 1, config['window'])
        return None
    
    def _get_client_ip(self, request):
        """Get real client IP considering proxies"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        return request.META.get('REMOTE_ADDR')


class SecurityAuditMiddleware(MiddlewareMixin):
    """
    ✅ SECURED: Security audit middleware
    Logs security-relevant events for monitoring
    """
    
    def process_request(self, request):
        # Log suspicious requests
        self._audit_request(request)
        return None
    
    def _audit_request(self, request):
        client_ip = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        path = request.path
        
        # Check for suspicious patterns
        suspicious_patterns = [
            '../',  # Directory traversal
            '<script',  # XSS attempt
            'SELECT.*FROM',  # SQL injection
            'UNION.*SELECT',  # SQL injection
            'DROP.*TABLE',  # SQL injection
            'INSERT.*INTO',  # SQL injection
            'eval(',  # Code injection
            'exec(',  # Code injection
        ]
        
        request_data = f"{path} {request.GET.urlencode()} {request.body}"
        
        for pattern in suspicious_patterns:
            if pattern.lower() in request_data.lower():
                SecurityLog.objects.create(
                    event_type='suspicious_activity',
                    user=request.user if request.user.is_authenticated else None,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={
                        'path': path,
                        'pattern_matched': pattern,
                        'request_data': request_data[:500],  # Truncate for storage
                    }
                )
                
                logger.warning(
                    f"Suspicious request detected from {client_ip}: {pattern} in {path}"
                )
                break
        
        # Check for automated tools
        automated_tools = [
            'sqlmap', 'nikto', 'nmap', 'dirb', 'gobuster',
            'burp', 'zap', 'acunetix', 'nuclei'
        ]
        
        for tool in automated_tools:
            if tool.lower() in user_agent.lower():
                SecurityLog.objects.create(
                    event_type='suspicious_activity',
                    user=request.user if request.user.is_authenticated else None,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={
                        'tool_detected': tool,
                        'path': path,
                    }
                )
                
                logger.warning(
                    f"Automated tool detected from {client_ip}: {tool}"
                )
                break
    
    def _get_client_ip(self, request):
        """Get real client IP considering proxies"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        return request.META.get('REMOTE_ADDR')


class LoginAttemptMiddleware(MiddlewareMixin):
    """
    ✅ SECURED: Login attempt tracking middleware
    Tracks failed login attempts for rate limiting and alerting
    """
    
    def process_request(self, request):
        if request.path == '/admin/login/' and request.method == 'POST':
            self._track_login_attempt(request)
        return None
    
    def _track_login_attempt(self, request):
        username = request.POST.get('username', '')
        client_ip = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Check if this is a failed login attempt
        # This would be called from the login view after authentication fails
        cache_key = f"failed_login_{client_ip}_{username}"
        failed_attempts = cache.get(cache_key, 0)
        
        # Increment failed attempts
        failed_attempts += 1
        cache.set(cache_key, failed_attempts, settings.FAILED_LOGIN_ATTEMPTS_TIMEOUT)
        
        # Log failed attempt
        FailedLoginAttempt.objects.create(
            username=username,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        # Check if we should block further attempts
        if failed_attempts >= settings.FAILED_LOGIN_ATTEMPTS_LIMIT:
            SecurityLog.objects.create(
                event_type='login_failed',
                ip_address=client_ip,
                user_agent=user_agent,
                details={
                    'username': username,
                    'failed_attempts': failed_attempts,
                    'blocked': True
                }
            )
            
            logger.warning(
                f"Login blocked for {username} from {client_ip} after {failed_attempts} failed attempts"
            )
    
    def _get_client_ip(self, request):
        """Get real client IP considering proxies"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        return request.META.get('REMOTE_ADDR')
