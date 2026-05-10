"""
Input validation utilities for the data export application.

This module provides comprehensive input validation to prevent security issues
and ensure data integrity.
"""

import re
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import unquote

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom validation error exception."""
    pass


def validate_export_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize export parameters.
    
    Args:
        params: Dictionary of request parameters
        
    Returns:
        Sanitized parameters dictionary
        
    Raises:
        ValidationError: If validation fails
    """
    validated_params = {}
    
    # Validate and sanitize each parameter
    for key, value in params.items():
        if key == 'name':
            validated_params[key] = validate_name_filter(value)
        elif key == 'status':
            validated_params[key] = validate_status_filter(value)
        elif key == 'format':
            validated_params[key] = validate_export_format(value)
        elif key == 'limit':
            validated_params[key] = validate_limit(value)
        elif key == 'offset':
            validated_params[key] = validate_offset(value)
        else:
            # Reject unknown parameters
            logger.warning(f"Unknown parameter: {key}")
            raise ValidationError(f"Unknown parameter: {key}")
    
    return validated_params


def validate_name_filter(name: Any) -> Optional[str]:
    """
    Validate and sanitize name filter parameter.
    
    Args:
        name: Name filter value
        
    Returns:
        Sanitized name filter or None
        
    Raises:
        ValidationError: If validation fails
    """
    if name is None:
        return None
    
    if not isinstance(name, str):
        raise ValidationError("Name filter must be a string")
    
    # Decode URL encoding
    try:
        name = unquote(name)
    except Exception as e:
        logger.warning(f"Failed to decode name filter: {e}")
        raise ValidationError("Invalid name filter encoding")
    
    # Remove leading/trailing whitespace
    name = name.strip()
    
    # Check for empty string
    if not name:
        return None
    
    # Length validation
    if len(name) > 100:
        raise ValidationError("Name filter too long (max 100 characters)")
    
    # SQL injection prevention - check for dangerous patterns
    dangerous_patterns = [
        r';',  # SQL statement separator
        r'--',  # SQL comment
        r'/\*', r'\*/',  # SQL comment block
        r'xp_',  # SQL extended procedure
        r'sp_',  # SQL stored procedure
        r'exec',  # SQL execute
        r'drop',  # SQL drop
        r'delete',  # SQL delete
        r'insert',  # SQL insert
        r'update',  # SQL update
        r'union',  # SQL union
        r'select',  # SQL select
        r'create',  # SQL create
        r'alter',  # SQL alter
        r'truncate',  # SQL truncate
        r'<script',  # XSS attempt
        r'javascript:',  # XSS attempt
        r'on\w+\s*=',  # XSS event handler
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, name, re.IGNORECASE):
            logger.warning(f"Potentially dangerous pattern detected in name filter: {pattern}")
            raise ValidationError(f"Invalid characters in name filter")
    
    # Allow only alphanumeric characters, spaces, and basic punctuation
    allowed_pattern = r'^[a-zA-Z0-9\s\-_\.]+$'
    if not re.match(allowed_pattern, name):
        raise ValidationError("Name filter contains invalid characters")
    
    return name


def validate_status_filter(status: Any) -> Optional[str]:
    """
    Validate and sanitize status filter parameter.
    
    Args:
        status: Status filter value
        
    Returns:
        Sanitized status filter or None
        
    Raises:
        ValidationError: If validation fails
    """
    if status is None:
        return None
    
    if not isinstance(status, str):
        raise ValidationError("Status filter must be a string")
    
    # Decode URL encoding
    try:
        status = unquote(status)
    except Exception as e:
        logger.warning(f"Failed to decode status filter: {e}")
        raise ValidationError("Invalid status filter encoding")
    
    # Remove leading/trailing whitespace
    status = status.strip()
    
    # Check for empty string
    if not status:
        return None
    
    # Length validation
    if len(status) > 50:
        raise ValidationError("Status filter too long (max 50 characters)")
    
    # SQL injection prevention
    dangerous_patterns = [
        r';', r'--', r'/\*', r'\*', r'xp_', r'sp_', r'exec', r'drop', 
        r'delete', r'insert', r'update', r'union', r'select'
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, status, re.IGNORECASE):
            logger.warning(f"Potentially dangerous pattern detected in status filter: {pattern}")
            raise ValidationError(f"Invalid characters in status filter")
    
    # Allow only alphanumeric characters, spaces, and basic punctuation
    allowed_pattern = r'^[a-zA-Z0-9\s\-_\.]+$'
    if not re.match(allowed_pattern, status):
        raise ValidationError("Status filter contains invalid characters")
    
    # Convert to lowercase for consistency
    return status.lower()


def validate_export_format(format_type: Any) -> str:
    """
    Validate export format parameter.
    
    Args:
        format_type: Export format value
        
    Returns:
        Validated format type
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(format_type, str):
        raise ValidationError("Format must be a string")
    
    format_type = format_type.strip().lower()
    
    allowed_formats = ['csv', 'json', 'xml']
    
    if format_type not in allowed_formats:
        raise ValidationError(f"Invalid format. Allowed formats: {', '.join(allowed_formats)}")
    
    return format_type


def validate_limit(limit: Any) -> int:
    """
    Validate and convert limit parameter.
    
    Args:
        limit: Limit value
        
    Returns:
        Validated limit as integer
        
    Raises:
        ValidationError: If validation fails
    """
    if limit is None:
        return 1000  # Default limit
    
    try:
        limit_int = int(limit)
    except (ValueError, TypeError):
        raise ValidationError("Limit must be a valid integer")
    
    if limit_int < 1:
        raise ValidationError("Limit must be greater than 0")
    
    if limit_int > 10000:
        raise ValidationError("Limit too large (max 10000)")
    
    return limit_int


def validate_offset(offset: Any) -> int:
    """
    Validate and convert offset parameter.
    
    Args:
        offset: Offset value
        
    Returns:
        Validated offset as integer
        
    Raises:
        ValidationError: If validation fails
    """
    if offset is None:
        return 0  # Default offset
    
    try:
        offset_int = int(offset)
    except (ValueError, TypeError):
        raise ValidationError("Offset must be a valid integer")
    
    if offset_int < 0:
        raise ValidationError("Offset must be non-negative")
    
    return offset_int


def validate_email(email: Any) -> str:
    """
    Validate email address.
    
    Args:
        email: Email address
        
    Returns:
        Validated email
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(email, str):
        raise ValidationError("Email must be a string")
    
    email = email.strip()
    
    # Basic email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        raise ValidationError("Invalid email format")
    
    if len(email) > 254:  # RFC 5321 limit
        raise ValidationError("Email too long (max 254 characters)")
    
    return email.lower()


def validate_user_id(user_id: Any) -> int:
    """
    Validate user ID parameter.
    
    Args:
        user_id: User ID value
        
    Returns:
        Validated user ID
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(user_id, (str, int)):
        raise ValidationError("User ID must be a string or integer")
    
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise ValidationError("User ID must be a valid integer")
    
    if user_id_int < 1:
        raise ValidationError("User ID must be positive")
    
    if user_id_int > 2147483647:  # Max 32-bit integer
        raise ValidationError("User ID too large")
    
    return user_id_int


def validate_date_range(start_date: Any, end_date: Any) -> tuple:
    """
    Validate date range parameters.
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        Tuple of validated dates
        
    Raises:
        ValidationError: If validation fails
    """
    from datetime import datetime
    
    if start_date is None and end_date is None:
        return None, None
    
    # Parse dates
    try:
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = None
            
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = None
            
    except ValueError as e:
        raise ValidationError(f"Invalid date format: {e}")
    
    # Validate date range
    if start_dt and end_dt:
        if start_dt > end_dt:
            raise ValidationError("Start date must be before end date")
    
    # Prevent very old or future dates
    min_date = datetime(1900, 1, 1)
    max_date = datetime.now() + timedelta(days=365)
    
    if start_dt and (start_dt < min_date or start_dt > max_date):
        raise ValidationError("Start date out of valid range")
    
    if end_dt and (end_dt < min_date or end_dt > max_date):
        raise ValidationError("End date out of valid range")
    
    return start_dt, end_dt


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal attacks.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(filename, str):
        raise ValidationError("Filename must be a string")
    
    # Remove directory traversal attempts
    filename = filename.replace('..', '').replace('/', '').replace('\\', '')
    
    # Remove dangerous characters
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\0']
    for char in dangerous_chars:
        filename = filename.replace(char, '')
    
    # Ensure filename is not empty
    if not filename:
        raise ValidationError("Filename cannot be empty")
    
    # Limit length
    if len(filename) > 255:
        raise ValidationError("Filename too long (max 255 characters)")
    
    return filename


def validate_pagination_params(params: Dict[str, Any]) -> Dict[str, int]:
    """
    Validate pagination parameters.
    
    Args:
        params: Dictionary with pagination parameters
        
    Returns:
        Validated pagination parameters
        
    Raises:
        ValidationError: If validation fails
    """
    page = validate_limit(params.get('page', 1))
    per_page = validate_limit(params.get('per_page', 20))
    
    # Ensure per_page is reasonable
    if per_page > 100:
        per_page = 100
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    return {
        'limit': per_page,
        'offset': offset,
        'page': page
    }


def check_sql_injection_attempt(input_string: str) -> bool:
    """
    Check if input string contains SQL injection attempts.
    
    Args:
        input_string: Input string to check
        
    Returns:
        True if SQL injection attempt detected, False otherwise
    """
    if not isinstance(input_string, str):
        return True  # Non-string input is suspicious
    
    sql_injection_patterns = [
        r'\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b',
        r'\b(xp_|sp_)\w+',
        r';.*?(drop|delete|update|insert)',
        r'--.*$',
        r'/\*.*\*/',
        r'\b(or|and)\s+\d+\s*=\s*\d+',
        r'\b(or|and)\s+\'\w*\'\s*=\s*\'\w*\'',
        r'\b(or|and)\s+\'\w*\'\s*like\s*\'\w*\'',
        r'\bwaitfor\s+delay',
        r'\bbenchmark\s*\(',
        r'\bsleep\s*\(',
        r'\bpg_sleep\s*\(',
    ]
    
    for pattern in sql_injection_patterns:
        if re.search(pattern, input_string, re.IGNORECASE | re.MULTILINE):
            logger.warning(f"SQL injection pattern detected: {pattern}")
            return True
    
    return False


def validate_json_input(json_data: Any) -> Dict[str, Any]:
    """
    Validate JSON input for API endpoints.
    
    Args:
        json_data: JSON data to validate
        
    Returns:
        Validated JSON data
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(json_data, dict):
        raise ValidationError("JSON data must be an object")
    
    # Check for suspicious keys
    suspicious_keys = ['__proto__', 'constructor', 'prototype']
    for key in json_data.keys():
        if key in suspicious_keys:
            raise ValidationError(f"Suspicious key detected: {key}")
    
    # Validate string values for SQL injection
    for key, value in json_data.items():
        if isinstance(value, str) and check_sql_injection_attempt(value):
            raise ValidationError(f"SQL injection attempt detected in field: {key}")
    
    return json_data


def validate_batch_export_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate batch export parameters.
    
    Args:
        params: Parameters dictionary
        
    Returns:
        Validated parameters
        
    Raises:
        ValidationError: If validation fails
    """
    validated = {}
    
    # Validate export format
    if 'format' in params:
        validated['format'] = validate_export_format(params['format'])
    
    # Validate filters
    if 'filters' in params:
        if not isinstance(params['filters'], dict):
            raise ValidationError("Filters must be a dictionary")
        
        validated['filters'] = validate_export_params(params['filters'])
    
    # Validate batch size
    if 'batch_size' in params:
        validated['batch_size'] = validate_limit(params['batch_size'])
        if validated['batch_size'] > 1000:
            raise ValidationError("Batch size too large (max 1000)")
    
    return validated
