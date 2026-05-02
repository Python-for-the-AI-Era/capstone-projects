"""
SECURED Django Utils - PRODUCTION READY
This file contains security utilities for secure media handling and logging.
"""

import hashlib
import logging
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone
from .models import SecurityLog


logger = logging.getLogger('security')


def get_private_media_url(file_path, expiration=600):
    """
    ✅ SECURED: Generate presigned URL for private S3 files
    Returns temporary URL that expires after specified seconds
    """
    if not hasattr(default_storage, 'bucket'):
        # Local storage - return direct URL
        return settings.MEDIA_URL + file_path
    
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
        )
        
        # Generate presigned URL
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': file_path,
            },
            ExpiresIn=expiration
        )
        
        # Log access for audit
        log_security_event(
            event_type='media_access',
            details={
                'file_path': file_path,
                'expiration': expiration,
                'generated_at': timezone.now().isoformat()
            }
        )
        
        return url
        
    except ClientError as e:
        logger.error(f"Failed to generate presigned URL for {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating presigned URL for {file_path}: {e}")
        return None


def validate_file_upload(file_obj, allowed_extensions=None, max_size_mb=5):
    """
    ✅ SECURED: Comprehensive file upload validation
    Returns (is_valid, error_message)
    """
    if not allowed_extensions:
        allowed_extensions = ['.pdf', '.doc', '.docx', '.txt']
    
    # Check file extension
    file_extension = file_obj.name.lower().split('.')[-1]
    if f'.{file_extension}' not in allowed_extensions:
        return False, f"File type .{file_extension} is not allowed."
    
    # Check file size
    max_size_bytes = max_size_mb * 1024 * 1024
    if file_obj.size > max_size_bytes:
        return False, f"File size exceeds {max_size_mb}MB limit."
    
    # Check file content (basic validation)
    if hasattr(file_obj, 'content_type'):
        allowed_mime_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain'
        ]
        
        if file_obj.content_type not in allowed_mime_types:
            return False, f"File content type {file_obj.content_type} is not allowed."
    
    # Generate secure filename
    secure_name = generate_secure_filename(file_obj.name)
    return True, secure_name


def generate_secure_filename(original_filename):
    """
    ✅ SECURED: Generate secure filename to prevent path traversal
    """
    import os
    import uuid
    
    # Remove directory traversal attempts
    filename = os.path.basename(original_filename)
    filename = filename.replace('..', '').replace('/', '').replace('\\', '')
    
    # Remove special characters
    allowed_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_'
    filename = ''.join(c for c in filename if c in allowed_chars)
    
    # Add UUID to prevent collisions
    name, extension = os.path.splitext(filename)
    secure_filename = f"{name}_{uuid.uuid4().hex[:8]}{extension}"
    
    return secure_filename


def log_security_event(event_type, user_id=None, details=None, ip_address=None, user_agent=None):
    """
    ✅ SECURED: Log security events for monitoring
    """
    try:
        SecurityLog.objects.create(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent or '',
            details=details or {}
        )
    except Exception as e:
        logger.error(f"Failed to log security event {event_type}: {e}")


def check_rate_limit(identifier, limit, window_seconds, cache_backend='default'):
    """
    ✅ SECURED: Generic rate limiting function
    Returns (is_allowed, current_count, reset_time)
    """
    from django.core.cache import cache
    
    cache_key = f"rate_limit_{identifier}"
    current_count = cache.get(cache_key, 0)
    
    if current_count >= limit:
        # Calculate reset time
        reset_time = cache.ttl(cache_key) or window_seconds
        return False, current_count, reset_time
    
    # Increment counter
    cache.set(cache_key, current_count + 1, window_seconds)
    return True, current_count + 1, window_seconds


def sanitize_user_input(input_string, max_length=255):
    """
    ✅ SECURED: Sanitize user input to prevent XSS
    """
    if not input_string:
        return ''
    
    import html
    
    # Remove HTML tags
    cleaned = html.escape(input_string)
    
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', 'javascript:', 'vbscript:', 'onload=', 'onerror=']
    for char in dangerous_chars:
        cleaned = cleaned.replace(char, '')
    
    # Truncate to max length
    cleaned = cleaned[:max_length]
    
    return cleaned.strip()


def validate_email_domain(email):
    """
    ✅ SECURED: Validate email domain against common disposable email services
    """
    domain = email.split('@')[-1].lower() if '@' in email else ''
    
    # Common disposable email domains
    disposable_domains = {
        '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
        'mailinator.com', 'yopmail.com', 'maildrop.cc',
        'temp-mail.org', 'throwaway.email', 'tempmail.de'
    }
    
    return domain not in disposable_domains


def detect_suspicious_patterns(text):
    """
    ✅ SECURED: Detect suspicious patterns in user input
    Returns list of detected patterns
    """
    import re
    
    suspicious_patterns = {
        'sql_injection': [
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)',
            r'(\'|\"|;|--|/\*|\*/|xp_|sp_)',
            r'\bOR\b.*\b=\b',
            r'\bAND\b.*\b=\b',
        ],
        'xss': [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',  # onclick, onload, etc.
            r'<iframe[^>]*>',
            r'<object[^>]*>',
            r'<embed[^>]*>',
        ],
        'path_traversal': [
            r'\.\./',
            r'\.\.\\',
            r'%2e%2e%2f',  # URL encoded ../
            r'\.\.%2f',
        ],
        'command_injection': [
            r'eval\s*\(',
            r'exec\s*\(',
            r'system\s*\(',
            r'passthru\s*\(',
            r'shell_exec\s*\(',
        ]
    }
    
    detected = []
    
    for category, patterns in suspicious_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                detected.append(f"{category}: {pattern}")
    
    return detected


def encrypt_sensitive_data(data, key=None):
    """
    ✅ SECURED: Encrypt sensitive data for storage
    Uses AES encryption for sensitive fields
    """
    from cryptography.fernet import Fernet
    
    if not key:
        key = getattr(settings, 'ENCRYPTION_KEY', None)
        if not key:
            raise ValueError("No encryption key configured")
    
    fernet = Fernet(key.encode())
    encrypted_data = fernet.encrypt(data.encode())
    return encrypted_data.decode()


def decrypt_sensitive_data(encrypted_data, key=None):
    """
    ✅ SECURED: Decrypt sensitive data from storage
    """
    from cryptography.fernet import Fernet
    
    if not key:
        key = getattr(settings, 'ENCRYPTION_KEY', None)
        if not key:
            raise ValueError("No encryption key configured")
    
    fernet = Fernet(key.encode())
    decrypted_data = fernet.decrypt(encrypted_data.encode())
    return decrypted_data.decode()


def generate_csrf_token():
    """
    ✅ SECURED: Generate CSRF token for forms
    """
    import secrets
    
    return secrets.token_urlsafe(32)


def verify_csrf_token(token, session_token):
    """
    ✅ SECURED: Verify CSRF token
    """
    import secrets
    
    try:
        return secrets.compare_digest(token, session_token)
    except (TypeError, AttributeError):
        return False


def audit_log_deletion(model_name, object_id, user_id, reason=None):
    """
    ✅ SECURED: Log when sensitive objects are deleted
    """
    log_security_event(
        event_type='data_deletion',
        user_id=user_id,
        details={
            'model': model_name,
            'object_id': object_id,
            'reason': reason,
            'timestamp': timezone.now().isoformat()
        }
    )


def check_password_strength(password):
    """
    ✅ SECURED: Check password strength
    Returns (is_strong, score, suggestions)
    """
    import re
    
    score = 0
    suggestions = []
    
    # Length check
    if len(password) >= 8:
        score += 1
    else:
        suggestions.append("Use at least 8 characters")
    
    # Uppercase check
    if re.search(r'[A-Z]', password):
        score += 1
    else:
        suggestions.append("Include uppercase letters")
    
    # Lowercase check
    if re.search(r'[a-z]', password):
        score += 1
    else:
        suggestions.append("Include lowercase letters")
    
    # Numbers check
    if re.search(r'\d', password):
        score += 1
    else:
        suggestions.append("Include numbers")
    
    # Special characters check
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
    else:
        suggestions.append("Include special characters")
    
    # Common patterns check
    common_patterns = [
        r'123', r'password', r'qwerty', r'abc123', r'admin'
    ]
    
    for pattern in common_patterns:
        if re.search(pattern, password, re.IGNORECASE):
            score -= 1
            suggestions.append("Avoid common patterns")
    
    is_strong = score >= 4
    return is_strong, score, suggestions
