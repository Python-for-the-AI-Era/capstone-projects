"""
Configuration management for the data export application.

This module handles secure configuration management with environment variables
and proper default values.
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


def get_database_url() -> str:
    """
    Get database URL from environment variables.
    
    Returns:
        Database URL string
    """
    db_host = os.getenv('DB_HOST', 'localhost')
    db_user = os.getenv('DB_USER', 'export_user')
    db_password = os.getenv('DB_PASSWORD', '')
    db_name = os.getenv('DB_NAME', 'export_db')
    db_port = os.getenv('DB_PORT', '5432')
    db_sslmode = os.getenv('DB_SSLMODE', 'prefer')
    
    if not db_password:
        raise ValueError("DB_PASSWORD environment variable is required")
    
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode={db_sslmode}"


def get_config() -> Dict[str, Any]:
    """
    Get application configuration from environment variables.
    
    Returns:
        Configuration dictionary
    """
    return {
        'debug': os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        'host': os.getenv('FLASK_HOST', '0.0.0.0'),
        'port': int(os.getenv('FLASK_PORT', '5000')),
        'secret_key': os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'max_export_rows': int(os.getenv('MAX_EXPORT_ROWS', '10000')),
        'export_timeout': int(os.getenv('EXPORT_TIMEOUT', '300')),
        'rate_limit_requests': int(os.getenv('RATE_LIMIT_REQUESTS', '100')),
        'rate_limit_window': int(os.getenv('RATE_LIMIT_WINDOW', '3600')),
    }


def validate_config() -> bool:
    """
    Validate that required configuration is present.
    
    Returns:
        True if configuration is valid, False otherwise
    """
    required_vars = ['DB_PASSWORD']
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return False
    
    return True


class ConfigError(Exception):
    """Configuration error exception."""
    pass


def get_database_config() -> Dict[str, Any]:
    """
    Get database configuration with validation.
    
    Returns:
        Database configuration dictionary
    """
    config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USER', 'export_user'),
        'password': os.getenv('DB_PASSWORD'),
        'database': os.getenv('DB_NAME', 'export_db'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'sslmode': os.getenv('DB_SSLMODE', 'prefer'),
        'pool_size': int(os.getenv('DB_POOL_SIZE', '10')),
        'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '20')),
        'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', '30')),
        'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '3600')),
    }
    
    # Validate required fields
    if not config['password']:
        raise ConfigError("Database password is required")
    
    return config


def get_security_config() -> Dict[str, Any]:
    """
    Get security configuration.
    
    Returns:
        Security configuration dictionary
    """
    return {
        'secret_key': os.getenv('FLASK_SECRET_KEY'),
        'session_timeout': int(os.getenv('SESSION_TIMEOUT', '3600')),
        'max_login_attempts': int(os.getenv('MAX_LOGIN_ATTEMPTS', '5')),
        'lockout_duration': int(os.getenv('LOCKOUT_DURATION', '900')),
        'password_min_length': int(os.getenv('PASSWORD_MIN_LENGTH', '8')),
        'require_https': os.getenv('REQUIRE_HTTPS', 'False').lower() == 'true',
    }


def get_logging_config() -> Dict[str, Any]:
    """
    Get logging configuration.
    
    Returns:
        Logging configuration dictionary
    """
    return {
        'level': os.getenv('LOG_LEVEL', 'INFO'),
        'format': os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
        'file_path': os.getenv('LOG_FILE_PATH', 'logs/app.log'),
        'max_file_size': int(os.getenv('LOG_MAX_FILE_SIZE', '10485760')),  # 10MB
        'backup_count': int(os.getenv('LOG_BACKUP_COUNT', '5')),
        'console_logging': os.getenv('LOG_CONSOLE', 'True').lower() == 'true',
        'file_logging': os.getenv('LOG_FILE', 'True').lower() == 'true',
    }


def setup_logging():
    """Setup logging configuration."""
    log_config = get_logging_config()
    
    # Create logs directory if it doesn't exist
    if log_config['file_logging']:
        log_dir = os.path.dirname(log_config['file_path'])
        os.makedirs(log_dir, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_config['level']),
        format=log_config['format'],
        handlers=[]
    )
    
    # Add console handler if enabled
    if log_config['console_logging']:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_config['format']))
        logging.getLogger().addHandler(console_handler)
    
    # Add file handler if enabled
    if log_config['file_logging']:
        from logging.handlers import RotatingFileHandler
        
        file_handler = RotatingFileHandler(
            log_config['file_path'],
            maxBytes=log_config['max_file_size'],
            backupCount=log_config['backup_count']
        )
        file_handler.setFormatter(logging.Formatter(log_config['format']))
        logging.getLogger().addHandler(file_handler)
    
    logger.info("Logging configured successfully")


def is_production() -> bool:
    """
    Check if the application is running in production.
    
    Returns:
        True if in production, False otherwise
    """
    return os.getenv('FLASK_ENV', 'development').lower() == 'production'


def is_development() -> bool:
    """
    Check if the application is running in development.
    
    Returns:
        True if in development, False otherwise
    """
    return os.getenv('FLASK_ENV', 'development').lower() == 'development'


def get_export_limits() -> Dict[str, Any]:
    """
    Get export limits and constraints.
    
    Returns:
        Export limits configuration
    """
    return {
        'max_rows_per_export': int(os.getenv('MAX_EXPORT_ROWS', '10000')),
        'max_file_size_mb': int(os.getenv('MAX_EXPORT_SIZE_MB', '50')),
        'export_timeout_seconds': int(os.getenv('EXPORT_TIMEOUT', '300')),
        'allowed_formats': os.getenv('ALLOWED_EXPORT_FORMATS', 'csv').split(','),
        'compression_enabled': os.getenv('EXPORT_COMPRESSION', 'False').lower() == 'true',
    }


def validate_export_limits(rows_count: int, file_size_bytes: int) -> bool:
    """
    Validate that export limits are not exceeded.
    
    Args:
        rows_count: Number of rows being exported
        file_size_bytes: Size of the export file in bytes
        
    Returns:
        True if within limits, False otherwise
    """
    limits = get_export_limits()
    
    if rows_count > limits['max_rows_per_export']:
        logger.warning(f"Export rows limit exceeded: {rows_count} > {limits['max_rows_per_export']}")
        return False
    
    max_file_size_bytes = limits['max_file_size_mb'] * 1024 * 1024
    if file_size_bytes > max_file_size_bytes:
        logger.warning(f"Export file size limit exceeded: {file_size_bytes} > {max_file_size_bytes}")
        return False
    
    return True
